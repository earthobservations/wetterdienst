# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsers for MIDAS Open's BADC-CSV files.

Every MIDAS Open file (station-metadata, capability, and per-station-year data files alike) shares
the BADC-CSV shape: a block of ``<field>,G,<value>...`` global-attribute header rows, a bare
``data`` line, a plain CSV table, and a trailing ``end data`` line. Confirmed against real files
downloaded from the archive during scoping (see ``fileindex.py``).
"""

from __future__ import annotations

import polars as pl

_EMPTY_STATIONS_SCHEMA = {
    "station_id": pl.String,
    "name": pl.String,
    "historic_county": pl.String,
    "station_file_name": pl.String,
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
    "quality": pl.Float64,
}


def _data_section(content: bytes) -> pl.DataFrame:
    """Split off the CSV table between the bare ``data`` and ``end data`` lines."""
    text = content.decode("utf-8")
    lines = text.splitlines()
    try:
        start = lines.index("data") + 1
    except ValueError:
        return pl.DataFrame()
    end = next((i for i in range(start, len(lines)) if lines[i].strip() == "end data"), len(lines))
    body = "\n".join(lines[start:end])
    if not body.strip():
        return pl.DataFrame()
    return pl.read_csv(body.encode("utf-8"), has_header=True, infer_schema_length=0, null_values=["NA"])


def parse_station_metadata(content: bytes) -> pl.DataFrame:
    """Parse a dataset's ``*_station-metadata.csv`` catalogue into one row per station.

    ``first_year``/``last_year`` mark the operational range *for this dataset*; a station may cover
    a different range in another MIDAS Open dataset.
    """
    df = _data_section(content)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_STATIONS_SCHEMA)
    return df.select(
        pl.col("src_id").cast(pl.String).alias("station_id"),
        pl.col("station_name").cast(pl.String).alias("name"),
        pl.col("historic_county").cast(pl.String),
        pl.col("station_file_name").cast(pl.String),
        pl.col("station_latitude").cast(pl.Float64, strict=False).alias("latitude"),
        pl.col("station_longitude").cast(pl.Float64, strict=False).alias("longitude"),
        pl.col("station_elevation").cast(pl.Float64, strict=False).alias("height"),
        pl.date(pl.col("first_year").cast(pl.Int32, strict=False), 1, 1)
        .cast(pl.Datetime(time_unit="us"))
        .dt.replace_time_zone("UTC")
        .alias("start_date"),
        pl.date(pl.col("last_year").cast(pl.Int32, strict=False), 12, 31)
        .cast(pl.Datetime(time_unit="us"))
        .dt.replace_time_zone("UTC")
        .alias("end_date"),
    )


def parse_values(
    content: bytes,
    time_column: str,
    columns: list[str],
    granularity: str,
    min_columns: frozenset[str] = frozenset(),
    scale: dict[str, float] | None = None,
    period_count_column: str | None = None,
) -> pl.DataFrame:
    """Parse a per-station-year data file into long ``(date, parameter, value, quality)`` rows.

    Every reading is truncated to ``granularity`` (``1d`` for daily datasets, ``1h`` for hourly)
    and aggregated to one value per ``(timestamp, parameter)``. This collapses MIDAS's *multiple
    report types per period* -- confirmed live: a daily station may transmit an overnight and a
    daytime 12-hour reading (``NCM``/``AWSDLY``) alongside a 24-hour one (``DLY3208``/``SYNOP``),
    all for the same calendar day. Taking ``max`` for max-type parameters and ``min`` for
    ``min_columns`` is idempotent over that duplication (``max(4.8, 5.4, 5.1)`` is exactly the
    24-hour value ``5.4``) and yields one clean daily extreme per station-day. Hourly datasets have
    a single reading per hour, so the aggregation is a no-op there.

    The calendar day is defined by the reading's ``ob_end_time`` date (a simple, documented choice;
    MIDAS's climatological day can run 09-09, so a day's min is the low of the night that ended that
    morning and its max the high of that afternoon).

    Args:
        content: the raw file bytes.
        time_column: the timestamp column for this dataset (``ob_date``, ``ob_time`` or
            ``ob_end_time`` -- it varies by dataset, see the per-dataset headers noted in
            ``metadata.py``).
        columns: the raw (``name_original``) value columns to extract -- kept as the raw MIDAS
            column name in the output ``parameter`` column, *not* humanized to the canonical name:
            ``model/values.py``'s ``_process_dataset()`` filters this column against the requested
            ``name_original`` values before humanizing it itself.
        granularity: polars truncation unit for the timestamp (``1d`` or ``1h``).
        min_columns: the subset of ``columns`` aggregated with ``min`` (the min-type parameters);
            all others use ``max``. The retained ``quality`` is the flag of the row that supplied
            the aggregated extreme.
        scale: optional ``{raw_column: factor}`` applied to a column's values to reach the unit
            declared in ``metadata.py``. Confirmed live: MIDAS ``visibility`` is stored in
            *decametres* (max ~7500 = 75 km at Heathrow), so it is scaled by 10 to metres -- there
            is no decametre unit in the shared unit converter to declare instead.
        period_count_column: the dataset's period-count column (``ob_day_cnt`` for daily rain), if
            it has one. Confirmed live: rain gauges are not always read every day -- a station read
            every 31 days posts its *31-day accumulated total* on the read date with this column set
            to 31, not 1. Rows where it isn't exactly 1 are dropped so a multi-day accumulation is
            never mistaken for a single-day value. (Not the same as temperature's ``ob_hour_count``,
            which is the 12/24-hour observation window, not a count of accumulated periods.)

    """
    df = _data_section(content)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    if period_count_column and period_count_column in df.columns:
        df = df.filter(pl.col(period_count_column).cast(pl.Float64, strict=False) == 1)
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    date = (
        pl.col(time_column)
        .str.to_datetime("%Y-%m-%d %H:%M:%S", time_unit="us")
        .dt.replace_time_zone("UTC")
        .dt.truncate(granularity)
    )
    scale = scale or {}
    frames = []
    for raw_column in columns:
        if raw_column not in df.columns:
            continue
        quality_column = f"{raw_column}_q"
        value = pl.col(raw_column).cast(pl.Float64, strict=False)
        if raw_column in scale:
            value = value * scale[raw_column]
        sub = df.select(
            date.alias("date"),
            value.alias("value"),
            (
                pl.col(quality_column).cast(pl.Float64, strict=False)
                if quality_column in df.columns
                else pl.lit(None, dtype=pl.Float64)
            ).alias("quality"),
        ).filter(pl.col("value").is_not_null())
        if sub.is_empty():
            continue
        if raw_column in min_columns:
            aggregated = sub.group_by("date").agg(
                pl.col("value").min().alias("value"),
                pl.col("quality").sort_by("value").first().alias("quality"),
            )
        else:
            aggregated = sub.group_by("date").agg(
                pl.col("value").max().alias("value"),
                pl.col("quality").sort_by("value").last().alias("quality"),
            )
        frames.append(
            aggregated.select(
                pl.col("date"),
                pl.lit(raw_column, dtype=pl.String).alias("parameter"),
                pl.col("value"),
                pl.col("quality"),
            ),
        )
    if not frames:
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    return pl.concat(frames)
