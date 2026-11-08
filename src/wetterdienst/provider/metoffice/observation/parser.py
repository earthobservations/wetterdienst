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
    a different range in another MIDAS Open dataset. The position is the text of the file and the bounds are dates,
    which the core reads as numbers and as midnight UTC (``shape_stations_frame``). A catalogue without a row is a
    frame without a row.
    """
    df = _data_section(content)
    if df.is_empty():
        return pl.DataFrame()
    return df.select(
        pl.col("src_id").alias("station_id"),
        # the catalogue pads some names with a blank (`PORTLAND `), which a comparison of the name misses
        pl.col("station_name").str.strip_chars().alias("name"),
        pl.col("historic_county"),
        pl.col("station_file_name"),
        pl.col("station_latitude").alias("latitude"),
        pl.col("station_longitude").alias("longitude"),
        pl.col("station_elevation").alias("elevation"),
        pl.date(pl.col("first_year").cast(pl.Int32, strict=False), 1, 1).alias("start_timestamp"),
        pl.date(pl.col("last_year").cast(pl.Int32, strict=False), 12, 31).alias("end_timestamp"),
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
    scale: dict[str, float] | None = None,
    period_count_column: str | None = None,
) -> pl.DataFrame:
    """Parse a per-station-year data file into long ``(timestamp, parameter, value, quality_flags)`` rows.

    Every reading is truncated to ``granularity`` (``1d`` for daily datasets, ``1h`` for hourly)
    and aggregated to one value per ``(timestamp, parameter)``, the ``max``, which collapses the second report of a
    period (the files of the other datasets hold one reading per period, so it is a no-op there). The calendar day is
    the date of the reading's ``ob_end_time``.

    The daily temperature is not read here: its rows are 12 and 24 hour windows, which `parse_window_rows` and
    `climatological_days` turn into the 24 hours ending 09Z (GH-3137).

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
            value of one day or hour.

    Returns:
        The rows, or a frame without any when the file holds none: the core makes the empty long form of it.

    """
    df = _data_section(content, na_is_null=False)
    if df.is_empty():
        return pl.DataFrame()
    if period_count_column and period_count_column in df.columns:
        df = df.filter(pl.col(period_count_column).cast(pl.Float64, strict=False) == 1)
        if df.is_empty():
            return pl.DataFrame()
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
        # the `quality_flags` kept are those of the row that supplied the extreme
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
        return pl.DataFrame()
    return pl.concat(frames)


# The daily temperature file holds the extremes of 12 and 24 hour windows, each with the time its window ends
# (`ob_end_time`) and its length (`ob_hour_count`): the TD page says "For air temperatures, the observation period will
# usually be one of the following: 09-09Z, 09-21Z, 21-09Z"
# (https://artefacts.ceda.ac.uk/badc_datadocs/ukmo-midas/TD_Table.html). A station reports either the 24 hour window
# ending 09Z (09-09Z), or the two 12 hour halves of it (21-09Z, ending 09Z, and 09-21Z, ending 21Z), and a few both
# (GH-3137: 96 station-years of 2015 and 2025, 64 of them with only 12 hour rows, 26 with only 24 hour rows, 6 with
# both). The day is the 24 hours ending 09Z on the stamped day (09-09Z), the Met Office's usual climatological day:
# the 24 hour row ending 09Z on D, or, at a 12 hour station, the extreme of the 21-09Z row ending 09Z on D and the
# 09-21Z row ending 21Z on D-1. Where a day has a 24 hour row, that row is the day.
_WINDOW_24 = "24h"
_WINDOW_NIGHT = "night"  # 21-09Z, ending 09:00 on the stamped day
_WINDOW_DAY = "day"  # 09-21Z, ending 21:00 the day before the stamped day

_WINDOW_ROW_SCHEMA = {
    "end_time": pl.Datetime("us", "UTC"),
    "window": pl.String,
    "parameter": pl.String,
    "value": pl.Float64,
    "quality_flags": pl.String,
    "sentinel": pl.String,
}
_DAY_SCHEMA = {
    "timestamp": pl.Datetime("us", "UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
    "quality_flags": pl.String,
}
_LEFT_OUT_SCHEMA = {"parameter": pl.String, "timestamp": pl.Datetime("us", "UTC")}


def parse_window_rows(
    content: bytes,
    time_column: str,
    columns: list[str],
    hour_count_column: str = "ob_hour_count",
) -> pl.DataFrame:
    """Parse a daily temperature file into the rows of its windows: one for each ``(row, column)`` of a known window.

    A row is of the window ``24h`` (24 hours ending 09:00), ``night`` (12 hours ending 09:00) or ``day`` (12 hours
    ending 21:00) by ``ob_hour_count`` and the time of ``ob_end_time``; a row of any other window is no part of the
    09-09Z day and is not returned. ``value`` is null for an `NA` and a text that is no number, with its text as
    `sentinel` and as the `raw:` token of `quality_flags`, as `parse_values` does. `climatological_days` builds the
    days from the rows of all the years of a station.
    """
    df = _data_section(content, na_is_null=False)
    if df.is_empty() or hour_count_column not in df.columns:
        return pl.DataFrame(schema=_WINDOW_ROW_SCHEMA)
    end = (
        pl.col(time_column)
        .replace(_MISSING, None)
        .str.to_datetime("%Y-%m-%d %H:%M:%S", time_unit="us")
        .dt.replace_time_zone("UTC")
    )
    hours = pl.col(hour_count_column).str.strip_chars().cast(pl.Float64, strict=False)
    window = (
        pl.when((hours == 24) & (end.dt.hour() == 9) & (end.dt.minute() == 0))
        .then(pl.lit(_WINDOW_24))
        .when((hours == 12) & (end.dt.hour() == 9) & (end.dt.minute() == 0))
        .then(pl.lit(_WINDOW_NIGHT))
        .when((hours == 12) & (end.dt.hour() == 21) & (end.dt.minute() == 0))
        .then(pl.lit(_WINDOW_DAY))
    )
    frames = []
    for raw_column in columns:
        if raw_column not in df.columns:
            continue
        quality_column = f"{raw_column}_q"
        value, sentinel = null_sentinels(pl.col(raw_column), Sentinel(_MISSING), non_numeric=True)
        frames.append(
            df.select(
                end.alias("end_time"),
                window.alias("window"),
                pl.lit(raw_column, dtype=pl.String).alias("parameter"),
                value.alias("value"),
                join_quality_flags(
                    pl.col(quality_column).replace(_MISSING, None) if quality_column in df.columns else None,
                    raw=sentinel,
                ),
                sentinel.alias("sentinel"),
            ).filter(pl.col("window").is_not_null())
        )
    if not frames:
        return pl.DataFrame(schema=_WINDOW_ROW_SCHEMA)
    return pl.concat(frames).select(list(_WINDOW_ROW_SCHEMA))


def climatological_days(
    rows: pl.DataFrame,
    min_columns: frozenset[str],
    night_only: frozenset[str] = frozenset(),
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Build the 24 hours ending 09Z of each stamped day from the window rows of `parse_window_rows` (GH-3137).

    The day ``D`` of a column is, in this order:

    - the 24 hour row ending 09:00 on ``D``, as given (a day with both kinds of row is this row);
    - else the extreme of the ``night`` row ending 09:00 on ``D`` and the ``day`` row ending 21:00 on ``D-1``,
      the ``max`` or, for ``min_columns``, the ``min``, whose `quality_flags` are those of the half that gave it;
    - else, with only one of the halves, no value: the day is the second return, which the provider tells
      (`note_left_out`), and is never an answer of "no values".

    A column in ``night_only`` is never reported in the ``day`` half, so its 12 hour day needs the ``night`` row alone
    (the extreme of both where a ``day`` row has a value). A day whose rows are all an `NA` is the null with its text,
    as `parse_values` gives it.

    Returns:
        The days as ``(timestamp, parameter, value, quality_flags)``, and the days left out as ``(parameter,
        timestamp)``; each a frame without rows when there is none.

    """
    if rows.is_empty():
        return pl.DataFrame(schema=_DAY_SCHEMA), pl.DataFrame(schema=_LEFT_OUT_SCHEMA)
    day = pl.col("end_time").dt.truncate("1d") + pl.when(pl.col("window") == _WINDOW_DAY).then(
        pl.duration(days=1)
    ).otherwise(pl.duration(days=0))
    rows = rows.with_columns(day.alias("timestamp"))
    is_min = pl.col("parameter").is_in(sorted(min_columns))

    present = rows.filter(pl.col("value").is_not_null())
    # one row for each (parameter, day, window): two reports of a window (NCM beside AWSDLY) are one extreme
    per_window = present.group_by("parameter", "timestamp", "window").agg(
        pl.col("value").min().alias("low"),
        pl.col("value").max().alias("high"),
        pl.col("quality_flags").sort_by("value").first().alias("low_flags"),
        pl.col("quality_flags").sort_by("value").last().alias("high_flags"),
    )
    per_window = per_window.with_columns(
        pl.when(is_min).then(pl.col("low")).otherwise(pl.col("high")).alias("value"),
        pl.when(is_min).then(pl.col("low_flags")).otherwise(pl.col("high_flags")).alias("quality_flags"),
    ).select("parameter", "timestamp", "window", "value", "quality_flags")

    def of(window: str, column: str) -> pl.Expr:
        return pl.col(column).filter(pl.col("window") == window).first()

    wide = per_window.group_by("parameter", "timestamp").agg(
        of(_WINDOW_24, "value").alias("v24"),
        of(_WINDOW_24, "quality_flags").alias("f24"),
        of(_WINDOW_NIGHT, "value").alias("vn"),
        of(_WINDOW_NIGHT, "quality_flags").alias("fn"),
        of(_WINDOW_DAY, "value").alias("vd"),
        of(_WINDOW_DAY, "quality_flags").alias("fd"),
    )
    needs_day = ~pl.col("parameter").is_in(sorted(night_only))
    has_halves = pl.col("vn").is_not_null() & (pl.col("vd").is_not_null() | ~needs_day)
    halves_win = (
        pl.when(pl.col("vd").is_null())
        .then(pl.lit(value=True))
        .when(pl.col("vn").is_null())
        .then(pl.lit(value=False))
        .when(is_min)
        .then(pl.col("vn") <= pl.col("vd"))
        .otherwise(pl.col("vn") >= pl.col("vd"))
    )  # True: the night half gives the extreme
    wide = wide.with_columns(
        pl.when(pl.col("v24").is_not_null())
        .then(pl.col("v24"))
        .when(has_halves)
        .then(pl.when(halves_win).then(pl.col("vn")).otherwise(pl.col("vd")))
        .alias("value"),
        pl.when(pl.col("v24").is_not_null())
        .then(pl.col("f24"))
        .when(has_halves)
        .then(pl.when(halves_win).then(pl.col("fn")).otherwise(pl.col("fd")))
        .alias("quality_flags"),
    )
    days = wide.filter(pl.col("value").is_not_null()).select("timestamp", "parameter", "value", "quality_flags")
    left_out = wide.filter(pl.col("value").is_null()).select("parameter", "timestamp")

    # a day whose every report is an `NA` has no value to build, and keeps the null with its text; a report with
    # neither value nor `NA` is a blank, which is dropped
    absent = (
        rows.filter(pl.col("value").is_null() & pl.col("sentinel").is_not_null())
        .group_by("parameter", "timestamp")
        .agg(pl.col("value").first(), pl.col("quality_flags").first())
        .join(wide.select("parameter", "timestamp"), on=["parameter", "timestamp"], how="anti")
        .select("timestamp", "parameter", "value", "quality_flags")
    )
    days = pl.concat([days, absent.cast(days.schema)]).sort("parameter", "timestamp")
    return days, left_out.sort("parameter", "timestamp")
