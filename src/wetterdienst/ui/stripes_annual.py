# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The annual values of climate stripes for a source that publishes days only: NOAA GHCN daily (GH-4222).

DWD publishes annual values, which the stripes read as they are. GHCN-Daily has daily values only, so the year is built
from the days, by the rules of the WMO Guidelines on the Calculation of Climate Normals (WMO-No. 1203):

- Temperature: a month counts with at most `MAX_MISSING_DAYS` days missing and at most `MAX_MISSING_IN_A_ROW` of them in
  a row. A day's mean is the source's own TAVG where it gives one, else (TMAX + TMIN) / 2, and a day with neither has
  no mean and is missing. The month's mean is the mean of the days' means, and a year with all 12 months counting is the
  mean of the 12 monthly means (each month weighs the same, whatever its length).
- Precipitation: a month counts only when complete, every one of its days has a value. A year with all 12 months
  counting is the sum of the 12 monthly sums.
- A year that fails is a gap, as a year DWD has no value for is, and is never filled.

A day the source has no row for, or whose value is null, is missing: that is what a station that did not report looks
like in the daily files. A value whose quality flag names a check it failed (`leave_out_failed`) is no value either, as
the readme of GHCN-Daily asks for.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal, cast

import polars as pl

#: a month counts for the temperature with no more than this many days missing, ...
MAX_MISSING_DAYS = 10
#: ... and no more than this many of them in a row
MAX_MISSING_IN_A_ROW = 4
#: a year counts with all of its months
MONTHS = 12
#: the decimals of an annual value: the source's tenths, averaged
DECIMALS = 3

TEMPERATURE_MEAN = "temperature_air_mean_2m"
TEMPERATURE_MAX = "temperature_air_max_2m"
TEMPERATURE_MIN = "temperature_air_min_2m"
PRECIPITATION = "precipitation_amount"

#: a plain code in `quality_flags` (the source's own quality flag, one that is no `kind:code` token) is a check the
#: value failed: GHCN-Daily writes a letter only where one failed, and blank where it passed all
_FAILED_CHECK = r"(^|,)[^,:]+(,|$)"


def leave_out_failed(df: pl.DataFrame) -> pl.DataFrame:
    """Null the value of every reading whose quality flag names a check it failed."""
    if "quality_flags" not in df.columns:
        return df
    failed = pl.col("quality_flags").str.contains(_FAILED_CHECK).fill_null(value=False)
    return df.with_columns(pl.when(failed).then(None).otherwise(pl.col("value")).alias("value"))


def annual_note(kind: Literal["temperature", "precipitation"]) -> str:
    """Say in one ASCII sentence how the annual values were calculated from the daily ones, for the note."""
    if kind == "temperature":
        rule = (
            f"a month counts with at most {MAX_MISSING_DAYS} days missing and at most {MAX_MISSING_IN_A_ROW} in a row, "
            "its mean is the mean of the days' means (the source's TAVG, else (TMAX + TMIN) / 2), and a year with "
            "all 12 months counting is the mean of its monthly means"
        )
    else:
        rule = (
            "a month counts only when complete, and a year with all 12 months counting is the sum of its monthly sums"
        )
    return (
        f"The annual values were calculated from the provider's daily values by the rules of WMO-No. 1203: {rule}; a "
        "year that fails is a gap."
    )


def _daily_values(daily: pl.DataFrame, kind: Literal["temperature", "precipitation"]) -> pl.DataFrame:
    """Give one value per day: `date` and `value`, null for a day the source has no usable value of."""
    value = pl.col("value")
    finite = pl.when(value.is_finite()).then(value).alias("value")
    frame = daily.select(pl.col("timestamp").dt.date().alias("date"), "parameter", finite)
    if kind == "precipitation":
        return frame.filter(pl.col("parameter") == PRECIPITATION).group_by("date").agg(pl.col("value").first())
    wide = frame.pivot(on="parameter", index="date", values="value", aggregate_function="first")
    for parameter in (TEMPERATURE_MEAN, TEMPERATURE_MAX, TEMPERATURE_MIN):
        if parameter not in wide.columns:
            wide = wide.with_columns(pl.lit(None, dtype=pl.Float64).alias(parameter))
    return wide.select(
        "date",
        pl.coalesce(TEMPERATURE_MEAN, (pl.col(TEMPERATURE_MAX) + pl.col(TEMPERATURE_MIN)) / 2).alias("value"),
    )


