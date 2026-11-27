# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The one rule of the stations a window reads: the size limit counts them, the walk and its fetch-ahead read them.

GH-4426. The first design (#4423) counted by the request's own buffer and left the walk as it was, which the live lists
proved wrong: a buffer of 0 on a window of today counted 0 stations of a list the walk read whole, and the walk read
stations the count had left out (ECCC, GHCN, a Geosphere region, SMHI). Here the count and the walk are held to each
other with the catalogue served from memory: the stations the walk reads are exactly those the count has (the network
that opted out aside, whose count is above its reads).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.api import Wetterdienst
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.station_window import (
    NAMED_BY_ID,
    STATION_END_LAG,
    STATION_END_LAG_ANNUAL,
    can_have_data_in_window,
    station_ids_read,
    window_cut_stations,
)
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.ui.limits import estimate_rows, selected_station_count
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.values import TimeseriesValues

UTC = dt.UTC
DAY = dt.timedelta(days=1)
TODAY = dt.datetime(2026, 11, 27, tzinfo=UTC)


def _frame(
    rows: list[tuple[str, dt.datetime | None, dt.datetime | None]], *, resolution: str, dataset: str
) -> pl.DataFrame:
    """Give a station list of one row per station: its id and the start and end the list publishes."""
    return pl.DataFrame(
        {
            "resolution": [resolution] * len(rows),
            "dataset": [dataset] * len(rows),
            "station_id": [row[0] for row in rows],
            "start_timestamp": [row[1] for row in rows],
            "end_timestamp": [row[2] for row in rows],
            "latitude": [50.0 + i / 100 for i in range(len(rows))],
            "longitude": [9.0] * len(rows),
            "elevation": [100.0] * len(rows),
            "name": [row[0] for row in rows],
            "region": ["x"] * len(rows),
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )


def _result(
    request: TimeseriesRequest,
    df: pl.DataFrame,
    selection: StationsFilter = StationsFilter.ALL,
    rank: int | None = None,
) -> StationsResult:
    return StationsResult(request=request, df=df, _df_all=df, _stations_filter=selection, _rank=rank)


def _dwd(
    parameters: str = "daily/climate_summary/temperature_air_mean_2m",
    **kwargs: Any,  # noqa: ANN401
) -> DwdObservationRequest:
    return DwdObservationRequest(parameters=[parameters], settings=Settings(cache_disable=True), **kwargs)


def _read_by_walk(result: StationsResult, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Walk the stations of a result with a collection that holds nothing, and give the ids that were collected."""
    read: list[str] = []

    def collect(self: TimeseriesValues, station_id: str, datasets: object) -> pl.DataFrame:  # noqa: ARG001
        read.append(station_id)
        return pl.DataFrame()

    monkeypatch.setattr(type(result.values()), "_collect_station_data", collect)
    list(result.values().query())
    return read


# the rule itself


def test_the_lag_is_a_year_and_two_for_annual_data() -> None:
    """The numbers of the decision: 366 days, 732 for annual data."""
    assert dt.timedelta(days=366) == STATION_END_LAG
    assert dt.timedelta(days=732) == STATION_END_LAG_ANNUAL


@pytest.mark.parametrize(
    ("resolution", "lag"),
    [
        ("daily", STATION_END_LAG),
        ("hourly", STATION_END_LAG),
        ("monthly", STATION_END_LAG),
        ("annual", STATION_END_LAG_ANNUAL),
    ],
)
def test_a_station_whose_list_ends_within_the_lag_counts_and_one_beyond_it_does_not(
    resolution: str, lag: dt.timedelta
) -> None:
    """The end is compared with the lag before the window's start, inclusive; the start with the window's end."""
    start, end = dt.datetime(2022, 2, 18, tzinfo=UTC), dt.datetime(2022, 2, 18, 23, 59, 59, tzinfo=UTC)
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame(
        [
            ("exactly", old, start - lag),
            ("beyond", old, start - lag - DAY),
            ("open", old, None),
            ("no_start", None, start - 10 * DAY),
            ("starts_on_the_last_day", end, None),
            ("starts_after", end + DAY, None),
        ],
        resolution=resolution,
        dataset="x",
    )

    passing = df.filter(can_have_data_in_window(df, start, end)).get_column("station_id").to_list()

    assert passing == ["exactly", "open", "no_start", "starts_on_the_last_day"]


def test_a_station_with_several_rows_counts_when_any_row_passes() -> None:
    """The count is per station: a station with one dataset that is closed and one that is open is one station."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    one = _frame([("00001", old, dt.datetime(2000, 1, 1, tzinfo=UTC))], resolution="daily", dataset="climate_summary")
    two = _frame([("00001", old, None)], resolution="daily", dataset="more_precip")
    closed = _frame(
        [("00002", old, dt.datetime(2000, 1, 1, tzinfo=UTC))], resolution="daily", dataset="climate_summary"
    )

    result = _result(request, pl.concat([one, two, closed]))

    assert station_ids_read(result) == ["00001"]
    assert selected_station_count(result) == 1


def test_no_bounds_no_cut() -> None:
    """A list that publishes none (noaa/ghcn hourly, imgw) has every station counted and read."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    df = _frame([(f"{i:05d}", None, None) for i in range(5)], resolution="daily", dataset="climate_summary")

    assert selected_station_count(_result(request, df)) == 5


def test_a_request_without_a_window_cuts_nothing() -> None:
    """No window, no cut: the count is the list, as it was."""
    request = _dwd()
    df = _frame(
        [("00001", None, dt.datetime(1990, 1, 1, tzinfo=UTC)), ("00002", None, None)],
        resolution="daily",
        dataset="climate_summary",
    )

    assert station_ids_read(_result(request, df)) is None
    assert selected_station_count(_result(request, df)) == 2


# the traps of the first design


def test_a_buffer_of_zero_does_not_count_zero_stations_for_a_window_on_today() -> None:
    """`station_window_end_buffer=0` made every station that ends before today "closed": the count was 0 (#4423).

    The lag is the rule's own, never the request's: the stations that end yesterday, as DWD's daily list does, count.
    """
    request = _dwd(
        start=TODAY.strftime("%Y-%m-%d"), end=TODAY.strftime("%Y-%m-%d"), options={"station_window_end_buffer": 0}
    )
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame(
        [(f"{i:05d}", old, TODAY - DAY) for i in range(1284)] + [("closed", old, dt.datetime(2015, 1, 1, tzinfo=UTC))],
        resolution="daily",
        dataset="climate_summary",
    )

    assert selected_station_count(_result(request, df)) == 1284


def test_all_stations_of_one_minute_data_do_not_pass_with_zero_stations_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`all=true` of 1-minute data counted 0 with a buffer of 0, and 1,356 were collected: now the count is the walk."""
    request = DwdObservationRequest(
        parameters=["1_minute/precipitation/precipitation_amount"],
        start="2026-11-27",
        end="2026-11-27",
        settings=Settings(cache_disable=True),
        options={"station_window_end_buffer": 0},
    )
    old = dt.datetime(1990, 1, 1, tzinfo=UTC)
    rows = [(f"{i:05d}", old, TODAY - DAY) for i in range(1356)]
    rows += [(f"c{i:04d}", old, dt.datetime(2015, 1, 1, tzinfo=UTC)) for i in range(151)]
    result = _result(request, _frame(rows, resolution="1_minute", dataset="precipitation"))

    read = _read_by_walk(result, monkeypatch)

    assert selected_station_count(result) == 1356
    assert len(read) == 1356


def test_the_estimate_of_rows_is_of_the_stations_read() -> None:
    """The stations the rule leaves out add no rows to the estimate, and a request with none is not held to them."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    kept = _frame([("00001", old, None)], resolution="daily", dataset="climate_summary")
    cut = _frame([("00002", old, dt.datetime(2000, 1, 1, tzinfo=UTC))], resolution="daily", dataset="climate_summary")

    assert estimate_rows(_result(request, pl.concat([kept, cut]))) == estimate_rows(_result(request, kept))


# what the rule does not cut


def test_explicit_ids_are_not_cut_by_the_end_of_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station named by id is counted and read, closed or not: the case that counted 0 stations.

    Only its end is no reason: one whose list begins after the window is left out as it was, so that no request is made
    for it (a request per station at a provider that reads one file for each).
    """
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame(
        [
            ("00001", old, None),
            ("00002", old, dt.datetime(2000, 1, 1, tzinfo=UTC)),
            ("00003", dt.datetime(2030, 1, 1, tzinfo=UTC), None),
        ],
        resolution="daily",
        dataset="climate_summary",
    )
    for selection in NAMED_BY_ID:
        result = _result(request, df, selection)

        assert station_ids_read(result) is None
        assert selected_station_count(result) == 3
        assert _read_by_walk(result, monkeypatch) == ["00001", "00002"]


def test_a_station_named_by_id_with_no_data_in_the_window_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """It is read, comes back empty and is named by `station-without-rows` in the metadata of the answer."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame(
        [("00001", old, None), ("00002", old, dt.datetime(2000, 1, 1, tzinfo=UTC))],
        resolution="daily",
        dataset="climate_summary",
    )
    result = _result(request, df, StationsFilter.BY_STATION_ID)

    def collect(self: TimeseriesValues, station_id: str, datasets: list[Any]) -> pl.DataFrame:  # noqa: ARG001
        if station_id == "00002":
            return pl.DataFrame()
        name = datasets[0].parameters[0].name_original
        return pl.DataFrame(
            {
                "resolution": ["daily"],
                "dataset": ["climate_summary"],
                "parameter": [name],
                "timestamp": [dt.datetime(2022, 2, 18, tzinfo=UTC)],
                "value": [1.0],
                "quality_flags": [None],
            },
            schema_overrides={"quality_flags": pl.String},
        )

    monkeypatch.setattr(type(result.values()), "_collect_station_data", collect)
    begin_response()
    list(result.values().query())

    (warning,) = [w for w in recorded_warnings() if w["code"] == "station-without-rows"]
    assert warning["stations"] == ["00002"]


def test_a_rank_is_counted_and_walked_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rank is its rank, and its walk stops at the start of the list alone: closed stations are no cut."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame(
        [
            ("00001", old, dt.datetime(2000, 1, 1, tzinfo=UTC)),
            ("00002", old, dt.datetime(2000, 1, 1, tzinfo=UTC)),
            ("00003", old, None),
            ("00004", dt.datetime(2030, 1, 1, tzinfo=UTC), None),
        ],
        resolution="daily",
        dataset="climate_summary",
    )
    result = _result(request, df, StationsFilter.BY_RANK, rank=3)

    assert station_ids_read(result) is None
    assert selected_station_count(result) == 3
    assert _read_by_walk(result, monkeypatch) == ["00001", "00002", "00003"]


def test_a_name_is_walked_by_the_start_of_the_list_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """`filter_by_name` cut the stations by the request's buffer already; the walk leaves its stations as they are."""
    request = _dwd(start="2022-02-18", end="2022-02-18", options={"station_window_end_buffer": 3000})
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame(
        [("00001", old, dt.datetime(2015, 1, 1, tzinfo=UTC)), ("00002", dt.datetime(2030, 1, 1, tzinfo=UTC), None)],
        resolution="daily",
        dataset="climate_summary",
    )
    result = _result(request, df, StationsFilter.BY_NAME)

    assert station_ids_read(result) is None
    assert _read_by_walk(result, monkeypatch) == ["00001"]


# the warning: a selection the rule cuts is not an answer with no word


def _warnings_of(result: StationsResult, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[dict[str, Any]]]:
    begin_response()
    read = _read_by_walk(result, monkeypatch)
    return read, [w for w in recorded_warnings() if w["code"] == "stations-outside-window"]


def test_a_selection_the_rule_cuts_to_nothing_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stations whose lists end in 2000 and 2005, asked for 2022: no rows, and the answer says why (GH-3539)."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame(
        [("00001", old, dt.datetime(2000, 1, 1, tzinfo=UTC)), ("00002", old, dt.datetime(2005, 1, 1, tzinfo=UTC))],
        resolution="daily",
        dataset="climate_summary",
    )
    for selection in (StationsFilter.ALL, StationsFilter.BY_BBOX, StationsFilter.BY_DISTANCE):
        read, (warning,) = _warnings_of(_result(request, df, selection), monkeypatch)

        assert read == []
        assert warning["stations"] == ["00001", "00002"]
        assert warning["message"] == (
            "2 of the 2 stations of the selection are not read: their station list ends more than 366 days before "
            "the window or begins after it (00001, 00002), so they have no data in it by the list. Name the "
            "stations by id (`stations`) to read them anyway."
        )


def test_the_warning_counts_and_names_the_few_and_says_one_station_in_the_singular(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Twelve of thirteen left out: ten are named and the rest counted; one of two is told in the singular."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    closed = dt.datetime(2000, 1, 1, tzinfo=UTC)
    df = _frame(
        [("open", old, None), *[(f"c{i:02d}", old, closed) for i in range(12)]],
        resolution="daily",
        dataset="climate_summary",
    )

    read, (warning,) = _warnings_of(_result(request, df), monkeypatch)

    assert read == ["open"]
    assert warning["stations"] == [f"c{i:02d}" for i in range(10)]
    assert warning["message"].startswith("12 of the 13 stations of the selection are not read: ")
    assert "(c00, c01, c02, c03, c04, c05, c06, c07, c08, c09, and 2 more)" in warning["message"]

    two = _frame([("open", old, None), ("c00", old, closed)], resolution="daily", dataset="climate_summary")
    _, (single,) = _warnings_of(_result(request, two), monkeypatch)
    assert single["message"].startswith("1 of the 2 stations of the selection is not read: its station list ends")
    assert "so it has no data in it by the list. Name the station by id" in single["message"]


def test_the_warning_says_732_days_for_annual_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lag of annual data is two years, and so is what the text says."""
    request = _dwd("annual/climate_summary/temperature_air_mean_2m", start="2022-01-01", end="2022-12-31")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame([("00001", old, dt.datetime(2000, 1, 1, tzinfo=UTC))], resolution="annual", dataset="climate_summary")

    _, (warning,) = _warnings_of(_result(request, df), monkeypatch)

    assert "ends more than 732 days before the window" in warning["message"]


def test_no_station_left_out_no_warning_and_none_where_the_rule_does_not_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is told where all stations are read, nor for a rank, a name, ids or a list with no bounds."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    closed = dt.datetime(2000, 1, 1, tzinfo=UTC)
    open_stations = _frame([("00001", old, None), ("00002", None, None)], resolution="daily", dataset="climate_summary")
    mixed = _frame([("00001", old, None), ("00002", old, closed)], resolution="daily", dataset="climate_summary")

    assert _warnings_of(_result(request, open_stations), monkeypatch)[1] == []
    for selection in (StationsFilter.BY_RANK, StationsFilter.BY_NAME, StationsFilter.BY_STATION_ID):
        assert _warnings_of(_result(request, mixed, selection, rank=2), monkeypatch)[1] == []


def test_a_walk_that_switched_the_rule_off_tells_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`interpolate` and `summarize` read as they did."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame([("00001", old, dt.datetime(2000, 1, 1, tzinfo=UTC))], resolution="daily", dataset="climate_summary")
    result = _result(request, df)
    values = result.values()
    values._window_rule_allowed = False  # noqa: SLF001
    monkeypatch.setattr(type(values), "_collect_station_data", lambda *_: pl.DataFrame())
    begin_response()

    list(values.query())

    assert [w for w in recorded_warnings() if w["code"] == "stations-outside-window"] == []


def test_the_text_of_the_limit_names_the_window_only_where_it_cut_the_count() -> None:
    """A list with no bounds, or a window that leaves every station, is counted as it was: no "can have data"."""
    request = _dwd(start="2022-02-18", end="2022-02-18")
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    uncut = _result(request, _frame([("00001", old, None), ("00002", None, None)], resolution="daily", dataset="x"))
    cut = _result(
        request,
        _frame(
            [("00001", old, None), ("00002", old, dt.datetime(2000, 1, 1, tzinfo=UTC))], resolution="daily", dataset="x"
        ),
    )

    assert not window_cut_stations(uncut)
    assert window_cut_stations(cut)


# the opt-out


def test_a_network_that_opts_out_names_why() -> None:
    """The opt-out is a declared property of the request class, with its reason, and not a name check."""
    opted_out = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            api = Wetterdienst.resolve(provider, network)
            if not api.station_list_bounds_hold:
                opted_out.append(f"{provider}/{network}")
                assert api.station_list_bounds_note
            else:
                assert api.station_list_bounds_note is None
    assert opted_out == ["eccc/observation"]


def test_eccc_counts_every_station_and_its_walk_reads_as_it_did(monkeypatch: pytest.MonkeyPatch) -> None:
    """The list start of ECCC is after the first value of most stations: all are counted, none cut by the lag."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")], start="2022-02-18", end="2022-02-18", settings=Settings(cache_disable=True)
    )
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    df = _frame(
        [
            ("1", old, None),
            ("2", old, dt.datetime(2000, 1, 1, tzinfo=UTC)),
            ("3", dt.datetime(2030, 1, 1, tzinfo=UTC), None),
        ],
        resolution="daily",
        dataset="data",
    )
    result = _result(request, df)

    assert station_ids_read(result) is None
    assert selected_station_count(result) == 3
    # no FIRST_DATE to say otherwise (`_collection_bounds` is None here): every station is read, the count is not below
    assert _read_by_walk(result, monkeypatch) == ["1", "2", "3"]


# the count is what is read, for the providers whose lists the first design got wrong


def _mixed(resolution: str, dataset: str, end_open: dt.datetime | None) -> pl.DataFrame:
    """Give a list of stations that are open, closed within the year, closed long ago and not yet begun."""
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    rows = [
        ("open_1", old, end_open),
        ("open_2", old, end_open),
        ("closed_this_year", old, dt.datetime(2025, 12, 31, tzinfo=UTC)),
        ("closed_2015", old, dt.datetime(2015, 12, 31, tzinfo=UTC)),
        ("closed_2020", old, dt.datetime(2020, 6, 1, tzinfo=UTC)),
        ("not_begun", dt.datetime(2027, 1, 1, tzinfo=UTC), None),
        ("unbounded", None, None),
    ]
    return _frame(rows, resolution=resolution, dataset=dataset)


NETWORKS: list[tuple[str, type[TimeseriesRequest], tuple[str, str], dt.datetime | None]] = [
    ("dwd/observation", DwdObservationRequest, ("daily", "climate_summary"), None),
    # GHCN daily: whole years, the stations that report have no end
    ("noaa/ghcn", NoaaGhcnRequest, ("daily", "data"), None),
    # Geosphere lists 2100-12-31 as the end of a station in service
    ("geosphere", GeosphereObservationRequest, ("daily", "data"), dt.datetime(2100, 12, 31, tzinfo=UTC)),
    ("smhi", SmhiObservationRequest, ("hourly", "data"), dt.datetime(2026, 11, 26, tzinfo=UTC)),
]


@pytest.mark.parametrize(("network", "api", "dataset", "end_open"), NETWORKS, ids=[n[0] for n in NETWORKS])
def test_the_walk_reads_exactly_the_stations_the_count_has(
    network: str,
    api: type[TimeseriesRequest],
    dataset: tuple[str, str],
    end_open: dt.datetime | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stations read are the stations counted, no more: the quota of a provider is what the walk spends."""
    request = api(parameters=[dataset], start="2026-06-01", end="2026-06-30", settings=Settings(cache_disable=True))
    df = _mixed(dataset[0], dataset[1], end_open)
    result = _result(request, df)

    read = _read_by_walk(result, monkeypatch)

    assert selected_station_count(result) == 4, network
    assert sorted(read) == ["closed_this_year", "open_1", "open_2", "unbounded"]
    assert set(read) == set(station_ids_read(result) or [])


def test_a_region_of_a_provider_with_a_quota_is_counted_as_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Geosphere region counted 97 stations and the walk read 240: with its hourly quota of 240 requests (#4423)."""
    request = GeosphereObservationRequest(
        parameters=[("daily", "data")], start="2026-01-01", end="2026-11-27", settings=Settings(cache_disable=True)
    )
    old = dt.datetime(1950, 1, 1, tzinfo=UTC)
    end = dt.datetime(2100, 12, 31, tzinfo=UTC)
    rows = [(f"o{i}", old, end) for i in range(97)] + [
        (f"c{i}", old, dt.datetime(2000 + i % 20, 1, 1, tzinfo=UTC)) for i in range(143)
    ]
    result = _result(request, _frame(rows, resolution="daily", dataset="data"), StationsFilter.BY_REGION)

    read = _read_by_walk(result, monkeypatch)

    assert selected_station_count(result) == 97
    assert len(read) == 97
