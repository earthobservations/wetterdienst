# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A request for several datasets gets its station rows in one order, however often it is asked (GH-3551).

A station of two datasets is two rows of the stations frame. `unique` and a sort on the station id alone leave
the order of those two to the thread pool of polars, so the same request listed them one way and the next time
the other, and the features of an OGC answer followed. Each test here asks the same request many times in one
process and compares the answers row by row; one run of the old code differed on almost every ask.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import polars as pl
import pytest

from wetterdienst import Options, Settings
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as derived_api
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as observation_api
from wetterdienst.provider.dwd.observation.api import DwdObservationValues

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.model.request import TimeseriesRequest

#: enough stations that a shuffled tie is a near certainty on the old code, and enough asks that it is certain
_STATION_IDS = [str(number).zfill(5) for number in range(1, 13)]
_ASKS = 30

_OBSERVATION = [("daily", "climate_summary"), ("daily", "precipitation_more"), ("hourly", "temperature_air")]
_DERIVED = [("hourly", "radiation_global"), ("hourly", "sunshine_duration"), ("daily", "soil")]


def _station_list(dataset: DatasetModel) -> pl.LazyFrame:
    return pl.LazyFrame(
        {"station_id": _STATION_IDS, "resolution": dataset.resolution.name, "dataset": dataset.name},
        schema={"station_id": pl.String, "resolution": pl.String, "dataset": pl.String},
    )


def _file_ids() -> pl.LazyFrame:
    return pl.LazyFrame({"station_id": _STATION_IDS}, schema={"station_id": pl.String})


@pytest.fixture
def _observation_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve every station for every dataset and period, as the descriptions and file indexes of DWD would."""
    monkeypatch.setattr(
        observation_api, "create_meta_index_for_climate_observations", lambda dataset, *_: _station_list(dataset)
    )
    monkeypatch.setattr(observation_api, "create_file_index_for_climate_observations", lambda *_: _file_ids())


@pytest.fixture
def _derived_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve every station for every dataset and period, as the descriptions and file indexes of DWD would."""
    monkeypatch.setattr(
        derived_api,
        "create_meta_index_for_climate_derived",
        lambda dataset, *_: _station_list(dataset).drop("resolution", "dataset"),
    )
    monkeypatch.setattr(derived_api, "create_file_index_for_climate_derived", lambda *_: _file_ids())


def _rows(request: TimeseriesRequest) -> list[tuple[str, str, str]]:
    return request.all().df.select("station_id", "resolution", "dataset").rows()


def _expected(datasets: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """Give the rows of a station in the order the request names its datasets, the stations by id."""
    return [(station_id, resolution, dataset) for station_id in _STATION_IDS for resolution, dataset in datasets]


@pytest.mark.usefixtures("_observation_lists")
@pytest.mark.parametrize("datasets", [_OBSERVATION, list(reversed(_OBSERVATION))])
def test_the_stations_of_dwd_observation_come_in_one_order(datasets: list[tuple[str, str]]) -> None:
    """Hold the rows of a station to the order the request names its datasets in, on every ask."""
    for _ in range(_ASKS):
        request = DwdObservationRequest(parameters=datasets, settings=Settings(cache_disable=True))
        assert _rows(request) == _expected(datasets)


@pytest.mark.usefixtures("_derived_lists")
@pytest.mark.parametrize("datasets", [_DERIVED, list(reversed(_DERIVED))])
def test_the_stations_of_dwd_derived_come_in_one_order(datasets: list[tuple[str, str]]) -> None:
    """Hold the rows of a station to the order the request names its datasets in, on every ask."""
    for _ in range(_ASKS):
        request = DwdDerivedRequest(parameters=datasets, settings=Settings(cache_disable=True))
        assert _rows(request) == _expected(datasets)


def _collect(self: DwdObservationValues, station_id: str, parameter_or_dataset: DatasetModel) -> pl.DataFrame:  # noqa: ARG001
    """Give every parameter of the dataset three readings, hourly or daily, without a download."""
    dataset = parameter_or_dataset
    step = dt.timedelta(hours=1) if dataset.resolution.name == "hourly" else dt.timedelta(days=1)
    start = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    return pl.DataFrame(
        [
            {"parameter": parameter.name_original, "timestamp": start + step * number, "value": float(number)}
            for parameter in dataset.parameters
            for number in range(3)
        ],
        schema={"parameter": pl.String, "timestamp": pl.Datetime(time_zone="UTC"), "value": pl.Float64},
    )


@pytest.mark.usefixtures("_observation_lists")
@pytest.mark.parametrize("shape", ["long", "wide"])
def test_the_values_and_the_stations_they_name_come_in_one_order(monkeypatch: pytest.MonkeyPatch, shape: str) -> None:
    """Hold the values, the stations they name and the features of the OGC answer to the same order on every ask."""
    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", _collect)
    answers = []
    for _ in range(_ASKS):
        request = DwdObservationRequest(
            parameters=_OBSERVATION, settings=Settings(cache_disable=True), options=Options(shape=shape)
        )
        result = request.all().values().all()
        features = result.to_ogc_feature_collection()["data"]["features"]
        answers.append(
            (
                result.df.rows(),
                result.df_stations.select("station_id", "resolution", "dataset").rows(),
                [(f["properties"]["id"], f["properties"]["resolution"], f["properties"]["dataset"]) for f in features],
            )
        )
    assert answers[0][0], "the stub gave no values, so the comparison would compare nothing"
    assert all(answer == answers[0] for answer in answers)
