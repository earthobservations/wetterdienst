# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a series of readings holds: how many values, of how many expected, from when to when (GH-4411, GH-4412).

The report of every answer that searches a series (`values` with row options, `statistics`): per station and series
the values `searched`, those `expected` in the steps of the resolution, the `gaps` inside its own span and the stamps
of its first and last value. One function (`searched_of`) for every surface, so that the two routes cannot count
differently. The module imports no polars until a frame is counted.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    import polars as pl

    from wetterdienst.metadata.resolution import Resolution


def latest_complete(resolution: Resolution, now: dt.datetime) -> dt.datetime | None:
    """Give the stamp of the last reading of a resolution that is complete at `now`, None where it has no fixed step.

    The reading of the day, the hour or the month that is still running does not exist yet: for daily data the stamp of
    yesterday, for hourly data that of the hour before this one, for monthly data the first of last month and for annual
    data the first of January of last year. What lies after it is the future, which a window may reach into and no
    series can be missing.
    """
    from wetterdienst.metadata.resolution import Resolution, reading_step  # noqa: PLC0415

    now = now.astimezone(dt.UTC)
    if resolution == Resolution.MONTHLY:
        year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        return dt.datetime(year, month, 1, tzinfo=dt.UTC)
    if resolution == Resolution.ANNUAL:
        return dt.datetime(now.year - 1, 1, 1, tzinfo=dt.UTC)
    step = reading_step(resolution)
    if step is None:
        return None
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)
    return now - (now - epoch) % step - step


def station_names(stations: pl.DataFrame) -> dict[str, str | None]:
    """Give the name of each station of a stations frame by its id, for the report; none where the frame has none."""
    if "name" not in stations.columns or "station_id" not in stations.columns:
        return {}
    rows = stations.select("station_id", "name").unique(subset="station_id", keep="first", maintain_order=True)
    return dict(rows.iter_rows())


def wide_value_columns(frame: pl.DataFrame) -> list[str]:
    """Name the columns of a wide frame that hold a parameter's values: not the keys, not the columns of the flags."""
    keys = {"station_id", "resolution", "dataset", "timestamp"}
    return [c for c in frame.columns if c not in keys and not c.endswith("_quality_flags")]


def _usual_step(resolution: Resolution) -> dt.timedelta | None:
    """Give how far apart the readings of a resolution usually are, for the comparison with a series' own step."""
    from wetterdienst.metadata.resolution import Resolution, reading_step  # noqa: PLC0415

    if resolution == Resolution.MONTHLY:
        return dt.timedelta(days=30)
    if resolution == Resolution.ANNUAL:
        return dt.timedelta(days=365)
    return reading_step(resolution)


