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
