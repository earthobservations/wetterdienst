# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import InvalidTimeIntervalError
from wetterdienst.metadata.columns import Columns
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
    if "/" in date:
        if date.count("/") >= 2:
            raise InvalidTimeIntervalError("Invalid ISO 8601 time interval")

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
    """
    Filter Pandas DataFrame by date or date interval.

    Accepts different kinds of date formats, like:

    - 2020-05-01
    - 2020-06-15T12
    - 2020-05
    - 2019
    - 2020-05-01/2020-05-05
    - 2017-01/2019-12
    - 2010/2020

    :param df:
    :param date:
    :return: Filtered DataFrame
    """

    # TODO: datetimes should be aware of tz
    # TODO: resolution is not necessarily available and ideally filtering does not
    #  depend on it
    # Filter by date interval.
    if "/" in date:
        if date.count("/") >= 2:
            raise InvalidTimeIntervalError("Invalid ISO 8601 time interval")

        date_from, date_to = date.split("/")
        date_from = parse_date(date_from)
        date_to = parse_date(date_to)

        expression = pl.col(Columns.DATE.value).is_between(date_from, date_to, closed="both")

        return df.filter(expression)

    # Filter by specific date.
    else:
        date = parse_date(date)

        expression = pl.col(Columns.DATE.value).eq(date)

        return df.filter(expression)
