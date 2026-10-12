# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsers for IPMA's open-data JSON feeds (station catalogue and hourly observations)."""

from __future__ import annotations

import json

import polars as pl

from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels

# IPMA's missing-value sentinel, used across every numeric observation field, as the feed writes it
# (`"radiacao": -99.0`; on the live feed of 2026-10-12 it is the only one, in every field)
_MISSING = Sentinel("-99.0")

# ``idDireccVento`` is an 8-point wind-direction code, not degrees. Per the IPMA docs: 0 = no
# direction (calm) -> null; 1 and 9 both mean N; 2..8 step clockwise through NE, E, SE, S, SW, W, NW.
_WIND_DIRECTION_DEGREES = {
    1.0: 0.0,
    2.0: 45.0,
    3.0: 90.0,
    4.0: 135.0,
    5.0: 180.0,
    6.0: 225.0,
    7.0: 270.0,
    8.0: 315.0,
    9.0: 0.0,
}

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
    "timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
    "quality_flags": pl.String,
}


def parse_ipma_stations(content: bytes) -> pl.DataFrame:
    """Parse ``stations.json`` into one row per station.

    IPMA serves the catalogue as a bare JSON array of GeoJSON ``Feature`` objects, but a standard
    ``FeatureCollection`` wrapper (``{"type": "FeatureCollection", "features": [...]}``) is accepted
    too. Each feature carries ``properties.idEstacao`` (the numeric station id) and
    ``properties.localEstacao`` (the name), plus a ``Point`` geometry as ``[longitude, latitude]``.
    The catalogue exposes no elevation, so ``elevation`` is left for the framework to null-fill.
    """
    data = json.loads(content)
    features = data.get("features") if isinstance(data, dict) else data
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


def parse_ipma_observations_feed(content: bytes) -> dict:
    """Deserialise the all-stations ``observations.json`` once into its nested dict.

    The feed is a nested object ``{timestamp: {station_id: {field: value}}}`` covering roughly the
    last day and holding every station. Because a single feed serves all stations, callers parse it
    once and hand the result to :func:`extract_ipma_station_observations` per station, rather than
    re-running :func:`json.loads` over the whole payload for every station. A payload that is not a
    JSON object yields an empty dict.
    """
    feed = json.loads(content)
    return feed if isinstance(feed, dict) else {}


def extract_ipma_station_observations(feed: dict, station_id: str) -> pl.DataFrame:
    """Extract one station's long-form rows from an already-parsed observations ``feed``.

    A station that reported nothing for a timestamp maps to ``null`` and is skipped. The emitted
    ``parameter`` column keeps the raw IPMA field name (``name_original``). The ``-99.0`` sentinel is nulled, a
    wind-direction code is converted to degrees, and the text of what was nulled is kept as ``raw:`` in
    ``quality_flags`` (GH-2759). Timestamps are UTC (``YYYY-MM-DDTHH:MM``).
    """
    rows = []
    for timestamp, stations in feed.items():
        record = stations.get(station_id) if isinstance(stations, dict) else None
        if not record:
            continue
        for field in (*_VALUE_FIELDS, "idDireccVento"):
            value = record.get(field)
            rows.append({"timestamp": timestamp, "parameter": field, "value": None if value is None else float(value)})
    if not rows:
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    cleaned, raw = null_sentinels(pl.col("value"), _MISSING, text=False)
    # a wind direction is a code of eight points, and code 0 is "no direction (calm)" or a code no table lists: no
    # direction either way, and the code is kept as its text
    is_direction = pl.col("parameter") == "idDireccVento"
    no_direction = is_direction & cleaned.is_not_null() & ~cleaned.is_in(list(_WIND_DIRECTION_DEGREES))
    raw = pl.coalesce(raw, pl.when(no_direction).then(cleaned.cast(pl.Int64).cast(pl.String)))
    degrees = cleaned.replace_strict(_WIND_DIRECTION_DEGREES, default=None, return_dtype=pl.Float64)
    return pl.DataFrame(rows, schema={"timestamp": pl.String, "parameter": pl.String, "value": pl.Float64}).select(
        pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M", time_unit="us").dt.replace_time_zone("UTC"),
        pl.col("parameter"),
        pl.when(is_direction).then(degrees).otherwise(cleaned).alias("value"),
        join_quality_flags(None, raw=raw),
    )


def parse_ipma_observations(content: bytes, station_id: str) -> pl.DataFrame:
    """Parse the all-stations ``observations.json`` into long rows for a single station.

    Convenience wrapper that deserialises the feed and extracts one station in a single call. Callers
    fetching many stations from the same feed should instead parse once via
    :func:`parse_ipma_observations_feed` and reuse the result across
    :func:`extract_ipma_station_observations` calls.
    """
    return extract_ipma_station_observations(parse_ipma_observations_feed(content), station_id)
