# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A values walk that ran to its end and read no station says so, as `no-station-read` (GH-4510).

Every station left out because its list begins after the window (named by id, a `rank`, ECCC), or a selection that
holds no station, was an answer with no rows and no word. Not told where `stations-outside-window`, `unknown-station`
or `positions-unavailable` already explains it, nor for an estimate, nor where a station was read.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.io.compact import warning_text
from wetterdienst.model.listing_gap import ListingGap
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.station_window import station_ids_read
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.pollen import DwdPollenRequest
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from wetterdienst.model.request import TimeseriesRequest

UTC = dt.UTC
OLD = dt.datetime(1950, 1, 1, tzinfo=UTC)
FUTURE = dt.datetime(2030, 1, 1, tzinfo=UTC)
CLOSED = dt.datetime(2000, 1, 1, tzinfo=UTC)
CODE = "no-station-read"


def _frame(
    rows: list[tuple[str, dt.datetime | None, dt.datetime | None]], dataset: str = "climate_summary"
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "resolution": ["daily"] * len(rows),
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
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "name": pl.String,
            "region": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )


def _dwd() -> DwdObservationRequest:
    return DwdObservationRequest(
        parameters=["daily/climate_summary/temperature_air_mean_2m"],
        start="2022-02-18",
        end="2022-02-18",
        settings=Settings(cache_disable=True),
    )


def _walk(
    request: TimeseriesRequest,
    df: pl.DataFrame,
    selection: StationsFilter,
    monkeypatch: pytest.MonkeyPatch,
    *,
    rank: int | None = None,
    estimate: bool = False,
) -> list[dict[str, Any]]:
    """Walk the stations of a selection and give the `no-station-read` warnings the answer carries."""
    result = StationsResult(request=request, df=df, _df_all=df, _stations_filter=selection, _rank=rank)
    values = result.values()
    if estimate:
        values._window_rule_allowed = False  # noqa: SLF001
        values._warn_without_rows = False  # noqa: SLF001
    monkeypatch.setattr(type(values), "_collect_station_data", lambda *_: pl.DataFrame())
    begin_response()
    list(values.query())
    return [dict(w) for w in recorded_warnings() if w["code"] == CODE]


def test_stations_named_by_id_that_all_begin_after_the_window_are_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """Naming them does not read them: the answer says so, and names them."""
    df = _frame([("00001", FUTURE, None), ("00002", FUTURE, None)])

    (warning,) = _walk(_dwd(), df, StationsFilter.BY_STATION_ID, monkeypatch)

    assert warning["stations"] == ["00001", "00002"]
    assert warning["message"] == (
        "No station was read: the station list of 00001, 00002 begins after the window's end, 2022-02-18, so by "
        "the list they have no data in it. The answer has no rows because of that, not because the "
        "request failed. Naming them by id does not read them."
    )
    assert "00001, 00002" in warning_text({**warning})


def test_one_station_named_by_id_is_told_in_the_singular(monkeypatch: pytest.MonkeyPatch) -> None:
    """One station is worded in the singular."""
    (warning,) = _walk(_dwd(), _frame([("00001", FUTURE, None)]), StationsFilter.BY_WMO_ID, monkeypatch)

    assert warning["message"].startswith("No station was read: the station list of 00001 begins after the window")
    assert "so by the list it has no data in it" in warning["message"]
    assert warning["message"].endswith("Naming it by id does not read it.")


def test_a_rank_whose_candidates_all_begin_after_the_window_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rank is walked by the start of the list alone: all candidates late is a walk that read nothing."""
    df = _frame([("00001", FUTURE, None), ("00002", FUTURE, None), ("00003", FUTURE, None)])

    (warning,) = _walk(_dwd(), df, StationsFilter.BY_RANK, monkeypatch, rank=2)

    assert warning["stations"] == ["00001", "00002", "00003"]
    assert "begins after the window's end, 2022-02-18," in warning["message"]
    # a rank is not named by id: no advice about naming
    assert "Naming" not in warning["message"]


def test_the_stations_named_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ten stations are named and the rest counted."""
    df = _frame([(f"{i:05d}", FUTURE, None) for i in range(12)])

    (warning,) = _walk(_dwd(), df, StationsFilter.BY_STATION_ID, monkeypatch)

    assert warning["stations"] == [f"{i:05d}" for i in range(10)]
    assert "00009, and 2 more begins after" in warning["message"]


