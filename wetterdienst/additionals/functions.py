"""
A set of more general functions used for the organization
"""
from functools import lru_cache
from typing import Tuple, Optional, Union, Callable

import pandas as pd

from wetterdienst.constants.parameter_mapping import TIME_RESOLUTION_PARAMETER_MAPPING
from wetterdienst.constants.time_resolution_mapping import (
    TIME_RESOLUTION_TO_DATETIME_FORMAT_MAPPING,
)
from wetterdienst.enumerations.column_names_enumeration import (
    DWDMetaColumns,
    DWDDataColumns,
    DWDOrigDataColumns,
)
from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.exceptions import InvalidParameter

FILE_2_PARAMETER = {
    TimeResolution.MINUTE_1: {"nieder": Parameter.PRECIPITATION},
    TimeResolution.MINUTE_10: {
        "nieder": Parameter.PRECIPITATION,
        "tu": Parameter.TEMPERATURE_AIR,
        "extrema_temp": Parameter.TEMPERATURE_EXTREME,
        "tx": Parameter.TEMPERATURE_EXTREME,
        "fx": Parameter.WIND_EXTREME,
        "rr": Parameter.PRECIPITATION,
        "extrema_wind": Parameter.WIND_EXTREME,
        "solar": Parameter.SOLAR,
        "ff": Parameter.WIND,
        "wind": Parameter.WIND,
    },
    TimeResolution.HOURLY: {
        "tu": Parameter.TEMPERATURE_AIR,
        "cs": Parameter.CLOUD_TYPE,
        "n": Parameter.CLOUDINESS,
        "td": Parameter.DEW_POINT,
        "rr": Parameter.PRECIPITATION,
        "p0": Parameter.PRESSURE,
        "eb": Parameter.TEMPERATURE_SOIL,
        "st": Parameter.SOLAR,
        "sd": Parameter.SUNSHINE_DURATION,
        "vv": Parameter.VISIBILITY,
        "ff": Parameter.WIND,
        "f": Parameter.WIND_SYNOPTIC,
    },
    TimeResolution.SUBDAILY: {
        "tu": Parameter.TEMPERATURE_AIR,
        "n": Parameter.CLOUDINESS,
        "tf": Parameter.MOISTURE,
        "pp": Parameter.PRESSURE,
        "ek": Parameter.SOIL,
        "vk": Parameter.VISIBILITY,
        "fk": Parameter.WIND,
    },
    TimeResolution.DAILY: {
        "kl": Parameter.CLIMATE_SUMMARY,
        "rr": Parameter.PRECIPITATION_MORE,
        "eb": Parameter.TEMPERATURE_SOIL,
        "st": Parameter.SOLAR,
        "wa": Parameter.WATER_EQUIVALENT,
        "wetter": Parameter.WEATHER_PHENOMENA,
    },
    TimeResolution.MONTHLY: {
        "kl": Parameter.CLIMATE_SUMMARY,
        "rr": Parameter.PRECIPITATION_MORE,
        "wetter": Parameter.WEATHER_PHENOMENA,
    },
    TimeResolution.ANNUAL: {
        "kl": Parameter.CLIMATE_SUMMARY,
        "rr": Parameter.PRECIPITATION_MORE,
        "wetter": Parameter.WEATHER_PHENOMENA,
    },
}

FILE_2_TIME_RESOLUTION = {
    "1minutenwerte": TimeResolution.MINUTE_1,
    "10minutenwerte": TimeResolution.MINUTE_10,
    "stundenwerte": TimeResolution.HOURLY,
    "tageswerte": TimeResolution.DAILY,
    "monatswerte": TimeResolution.MONTHLY,
    "jahreswerte": TimeResolution.ANNUAL,
}

FILE_2_PERIOD = {
    "hist": PeriodType.HISTORICAL,
    "now": PeriodType.NOW,
    "akt": PeriodType.RECENT,
    "row": PeriodType.RECENT,  # files with row are also classified as "recent" by DWD
}

DATE_FIELDS_REGULAR = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)

DATE_FIELDS_IRREGULAR = (
    DWDDataColumns.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DWDDataColumns.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
)

