# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A request gets its station rows in one order, however often it is asked (GH-3551).

A station of two datasets is two rows of the stations frame. `unique` and a sort on the station id alone leave
the order of those two to the thread pool of polars, so the same request listed them one way and the next time
the other, and the features of an OGC answer followed. A `group_by` without `maintain_order` does the same to the
stations of `smhi/observation`, `dmi/observation` and `chmi/observation` (one dataset is enough), and the walk of
the values follows the frame. Each test here asks the same request many times in one process and compares the
answers row by row; the old code differed on almost every ask.
"""

from __future__ import annotations

import datetime as dt
import sys
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.station_catalogue_stubs import _chmi, _dmi, _smhi
from wetterdienst import Options, Settings
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as derived_api
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as observation_api
from wetterdienst.provider.dwd.observation.api import DwdObservationValues

if TYPE_CHECKING:
    from collections.abc import Callable

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.model.request import TimeseriesRequest

#: enough stations that a shuffled tie is a near certainty on the old code, and enough asks that it is certain
_STATION_IDS = [str(number).zfill(5) for number in range(1, 13)]
_ASKS = 30
#: the values walk is slower than a listing
_VALUES_ASKS = 4

_OBSERVATION = [("daily", "climate_summary"), ("daily", "precipitation_more"), ("hourly", "temperature_air")]
_DERIVED = [("hourly", "radiation_global"), ("hourly", "sunshine_duration"), ("daily", "soil")]


def _step(number: int, count: int) -> int:
    """Give the place of a station in the order of their distance: 7 and the count have no divisor in common."""
    return number * 7 % count


def _station_list(dataset: DatasetModel) -> pl.LazyFrame:
    """List every station for the dataset, a thousandth of a degree of latitude (110 m) apart.

    The nearest to 50 degrees is not the first of the list, nor are the others in the order of the list: a sort
    of rows that already come in order of distance does not shuffle the ones that tie.
    """
    return pl.LazyFrame(
        {
            "station_id": _STATION_IDS,
            "resolution": dataset.resolution.name,
            "dataset": dataset.name,
            "latitude": [50.0 + _step(number, len(_STATION_IDS)) / 1000 for number, _ in enumerate(_STATION_IDS)],
            "longitude": 10.0,
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "latitude": pl.Float64,
            "longitude": pl.Float64,
        },
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


def _assert_same(actual: list[tuple[str, str, str]], expected: list[tuple[str, str, str]]) -> None:
    """Compare two long lists of rows and name the first one that differs, not all of them."""
    assert len(actual) == len(expected), f"{len(actual)} rows, expected {len(expected)}"
    for index, (row, wanted) in enumerate(zip(actual, expected, strict=True)):
        assert row == wanted, f"row {index} is {row}, expected {wanted}"


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
    for _ in range(_VALUES_ASKS):
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


@pytest.mark.usefixtures("_observation_lists")
def test_the_rank_and_the_distance_keep_the_datasets_of_a_station_in_request_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hold the stations nearest a point to their distance, then the order the request names the datasets in.

    The datasets of one station have the one distance, so a sort on the distance and the id alone left them to
    the thread pool, and `filter_by_distance` is made of the rank.
    """
    # a sort of a few rows does not show it: the frame has to be a long one
    monkeypatch.setattr(sys.modules[__name__], "_STATION_IDS", [str(number).zfill(5) for number in range(1, 5001)])
    count = len(_STATION_IDS)
    by_distance = [station_id for _, station_id in sorted((_step(n, count), sid) for n, sid in enumerate(_STATION_IDS))]
    nearest = by_distance[:5]
    expected = [(station_id, resolution, dataset) for station_id in by_distance for resolution, dataset in _OBSERVATION]
    for _ in range(_VALUES_ASKS):
        request = DwdObservationRequest(parameters=_OBSERVATION, settings=Settings(cache_disable=True))
        ranked = request.filter_by_rank((50.0, 10.0), rank=5).df
        # a rank walks every located station by distance: the nearest five are the first of them
        _assert_same(ranked.select("station_id", "resolution", "dataset").rows(), expected)
        assert ranked.get_column("station_id").unique(maintain_order=True).to_list()[:5] == nearest
        within = request.filter_by_distance((50.0, 10.0), distance=0.5).df
        _assert_same(within.select("station_id", "resolution", "dataset").rows(), expected[: len(nearest) * 3])


@pytest.mark.parametrize(
    ("stub", "expected"),
    [
        (_smhi, ["1", "188800", "85600", "97400", "25080"]),
        (_dmi, ["06180", "06041", "04202", "04205"]),
        (_chmi, ["0-20000-0-11406", "0-203-0-20303032003", "0-203-0-41302035001"]),
    ],
    ids=["smhi", "dmi", "chmi"],
)
def test_the_stations_of_a_catalogue_read_by_a_group_by_come_in_the_order_of_the_catalogue(
    monkeypatch: pytest.MonkeyPatch, stub: Callable[[pytest.MonkeyPatch], pl.DataFrame], expected: list[str]
) -> None:
    """Hold the stations of a catalogue that is collapsed to a row per station to the order the catalogue lists them."""
    for _ in range(_ASKS):
        assert stub(monkeypatch).get_column("station_id").to_list() == expected
