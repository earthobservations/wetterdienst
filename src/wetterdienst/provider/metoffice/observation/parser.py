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

from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels

_EMPTY_STATIONS_SCHEMA = {
    "station_id": pl.String,
    "name": pl.String,
    "historic_county": pl.String,
    "station_file_name": pl.String,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "elevation": pl.Float64,
    "start_timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
    "end_timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
}

_EMPTY_VALUES_SCHEMA = {
    "timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
    "quality_flags": pl.String,
}


# how the files write a value they do not have
_MISSING = "NA"

# a wind direction of 0 is no bearing but a calm: the WH page says "zero values in both wind speec[sic] and wind
# direction fields indicate that there was no wind blowing at the time of observation", and north is written 360
# (https://artefacts.ceda.ac.uk/badc_datadocs/ukmo-midas/WH_Table.html). Over 75 station-years of 2022 (25 stations of
# each of hourly weather, mean wind and daily temperature), the direction of the hourly weather was 0 in 1,574 of
# 137,423 readings, all but one at a speed of 0, of the mean wind 381 of 207,174 (all at a speed of 0) and of the
# direction of the gust 97 of 207,639 (a gust speed of 0 in 55, none in 42), where 2,210, 3,024 and 2,630 were 360
# (GH-3135). One rule for every provider: the 0 is null only beside a speed of 0, and the speed that is judged is the
# one of the same reading: the gust direction against the gust speed `max_gust_speed`, not the mean speed (the 42
# gusts without a speed have no mean speed either, so a 0 beside no speed stays, as a 0 beside a speed above 0 does)
_CALM_SPEED_COLUMNS = {
    "wind_direction": "wind_speed",
    "mean_wind_dir": "mean_wind_speed",
    "max_gust_dir": "max_gust_speed",
}
_CALM = "0"

# the total cloud amount is in oktas, and a 9 is the sky obscured, no amount (9 was 1.125 once converted): 397 of
# 120,393 readings in the 25 hourly weather station-years of 2022, at a median visibility of 100 m and at most 1.6 km.
# The documentation of the GL and WH tables names the unit but no code (GH-3135)
_SKY_OBSCURED_COLUMNS = frozenset({"cld_ttl_amt_id"})
_SKY_OBSCURED = "9"


def _data_section(content: bytes, *, na_is_null: bool = True) -> pl.DataFrame:
    """Split off the CSV table between the bare ``data`` and ``end data`` lines.

    ``NA`` is null unless ``na_is_null`` is off, which leaves it as the text it is for a reader that keeps it.
    """
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
    return pl.read_csv(
        body.encode("utf-8"), has_header=True, infer_schema_length=0, null_values=[_MISSING] if na_is_null else None
    )


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
        # the catalogue pads some names with a blank (`PORTLAND `), which a comparison of the name misses
        pl.col("station_name").cast(pl.String).str.strip_chars().alias("name"),
        pl.col("historic_county").cast(pl.String),
        pl.col("station_file_name").cast(pl.String),
        pl.col("station_latitude").cast(pl.Float64, strict=False).alias("latitude"),
        pl.col("station_longitude").cast(pl.Float64, strict=False).alias("longitude"),
        pl.col("station_elevation").cast(pl.Float64, strict=False).alias("elevation"),
        pl.date(pl.col("first_year").cast(pl.Int32, strict=False), 1, 1)
        .cast(pl.Datetime(time_unit="us"))
        .dt.replace_time_zone("UTC")
        .alias("start_timestamp"),
        pl.date(pl.col("last_year").cast(pl.Int32, strict=False), 12, 31)
        .cast(pl.Datetime(time_unit="us"))
        .dt.replace_time_zone("UTC")
        .alias("end_timestamp"),
    )


def _code_sentinels(raw_column: str, columns: list[str]) -> list[Sentinel]:
    """Give the codes of a column that are no reading: a 0 of a direction beside a speed of 0, the 9 of the sky."""
    codes = []
    speed = _CALM_SPEED_COLUMNS.get(raw_column)
    if speed in columns:
        calm = pl.col(speed).str.strip_chars().cast(pl.Float64, strict=False) == 0
        codes.append(Sentinel(_CALM, where=calm.fill_null(value=False)))
    if raw_column in _SKY_OBSCURED_COLUMNS:
        codes.append(Sentinel(_SKY_OBSCURED))
    return codes