QUALITY_FIELDS = (
    # 1_minute
    # precipitation
    DWDOrigDataColumns.MINUTE_1.PRECIPITATION.QN.value,
    # 10_minutes
    # temperature_air
    DWDOrigDataColumns.MINUTES_10.TEMPERATURE_AIR.QN.value,
    # temperature_extreme
    DWDOrigDataColumns.MINUTES_10.TEMPERATURE_EXTREME.QN.value,
    # wind_extreme
    DWDOrigDataColumns.MINUTES_10.WIND_EXTREME.QN.value,
    # precipitation
    DWDOrigDataColumns.MINUTES_10.PRECIPITATION.QN.value,
    # solar
    DWDOrigDataColumns.MINUTES_10.SOLAR.QN.value,
    # wind
    DWDOrigDataColumns.MINUTES_10.WIND.QN.value,
    # hourly
    # temperature_air
    DWDOrigDataColumns.HOURLY.TEMPERATURE_AIR.QN_9.value,
    # cloud_type
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.QN_8.value,
    # cloudiness
    DWDOrigDataColumns.HOURLY.CLOUDINESS.QN_8.value,
    # dew_point
    DWDOrigDataColumns.HOURLY.DEW_POINT.QN_8.value,
    # precipitation
    DWDOrigDataColumns.HOURLY.PRECIPITATION.QN_8.value,
    # pressure
    DWDOrigDataColumns.HOURLY.PRESSURE.QN_8.value,
    # soil_temperature
    DWDOrigDataColumns.HOURLY.TEMPERATURE_SOIL.QN_2.value,
    # solar
    DWDOrigDataColumns.HOURLY.SOLAR.QN_592.value,
    # sun
    DWDOrigDataColumns.HOURLY.SUN.QN_7.value,
    # visibility
    DWDOrigDataColumns.HOURLY.VISIBILITY.QN_8.value,
    # wind
    DWDOrigDataColumns.HOURLY.WIND.QN_3.value,
    # wind_synop
    DWDOrigDataColumns.HOURLY.WIND_SYNOPTIC.QN_8.value,
    # subdaily
    # air_temperature
    DWDOrigDataColumns.SUBDAILY.TEMPERATURE_AIR.QN_4.value,
    # cloudiness
    DWDOrigDataColumns.SUBDAILY.CLOUDINESS.QN_4.value,
    # moisture
    DWDOrigDataColumns.SUBDAILY.MOISTURE.QN_4.value,
    # pressure
    DWDOrigDataColumns.SUBDAILY.PRESSURE.QN_4.value,
    # soil
    DWDOrigDataColumns.SUBDAILY.SOIL.QN_4.value,
    # visibility
    DWDOrigDataColumns.SUBDAILY.VISIBILITY.QN_4.value,
    # wind
    DWDOrigDataColumns.SUBDAILY.WIND.QN_4.value,
    # daily
    # kl
    DWDOrigDataColumns.DAILY.CLIMATE_SUMMARY.QN_3.value,
    DWDOrigDataColumns.DAILY.CLIMATE_SUMMARY.QN_4.value,
    # more_precip
    DWDOrigDataColumns.DAILY.PRECIPITATION_MORE.QN_6.value,
    # soil_temperature
    DWDOrigDataColumns.DAILY.TEMPERATURE_SOIL.QN_2.value,
    # solar
    DWDOrigDataColumns.DAILY.SOLAR.QN_592.value,
    # water_equiv
    DWDOrigDataColumns.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.QN_4.value,
    # monthly
    # kl
    DWDOrigDataColumns.MONTHLY.CLIMATE_SUMMARY.QN_4.value,
    DWDOrigDataColumns.MONTHLY.CLIMATE_SUMMARY.QN_6.value,
    # more_precip
    DWDOrigDataColumns.MONTHLY.PRECIPITATION_MORE.QN_6.value,
    # weather_phenomena
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.QN_4.value,
    # annual
    # kl
    DWDOrigDataColumns.ANNUAL.CLIMATE_SUMMARY.QN_4.value,
    # more_precip
    DWDOrigDataColumns.ANNUAL.PRECIPITATION_MORE.QN_6.value,
    # weather_phenomena
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.QN_4.value,
)

