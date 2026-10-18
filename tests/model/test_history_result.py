# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for `HistoryResult.to_dict` and `to_json`, which REST and the CLI answer with (GH-2633)."""

import datetime as dt
import json
from collections.abc import Iterator

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.model.history import (
    History,
    TimeseriesHistory,
    _NameHistory,
    _OperatorName,
    _StationName,
)
from wetterdienst.model.result import HistoryResult, StationsFilter, StationsResult, select_history_sections
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.dwd.observation import DwdObservationRequest

KLOTZSCHE = "01048"


def _stations() -> StationsResult:
    request = DwdObservationRequest(parameters=[("daily", "climate_summary")], settings=Settings(cache_disable=True))
    df = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": KLOTZSCHE,
                "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
                "end_timestamp": None,
                "latitude": 51.1278,
                "longitude": 13.7543,
                "elevation": 228.0,
                "name": "Dresden-Klotzsche",
                "region": "Sachsen",
            }
        ],
        schema=STATIONS_SCHEMA,
    )
    return StationsResult(request=request, df=df, _df_all=df, _stations_filter=StationsFilter.BY_STATION_ID)


def _history(station_id: str = KLOTZSCHE) -> History:
    return History(
        station_id=station_id,
        resolution="daily",
        dataset="climate_summary",
        name=_NameHistory(
            station=[
                # a stamp with its zone, and one without, which is UTC like everything else here
                _StationName(
                    station_id=station_id,
                    station_name="Dresden-Hellerau",
                    valid_from=dt.datetime(1926, 5, 1, tzinfo=dt.UTC),
                    valid_to=dt.datetime(1934, 1, 1),  # noqa: DTZ001
                ),
            ],
            operator=[
                _OperatorName(
                    station_id=station_id,
                    operator_name="Wetterdienst",
                    valid_from=dt.datetime(1934, 1, 1, 2, tzinfo=dt.timezone(dt.timedelta(hours=2))),
                    valid_to=None,
                ),
            ],
        ),
    )


def test_a_history_result_writes_its_stamps_as_every_other_result_does() -> None:
    """Test that `valid_from` and `valid_to` are text in the one timestamp format, null where open."""
    data = HistoryResult(stations=_stations(), history=_history()).to_dict()
    assert list(data) == ["histories"]
    (history,) = data["histories"]
    assert history["name"]["station"] == [
        {
            "station_id": KLOTZSCHE,
            "station_name": "Dresden-Hellerau",
            "valid_from": "1926-05-01T00:00:00.000000+00:00",
            "valid_to": "1934-01-01T00:00:00.000000+00:00",
        }
    ]
    assert history["name"]["operator"][0]["valid_from"] == "1934-01-01T00:00:00.000000+00:00"
    assert history["name"]["operator"][0]["valid_to"] is None


def test_a_history_result_has_the_envelope_of_the_other_results() -> None:
    """Test that `with_metadata` and `with_stations` come first, in that order, as for values."""
    result = HistoryResult(stations=_stations(), history=_history())
    data = result.to_dict(with_metadata=True, with_stations=True)
    assert list(data) == ["metadata", "stations", "histories"]
    assert data["metadata"]["provider"]["name_english"] == "German Weather Service"
    assert [station["station_id"] for station in data["stations"]] == [KLOTZSCHE]
    assert data["stations"][0]["start_timestamp"] == "1934-01-01T00:00:00.000000+00:00"


def test_a_history_result_narrowed_to_sections_still_names_its_station() -> None:
    """Test that `sections` keeps the identifiers and the sections asked for, in the history's own order."""
    data = HistoryResult(stations=_stations(), history=_history()).to_dict(sections={"name"})
    assert list(data["histories"][0]) == ["station_id", "resolution", "dataset", "name"]
    assert list(
        HistoryResult(stations=_stations(), history=_history()).to_dict(sections={"device"})["histories"][0]
    ) == [
        "station_id",
        "resolution",
        "dataset",
        "device",
    ]


def test_select_history_sections_keeps_station_and_dataset() -> None:
    """Test a history narrowed to some sections still names its station and dataset, first as in the history."""
    history = {
        "station_id": "01048",
        "resolution": "daily",
        "dataset": "climate_summary",
        "name": {"station": [], "operator": []},
        "parameter": [],
        "device": [],
        "geography": [],
        "missing_data": {"summary": [], "periods": []},
    }
    selected = select_history_sections(history, {"missing_data"})
    assert list(selected.items()) == [
        ("station_id", "01048"),
        ("resolution", "daily"),
        ("dataset", "climate_summary"),
        ("missing_data", {"summary": [], "periods": []}),
    ]
    assert select_history_sections(history, None) == history
    assert select_history_sections(history, set()) == history


@pytest.mark.parametrize(("indent", "pretty"), [(4, True), (True, True), (None, False), (False, False)])
def test_to_json_is_the_dict_as_text(indent: int | bool | None, pretty: bool) -> None:  # noqa: FBT001
    """Test that `to_json` carries what `to_dict` has, indented as asked, as the other results' do."""
    result = HistoryResult(stations=_stations(), history=_history())
    text = result.to_json(indent=indent, with_stations=True)
    assert json.loads(text) == json.loads(json.dumps(result.to_dict(with_stations=True)))
    assert ("\n" in text) is pretty


class _CollectedHistory(TimeseriesHistory):
    """A history that serves two stations' records, as a provider that has them would."""

    def _collect_station_history(self, station_id: str, available_datasets: list) -> Iterator[History]:  # noqa: ARG002
        yield _history(station_id)


def test_the_history_of_a_request_is_one_document_of_all_its_stations() -> None:
    """Test that `TimeseriesHistory.to_json`, which REST and the CLI return, holds every station's history."""
    stations = _stations()
    collector = _CollectedHistory(sr=stations)
    data = json.loads(collector.to_json(with_metadata=True, with_stations=True, indent=False))
    assert list(data) == ["metadata", "stations", "histories"]
    assert [history["station_id"] for history in data["histories"]] == [KLOTZSCHE]
    assert collector.to_dict() == {"histories": [result.to_dict()["histories"][0] for result in collector.query()]}
    # one history per station and dataset the collector yields, whatever the sections asked for
    assert collector.to_dict(sections={"geography"})["histories"][0].keys() == {
        "station_id",
        "resolution",
        "dataset",
        "geography",
    }