def searched_of(
    frame: pl.DataFrame,
    window: tuple[dt.datetime | None, dt.datetime | None] = (None, None),
    now: dt.datetime | None = None,
    *,
    names: Mapping[str, str | None] | None = None,
    forecast: bool = False,
    stamped_on_the_day: bool = False,
) -> pl.DataFrame:
    """Count what a frame of values holds per station and series, before any selection: the report's raw rows.

    The frame is long (a row a value) or wide (a column a parameter, whose `parameter` is then the name of the column).
    `searched` counts the readings with a value; `first` and `last` are the stamps of the first and the last of them;
    `name` is the station's, from `names`. `expected` is what the request covers, counted in the steps of the
    resolution (calendar months and years for the monthly and annual data), null where the resolution has none or more
    readings were found than the step allows (a source with a finer step than its resolution says):

    - with a window, from its start to its end or to the last complete reading at `now`, whichever is earlier, so that
      a window that begins before the data, a series that ended before the window does, and a year that is not over
      are incomplete, as they are; never narrower than the values found. A window that begins after the last complete
      reading (a forecast's) has no past to be missing: the span of the values is counted. A series with no value is
      counted over the window too, so that it reads as all missing;
    - without one, from the first value to the last.

    `gaps` is what the series lacks inside its own span, from its first value to its last, whatever the window says.

    Both are null for a `forecast` and where the series is coarser than its resolution: almost none of its steps is as
    short as the resolution's (the 5 % quantile of the steps is above one and a half times it). A maximum of the last
    12 hours in an hourly dataset has a value every 12 hours, so 11 of 12 hours are no gap; a series that misses half
    its hours, or that was read at 7, 14 and 21 h for twenty years and then every hour, is not coarser: its gaps
    count. A series with no value has no gaps to count, and its `expected` is the window.
    """
    import polars as pl  # noqa: PLC0415

    from wetterdienst.metadata.resolution import Resolution, count_readings  # noqa: PLC0415

    now = now or dt.datetime.now(dt.UTC)
    keys = ["station_id", "resolution", "dataset", "parameter"]
    if "parameter" in frame.columns:
        valued = pl.col("value").is_not_null()
        grouped = frame.group_by(keys, maintain_order=True).agg(
            valued.sum().alias("searched"),
            pl.col("timestamp").filter(valued).min().alias("first"),
            pl.col("timestamp").filter(valued).max().alias("last"),
            pl.col("timestamp").filter(valued).sort().diff().quantile(0.05, interpolation="lower").alias("usual"),
        )
    else:
        parts = [
            frame.group_by(keys[:3], maintain_order=True)
            .agg(
                pl.col(column).is_not_null().sum().alias("searched"),
                pl.col("timestamp").filter(pl.col(column).is_not_null()).min().alias("first"),
                pl.col("timestamp").filter(pl.col(column).is_not_null()).max().alias("last"),
                pl.col("timestamp")
                .filter(pl.col(column).is_not_null())
                .sort()
                .diff()
                .quantile(0.05, interpolation="lower")
                .alias("usual"),
            )
            .with_columns(pl.lit(column).alias("parameter"))
            for column in wide_value_columns(frame)
        ]
        grouped = (
            pl.concat(parts).select([*keys, "searched", "first", "last", "usual"])
            if parts
            else pl.DataFrame(
                schema={
                    **dict.fromkeys(keys, pl.String),
                    "searched": pl.UInt32,
                    "first": pl.Datetime("us", "UTC"),
                    "last": pl.Datetime("us", "UTC"),
                    "usual": pl.Duration("us"),
                }
            )
        )
    known = {resolution.value for resolution in Resolution}
    start, end = window
    expected: list[int | None] = []
    gaps: list[int | None] = []
    for row in grouped.iter_rows(named=True):
        span = covered = None
        if row["resolution"] in known and not forecast:
            resolution = Resolution(row["resolution"])
            nominal = _usual_step(resolution)
            coarser = row["usual"] is not None and nominal is not None and row["usual"] > nominal * 1.5
            latest = latest_complete(resolution, now)
            has_window = start is not None and latest is not None and start <= latest
            if coarser:
                pass
            elif row["first"] is not None:
                span = count_readings(resolution, row["first"], row["last"], own_stamp=stamped_on_the_day)
                covered = span
                if has_window:
                    until = min(end or latest, latest)
                    covered = count_readings(
                        resolution,
                        min(start, row["first"]),
                        max(until, row["last"]),
                        own_stamp=stamped_on_the_day and row["first"] <= start,
                    )
            elif has_window:
                covered = count_readings(resolution, start, min(end or latest, latest))
            if span is not None and row["searched"] > span:
                span = covered = None
            if covered is not None and row["searched"] > covered:
                covered = None
        expected.append(covered)
        gaps.append(None if span is None else span - row["searched"])
    name = (
        pl.col("station_id").replace_strict(dict(names), default=None, return_dtype=pl.String)
        if names
        else pl.lit(None, pl.String)
    )
    return grouped.with_columns(
        name.alias("name"),
        pl.Series("expected", expected, dtype=pl.UInt32),
        pl.Series("gaps", gaps, dtype=pl.UInt32),
        pl.col("searched").cast(pl.UInt32),
    ).select(["station_id", "name", *keys[1:], "searched", "expected", "gaps", "first", "last"])
