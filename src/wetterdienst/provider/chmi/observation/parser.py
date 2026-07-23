# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsers for CHMI's open-data CSV files (station catalogue and per-element observations).

Observation files come in three shapes: the ``daily`` files carry a ``TIMEFUNC``/``DT`` pair, the
sub-daily (``10_minutes``/``hourly``) files a bare ``DT``, and the ``monthly``/``annual`` files a
``YEAR``(+``MONTH``)/``TIMEFUNCTION`` aggregate layout. Each parser normalises to a common
``(date, parameter, value)`` frame.
"""

from __future__ import annotations

import polars as pl

# CHMI encodes timestamps without seconds, e.g. ``1863-10-01T00:00Z``.
_DATE_FORMAT = "%Y-%m-%dT%H:%MZ"

_EMPTY_STATIONS_SCHEMA = {
    "station_id": pl.String,
    "name": pl.String,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "height": pl.Float64,
    "start_date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "end_date": pl.Datetime(time_unit="us", time_zone="UTC"),
}

_EMPTY_VALUES_SCHEMA = {
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
}


def parse_chmi_stations(content: bytes) -> pl.DataFrame:
    """Parse CHMI's ``metadata/meta1.csv`` station catalogue into one row per station.

    The catalogue carries one row per operational period (``WSI``, ``BEGIN_DATE``/``END_DATE``,
    ``FULL_NAME``, ``GEOGR1``/``GEOGR2`` = longitude/latitude, ``ELEVATION``), so a station with a
    relocated sensor appears multiple times. Collapse to a single row using the most recent
    position for the coordinates/name and the full operational extent for the dates. An
    ``END_DATE`` in year 3999 marks a still-active station and leaves ``end_date`` null.
    """
    df = pl.read_csv(content, has_header=True, infer_schema_length=0)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_STATIONS_SCHEMA)
    df = df.with_columns(
        pl.col("BEGIN_DATE").str.to_datetime(_DATE_FORMAT, time_unit="us").dt.replace_time_zone("UTC"),
        pl.col("END_DATE").str.to_datetime(_DATE_FORMAT, time_unit="us").dt.replace_time_zone("UTC"),
    )
    df = df.group_by("WSI").agg(
        pl.col("FULL_NAME").sort_by("END_DATE").last().alias("name"),
        pl.col("GEOGR2").sort_by("END_DATE").last().alias("latitude"),
        pl.col("GEOGR1").sort_by("END_DATE").last().alias("longitude"),
        pl.col("ELEVATION").sort_by("END_DATE").last().alias("height"),
        pl.col("BEGIN_DATE").min().alias("start_date"),
        pl.col("END_DATE").max().alias("end_date"),
    )
    return df.select(
        pl.col("WSI").cast(pl.String).alias("station_id"),
        pl.col("name").cast(pl.String),
        pl.col("latitude").cast(pl.Float64, strict=False),
        pl.col("longitude").cast(pl.Float64, strict=False),
        pl.col("height").cast(pl.Float64, strict=False),
        pl.col("start_date"),
        pl.when(pl.col("end_date").dt.year() >= 3999).then(None).otherwise(pl.col("end_date")).alias("end_date"),
    )


def _values(date: pl.Expr, element: str, df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        date.alias("date"),
        pl.lit(element, dtype=pl.String).alias("parameter"),
        pl.col("VALUE").cast(pl.Float64, strict=False).alias("value"),
    )


def parse_chmi_values_daily(content: bytes, element: str, timefunc: str) -> pl.DataFrame:
    """Parse a daily per-element CSV, keeping only the ``TIMEFUNC`` for the requested parameter.

    A single file (e.g. ``dly-<WSI>-T.csv``) may hold several ``TIMEFUNC`` variants (the daily
    mean ``AVG`` alongside fixed-term readings), so keep only the relevant one. Timestamps are
    normalised to the calendar day so every daily parameter aligns on ``YYYY-MM-DD``.
    """
    df = pl.read_csv(content, has_header=True, infer_schema_length=0)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    df = df.filter(pl.col("TIMEFUNC") == timefunc)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    date = pl.col("DT").str.to_datetime(_DATE_FORMAT, time_unit="us").dt.replace_time_zone("UTC").dt.truncate("1d")
    return _values(date, element, df)


def parse_chmi_values_subdaily(content: bytes, element: str) -> pl.DataFrame:
    """Parse a sub-daily (10-minute/hourly) per-element CSV.

    Sub-daily files hold a single reading per ``DT`` (no ``TIMEFUNC``), so the native timestamp is
    kept as-is.
    """
    df = pl.read_csv(content, has_header=True, infer_schema_length=0)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    date = pl.col("DT").str.to_datetime(_DATE_FORMAT, time_unit="us").dt.replace_time_zone("UTC")
    return _values(date, element, df)


def parse_chmi_values_aggregate(
    content: bytes,
    element: str,
    timefunc: str,
    mdfunc: str,
    *,
    has_month: bool,
) -> pl.DataFrame:
    """Parse a monthly/annual per-element CSV.

    Aggregate files store the period as ``YEAR`` (plus ``MONTH`` for monthly) and two aggregation
    keys: ``TIMEFUNCTION`` mirrors the daily ``TIMEFUNC`` (which daily value was aggregated) and
    ``MDFUNCTION`` is how the daily values were combined over the period (``AVG`` mean, ``SUM`` total,
    ``MAX``/``MIN`` extremes, ``GE(..)``/``L(..)`` day counts). Both must be pinned to select a
    single series. The date is set to the period start.
    """
    df = pl.read_csv(content, has_header=True, infer_schema_length=0)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    df = df.filter(pl.col("TIMEFUNCTION") == timefunc, pl.col("MDFUNCTION") == mdfunc)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    month = pl.col("MONTH").cast(pl.Int32) if has_month else pl.lit(1, dtype=pl.Int32)
    date = (
        pl.date(pl.col("YEAR").cast(pl.Int32), month, 1).cast(pl.Datetime(time_unit="us")).dt.replace_time_zone("UTC")
    )
    return _values(date, element, df)
