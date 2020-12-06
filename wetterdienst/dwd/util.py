from datetime import datetime
from typing import Union, Tuple, Optional

import dateparser
import pandas as pd
import pytz
from dateutil.relativedelta import relativedelta

from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameterSet,
    DWDObservationResolution,
    DWDObservationPeriod,
)
from wetterdienst.dwd.metadata.datetime import DatetimeFormat


def build_parameter_set_identifier(
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
    station_id: str,
    date_range_string: Optional[str] = None,
) -> str:
    """ Create parameter set identifier that is used for storage interactions """
    identifier = (
        f"{parameter_set.value}/{resolution.value}/" f"{period.value}/{station_id}"
    )

    if date_range_string:
        identifier = f"{identifier}/{date_range_string}"

    return identifier


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
    ).replace(tzinfo=pytz.UTC)


def mktimerange(
    resolution: DWDObservationResolution,
    date_from: Union[datetime, str],
    date_to: Union[datetime, str] = None,
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

    if resolution == DWDObservationResolution.ANNUAL:
        date_from = pd.to_datetime(date_from) + relativedelta(month=1, day=1)
        date_to = pd.to_datetime(date_to) + relativedelta(month=12, day=31)

    elif resolution == DWDObservationResolution.MONTHLY:
        date_from = pd.to_datetime(date_from) + relativedelta(day=1)
        date_to = pd.to_datetime(date_to) + relativedelta(day=31)

    else:
        raise NotImplementedError(
            "mktimerange only implemented for annual and monthly time ranges"
        )

    # TODO: make tz aware
    date_from = date_from.replace(tzinfo=pytz.UTC)
    date_to = date_to.replace(tzinfo=pytz.UTC)

    return date_from, date_to
