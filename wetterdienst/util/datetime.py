# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime, timedelta
from typing import Tuple

from dateutil.relativedelta import relativedelta

from wetterdienst.metadata.resolution import Resolution


def round_minutes(timestamp: datetime, step: int):
    """
    Align timestamp to the given minute mark before tm.
    - https://stackoverflow.com/a/3464000

    :param timestamp:
    :param step:
    :return:
    """

    timestamp = timestamp.replace(second=0, microsecond=0)
    change = timedelta(minutes=timestamp.minute % step)
    return timestamp - change


def raster_minutes(timestamp: datetime, value: int):
    """
    Align timestamp to the most recent minute mark.

    - https://stackoverflow.com/a/55013608
    - https://stackoverflow.com/a/60709050

    :param timestamp:
    :param value:
    :return:
    """

    timestamp = timestamp.replace(second=0, microsecond=0)

    if timestamp.minute < value:
        timestamp = timestamp - timedelta(hours=1)

    return timestamp.replace(minute=value)


def mktimerange(
    resolution: Resolution,
    date_from: datetime,
    date_to: datetime = None,
) -> Tuple[datetime, datetime]:
    """
    Compute appropriate time ranges for monthly and annual time resolutions.
    This takes into account to properly floor/ceil the date_from/date_to
    values to respective "begin of month/year" and "end of month/year" values.

    Args:
        resolution: time resolution as enumeration
        date_from: datetime string or object
        date_to: datetime string or object

    Returns:
        Tuple of two Timestamps: "date_from" and "date_to"
    """

    if date_to is None:
        date_to = date_from

    if resolution == Resolution.ANNUAL:
        date_from = date_from + relativedelta(month=1, day=1)
        date_to = date_to + relativedelta(month=12, day=31)

    elif resolution == Resolution.MONTHLY:
        date_from = date_from + relativedelta(day=1)
        date_to = date_to + relativedelta(day=31)

    else:
        raise NotImplementedError("mktimerange only implemented for annual and monthly time ranges")

    return date_from, date_to
