# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsers for IPMA's open-data JSON feeds (station catalogue and hourly observations)."""

from __future__ import annotations

import json

import polars as pl

from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, no_direction_code, null_sentinels

# IPMA's missing-value sentinel, used across every numeric observation field, as the feed writes it
# (`"radiacao": -99.0`; on the live feed of 2026-10-12 it is the only one, in every field)
_MISSING = Sentinel("-99.0")

# ``idDireccVento`` is an 8-point wind-direction code, not degrees. Per the IPMA docs: 0 = "sem rumo" (no
# direction) -> null; 1 and 9 both mean N; 2..8 step clockwise through NE, E, SE, S, SW, W, NW.
# The docs do not say calm: the code 0 is also served with a wind that blows (26 of the 558 rows with code 0 in the
# feed of 2026-10-21 21:00 to 2026-10-22 20:00 have a speed above 0, 101 a speed of 0.0 and 431 none).
# It is a code on a scale whose north is 1 or 9, so it can never be a bearing: it is null whatever the speed, the
# rule of a no-direction code (GH-3222), and so is a code no table lists
_DIRECTION = "idDireccVento"
_NO_DIRECTION = no_direction_code("0", where=pl.col("parameter") == _DIRECTION)
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


def parse_ipma_stations(content: bytes) -> pl.DataFrame:
    """Parse ``stations.json`` into one row per station.

    IPMA serves the catalogue as a bare JSON array of GeoJSON ``Feature`` objects, but a standard
    ``FeatureCollection`` wrapper (``{"type": "FeatureCollection", "features": [...]}``) is accepted
    too. Each feature carries ``properties.idEstacao`` (the numeric station id) and
    ``properties.localEstacao`` (the name), plus a ``Point`` geometry as ``[longitude, latitude]``.
    The catalogue exposes no elevation, so ``elevation`` is left for the core to null-fill. A catalogue without a
    feature is a frame without a row.
    """
    data = json.loads(content)
    features = data.get("features") if isinstance(data, dict) else data
    if not isinstance(features, list) or not features:
        return pl.DataFrame()
    rows = [
        {
            "station_id": str(feature["properties"]["idEstacao"]),
            "name": feature["properties"]["localEstacao"],
            "latitude": feature["geometry"]["coordinates"][1],
            "longitude": feature["geometry"]["coordinates"][0],
        }
        for feature in features
    ]
    return pl.DataFrame(rows, infer_schema_length=None)


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

    The value is handed over as the text the feed writes, which the core reads as a number: a cell that is a text and
    no number, or a JSON ``NaN``, is null there and counted in its debug line, where ``float`` raised on the text and
    failed the request (GH-3222).
    """
    rows = []
    for timestamp, stations in feed.items():
        record = stations.get(station_id) if isinstance(stations, dict) else None
        if not record:
            continue
        for field in (*_VALUE_FIELDS, _DIRECTION):
            value = record.get(field)
            rows.append({"timestamp": timestamp, "parameter": field, "value": None if value is None else str(value)})
    if not rows:
        return pl.DataFrame()
    cleaned, raw = null_sentinels(pl.col("value"), _MISSING, _NO_DIRECTION)
    number = cleaned.cast(pl.Float64, strict=False)
    # a direction is a point of the eight, turned into degrees; a text that is no number is left to the core
    is_code = (pl.col("parameter") == _DIRECTION) & number.is_finite().fill_null(value=False)
    unlisted = is_code & ~number.is_in(list(_WIND_DIRECTION_DEGREES))
    raw = pl.coalesce(raw, pl.when(unlisted).then(cleaned))
    degrees = number.replace_strict(_WIND_DIRECTION_DEGREES, default=None, return_dtype=pl.Float64)
    return pl.DataFrame(rows, schema={"timestamp": pl.String, "parameter": pl.String, "value": pl.String}).select(
        pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M", time_unit="us").dt.replace_time_zone("UTC"),
        pl.col("parameter"),
        pl.when(is_code).then(degrees.cast(pl.String)).otherwise(cleaned).alias("value"),
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