def test_a_network_that_opted_out_of_the_rule_is_told_by_its_own_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    """ECCC reads by the start of the list alone: `stations-outside-window` is not told, so this one is."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")], start="2022-02-18", end="2022-02-18", settings=Settings(cache_disable=True)
    )
    df = _frame([("1", FUTURE, None), ("2", FUTURE, None)], dataset="data")
    # the walk's own bound: the first date of the station, which the list's start does not stand for
    request._collection_bounds = df.select(  # noqa: SLF001
        "station_id", "resolution", "dataset", first_date=pl.col("start_timestamp"), last_date=pl.col("end_timestamp")
    )

    (warning,) = _walk(request, df, StationsFilter.ALL, monkeypatch)

    assert warning["stations"] == ["1", "2"]
    assert "Naming" not in warning["message"]
    assert not [w for w in recorded_warnings() if w["code"] == "stations-outside-window"]


@pytest.mark.parametrize(
    ("selection", "why"),
    [
        (StationsFilter.BY_NAME, "no station with a record in the window matches the name"),
        (StationsFilter.BY_BBOX, "no station with a record in the window lies in the bounding box"),
        (StationsFilter.BY_DISTANCE, "no station with a record in the window lies within the distance"),
        (StationsFilter.BY_SQL, "no station with a record in the window matches the SQL filter"),
        (StationsFilter.BY_REGION, "no station with a record in the window is listed under the region"),
        (StationsFilter.BY_RANK, "no station with a record in the window with a position was found for the rank"),
        (
            StationsFilter.ALL,
            "the network lists no station for the requested parameters and periods of DwdObservationRequest",
        ),
    ],
)
def test_an_empty_selection_says_it_holds_no_station(
    selection: StationsFilter, why: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selection that holds no station says so, by what it was made with.

    With a window a name and the searches by place are matched among the stations with a record in it (`filter_by_name`
    applies `limit_to_window`, and `metno/frost` narrows a search by place), so the text says that and not that no
    station matches: a station that closed before the window does.
    """
    (warning,) = _walk(_dwd(), _frame([]), selection, monkeypatch)

    assert warning["message"] == (
        "The selection holds no station, so no station was read and the answer has no rows on 2022-02-18: "
        f"{why}. The request did not fail."
    )
    assert "stations" not in warning


def test_a_name_that_only_a_closed_station_has_does_not_say_no_station_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    """The name of a station closed in 1990, asked for 2022: the station exists, the window leaves it out."""
    (warning,) = _walk(_dwd(), _frame([]), StationsFilter.BY_NAME, monkeypatch)

    assert "no station with a record in the window matches the name" in warning["message"]
    assert "no station matches the name" not in warning["message"]


def test_a_search_by_place_of_metno_frost_is_worded_for_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """`metno/frost` narrows a box, a distance and a rank to the stations with a record in the window."""
    request = MetnoFrostRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start="2022-02-18",
        end="2022-02-18",
        settings=Settings(cache_disable=True, auth={"metno_frost": ("DUMMY-ID", "DUMMY-SECRET")}),
    )

    (warning,) = _walk(request, _frame([]), StationsFilter.BY_DISTANCE, monkeypatch)

    assert warning["message"].endswith(
        "no station with a record in the window lies within the distance. The request did not fail."
    )


