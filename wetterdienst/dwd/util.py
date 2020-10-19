from datetime import datetime
from typing import Union, Tuple

import dateparser
import pandas as pd
from dateutil.relativedelta import relativedelta

from wetterdienst.dwd.observations.metadata import (
    DWDObsParameterSet,
    DWDObsTimeResolution,
    DWDObsPeriodType,
)
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations.metadata.column_types import (
    DATE_FIELDS_REGULAR,
    DATE_FIELDS_IRREGULAR,
    QUALITY_FIELDS,
    INTEGER_FIELDS,
    STRING_FIELDS,
)
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.dwd.observations.metadata.time_resolution import (
    TIME_RESOLUTION_TO_DATETIME_FORMAT_MAPPING,
)


def build_parameter_set_identifier(
    parameter_set: DWDObsParameterSet,
    time_resolution: DWDObsTimeResolution,
    period_type: DWDObsPeriodType,
    station_id: int,
) -> str:
    """ Create parameter set identifier that is used for storage interactions """
    return (
        f"{parameter_set.value}/{time_resolution.value}/"
        f"{period_type.value}/station_id_{str(station_id)}"
    )


def coerce_field_types(
    df: pd.DataFrame, time_resolution: DWDObsTimeResolution
) -> pd.DataFrame:
    """
    A function used to create a unique dtype mapping for a given list of column names.
    This function is needed as we want to ensure the expected dtypes of the returned
    DataFrame as well as for mapping data after reading it from a stored .h5 file. This
    is required as we want to store the data in this file with the same format which is
    a string, thus after reading data back in the dtypes have to be matched.

    Args:
        df: the station_data gathered in a pandas.DataFrame
        time_resolution: time resolution of the data as enumeration
    Return:
         station data with converted dtypes
    """

    for column in df.columns:
        # Station ids are handled separately as they are expected to not have any nans
        if column == DWDMetaColumns.STATION_ID.value:
            df[column] = df[column].astype(int)
        elif column in DATE_FIELDS_REGULAR:
            df[column] = pd.to_datetime(
                df[column],
                format=TIME_RESOLUTION_TO_DATETIME_FORMAT_MAPPING[time_resolution],
            )
        elif column in DATE_FIELDS_IRREGULAR:
            df[column] = pd.to_datetime(
                df[column], format=DatetimeFormat.YMDH_COLUMN_M.value
            )
        elif column in QUALITY_FIELDS or column in INTEGER_FIELDS:
            df[column] = pd.to_numeric(df[column], errors="coerce").astype(
                pd.Int64Dtype()
            )
        elif column in STRING_FIELDS:
            df[column] = df[column].astype(pd.StringDtype())
        else:
            df[column] = df[column].astype(float)

    return df


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
    time_resolution: DWDObsTimeResolution,
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

    if time_resolution == DWDObsTimeResolution.ANNUAL:
        date_from = pd.to_datetime(date_from) + relativedelta(month=1, day=1)
        date_to = pd.to_datetime(date_to) + relativedelta(month=12, day=31)

    elif time_resolution == DWDObsTimeResolution.MONTHLY:
        date_from = pd.to_datetime(date_from) + relativedelta(day=1)
        date_to = pd.to_datetime(date_to) + relativedelta(day=31)

    else:
        raise NotImplementedError(
            "mktimerange only implemented for annual and monthly time ranges"
        )

    return date_from, date_to
