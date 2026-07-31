# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsers for IPMA's open-data JSON feeds (station catalogue and hourly observations)."""

from __future__ import annotations

import json

import polars as pl

# IPMA's missing-value sentinel, used across every numeric observation field.
_MISSING = -99.0

# ``idDireccVento`` is an 8-point wind-direction code, not degrees. Per the IPMA docs: 0 = no
# direction (calm) -> null; 1 and 9 both mean N; 2..8 step clockwise through NE, E, SE, S, SW, W, NW.
_WIND_DIRECTION_DEGREES = {1: 0.0, 2: 45.0, 3: 90.0, 4: 135.0, 5: 180.0, 6: 225.0, 7: 270.0, 8: 315.0, 9: 0.0}

# the raw observation fields mapped to parameters (i.e. every ``name_original`` in metadata.py).
_VALUE_FIELDS = (
    "temperatura",
    "humidade",
    "pressao",
    "intensidadeVento",
    "precAcumulada",
    "radiacao",
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


def parse_ipma_stations(content: bytes) -> pl.DataFrame:
    """Parse ``stations.json`` (a bare JSON array of GeoJSON Feature objects) into one row per station.

    Each feature carries ``properties.idEstacao`` (the numeric station id) and
    ``properties.localEstacao`` (the name), plus a ``Point`` geometry as ``[longitude, latitude]``.
    The catalogue exposes no elevation, so ``height`` is left for the framework to null-fill.
    """
    features = json.loads(content)
    if not isinstance(features, list) or not features:
        return pl.DataFrame(schema=_EMPTY_STATIONS_SCHEMA)
    rows = [
        {
            "station_id": str(feature["properties"]["idEstacao"]),
            "name": feature["properties"]["localEstacao"],
            "latitude": feature["geometry"]["coordinates"][1],
            "longitude": feature["geometry"]["coordinates"][0],
        }
        for feature in features
    ]
    return pl.DataFrame(rows, schema=_EMPTY_STATIONS_SCHEMA)


def _value(field: str, raw: float | None) -> float | None:
    """Normalise one raw field value: sentinel/missing to null, wind-direction code to degrees."""
    if raw is None or raw == _MISSING:
        return None
    if field == "idDireccVento":
        return _WIND_DIRECTION_DEGREES.get(int(raw))  # code 0 (calm) and unknown codes -> null
    return float(raw)


def parse_ipma_observations(content: bytes, station_id: str) -> pl.DataFrame:
    """Parse the all-stations ``observations.json`` into long rows for a single station.

    The feed is a nested object ``{timestamp: {station_id: {field: value}}}`` covering roughly the
    last day. A station that reported nothing for a timestamp maps to ``null`` and is skipped. The
    emitted ``parameter`` column keeps the raw IPMA field name (``name_original``); values are
    normalised via :func:`_value`. Timestamps are UTC (``YYYY-MM-DDTHH:MM``).
    """
    feed = json.loads(content)
    if not isinstance(feed, dict):
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    rows = []
    for timestamp, stations in feed.items():
        record = stations.get(station_id) if isinstance(stations, dict) else None
        if not record:
            continue
        for field in (*_VALUE_FIELDS, "idDireccVento"):
            rows.append({"date": timestamp, "parameter": field, "value": _value(field, record.get(field))})
    if not rows:
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    return pl.DataFrame(rows, schema={"date": pl.String, "parameter": pl.String, "value": pl.Float64}).with_columns(
        pl.col("date").str.to_datetime("%Y-%m-%dT%H:%M", time_unit="us").dt.replace_time_zone("UTC"),
    )
