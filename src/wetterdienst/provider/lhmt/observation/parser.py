# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsers for LHMT's api.meteo.lt JSON responses (station list and per-day observations)."""

from __future__ import annotations

import json

import polars as pl

# the raw observation fields mapped to parameters (i.e. every ``name_original`` in metadata.py).
_VALUE_FIELDS = (
    "airTemperature",
    "relativeHumidity",
    "windSpeed",
    "windGust",
    "windDirection",
    "cloudCover",
    "seaLevelPressure",
    "precipitation",
    "snowDepth",
)

_EMPTY_STATIONS_SCHEMA = {
    "station_id": pl.String,
    "name": pl.String,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
}

_EMPTY_VALUES_SCHEMA = {
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
}


def parse_lhmt_stations(content: bytes) -> pl.DataFrame:
    """Parse ``/v1/stations`` into one row per station.

    Each entry carries ``code`` (a slug used as the station id and in observation URLs), ``name``
    and ``coordinates`` (``latitude``/``longitude``). The API exposes no elevation, so ``height`` is
    left for the framework to null-fill.
    """
    try:
        stations = json.loads(content)
    except json.JSONDecodeError:
        return pl.DataFrame(schema=_EMPTY_STATIONS_SCHEMA)
    if not isinstance(stations, list) or not stations:
        return pl.DataFrame(schema=_EMPTY_STATIONS_SCHEMA)
    rows = [
        {
            "station_id": station["code"],
            "name": station["name"],
            "latitude": station["coordinates"]["latitude"],
            "longitude": station["coordinates"]["longitude"],
        }
        for station in stations
    ]
    return pl.DataFrame(rows, schema=_EMPTY_STATIONS_SCHEMA)


def parse_lhmt_observations(content: bytes) -> pl.DataFrame:
    """Parse a per-day ``/observations/{date}`` response into long ``(date, parameter, value)`` rows.

    The response is ``{"station": {...}, "observations": [{"observationTimeUtc": ..., <field>: ...}]}``
    with one entry per hour. Missing values are already ``null`` (no sentinel). Timestamps are UTC
    (``YYYY-MM-DD HH:MM:SS``).
    """
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    observations = payload.get("observations") if isinstance(payload, dict) else None
    if not observations:
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    rows = [
        {"date": observation["observationTimeUtc"], "parameter": field, "value": observation.get(field)}
        for observation in observations
        for field in _VALUE_FIELDS
    ]
    return pl.DataFrame(rows, schema={"date": pl.String, "parameter": pl.String, "value": pl.Float64}).with_columns(
        pl.col("date").str.to_datetime("%Y-%m-%d %H:%M:%S", time_unit="us").dt.replace_time_zone("UTC"),
    )
