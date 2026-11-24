# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A DWD network served from memory for the tests of the row options (GH-4411).

Three stations with a daily record from 2018 to 2020, each with gaps, and the same readings from a plain Python
function, so that a test works out what the options must answer without polars: the oracle does not share a line
with the code it holds to account.
"""

from __future__ import annotations

import datetime as dt
import functools
from typing import TYPE_CHECKING, Any

import polars as pl

from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues

if TYPE_CHECKING:
    import pytest

STATIONS = {"00001": "Alpha", "00002": "Beta", "00003": "Gamma"}
FIRST_DAY = dt.datetime(2018, 1, 1, tzinfo=dt.UTC)
DAYS = 1096  # 2018, 2019 and 2020
TMIN = "daily/climate_summary/temperature_air_min_2m"
TMAX = "daily/climate_summary/temperature_air_max_2m"
GUST = "daily/climate_summary/wind_gust_max"


def reading(station_id: str, parameter: str, day: int) -> float | None:
    """Give the reading of a station on a day, `None` on a gap: a function, with many equal values (ties)."""
    if (day * 7 + int(station_id)) % 13 == 0:
        return None
    base = (day * 37 + int(station_id) * 11 + len(parameter)) % 61
    return base / 2.0 - 10.0 if "gust" not in parameter else base / 4.0


@functools.lru_cache(maxsize=64)
def _frame(station_id: str, name: str, name_original: str, dataset: str) -> pl.DataFrame:
    """Give the readings of a station for a parameter as a provider hands them over, in the order of the days."""
    values = [reading(station_id, name, day) for day in range(DAYS)]
    return pl.DataFrame(
        {
            "timestamp": [FIRST_DAY + dt.timedelta(days=day) for day in range(DAYS)],
            "parameter": [name_original] * DAYS,
            "value": values,
            "quality_flags": ["1"] * DAYS,
            "resolution": ["daily"] * DAYS,
            "dataset": [dataset] * DAYS,
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC"), "value": pl.Float64},
    )


def oracle(station_id: str, parameter: str) -> list[tuple[dt.datetime, float]]:
    """Give the readings of a station in the order of the days, the gaps left out."""
    rows = []
    for day in range(DAYS):
        value = reading(station_id, parameter, day)
        if value is not None:
            rows.append((FIRST_DAY + dt.timedelta(days=day), value))
    return rows


def serve(monkeypatch: pytest.MonkeyPatch, count: int = 3, *, missing: tuple[str, ...] = ()) -> None:
    """Serve `count` stations and their daily readings from memory, so that nothing is read upstream.

    The first three are the stations of `STATIONS`; more are numbered on and named after their number. A station in
    `missing` has every reading missing: its files are there and say nothing.
    """
    ids = [f"{number:05d}" for number in range(1, count + 1)]
    names = [STATIONS.get(station_id, f"Station {station_id}") for station_id in ids]
    stations = pl.DataFrame(
        {
            "resolution": ["daily"] * count,
            "dataset": ["climate_summary"] * count,
            "station_id": ids,
            "start_timestamp": [FIRST_DAY] * count,
            "end_timestamp": [None] * count,
            "latitude": [53.6 - 0.01 * number for number in range(count)],
            "longitude": [10.0 + 0.01 * number for number in range(count)],
            "elevation": [11.0 + number for number in range(count)],
            "name": names,
            "state": ["Hamburg"] * count,
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        # only what a test reads: the two temperatures and the gust, which the oracle knows how to read
        frames = [
            _frame(station_id, parameter.name, parameter.name_original, dataset.name)
            for parameter in dataset
            if parameter.name in ("temperature_air_min_2m", "temperature_air_max_2m", "wind_gust_max")
        ]
        frame = pl.concat(frames)
        if station_id in missing:
            frame = frame.with_columns(pl.lit(None, pl.Float64).alias("value"))
        return frame

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