def test_an_empty_selection_without_a_window_has_no_window_in_its_words(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a window the message names none."""
    request = DwdObservationRequest(
        parameters=["daily/climate_summary/temperature_air_mean_2m"], settings=Settings(cache_disable=True)
    )

    (warning,) = _walk(request, _frame([]), StationsFilter.BY_NAME, monkeypatch)

    assert "the answer has no rows: no station matches the name." in warning["message"]


@pytest.mark.parametrize("selection", [StationsFilter.BY_STATION_ID, StationsFilter.BY_WMO_ID])
def test_ids_the_network_has_no_station_for_are_left_to_unknown_station(
    selection: StationsFilter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`unknown-station` has named the ids: this one does not say it twice."""
    assert _walk(_dwd(), _frame([]), selection, monkeypatch) == []


@pytest.mark.parametrize("selection", [StationsFilter.BY_RANK, StationsFilter.BY_DISTANCE, StationsFilter.BY_BBOX])
def test_a_search_by_place_without_positions_is_left_to_positions_unavailable(
    selection: StationsFilter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`positions-unavailable` says why a search by place finds none: known from the request, told or not.

    No response is begun here, as in the library: the suppression does not depend on what was recorded.
    """
    request = DwdPollenRequest(
        parameters=[("daily", "data")], start="2022-02-18", end="2022-02-18", settings=Settings(cache_disable=True)
    )

    assert _walk(request, _frame([]), selection, monkeypatch) == []


def test_a_search_by_name_on_a_network_without_positions_is_still_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """A name finds stations without positions, so a name that matches none is no `positions-unavailable` case."""
    request = DwdPollenRequest(
        parameters=[("daily", "data")], start="2022-02-18", end="2022-02-18", settings=Settings(cache_disable=True)
    )

    (warning,) = _walk(request, _frame([]), StationsFilter.BY_NAME, monkeypatch)

    assert "matches the name" in warning["message"]


@pytest.mark.parametrize("selection", [StationsFilter.BY_NAME, StationsFilter.BY_BBOX, StationsFilter.ALL])
def test_a_lookup_that_went_without_a_directory_is_left_to_file_skipped(
    selection: StationsFilter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`dwd/observation` skips an empty listing and says `file-skipped`: "the network lists no station" is not true."""
    request = _dwd()
    request._gaps_of_lookup = {"daily/climate_summary/recent": ListingGap(reason="the directory was found empty")}  # noqa: SLF001

    assert _walk(request, _frame([]), selection, monkeypatch) == []


def test_it_is_not_told_where_stations_outside_window_says_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rule left out every station, ended or late: that warning names them, so this one does not repeat it."""
    ended = _frame([("00001", OLD, CLOSED), ("00002", OLD, CLOSED)])
    late = _frame([("00001", FUTURE, None), ("00002", FUTURE, None)])
    both = _frame([("00001", OLD, CLOSED), ("00002", FUTURE, None)])

    for df in (ended, late, both):
        assert _walk(_dwd(), df, StationsFilter.ALL, monkeypatch) == []
        assert any(w["code"] == "stations-outside-window" for w in recorded_warnings())


def test_it_is_not_told_for_an_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    """`interpolate` and `summarize` read the stations around a point as candidates, and say what they left out."""
    late = _frame([("00001", FUTURE, None)])

    assert _walk(_dwd(), late, StationsFilter.BY_RANK, monkeypatch, rank=1, estimate=True) == []
    assert _walk(_dwd(), _frame([]), StationsFilter.BY_DISTANCE, monkeypatch, estimate=True) == []


def test_it_is_not_told_where_a_station_was_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station that was read and holds nothing in the window is the ordinary empty answer, told as it always was."""
    df = _frame([("00001", OLD, None), ("00002", FUTURE, None)])

    assert _walk(_dwd(), df, StationsFilter.BY_STATION_ID, monkeypatch) == []


def test_the_end_of_a_window_that_is_not_a_day_is_told_with_its_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A window that ends at 12:30 begins nothing "on" a date: the text says when."""
    request = DwdObservationRequest(
        parameters=["daily/climate_summary/temperature_air_mean_2m"],
        start="2022-02-18T06:00:00+00:00",
        end="2022-02-18T12:30:00+00:00",
        settings=Settings(cache_disable=True),
    )

    (warning,) = _walk(request, _frame([("00001", FUTURE, None)]), StationsFilter.BY_STATION_ID, monkeypatch)

    assert "begins after the window's end, 2022-02-18 12:30 UTC, so by the list" in warning["message"]


def test_a_result_built_by_hand_without_the_start_column_is_cut_by_no_rule() -> None:
    """The rule cuts nothing where the frame has no `start_timestamp`, as before: it does not raise."""
    df = _frame([("00001", FUTURE, None)]).drop("start_timestamp")
    result = StationsResult(request=_dwd(), df=df, _df_all=df, _stations_filter=StationsFilter.ALL)

    assert station_ids_read(result) is None