INTEGER_FIELDS = (
    # 1_minute
    # precipitation
    DWDOrigDataColumns.MINUTE_1.PRECIPITATION.RS_IND_01.value,
    # 10_minutes
    # wind_extreme
    DWDOrigDataColumns.MINUTES_10.WIND_EXTREME.DX_10.value,
    # precipitation
    DWDOrigDataColumns.MINUTES_10.PRECIPITATION.RWS_IND_10.value,
    # hourly
    # cloud_type
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_N.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_CS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_NS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_CS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_NS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_CS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_NS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_CS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_NS.value,
    # cloudiness
    DWDOrigDataColumns.HOURLY.CLOUDINESS.V_N.value,
    # precipitation
    DWDOrigDataColumns.HOURLY.PRECIPITATION.RS_IND.value,
    DWDOrigDataColumns.HOURLY.PRECIPITATION.WRTR.value,
    # visibility
    DWDOrigDataColumns.HOURLY.VISIBILITY.V_VV.value,
    # wind
    DWDOrigDataColumns.HOURLY.WIND.D.value,
    # wind_synop
    DWDOrigDataColumns.HOURLY.WIND_SYNOPTIC.DD.value,
    # subdaily
    # cloudiness
    DWDOrigDataColumns.SUBDAILY.CLOUDINESS.N_TER.value,
    DWDOrigDataColumns.SUBDAILY.CLOUDINESS.CD_TER.value,
    # soil
    DWDOrigDataColumns.SUBDAILY.SOIL.EK_TER.value,
    # visibility
    DWDOrigDataColumns.SUBDAILY.VISIBILITY.VK_TER.value,
    # wind
    DWDOrigDataColumns.SUBDAILY.WIND.DK_TER.value,
    DWDOrigDataColumns.SUBDAILY.WIND.FK_TER.value,
    # daily
    # more_precip
    DWDOrigDataColumns.DAILY.PRECIPITATION_MORE.RSF.value,
    DWDOrigDataColumns.DAILY.PRECIPITATION_MORE.SH_TAG.value,
    DWDOrigDataColumns.DAILY.PRECIPITATION_MORE.NSH_TAG.value,
    # water_equiv
    DWDOrigDataColumns.DAILY.WATER_EQUIVALENT.ASH_6.value,
    DWDOrigDataColumns.DAILY.WATER_EQUIVALENT.SH_TAG.value,
    # weather_phenomena
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.NEBEL.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.GEWITTER.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.STURM_6.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.STURM_8.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.TAU.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.GLATTEIS.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.REIF.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.GRAUPEL.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.HAGEL.value,
    # monthly
    # more_precip
    DWDOrigDataColumns.MONTHLY.PRECIPITATION_MORE.MO_NSH.value,
    DWDOrigDataColumns.MONTHLY.PRECIPITATION_MORE.MO_SH_S.value,
    # weather_phenomena
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_STURM_6.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_STURM_8.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GEWITTER.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GLATTEIS.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GRAUPEL.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_HAGEL.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_NEBEL.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_TAU.value,
    # annual
    # more_precip
    DWDOrigDataColumns.ANNUAL.PRECIPITATION_MORE.JA_NSH.value,
    DWDOrigDataColumns.ANNUAL.PRECIPITATION_MORE.JA_SH_S.value,
    # weather_phenomena
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_STURM_6.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_STURM_8.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GEWITTER.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GLATTEIS.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GRAUPEL.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_HAGEL.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_NEBEL.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_TAU.value,
)

STRING_FIELDS = (
    # hourly
    # cloud_type
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_N_I.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_CSA.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_CSA.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_CSA.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_CSA.value,
    # cloudiness
    DWDOrigDataColumns.HOURLY.CLOUDINESS.V_N_I.value,
    # visibility
    DWDOrigDataColumns.HOURLY.VISIBILITY.V_VV_I.value,
)


def determine_parameters(filename: str) -> Tuple[Parameter, TimeResolution, PeriodType]:
    """
    Function to determine the type of file from the bare filename
    Needed for downloading the file and naming it correctly and understandable

    Args:
        filename: str containing all parameter information

    Returns:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    """
    filename = filename.lower()

    # First check for time resolution
    time_resolution = retrieve_time_resolution_from_filename(filename)

    if time_resolution is None:
        raise ValueError(f"Resolution {time_resolution} could not be determined.")

    # First determine the variable
    parameter = retrieve_parameter_from_filename(filename, time_resolution)

    if parameter is None:
        raise ValueError(f"Variable {parameter} could not be determined.")

    period_type = retrieve_period_type_from_filename(filename)

    if period_type is None:
        raise ValueError(f"Timestamp {period_type} could not be determined.")

    return parameter, time_resolution, period_type


