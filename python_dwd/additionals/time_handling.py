""" date time handling functions """
from datetime import datetime
from dateparser import parse as parsedate
from typing import Optional, Tuple, Union
import pandas as pd
from pandas import Timestamp
from pandas.tseries.offsets import YearBegin, YearEnd, MonthBegin, MonthEnd

from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def parse_date(date_string: str) -> Optional[Timestamp]:
    """
    A function used to parse a date from a string.

    Args:
        date_string: the string of the date
    Returns:
        Timestamp of the string or None
    """
    date = Timestamp(date_string)

    if pd.isna(date):
        return None

    return date


def parse_datetime(date_string: str) -> datetime:
    return parsedate(date_string, date_formats=['%Y-%m-%dT%H'])


def mktimerange(time_resolution: TimeResolution,
                date_from: Union[datetime, str],
                date_to: Union[datetime, str] = None) -> Tuple[Timestamp, Timestamp]:
    """
    Compute appropriate time ranges for monthly and annual time resolutions.
    This takes into account to properly floor/ceil the date_from/date_to
    values to respective "begin of month/year" and "end of month/year" values.

    Args:
        time_resolution: time resolution as enumeration
        date_from: datetime string or object
        date_to: datetime string or object

    Returns:
        Tuple of two Timestamps: "date_from" and "date_to"
    """

    if date_to is None:
        date_to = date_from

    if time_resolution == TimeResolution.ANNUAL:
        date_from = pd.to_datetime(date_from) - YearBegin(1)
        date_to = pd.to_datetime(date_to) + YearEnd(1)

    elif time_resolution == TimeResolution.MONTHLY:
        date_from = pd.to_datetime(date_from) - MonthBegin(1)
        date_to = pd.to_datetime(date_to) + MonthEnd(1)

    else:
        raise NotImplementedError("mktimerange only implemented for annual and monthly time ranges")

    return date_from, date_to


def convert_datetime_hourly(date_string: str) -> datetime:
    """
    Data from the hourly time resolution has a timestamp format
    of e.g. "2018121300". So, let's parse it using the custom
    timestamp pattern %Y%m%d%H.

    There's also an anomaly for hourly/solar observations,
    where the timestamp seems to also include minutes,
    like "2001010100:03" or "2001011508:09". For them,
    we consider it to be safe to drop the minute part
    right away by flooring it to "00".

    :param date_string:
    :return:
    """

    pattern = '%Y%m%d%H'

    if ':' in date_string:
        pattern = '%Y%m%d%H:%M'

    return pd.to_datetime(date_string, format=pattern).replace(minute=00)
