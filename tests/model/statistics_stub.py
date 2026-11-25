# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A DWD network served from memory with any readings: the hand-worked cases of `statistics` (GH-4412)."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import polars as pl

from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import pytest

DAILY = "daily/climate_summary/temperature_air_mean_2m"
HOURLY = "hourly/air_temperature/temperature_air_mean_2m"


def serve_custom(
    monkeypatch: pytest.MonkeyPatch,
    series: Mapping[str, Mapping[dt.datetime, float | None]],
    *,
    resolution: str = "daily",
    dataset: str = "climate_summary",
    parameter: str = "temperature_air_mean_2m",
) -> None:
    """Serve stations whose readings the caller gives (a missing step is simply not there), from memory."""
    ids = list(series)
    count = len(ids)
    stations = pl.DataFrame(
        {
            "resolution": [resolution] * count,
            "dataset": [dataset] * count,
            "station_id": ids,
            "start_timestamp": [dt.datetime(1850, 1, 1, tzinfo=dt.UTC)] * count,
            "end_timestamp": [None] * count,
            "latitude": [53.6 - 0.01 * n for n in range(count)],
            "longitude": [10.0 + 0.01 * n for n in range(count)],
            "elevation": [11.0 + n for n in range(count)],
            "name": [f"Station {station_id}" for station_id in ids],
            "state": ["Hamburg"] * count,
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        found = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        readings = series[station_id]
        frames = [
            pl.DataFrame(
                {
                    "timestamp": list(readings),
                    "parameter": [member.name_original] * len(readings),
                    "value": list(readings.values()),
                    "quality_flags": ["1"] * len(readings),
                    "resolution": [resolution] * len(readings),
                    "dataset": [found.name] * len(readings),
                },
                schema_overrides={"timestamp": pl.Datetime("us", "UTC"), "value": pl.Float64},
            )
            for member in found
            if member.name == parameter
        ]
        return pl.concat(frames)

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def at(year: int, month: int, day: int, hour: int = 0) -> dt.datetime:
    """Give a UTC stamp."""
    return dt.datetime(year, month, day, hour, tzinfo=dt.UTC)


def daily(start: dt.date, values: Sequence[float | None]) -> dict[dt.datetime, float | None]:
    """Give daily readings from `start` on; a None is a day with no reading, which is left out as a gap is."""
    first = at(start.year, start.month, start.day)
    return {first + dt.timedelta(days=n): value for n, value in enumerate(values) if value is not None}
