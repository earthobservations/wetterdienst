# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime
from typing import Optional, Tuple

import dateutil
import pandas as pd
import pytz

from wetterdienst.exceptions import InvalidTimeInterval
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.datetime import mktimerange


def create_date_range(date: str, resolution: Resolution) -> Tuple[Optional[datetime], Optional[datetime]]:
    date_from, date_to = None, None

    if "/" in date:
        if date.count("/") >= 2:
            raise InvalidTimeInterval("Invalid ISO 8601 time interval")

        date_from, date_to = date.split("/")
        date_from = dateutil.parser.isoparse(date_from)
        if not date_from.tzinfo:
            date_from = date_from.replace(tzinfo=pytz.UTC)

        date_to = dateutil.parser.isoparse(date_to)
        if not date_to.tzinfo:
            date_to = date_to.replace(tzinfo=pytz.UTC)

        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date_from, date_to)

    # Filter by specific date.
    else:
        date = dateutil.parser.isoparse(date)
        if not date.tzinfo:
            date = date.replace(tzinfo=pytz.UTC)

        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date)

    return date_from, date_to


def filter_by_date_and_resolution(df: pd.DataFrame, date: str, resolution: Resolution) -> pd.DataFrame:
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
    :param resolution:
    :return: Filtered DataFrame
    """

    # TODO: datetimes should be aware of tz
    # TODO: resolution is not necessarily available and ideally filtering does not
    #  depend on it
    # Filter by date interval.
    if "/" in date:
        if date.count("/") >= 2:
            raise InvalidTimeInterval("Invalid ISO 8601 time interval")

        date_from, date_to = date.split("/")
        date_from = dateutil.parser.isoparse(date_from)
        if not date_from.tzinfo:
            date_from = date_from.replace(tzinfo=pytz.UTC)

        date_to = dateutil.parser.isoparse(date_to)
        if not date_to.tzinfo:
            date_to = date_to.replace(tzinfo=pytz.UTC)

        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date_from, date_to)
            expression = (date_from <= df[Columns.FROM_DATE.value]) & (df[Columns.TO_DATE.value] <= date_to)
        else:
            expression = (date_from <= df[Columns.DATE.value]) & (df[Columns.DATE.value] <= date_to)
        return df[expression]

    # Filter by specific date.
    else:
        date = dateutil.parser.isoparse(date)
        if not date.tzinfo:
            date = date.replace(tzinfo=pytz.UTC)

        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date)
            expression = (date_from <= df[Columns.FROM_DATE.value]) & (df[Columns.TO_DATE.value] <= date_to)
        else:
            expression = date == df[Columns.DATE.value]
        return df[expression]
