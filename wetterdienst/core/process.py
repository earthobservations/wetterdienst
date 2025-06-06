# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Processing utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import InvalidTimeIntervalError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.datetime import mktimerange, parse_date

if TYPE_CHECKING:
    import datetime as dt

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()


def create_date_range(date: str, resolution: Resolution) -> tuple[dt.datetime | None, dt.datetime | None]:
    """Create date range from date string and resolution.

    Args:
        date: Date string.
        resolution: Resolution.

    Returns:
        Tuple of date range.

    """
    if "/" in date:
        if date.count("/") >= 2:
            msg = "Invalid ISO 8601 time interval"
            raise InvalidTimeIntervalError(msg)

        date_from, date_to = date.split("/")
        date_from = parse_date(date_from)
        date_to = parse_date(date_to)

        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date_from, date_to)

    # Filter by specific date.
    else:
        date = parse_date(date)
        date_from, date_to = date, date
        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date)

    return date_from, date_to


def filter_by_date(df: pl.DataFrame, date: str) -> pl.DataFrame:
    """Filter DataFrame by date or date interval.

    Accepts different kinds of date formats, like:

    - 2020-05-01
    - 2020-06-15T12
    - 2020-05
    - 2019
    - 2020-05-01/2020-05-05
    - 2017-01/2019-12
    - 2010/2020

    Args:
        df: DataFrame.
        date: Date string.

    Returns:
        Filtered DataFrame.

    """
    # TODO: datetimes should be aware of tz
    # TODO: resolution is not necessarily available and ideally filtering does not
    #  depend on it
    # Filter by date interval.
    if "/" in date:
        if date.count("/") >= 2:
            msg = "Invalid ISO 8601 time interval"
            raise InvalidTimeIntervalError(msg)

        date_from, date_to = date.split("/")
        date_from = parse_date(date_from)
        date_to = parse_date(date_to)

        expression = pl.col("date").is_between(date_from, date_to, closed="both")

        return df.filter(expression)

    # Filter by specific date.
    date = parse_date(date)

    expression = pl.col("date").eq(date)

    return df.filter(expression)
