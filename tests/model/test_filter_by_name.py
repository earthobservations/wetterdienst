# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`filter_by_name` returns the best matches first and at most `rank` stations (GH-3025).

The station list is served from memory, so nothing leaves the machine. Scores are those of rapidfuzz's
`WRatio` for the query "Kiel": 100 for "Kiel", 90 for every name that holds it, 88.9 for "Kiehl".
"""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

_UTC = ZoneInfo("UTC")

# (station_id, resolution, name), in the order a provider might list them: the best match is not first, and
# the stations that tie are not in the order of their ids
_ROWS = [
    ("00006", "daily", "Kiel-Holtenau"),
    ("00003", "daily", "Kiel-Holtenau"),
    ("00002", "daily", "Kiel-Kronshagen"),
    ("00001", "daily", "Kiehl"),
    ("00005", "daily", "Kiel"),
    ("00005", "hourly", "Kiel"),
    ("00009", "daily", "Dresden"),
]


def _serve(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[str, str, str]]) -> None:
    stations = pl.DataFrame(
        {
            "resolution": [row[1] for row in rows],
            "dataset": ["climate_summary" if row[1] == "daily" else "temperature_air" for row in rows],
            "station_id": [row[0] for row in rows],
            "start_timestamp": [dt.datetime(1934, 1, 1, tzinfo=_UTC)] * len(rows),
            "end_timestamp": [dt.datetime(2026, 10, 1, tzinfo=_UTC)] * len(rows),
            "latitude": [54.0] * len(rows),
            "longitude": [10.0] * len(rows),
            "elevation": [10.0] * len(rows),
            "name": [row[2] for row in rows],
            "region": ["Schleswig-Holstein"] * len(rows),
        },
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())


@pytest.fixture
def request_() -> DwdObservationRequest:
    """Build a request for a daily and an hourly dataset, so that a station has two rows."""
    return DwdObservationRequest(
        parameters=[("daily", "climate_summary"), ("hourly", "temperature_air")],
        settings=Settings(),
    )


def _stations(request: DwdObservationRequest, **kwargs: float | str) -> list[str]:
    return request.filter_by_name("Kiel", **kwargs).df.get_column("station_id").to_list()


def test_the_rows_come_back_best_match_first(monkeypatch: pytest.MonkeyPatch, request_: DwdObservationRequest) -> None:
    """The exact name is first although it is listed after the stations that merely hold it, the 88.9 one last."""
    _serve(monkeypatch, _ROWS)

    # a station has a row for each dataset asked for, and its rows stay together
    assert _stations(request_, rank=4) == ["00005", "00005", "00002", "00003", "00006"]
    assert _stations(request_, rank=10) == ["00005", "00005", "00002", "00003", "00006", "00001"]


def test_a_station_is_one_match_whatever_its_number_of_datasets(
    monkeypatch: pytest.MonkeyPatch, request_: DwdObservationRequest
) -> None:
    """`rank=1` is one station, with both its rows; `rank=2` is two stations, not two rows of the first."""
    _serve(monkeypatch, _ROWS)

    assert _stations(request_, rank=1) == ["00005", "00005"]
    assert _stations(request_) == ["00005", "00005"], "the default rank is the best match"
    assert _stations(request_, rank=2) == ["00005", "00005", "00002"]


def test_stations_that_share_a_name_do_not_exceed_the_rank(
    monkeypatch: pytest.MonkeyPatch, request_: DwdObservationRequest
) -> None:
    """Three stations hold the query alike and two are called the same: `rank=3` is still three stations."""
    _serve(monkeypatch, _ROWS)

    result = request_.filter_by_name("Kiel", rank=3).df
    assert result.get_column("station_id").unique(maintain_order=True).to_list() == ["00005", "00002", "00003"]
    # the other station called "Kiel-Holtenau" is not dragged in by its name
    assert "00006" not in result.get_column("station_id").to_list()


def test_equal_scores_are_ordered_by_station_id_whatever_the_order_of_the_list(
    monkeypatch: pytest.MonkeyPatch, request_: DwdObservationRequest
) -> None:
    """A tie is broken by `station_id`, so that the provider's own ordering decides nothing."""
    expected = ["00005", "00005", "00002", "00003"]
    for rows in (_ROWS, list(reversed(_ROWS)), sorted(_ROWS, key=lambda row: row[2])):
        _serve(monkeypatch, rows)
        assert _stations(request_, rank=3) == expected