def parse_values(
    content: bytes,
    time_column: str,
    columns: list[str],
    granularity: str,
    min_columns: frozenset[str] = frozenset(),
    scale: dict[str, float] | None = None,
    period_count_column: str | None = None,
) -> pl.DataFrame:
    """Parse a per-station-year data file into long ``(timestamp, parameter, value, quality_flags)`` rows.

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
            all others use ``max``. The retained ``quality_flags`` is the flag of the row that supplied
            the aggregated extreme.
        scale: optional ``{raw_column: factor}`` applied to a column's values to reach the unit
            declared in ``metadata.py``. Confirmed live: MIDAS ``visibility`` is stored in
            *decametres* (max ~7500 = 75 km at Heathrow), so it is scaled by 10 to metres -- there
            is no decametre unit in the shared unit converter to declare instead.
        period_count_column: the dataset's period-count column (``ob_day_cnt`` for daily rain,
            ``ob_hour_count`` for the hourly rain, radiation and mean wind), if it has one. Confirmed
            live: rain gauges are not always read every day -- a station read every 31 days posts its
            *31-day accumulated total* on the read date with this column set to 31, not 1 -- and the
            hourly rain and radiation files hold 12 and 24 hour totals beside the hourly readings.
            Rows where it isn't exactly 1 are dropped so an accumulation is never mistaken for the
            value of one day or hour. (Not applied to the daily temperature, whose ``ob_hour_count``
            of 12 or 24 is the window of the extreme, which is no accumulation.)

    """
    df = _data_section(content, na_is_null=False)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    if period_count_column and period_count_column in df.columns:
        df = df.filter(pl.col(period_count_column).cast(pl.Float64, strict=False) == 1)
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    date = (
        pl.col(time_column)
        .replace(_MISSING, None)
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
        # an `NA`, and a text that is no number, is null with its text kept as `raw:` (GH-2759)
        # (a calm direction and a sky obscured are a 0 and a 9 that are no reading of their column, GH-3135)
        value, sentinel = null_sentinels(
            pl.col(raw_column), Sentinel(_MISSING), *_code_sentinels(raw_column, df.columns), non_numeric=True
        )
        if raw_column in scale:
            value = value * scale[raw_column]
        sub = df.select(
            date.alias("timestamp"),
            value.alias("value"),
            # MESQL as the text the file writes, not as a number; the file's `NA` is no flag
            join_quality_flags(
                pl.col(quality_column).replace(_MISSING, None) if quality_column in df.columns else None,
                raw=sentinel,
            ),
            sentinel.alias("sentinel"),
        )
        present = sub.filter(pl.col("value").is_not_null())
        if raw_column in min_columns:
            aggregated = present.group_by("timestamp").agg(
                pl.col("value").min().alias("value"),
                pl.col("quality_flags").sort_by("value").first(),
            )
        else:
            aggregated = present.group_by("timestamp").agg(
                pl.col("value").max().alias("value"),
                pl.col("quality_flags").sort_by("value").last(),
            )
        # a day whose every report is an `NA` has no value to aggregate, and keeps the null with its text; a report
        # with neither value nor `NA` is a blank, which is dropped as before
        absent = (
            sub.filter(pl.col("value").is_null() & pl.col("sentinel").is_not_null())
            .group_by("timestamp")
            .agg(pl.col("value").first(), pl.col("quality_flags").first())
            .join(aggregated.select("timestamp"), on="timestamp", how="anti")
        )
        aggregated = pl.concat([aggregated, absent])
        if aggregated.is_empty():
            continue
        frames.append(
            aggregated.select(
                pl.col("timestamp"),
                pl.lit(raw_column, dtype=pl.String).alias("parameter"),
                pl.col("value"),
                pl.col("quality_flags"),
            ),
        )
    if not frames:
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    return pl.concat(frames)
