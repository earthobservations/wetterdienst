# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A `rank` of N lists N stations, each with a row for every dataset asked for, not N rows.

`limit_stations_to_rank` cuts the distance-sorted listing of a point and a rank. Served from memory, so nothing
leaves the machine.
"""

from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import core
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app

_UTC = ZoneInfo("UTC")
DAILY = "daily/climate_summary/temperature_air_mean_2m"
HOURLY = "hourly/temperature_air/temperature_air_2m"
POINT = {"latitude": "51.2", "longitude": "6.8"}


def _listing(datasets: list[str], rank: int) -> StationsResult:
    """Build a rank-filtered listing of three stations, the nearest first, with a row for each dataset."""
    rows = [
        (station_id, resolution, distance)
        for station_id, distance in (("00001", 1.0), ("00002", 2.0), ("00003", 3.0))
        for resolution in datasets
    ]
    df = pl.DataFrame(
        {
            "resolution": [row[1] for row in rows],
            "station_id": [row[0] for row in rows],
            "distance": [row[2] for row in rows],
        },
    )
    request = type("Request", (), {"start": None, "end": None})()
    return StationsResult(
        request=request,  # ty: ignore[invalid-argument-type]
        df=df,
        _df_all=df,
        _stations_filter=StationsFilter.BY_RANK,
        _rank=rank,
    )


@pytest.mark.parametrize(
    ("datasets", "rank", "stations", "rows"),
    [
        (["daily"], 1, ["00001"], 1),
        (["daily"], 2, ["00001", "00002"], 2),
        (["daily", "hourly"], 1, ["00001"], 2),
        # the case that listed one station twice: two rows are two datasets of the nearest station
        (["daily", "hourly"], 2, ["00001", "00002"], 4),
        (["daily", "hourly"], 10, ["00001", "00002", "00003"], 6),
    ],
)
def test_a_rank_keeps_the_rows_of_that_many_stations(
    datasets: list[str], rank: int, stations: list[str], rows: int
) -> None:
    """The unit is the station: every row of the `rank` nearest is kept, in the order they came."""
    df = core.limit_stations_to_rank(_listing(datasets, rank)).df

    assert df.get_column("station_id").unique(maintain_order=True).to_list() == stations
    assert df.height == rows
    assert df.get_column("distance").is_sorted()


def test_a_listing_that_is_not_by_rank_is_left_as_it_is() -> None:
    """Only the rank filter is cut."""
    stations = _listing(["daily", "hourly"], 1)
    stations = StationsResult(
        request=stations.request,
        df=stations.df,
        _df_all=stations.df,
        _stations_filter=StationsFilter.BY_STATION_ID,
        _rank=1,
    )

    assert core.limit_stations_to_rank(stations).df.height == 6


@pytest.fixture(autouse=True)
def _serve_dwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve three stations around Düsseldorf, each with a daily and an hourly dataset."""
    rows = [
        (resolution, dataset, station_id, latitude)
        for station_id, latitude in (("00001", 51.2), ("00002", 51.3), ("00003", 51.5))
        for resolution, dataset in (("daily", "climate_summary"), ("hourly", "temperature_air"))
    ]
    stations = pl.DataFrame(
        {
            "resolution": [row[0] for row in rows],
            "dataset": [row[1] for row in rows],
            "station_id": [row[2] for row in rows],
            "start_timestamp": [dt.datetime(1950, 1, 1, tzinfo=_UTC)] * len(rows),
            "end_timestamp": [None] * len(rows),
            "latitude": [row[3] for row in rows],
            "longitude": [6.8] * len(rows),
            "elevation": [10.0] * len(rows),
            "name": [f"Station {row[2]}" for row in rows],
            "state": ["Nordrhein-Westfalen"] * len(rows),
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )

    def served(self: DwdObservationRequest) -> pl.LazyFrame:
        wanted = {(resolution, dataset) for resolution, dataset in self._requested_datasets}
        return stations.filter(
            pl.struct("resolution", "dataset").map_elements(
                lambda row: (row["resolution"], row["dataset"]) in wanted, return_dtype=pl.Boolean
            )
        ).lazy()

    monkeypatch.setattr(DwdObservationRequest, "_all", served)


def _rest(parameters: str, rank: str) -> list[dict]:
    query = {"provider": "dwd", "network": "observation", "parameters": parameters, "rank": rank, **POINT}
    response = TestClient(app).get("/api/stations", params=query)
    assert response.status_code == 200, response.text
    return response.json()["stations"]


def _cli(parameters: str, rank: str) -> list[dict]:
    args = ["stations", "--provider=dwd", "--network=observation", f"--parameters={parameters}", f"--rank={rank}"]
    args += [f"--{key}={value}" for key, value in POINT.items()]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["stations"]


@pytest.mark.parametrize("surface", [_rest, _cli])
@pytest.mark.parametrize(
    ("parameters", "rank", "stations", "datasets"),
    [
        (DAILY, "2", ["00001", "00002"], 1),
        (f"{DAILY},{HOURLY}", "1", ["00001"], 2),
        (f"{DAILY},{HOURLY}", "2", ["00001", "00002"], 2),
    ],
)
def test_the_listing_of_a_rank_has_that_many_stations_with_a_row_per_dataset_on_every_surface(
    surface: object, parameters: str, rank: str, stations: list[str], datasets: int
) -> None:
    """`rank=2` with two datasets is two stations and four rows, and no longer one station twice."""
    rows = surface(parameters, rank)  # ty: ignore[call-non-callable]

    assert list(dict.fromkeys(row["station_id"] for row in rows)) == stations
    assert len(rows) == len(stations) * datasets
    assert {
        row["station_id"]: sum(r["station_id"] == row["station_id"] for r in rows) for row in rows
    } == dict.fromkeys(stations, datasets)
