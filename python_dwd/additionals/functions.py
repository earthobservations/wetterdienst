"""
A set of more general functions used for the organization
"""
from typing import Tuple, List, Optional, Dict

from python_dwd.constants.parameter_mapping import TIME_RESOLUTION_PARAMETER_MAPPING
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.parameter_enumeration import Parameter

FILE_2_PARAMETER: Dict[TimeResolution, Dict[str, Parameter]] = {
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
         'p0': Parameter.PRESSURE,
         'eb': Parameter.TEMPERATURE_SOIL,
         'st': Parameter.SOLAR,
         'vv': Parameter.VISBILITY,
         'sd': Parameter.SUNSHINE_DURATION,
         'rr': Parameter.PRECIPITATION},
    TimeResolution.DAILY:
        {'kl': Parameter.CLIMATE_SUMMARY,
         'rr': Parameter.PRECIPITATION,
         'eb': Parameter.TEMPERATURE_SOIL,
         'wa': Parameter.WATER_EQUIVALENT,
         'st': Parameter.SOLAR},
    TimeResolution.MONTHLY:
        {'kl': Parameter.CLIMATE_SUMMARY,
         'rr': Parameter.PRECIPITATION},
    TimeResolution.ANNUAL:
        {'kl': Parameter.CLIMATE_SUMMARY,
         'rr': Parameter.PRECIPITATION}
}

FILE_2_TIME_RESOLUTION: Dict[str, TimeResolution] = {
    '1minutenwerte': TimeResolution.MINUTE_1,
    '10minutenwerte': TimeResolution.MINUTE_10,
    'stundenwerte': TimeResolution.HOURLY,
    'tageswerte': TimeResolution.DAILY,
    'monatswerte': TimeResolution.MONTHLY,
    'jahreswerte': TimeResolution.ANNUAL,
}

FILE_2_PERIOD: Dict[str, PeriodType] = {
    'hist': PeriodType.HISTORICAL,
    'now': PeriodType.NOW,
    'akt': PeriodType.RECENT,
    'row': PeriodType.ROW
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
        raise NameError(f"Resolution {time_resolution} couldn't be determined.")

    # First determine the variable
    parameter = retrieve_parameter_from_filename(filename, time_resolution)

    if parameter is None:
        raise NameError(f"Variable {parameter} couldn't be determined.")

    period_type = retrieve_period_type_from_filename(filename)

    if period_type is None:
        raise NameError(f"Timestamp {period_type} couldn't be determined.")

    return parameter, time_resolution, period_type


def retrieve_period_type_from_filename(filename: str) -> Optional[PeriodType]:
    """
    defines the period type of storages on dwd server

    """
    filename = filename.lower()

    try:
        # period type is connected to the file extension e.g. ".csv" that's why we have to replace the "." by a "_" to
        # apply the same functionality of getting the period type by using set
        period_type = \
            FILE_2_PERIOD[
                list(set(FILE_2_PERIOD.keys()) & set(filename.replace(".", "_").split('_')))[0]]
    except IndexError:
        period_type = None

    return period_type


def retrieve_parameter_from_filename(filename: str,
                                     time_resolution: TimeResolution) -> Optional[Parameter]:
    """
    defines the requested Parameter by checking the filename

    """
    filename = filename.lower()

    if time_resolution not in TimeResolution:
        raise ValueError(f"Error: {time_resolution} not in TimeResolution")
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
    check = TIME_RESOLUTION_PARAMETER_MAPPING.get(time_resolution, [[], []])

    if parameter not in check[0] or period_type not in check[1]:
        return False

    return True


def find_all_matchstrings_in_string(string: str,
                                    matchstrings: List[str]) -> bool:
    """ check if string has all matchstrings in it """
    return all([matchstring in string for matchstring in matchstrings])


def cast_to_list(iterable_) -> list:
    """
    A function that either converts an existing iterable to a list or simply puts the item into a list to make an
    iterable that includes this item.
    Args:
        iterable_:
    Return:
        list of iterable_
    """
    try:
        iterable_ = iterable_.split()
    except (AttributeError, SyntaxError):
        try:
            iterable_ = list(iterable_)
        except TypeError:
            iterable_ = [iterable_]

    return iterable_
