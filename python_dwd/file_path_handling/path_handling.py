""" functions to handle paths and file names"""
from pathlib import Path, PurePosixPath
from typing import Union

from python_dwd.constants.access_credentials import DWD_PATH
from python_dwd.constants.metadata import DWD_FOLDER_STATION_DATA, DWD_FILE_STATION_DATA, H5_FORMAT
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def build_local_filepath_for_station_data(folder: Union[str, Path]) -> Union[str, Path]:
    """
    Function to create the local filepath for the station data that is being stored
    in a file if requested.
    Args:
        folder: the given folder where the data should be stored

    Returns:
        a Path build upon the folder
    """
    local_filepath = Path(folder, DWD_FOLDER_STATION_DATA).absolute() / \
        f"{DWD_FILE_STATION_DATA}{H5_FORMAT}"

    return local_filepath


def build_index_path(parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType) -> PurePosixPath:
    """
    Function to build a indexing file path
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    Returns:
        indexing file path as PurePosixPath
    """
    if parameter == Parameter.SOLAR and time_resolution in (TimeResolution.HOURLY, TimeResolution.DAILY):
        server_path = PurePosixPath(
            DWD_PATH, time_resolution.value, parameter.value)
    else:
        server_path = PurePosixPath(
            DWD_PATH, time_resolution.value, parameter.value, period_type.value)

    return server_path