def test_the_rows_of_a_station_keep_their_order(
    monkeypatch: pytest.MonkeyPatch, request_: DwdObservationRequest
) -> None:
    """A station's rows are in the order the list gives them: the sort is on the match, not on the dataset."""
    _serve(
        monkeypatch, [("00005", "hourly", "Kiel"), ("00005", "daily", "Kiel"), ("00002", "daily", "Kiel-Kronshagen")]
    )

    assert request_.filter_by_name("Kiel", rank=2).df.get_column("resolution").to_list() == ["hourly", "daily", "daily"]


def test_a_name_nothing_matches_is_an_empty_result(
    monkeypatch: pytest.MonkeyPatch, request_: DwdObservationRequest
) -> None:
    """No match is an empty frame with the schema of the list."""
    _serve(monkeypatch, _ROWS)

    result = request_.filter_by_name("FizzBuzz")
    assert result.df.is_empty()
    assert result.df.schema == request_.all().df.schema


def _serve_with_records(
    monkeypatch: pytest.MonkeyPatch, rows: list[tuple[str, str | None, int | None, int | None]]
) -> None:
    """Serve daily stations of (station_id, name, first year, last year) with the record each published."""

    def year(value: int | None) -> dt.datetime | None:
        return None if value is None else dt.datetime(value, 1, 1, tzinfo=_UTC)

    stations = pl.DataFrame(
        {
            "resolution": ["daily"] * len(rows),
            "dataset": ["climate_summary"] * len(rows),
            "station_id": [row[0] for row in rows],
            "start_timestamp": [year(row[2]) for row in rows],
            "end_timestamp": [year(row[3]) for row in rows],
            "latitude": [51.0] * len(rows),
            "longitude": [7.0] * len(rows),
            "elevation": [10.0] * len(rows),
            "name": [row[1] for row in rows],
            "region": ["Nordrhein-Westfalen"] * len(rows),
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "name": pl.String,
        },
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())


_DIACRITICS = [
    ("00001", "Köln", None, None),
    ("00002", "Koln-Bonn", None, None),
    ("00003", "Düsseldorf", None, None),
    ("00004", "Dusseldorf-Flughafen", None, None),
    ("00005", None, None, None),
    ("00006", "Dresden", None, None),
]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # the umlaut as it is, dropped, and written out: Köln is found by all three
        ("Köln", ["00001", "00002"]),
        ("Koln", ["00001", "00002"]),
        ("koeln", ["00001", "00002"]),
        ("KÖLN", ["00001", "00002"]),
        ("Düsseldorf", ["00003", "00004"]),
        ("Dusseldorf", ["00003", "00004"]),
        ("duesseldorf", ["00003", "00004"]),
    ],
)
def test_a_name_finds_the_station_whatever_the_way_its_diacritics_are_written(
    monkeypatch: pytest.MonkeyPatch, query: str, expected: list[str]
) -> None:
    """Umlauts, their transliteration and their absence find the same stations; a null name never matches."""
    _serve_with_records(monkeypatch, _DIACRITICS)
    request = DwdObservationRequest(parameters=("daily", "climate_summary"), settings=Settings())

    result = request.filter_by_name(query, rank=10).df

    assert result.get_column("station_id").to_list() == expected
    assert "00005" not in result.get_column("station_id").to_list()


