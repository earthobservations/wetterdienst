"""
A set of more general functions used for the organization
"""
from typing import Tuple, List, Optional

from wetterdienst.constants.parameter_mapping import TIME_RESOLUTION_PARAMETER_MAPPING
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns, DWDDataColumns
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.parameter_enumeration import Parameter

FILE_2_PARAMETER = {
    TimeResolution.MINUTE_1:
        {'nieder': Parameter.PRECIPITATION},
    TimeResolution.MINUTE_10:
        {'nieder': Parameter.PRECIPITATION,
         'tu': Parameter.TEMPERATURE_AIR,
         'extrema_temp': Parameter.TEMPERATURE_EXTREME,
         'tx': Parameter.TEMPERATURE_EXTREME,
         'fx': Parameter.WIND_EXTREME,
         'rr': Parameter.PRECIPITATION,
         'extrema_wind': Parameter.WIND_EXTREME,
         'solar': Parameter.SOLAR,
         'ff': Parameter.WIND,
         'wind': Parameter.WIND},
    TimeResolution.HOURLY:
        {'tu': Parameter.TEMPERATURE_AIR,
         'cs': Parameter.CLOUD_TYPE,
         'n': Parameter.CLOUDINESS,
         "td": Parameter.DEW_POINT,
         'rr': Parameter.PRECIPITATION,
         'p0': Parameter.PRESSURE,
         'eb': Parameter.TEMPERATURE_SOIL,
         'st': Parameter.SOLAR,
         "sd": Parameter.SUNSHINE_DURATION,
         'vv': Parameter.VISIBILITY,
         "ff": Parameter.WIND,
         "f": Parameter.WIND_SYNOPTIC},
    TimeResolution.SUBDAILY:
        {'tu': Parameter.TEMPERATURE_AIR,
         'n': Parameter.CLOUDINESS,
         "tf": Parameter.MOISTURE,
         'pp': Parameter.PRESSURE,
         "ek": Parameter.SOIL,
         "vk": Parameter.VISIBILITY,
         "fk": Parameter.WIND},
    TimeResolution.DAILY:
        {'kl': Parameter.CLIMATE_SUMMARY,
         'rr': Parameter.PRECIPITATION_MORE,
         'eb': Parameter.TEMPERATURE_SOIL,
         'st': Parameter.SOLAR,
         'wa': Parameter.WATER_EQUIVALENT,
         "wetter": Parameter.WEATHER_PHENOMENA},
    TimeResolution.MONTHLY:
        {'kl': Parameter.CLIMATE_SUMMARY,
         'rr': Parameter.PRECIPITATION_MORE,
         "wetter": Parameter.WEATHER_PHENOMENA},
    TimeResolution.ANNUAL:
        {'kl': Parameter.CLIMATE_SUMMARY,
         'rr': Parameter.PRECIPITATION_MORE,
         "wetter": Parameter.WEATHER_PHENOMENA}
}

FILE_2_TIME_RESOLUTION = {
    '1minutenwerte': TimeResolution.MINUTE_1,
    '10minutenwerte': TimeResolution.MINUTE_10,
    'stundenwerte': TimeResolution.HOURLY,
    'tageswerte': TimeResolution.DAILY,
    'monatswerte': TimeResolution.MONTHLY,
    'jahreswerte': TimeResolution.ANNUAL,
}

FILE_2_PERIOD = {
    'hist': PeriodType.HISTORICAL,
    'now': PeriodType.NOW,
    'akt': PeriodType.RECENT,
    'row': PeriodType.RECENT  # files with row are also classified as "recent" by DWD
}


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
        raise ValueError(f"Resolution {time_resolution} couldn't be determined.")

    # First determine the variable
    parameter = retrieve_parameter_from_filename(filename, time_resolution)

    if parameter is None:
        raise ValueError(f"Variable {parameter} couldn't be determined.")

    period_type = retrieve_period_type_from_filename(filename)

    if period_type is None:
        raise ValueError(f"Timestamp {period_type} couldn't be determined.")

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
        period_type = PeriodType.RECENT  # files with row are also classified as "recent" by DWD
    else:
        period_type = None
    return period_type


def retrieve_parameter_from_filename(filename: str,
                                     time_resolution: TimeResolution) -> Optional[Parameter]:
    """
    defines the requested Parameter by checking the filename

    """
    filename = filename.lower()

    try:
        parameter = \
            FILE_2_PARAMETER[time_resolution][
                list(set(FILE_2_PARAMETER[time_resolution].keys()) & set(filename.split('_')))[0]]
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
        time_resolution = \
            FILE_2_TIME_RESOLUTION[list(set(FILE_2_TIME_RESOLUTION.keys()) & set(filename.split('_')))[0]]
    except IndexError:
        time_resolution = None
    return time_resolution


def check_parameters(parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType) -> bool:
    """
    Function to check for element (alternative name) and if existing return it
    Differs from foldername e.g. air_temperature -> tu
    """
    check = TIME_RESOLUTION_PARAMETER_MAPPING.get(time_resolution, {}).get(parameter, [])

    if period_type not in check:
        return False

    return True


def find_all_match_strings_in_string(string: str,
                                     match_strings: List[str]):
    """ check if string has all match strings in it """
    return all([match_string in string for match_string in match_strings])


def create_station_data_dtype_mapping(columns: List[str]) -> dict:
    """
    A function used to create a unique dtype mapping for a given list of column names. This function is needed as we
    want to ensure the expected dtypes of the returned DataFrame as well as for mapping data after reading it from a
    stored .h5 file. This is required as we want to store the data in this file with the same format which is a string,
    thus after reading data back in the dtypes have to be matched.

    Args:
        columns: the column names of the DataFrame whose data should be converted
    Return:
         a dictionary with column names and dtypes for each of them
    """
    station_data_dtype_mapping = dict()

    """ Possible columns: STATION_ID, DATETIME, EOR, QN_ and other, measured values like rainfall """

    date_columns = (
        DWDMetaColumns.DATE.value,
        DWDMetaColumns.FROM_DATE.value,
        DWDMetaColumns.TO_DATE.value,
        DWDDataColumns.END_OF_INTERVAL.value,
        DWDDataColumns.TRUE_LOCAL_TIME.value
    )

    for column in columns:
        if column == DWDMetaColumns.STATION_ID.value:
            station_data_dtype_mapping[column] = int
        elif column in date_columns:
            station_data_dtype_mapping[column] = "datetime64"
        elif column == DWDMetaColumns.EOR.value:
            station_data_dtype_mapping[column] = str
        else:
            station_data_dtype_mapping[column] = float

    return station_data_dtype_mapping


def cast_to_list(iterable_) -> list:
    """
    A function that either converts an existing iterable to a list or simply puts the item into a list to make an
    iterable that includes this item.
    Args:
        iterable_:
    Return:
        ?
    """
    try:
        iterable_ = iterable_.split()
    except (AttributeError, SyntaxError):
        try:
            iterable_ = list(iterable_)
        except TypeError:
            iterable_ = [iterable_]

    return iterable_