def retrieve_period_type_from_filename(filename: str) -> Optional[PeriodType]:
    """
    defines the period type of storages on dwd server

    """
    filename = filename.lower()

    if "_hist" in filename:
        period_type = PeriodType.HISTORICAL
    elif "_akt" in filename:
        period_type = PeriodType.RECENT
    elif "_now" in filename:
        period_type = PeriodType.NOW
    elif "_row" in filename:
        period_type = (
            PeriodType.RECENT
        )  # files with row are also classified as "recent" by DWD
    else:
        period_type = None
    return period_type


def retrieve_parameter_from_filename(
    filename: str, time_resolution: TimeResolution
) -> Optional[Parameter]:
    """
    defines the requested Parameter by checking the filename

    """
    filename = filename.lower()

    try:
        parameter = FILE_2_PARAMETER[time_resolution][
            list(
                set(FILE_2_PARAMETER[time_resolution].keys()) & set(filename.split("_"))
            )[0]
        ]
    except IndexError:
        parameter = None

    return parameter


def retrieve_time_resolution_from_filename(filename: str) -> Optional[TimeResolution]:
    """
    defines the requested time_resolution/granularity of observations
    by checking the filename

    """
    filename = filename.lower()

    try:
        time_resolution = FILE_2_TIME_RESOLUTION[
            list(set(FILE_2_TIME_RESOLUTION.keys()) & set(filename.split("_")))[0]
        ]
    except IndexError:
        time_resolution = None
    return time_resolution


def check_parameters(
    parameter: Parameter, time_resolution: TimeResolution, period_type: PeriodType
) -> bool:
    """
    Function to check for element (alternative name) and if existing return it
    Differs from foldername e.g. air_temperature -> tu
    """
    check = TIME_RESOLUTION_PARAMETER_MAPPING.get(time_resolution, {}).get(
        parameter, []
    )

    if period_type not in check:
        return False

    return True


def coerce_field_types(
    df: pd.DataFrame, time_resolution: TimeResolution
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
        column_value_index = df[column].notna()

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
            df.loc[column_value_index, column] = df.loc[
                column_value_index, column
            ].astype(int)
        elif column in STRING_FIELDS:
            df.loc[column_value_index, column] = df.loc[
                column_value_index, column
            ].astype(str)
        else:
            df[column] = df[column].astype(float)

    return df


def cast_to_list(iterable_) -> list:
    """
    A function that either converts an existing iterable to a list or simply puts the
    item into a list to make an iterable that includes this item.
    Args:
        iterable_:
    Return:
        list of anything
    """
    try:
        iterable_ = iterable_.split()
    except (AttributeError, SyntaxError):
        try:
            iterable_ = list(iterable_)
        except TypeError:
            iterable_ = [iterable_]

    return iterable_


def parse_enumeration_from_template(
    enum_: Union[str, Parameter, TimeResolution, PeriodType],
    enum_template: Union[Parameter, TimeResolution, PeriodType, Callable],
) -> Union[Parameter, TimeResolution, PeriodType]:
    """
    Function used to parse an enumeration(string) to a enumeration based on a template
    Args:
        enum_: enumeration as string or Enum
        enum_template: base enumeration from which the enumeration is parsed

    Returns:
        parsed enumeration from template
    Raises:
        InvalidParameter if no matching enumeration found
    """
    try:
        return enum_template[enum_.upper()]
    except (KeyError, AttributeError):
        try:
            return enum_template(enum_)
        except ValueError:
            raise InvalidParameter(
                f"{enum_} could not be parsed from {enum_template.__name__}."
            )


@lru_cache(maxsize=None)
def create_humanized_column_names_mapping(
    time_resolution: TimeResolution, parameter: Parameter
) -> dict:
    """
    Function to create an extend humanized column names mapping. The function
    takes care of the special cases of quality columns. Therefor it requires the
    time resolution and parameter.

    Args:
        time_resolution: time resolution enumeration
        parameter: parameter enumeration

    Returns:
        dictionary with mappings extended by quality columns mappings
    """
    column_name_mapping = {
        orig_column.value: humanized_column.value
        for orig_column, humanized_column in zip(
            DWDOrigDataColumns[time_resolution.name][parameter.name],
            DWDDataColumns[time_resolution.name][parameter.name],
        )
    }

    return column_name_mapping