def annual_from_daily(daily: pl.DataFrame, kind: Literal["temperature", "precipitation"]) -> pl.DataFrame:
    """Build the annual values of one station from its daily values, by the WMO rules of this module.

    `daily` is the long frame of the station's values: `timestamp` (the day, at 00:00), `parameter` (the canonical
    names of `TEMPERATURE_MEAN`, `TEMPERATURE_MAX` and `TEMPERATURE_MIN`, or `PRECIPITATION`) and `value`, in the unit
    wanted: the mean of a unit that is a linear change of another is that unit's, so the conversion can come first.

    Returns the frame of `timestamp` (1 January 00:00 UTC of the year) and `value` of every year from the first to the
    last the daily values have a row in, the value null where the year fails: the frame DWD's annual values come in.
    """
    schema = pl.Schema({"timestamp": pl.Datetime("us", "UTC"), "value": pl.Float64})
    if daily.is_empty():
        return pl.DataFrame(schema=schema)
    # the years run from the first day with a usable value to the last: a station that has rows of other parameters only
    # has no years
    days = _daily_values(daily, kind).filter(pl.col("value").is_not_null())
    if days.is_empty():
        return pl.DataFrame(schema=schema)
    dates = days.get_column("date")
    first_year, last_year = dates.dt.year().min(), dates.dt.year().max()
    # every day of every year between, so that a day without a row is a missing one, and a year not complete in the
    # record (the first, the one still running) fails
    calendar = pl.date_range(
        dt.date(cast("int", first_year), 1, 1), dt.date(cast("int", last_year), 12, 31), "1d", eager=True
    ).alias("date")
    frame = (
        calendar.to_frame()
        .join(days, on="date", how="left")
        .with_columns(
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.month().alias("month"),
            pl.col("value").is_null().alias("missing"),
        )
        .sort("date")
    )
    # runs of missing days, numbered over the whole frame and counted per month: a run over the turn of a month is
    # two, one in each
    runs = (
        frame.with_columns(pl.col("missing").rle_id().alias("run"))
        .filter(pl.col("missing"))
        .group_by("year", "month", "run")
        .len()
        .group_by("year", "month")
        .agg(pl.col("len").max().alias("longest_run"))
    )
    months = (
        frame.group_by("year", "month")
        .agg(
            pl.col("missing").sum().alias("missing_days"),
            pl.col("value").mean().alias("mean"),
            pl.col("value").sum().alias("total"),
        )
        .join(runs, on=["year", "month"], how="left")
        .with_columns(pl.col("longest_run").fill_null(0))
    )
    if kind == "temperature":
        counts = (pl.col("missing_days") <= MAX_MISSING_DAYS) & (pl.col("longest_run") <= MAX_MISSING_IN_A_ROW)
        months = months.with_columns(counts.alias("counts"), pl.col("mean").alias("monthly"))
        annual = pl.col("monthly").filter(pl.col("counts")).mean()
    else:
        months = months.with_columns((pl.col("missing_days") == 0).alias("counts"), pl.col("total").alias("monthly"))
        annual = pl.col("monthly").filter(pl.col("counts")).sum()
    years = (
        months.group_by("year")
        .agg(pl.col("counts").sum().alias("months"), annual.alias("annual"))
        .sort("year")
        .select(
            pl.datetime(pl.col("year"), 1, 1, time_zone="UTC", time_unit="us").alias("timestamp"),
            pl.when(pl.col("months") == MONTHS).then(pl.col("annual").round(DECIMALS)).alias("value"),
        )
    )
    return years.cast(schema)
