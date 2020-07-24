""" date time handling functions """
from datetime import datetime
import dateparser
from typing import Tuple, Union
import pandas as pd
from dateutil.relativedelta import relativedelta

from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


def parse_datetime(date_string: str) -> datetime:
    """
    Function used mostly for client to parse given date

    Args:
        date_string: the given date as string

    Returns:
        any kind of datetime
    """
    # Tries out any given format of DatetimeFormat enumeration
    return dateparser.parse(
        date_string, date_formats=[dt_format.value for dt_format in DatetimeFormat]
    )


def mktimerange(
    time_resolution: TimeResolution,
    date_from: Union[datetime, str],
    date_to: Union[datetime, str] = None,
) -> Tuple[datetime, datetime]:
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
        date_from = pd.to_datetime(date_from) + relativedelta(month=1, day=1)
        date_to = pd.to_datetime(date_to) + relativedelta(month=12, day=31)

    elif time_resolution == TimeResolution.MONTHLY:
        date_from = pd.to_datetime(date_from) + relativedelta(day=1)
        date_to = pd.to_datetime(date_to) + relativedelta(day=31)

    else:
        raise NotImplementedError(
            "mktimerange only implemented for annual and monthly time ranges"
        )

    return date_from, date_to
