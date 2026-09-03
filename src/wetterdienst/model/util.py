# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Processing utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import InvalidTimeIntervalError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.datetime import mktimerange, parse_date_span, parse_date_window

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

    The date is read as the span it names, as it is by ``filter_by_date``, and the range covers it
    from first to last instant. A monthly or annual resolution then widens the range to whole
    months or years, which is what this adds over ``parse_date_window``.

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

        date_from_string, date_to_string = date.split("/")
        date_from, _ = parse_date_window(date_from_string)
        _, date_to = parse_date_window(date_to_string)

        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date_from, date_to)

    # Filter by specific date.
    else:
        date_from, date_to = parse_date_window(date)
        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date_from)

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

    Each of these names a span of time, and everything measured within it is kept: "2020-05" is
    the month of May, "2019" the year, and "2020-05-01" the day -- which for anything measured
    more often than daily is 24 hours of readings, not the one at midnight. An interval runs from
    the start of the span its first half names to the end of the span its second half names, so
    "2017-01/2019-12" ends with December 2019 rather than on its first day. A date carrying a time
    names one instant and is matched exactly.

    Args:
        df: DataFrame.
        date: Date string.

    Returns:
        Filtered DataFrame.

    """
    # TODO: datetimes should be aware of tz
    # Filter by date interval.
    if "/" in date:
        if date.count("/") >= 2:
            msg = "Invalid ISO 8601 time interval"
            raise InvalidTimeIntervalError(msg)

        date_from_string, date_to_string = date.split("/")
        date_from, _ = parse_date_span(date_from_string)
        date_to, date_to_end = parse_date_span(date_to_string)

        if date_to_end is None:
            # the end names one instant, so it is the last one kept
            return df.filter(pl.col("date").is_between(date_from, date_to, closed="both"))

        return df.filter(pl.col("date").is_between(date_from, date_to_end, closed="left"))

    # Filter by specific date.
    date_from, date_to_end = parse_date_span(date)

    if date_to_end is None:
        return df.filter(pl.col("date").eq(date_from))

    return df.filter(pl.col("date").is_between(date_from, date_to_end, closed="left"))
