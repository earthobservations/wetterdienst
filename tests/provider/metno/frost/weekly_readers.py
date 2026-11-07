# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The rule that finds the weekly readers of the daily precipitation sum of Frost (GH-3820)."""

from __future__ import annotations

import polars as pl

# the rule of the issue: in a calendar year, a median gap between the readings of at least this many days, and at least
# this share of the rows `-1`
MEDIAN_GAP_DAYS = 4
MINUS_ONE_SHARE = 0.5


def unread_station_years(df: pl.DataFrame) -> set[tuple[str, int]]:
    """Give the (station, year) of the weekly readers in rows of the daily sum.

    ``df`` has `station_id`, `date`, `value` and `quality_flags`, a row of the daily sum as the reader hands it out (the
    `-1` as 0.0 or null, with `raw:-1` as the last flag). A station-year is the one of a weekly reader where the median
    gap between its readings (the rows that are no `-1`) is `MEDIAN_GAP_DAYS` or more and at least `MINUS_ONE_SHARE` of
    its rows are `-1`: a daily reader that has a dry spell reads every day or two, and a reader of one reading a month
    has no `-1`. A station-year with one reading has no gap and is not a weekly reader's.
    """
    minus_one = pl.col("quality_flags").fill_null("").str.contains(r"(^|,)raw:-1$")
    rows = df.with_columns(minus_one.alias("minus_one"), pl.col("date").dt.year().alias("year"))
    gaps = (
        rows.filter(~pl.col("minus_one"))
        .sort("station_id", "date")
        .group_by("station_id", "year", maintain_order=True)
        .agg(pl.col("date").diff().dt.total_days().median().alias("gap"))
    )
    counts = rows.group_by("station_id", "year").agg(pl.col("minus_one").mean().alias("share"))
    found = gaps.join(counts, on=["station_id", "year"]).filter(
        (pl.col("gap") >= MEDIAN_GAP_DAYS) & (pl.col("share") >= MINUS_ONE_SHARE)
    )
    return {(station, year) for station, year in found.select("station_id", "year").iter_rows()}
