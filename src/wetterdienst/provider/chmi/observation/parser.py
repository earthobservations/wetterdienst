# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsers for CHMI's open-data CSV files (station catalogue and per-element observations).

Observation files come in three shapes: the ``daily`` files carry a ``TIMEFUNC``/``DT`` pair, the
sub-daily (``10_minutes``/``hourly``) files a bare ``DT``, and the ``monthly``/``annual`` files a
``YEAR``(+``MONTH``)/``TIMEFUNCTION`` aggregate layout. Each parser normalises to a common
``(timestamp, parameter, value, quality_flags)`` frame, whose ``value`` is the text of the file: the core reads it as
the number it writes (``shape_provider_frame``).
"""

from __future__ import annotations

import polars as pl

from wetterdienst.model.quality_flags import join_quality_flags

# CHMI encodes timestamps without seconds, e.g. ``1863-10-01T00:00Z``.
_DATE_FORMAT = "%Y-%m-%dT%H:%MZ"


def parse_chmi_stations(content: bytes) -> pl.DataFrame:
    """Parse CHMI's ``metadata/meta1.csv`` station catalogue into one row per station.

    The coordinates and the elevation are the text of the file, and the stamps are naive: the core reads them as the
    numbers they write and as UTC (``shape_stations_frame``). A catalogue without a row is a frame without a row.

    The catalogue carries one row per operational period (``WSI``, ``BEGIN_DATE``/``END_DATE``,
    ``FULL_NAME``, ``GEOGR1``/``GEOGR2`` = longitude/latitude, ``ELEVATION``), so a station with a
    relocated sensor appears multiple times. Collapse to a single row using the most recent
    position for the coordinates/name and the full operational extent for the dates. An
    ``END_DATE`` in year 3999 marks a still-active station and leaves ``end_timestamp`` null.
    """
    df = pl.read_csv(content, has_header=True, infer_schema_length=0)
    if df.is_empty():
        return pl.DataFrame()
    df = df.with_columns(
        pl.col("BEGIN_DATE").str.to_datetime(_DATE_FORMAT, time_unit="us"),
        pl.col("END_DATE").str.to_datetime(_DATE_FORMAT, time_unit="us"),
    )
    df = df.group_by("WSI", maintain_order=True).agg(
        pl.col("FULL_NAME").sort_by("END_DATE").last().alias("name"),
        pl.col("GEOGR2").sort_by("END_DATE").last().alias("latitude"),
        pl.col("GEOGR1").sort_by("END_DATE").last().alias("longitude"),
        pl.col("ELEVATION").sort_by("END_DATE").last().alias("elevation"),
        pl.col("BEGIN_DATE").min().alias("start_timestamp"),
        pl.col("END_DATE").max().alias("end_timestamp"),
    )
    return df.select(
        pl.col("WSI").alias("station_id"),
        # some names end in a blank (`Třinec  Oldřichovice  Javorový `),
        # which an exact comparison of the name then misses
        pl.col("name").str.strip_chars(),
        pl.col("latitude"),
        pl.col("longitude"),
        pl.col("elevation"),
        pl.col("start_timestamp"),
        pl.when(pl.col("end_timestamp").dt.year() >= 3999)
        .then(None)
        .otherwise(pl.col("end_timestamp"))
        .alias("end_timestamp"),
    )


def _values(date: pl.Expr, element: str, df: pl.DataFrame) -> pl.DataFrame:
    """Select the timestamp, the parameter, the value and the quality flags of a file's rows.

    The daily and sub-daily files give every value a ``QUALITY`` code, written "0.0", "3.0", ... and
    explained by ``metadata/meta4.csv``: 0 Good, 1 Suspect, 2 Poor, 3 Estimated, 4 Missing, 5 Unknown.
    It is written as the whole number meta4 lists, the plain token of ``quality_flags``. They also give
    a row a ``FLAG`` letter that is blank for most rows and whose meaning is that of its element
    (``metadata/meta3.csv``, e.g. SRA ``T`` for an unmeasurable amount); it follows as
    ``element:<letter>``, so ``quality_flags`` reads ``0,element:T``.

    The aggregate files have neither column but ``FLAG_REPEAT`` and ``FLAG_INTERRUPTED``, which no
    metadata file and no CHMI document explains (``Klimatologicka_data_popis.pdf`` names the flag
    files and no more); what they mean follows from comparing the files with their daily files:

    - ``*`` in ``FLAG_REPEAT`` (and no other character, in any file of station 0-20000-0-11406) is on
      a ``MAX`` or ``MIN`` row only, and in ``mly-0-20000-0-11406-T.csv`` on exactly the 435 of the
      9528 such rows whose extreme ``dly-0-20000-0-11406-T.csv`` holds on more than one day of the
      month: the extreme was reached repeatedly.
    - ``I`` in ``FLAG_INTERRUPTED`` is on a row whose value is computed although daily values of the
      period are missing (``mly-...-T20.csv`` and ``-Fmax.csv`` against their daily files: every such
      row has it and no row of a complete period): the series was interrupted.

    They follow as ``repeat:*`` and ``interrupted:I``, in that order after ``element`` (these files
    have no quality code). The parameters read from the aggregate files are means and the precipitation
    total (``_AGGREGATE_ELEMENTS``), never a ``MAX`` or ``MIN``, so ``repeat:*`` does not show in
    them today; ``interrupted:I`` does.
    """
    quality = (
        pl.col("QUALITY").cast(pl.Float64, strict=False).cast(pl.Int64, strict=False)
        if "QUALITY" in df.columns
        else pl.lit(None, dtype=pl.String)
    )
    element_flag = pl.col("FLAG") if "FLAG" in df.columns else pl.lit(None, dtype=pl.String)
    repeat = pl.col("FLAG_REPEAT") if "FLAG_REPEAT" in df.columns else pl.lit(None, dtype=pl.String)
    interrupted = pl.col("FLAG_INTERRUPTED") if "FLAG_INTERRUPTED" in df.columns else pl.lit(None, dtype=pl.String)
    return df.select(
        date.alias("timestamp"),
        pl.lit(element, dtype=pl.String).alias("parameter"),
        pl.col("VALUE").alias("value"),
        join_quality_flags(quality, element=element_flag, repeat=repeat, interrupted=interrupted),
    )


def parse_chmi_values_daily(content: bytes, element: str, timefunc: str) -> pl.DataFrame:
    """Parse a daily per-element CSV, keeping only the ``TIMEFUNC`` for the requested parameter.

    A single file (e.g. ``dly-<WSI>-T.csv``) may hold several ``TIMEFUNC`` variants (the daily
    mean ``AVG`` alongside fixed-term readings), so keep only the relevant one. Timestamps are
    normalised to the calendar day so every daily parameter aligns on ``YYYY-MM-DD``.
    """
    df = pl.read_csv(content, has_header=True, infer_schema_length=0)
    if df.is_empty():
        return pl.DataFrame()
    df = df.filter(pl.col("TIMEFUNC") == timefunc)
    if df.is_empty():
        return pl.DataFrame()
    date = pl.col("DT").str.to_datetime(_DATE_FORMAT, time_unit="us").dt.replace_time_zone("UTC").dt.truncate("1d")
    return _values(date, element, df)


def parse_chmi_values_subdaily(content: bytes, element: str) -> pl.DataFrame:
    """Parse a sub-daily (10-minute/hourly) per-element CSV.

    Sub-daily files hold a single reading per ``DT`` (no ``TIMEFUNC``), so the native timestamp is
    kept as-is.
    """
    df = pl.read_csv(content, has_header=True, infer_schema_length=0)
    if df.is_empty():
        return pl.DataFrame()
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
        return pl.DataFrame()
    df = df.filter(pl.col("TIMEFUNCTION") == timefunc, pl.col("MDFUNCTION") == mdfunc)
    if df.is_empty():
        return pl.DataFrame()
    month = pl.col("MONTH").cast(pl.Int32) if has_month else pl.lit(1, dtype=pl.Int32)
    date = (
        pl.date(pl.col("YEAR").cast(pl.Int32), month, 1).cast(pl.Datetime(time_unit="us")).dt.replace_time_zone("UTC")
    )
    return _values(date, element, df)
