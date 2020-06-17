""" date time handling functions """
from datetime import datetime
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