def test_the_exact_spelling_beats_the_station_that_holds_the_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Düsseldorf` is a perfect match for the station of that name, and the airport comes after it."""
    _serve_with_records(
        monkeypatch, [("00001", "Dusseldorf-Flughafen", None, None), ("00002", "Düsseldorf", None, None)]
    )
    request = DwdObservationRequest(parameters=("daily", "climate_summary"), settings=Settings())

    assert request.filter_by_name("duesseldorf").df.get_column("station_id").to_list() == ["00002"]
    assert request.filter_by_name("Dusseldorf").df.get_column("station_id").to_list() == ["00002"]
    assert request.filter_by_name("Düsseldorf", threshold=1.0, rank=5).df.get_column("station_id").to_list() == [
        "00002"
    ]


# 00001 is open, 00002 closed in 2015 and 00003 begins after the window, 00004 publishes no record at all
_WINDOWED = [
    ("00001", "Düsseldorf", 1950, None),
    ("00002", "Dusseldorf-Flughafen", 1990, 2015),
    ("00003", "DÜSSELDORF", 2021, None),
    ("00004", "Düsseldorf-Unbekannt", None, None),
]


def test_a_name_is_matched_among_the_stations_with_a_record_in_the_window_of_the_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window of the request is applied before the ranking, as the command line and the REST API do."""
    _serve_with_records(monkeypatch, _WINDOWED)
    parameters = ("daily", "climate_summary")

    without = DwdObservationRequest(parameters=parameters, settings=Settings())
    assert without.filter_by_name("Dusseldorf", rank=10).df.get_column("station_id").to_list() == [
        "00001",
        "00003",
        "00002",
        "00004",
    ]

    windowed = DwdObservationRequest(parameters=parameters, start="2020-05-01", end="2020-05-03", settings=Settings())
    result = windowed.filter_by_name("Dusseldorf", rank=10)
    # the station that closed and the one that begins later are no candidates; a bound not published keeps the station
    assert result.df.get_column("station_id").to_list() == ["00001", "00004"]
    assert windowed.filter_by_name("Dusseldorf").df.get_column("station_id").to_list() == ["00001"]


def test_the_window_is_applied_to_a_df_all_that_is_passed_as_well(monkeypatch: pytest.MonkeyPatch) -> None:
    """The result does not depend on how the frame was obtained: a frame the window was applied to is left as it is."""
    from wetterdienst.model.request import limit_to_window  # noqa: PLC0415

    _serve_with_records(monkeypatch, _WINDOWED)
    request = DwdObservationRequest(
        parameters=("daily", "climate_summary"), start="2020-05-01", end="2020-05-03", settings=Settings()
    )
    everything = request.all().df
    cut = limit_to_window(everything, request.start, request.end)

    assert cut.height == 2
    expected = request.filter_by_name("Dusseldorf", rank=10).df
    for df_all in (everything, cut):
        assert request.filter_by_name("Dusseldorf", rank=10, df_all=df_all).df.equals(expected)


def test_filter_by_station_id_returns_the_stations_in_the_order_of_the_catalogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ids asked for in any order give the catalogue's order: sort the frame for another one."""
    _serve_with_records(
        monkeypatch, [("00003", "C", None, None), ("00001", "A", None, None), ("00002", "B", None, None)]
    )
    request = DwdObservationRequest(parameters=("daily", "climate_summary"), settings=Settings())

    catalogue = request.all().df.get_column("station_id").to_list()
    assert catalogue == ["00003", "00001", "00002"]
    for asked in (["00001", "00003"], ["00003", "00001"], ("00002", "00001", "00003")):
        found = request.filter_by_station_id(asked).df.get_column("station_id").to_list()
        assert found == [station for station in catalogue if station in set(asked)]
    # the caller sorts for another order
    df = request.filter_by_station_id(["00003", "00001"]).df.sort("station_id")
    assert df.get_column("station_id").to_list() == ["00001", "00003"]
