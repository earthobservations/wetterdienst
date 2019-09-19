"""
A set of more general functions used for the organization
"""
from typing import Tuple, Union

from python_dwd.constants.parameter_mapping import TIME_RESOLUTION_PARAMETER_MAPPING
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.parameter_enumeration import Parameter


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


def retrieve_period_type_from_filename(filename: str) -> Union[PeriodType, None]:
    """
    defines the period type of storages on dwd server

    """
    if "_hist" in filename:
        period_type = PeriodType.HISTORICAL
    elif "_akt" in filename:
        period_type = PeriodType.RECENT
    elif "_now" in filename:
        period_type = PeriodType.NOW
    elif "_row" in filename:
        period_type = PeriodType.ROW
    else:
        period_type = None
    return period_type


def retrieve_parameter_from_filename(filename: str,
                                     time_resolution: TimeResolution) -> Union[Parameter, None]:
    """
    defines the requested Parameter by checking the filename

    """
    if time_resolution == TimeResolution.MINUTE_1:
        if "_nieder_" in filename:
            parameter = Parameter.PRECIPITATION
        else:
            parameter = None
    elif time_resolution == TimeResolution.MINUTE_10:
        if "_tu_" in filename:
            parameter = Parameter.TEMPERATURE_AIR
        elif "_tx_" in filename or "_extrema_temp_" in filename:
            parameter = Parameter.TEMPERATURE_EXTREME
        elif "_fx_" in filename or "_extrema_wind_" in filename:
            parameter = Parameter.WIND_EXTREME
        elif "_rr_" in filename or "_nieder_" in filename:
            parameter = Parameter.PRECIPITATION
        elif "_solar_" in filename:
            parameter = Parameter.SOLAR
        elif "_ff_" in filename or "_wind_" in filename:
            parameter = Parameter.WIND
        else:
            parameter = None
    elif time_resolution == TimeResolution.HOURLY:
        if "_tu_" in filename:
            parameter = Parameter.TEMPERATURE_AIR
        elif "_cs_" in filename:
            parameter = Parameter.CLOUD_TYPE
        elif "_n_" in filename:
            parameter = Parameter.CLOUDINESS
        elif "_rr_" in filename:
            parameter = Parameter.PRECIPITATION
        elif "_p0_" in filename:
            parameter = Parameter.PRESSURE
        elif "_eb_" in filename:
            parameter = Parameter.TEMPERATURE_SOIL
        elif "_st_" in filename:
            parameter = Parameter.SOLAR
        elif "_sd_" in filename:
            parameter = Parameter.SUNSHINE_DURATION
        elif "_vv_" in filename:
            parameter = Parameter.VISBILITY
        elif "_ff_" in filename:
            parameter = Parameter.WIND
        else:
            parameter = None
    elif time_resolution == TimeResolution.DAILY:
        if "_kl_" in filename:
            parameter = Parameter.CLIMATE_SUMMARY
        elif "_rr_" in filename:
            parameter = Parameter.PRECIPITATION_MORE
        elif "_eb_" in filename:
            parameter = Parameter.TEMPERATURE_SOIL
        elif "_st_" in filename:
            parameter = Parameter.SOLAR
        elif "_wa_" in filename:
            parameter = Parameter.WATER_EQUIVALENT
        else:
            parameter = None
    elif time_resolution == TimeResolution.MONTHLY:
        if "_kl_" in filename:
            parameter = Parameter.CLIMATE_SUMMARY
        elif "_rr_" in filename:
            parameter = Parameter.PRECIPITATION_MORE
        else:
            parameter = None
    elif time_resolution == TimeResolution.ANNUAL:
        if "_kl_" in filename:
            parameter = Parameter.CLIMATE_SUMMARY
        elif "_rr_" in filename:
            parameter = Parameter.PRECIPITATION_MORE
        else:
            parameter = None
    else:
        parameter = None

    return parameter


def retrieve_time_resolution_from_filename(filename: str) -> Union[TimeResolution, None]:
    """
    defines the requested time_resolution/granularity of observations
    by checking the filename

    """
    if "1minutenwerte_" in filename:
        time_resolution = TimeResolution.MINUTE_1
    elif "10minutenwerte_" in filename:
        time_resolution = TimeResolution.MINUTE_10
    elif "stundenwerte_" in filename:
        time_resolution = TimeResolution.HOURLY
    elif "tageswerte_" in filename:
        time_resolution = TimeResolution.DAILY
    elif "monatswerte_" in filename:
        time_resolution = TimeResolution.MONTHLY
    elif "jahreswerte_" in filename:
        time_resolution = TimeResolution.ANNUAL
    else:
        time_resolution = None

    return time_resolution


def check_parameters(parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType):
    """
    Function to check for element (alternative name) and if existing return it
    Differs from foldername e.g. air_temperature -> tu

    """
    check = TIME_RESOLUTION_PARAMETER_MAPPING.get(time_resolution, [[], []])

    if parameter not in check[0] or period_type not in check[1]:
        return False

    return True
