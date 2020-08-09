""" functions to handle paths and file names"""
from pathlib import Path, PurePosixPath
from typing import Union, List
import datetime as dt

from bs4 import BeautifulSoup
import pandas as pd

from wetterdienst.constants.access_credentials import (
    HTTPS_EXPRESSION,
    DWD_SERVER,
    DWD_CDC_PATH,
    DWDCDCDataPath,
)
from wetterdienst.constants.metadata import (
    DWD_FOLDER_STATION_DATA,
    DWD_FILE_STATION_DATA,
    DataFormat, DWD_FOLDER_RADOLAN, DWD_FILE_RADOLAN
)
from wetterdienst.download.https_handling import create_dwd_session
from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


def build_path_to_parameter(
    parameter: Parameter, time_resolution: TimeResolution, period_type: PeriodType
) -> PurePosixPath:
    """
    Function to build a indexing file path
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    Returns:
        indexing file path relative to climate observations path
    """
    if parameter == Parameter.SOLAR and time_resolution in (
        TimeResolution.HOURLY,
        TimeResolution.DAILY,
    ):
        parameter_path = PurePosixPath(time_resolution.value, parameter.value)
    else:
        parameter_path = PurePosixPath(
            time_resolution.value, parameter.value, period_type.value
        )

    return parameter_path


def list_files_of_dwd(
    path: Union[PurePosixPath, str],
    base: DWDCDCDataPath,
    recursive: bool
) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server

    Args:
        path: the path which should be searched for files (relative to climate
        observations Germany)
        base: base path e.g. climate observations/germany
        recursive: definition if the function should iteratively list files
        from subfolders

    Returns:
        a list of strings representing the files from the path
    """
    dwd_session = create_dwd_session()

    r = dwd_session.get(build_dwd_cdc_data_path(path, base))
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    files_and_folders = [
        link.get("href") for link in soup.find_all("a") if link.get("href") != "../"
    ]

    files = []
    folders = []

    for f in files_and_folders:
        if not f.endswith("/"):
            files.append(str(PurePosixPath(path, f)))
        else:
            folders.append(PurePosixPath(path, f))

    if recursive:
        files_in_folders = [
            list_files_of_dwd(folder, base, recursive) for folder in folders
        ]

        for files_in_folder in files_in_folders:
            files.extend(files_in_folder)

    return files


def build_dwd_cdc_data_path(path: Union[PurePosixPath, str],
                            base: DWDCDCDataPath) -> str:
    """
    A function used to create the filepath consisting of the server, the
    climate observations path and the path of a subdirectory/file

    Args:
        path: the path of folder/file on the server
        base: the CDC base path e.g. "climate observations/germany"

    Returns:
        the path create from the given parameters
    """
    dwd_cdc_data_path = PurePosixPath(
        DWD_SERVER, DWD_CDC_PATH, base.value, path
    )

    return f"{HTTPS_EXPRESSION}{dwd_cdc_data_path}"


def build_local_filepath_for_station_data(folder: Union[str, Path]) -> Union[str, Path]:
    """
    Function to create the local filepath for the station data that is being stored
    in a file if requested.
    Args:
        folder: the given folder where the data should be stored

    Returns:
        a Path build upon the folder
    """
    local_filepath = Path(
        folder, DWD_FOLDER_STATION_DATA, f"{DWD_FILE_STATION_DATA}{DataFormat.H5.value}"
    ).absolute()

    return local_filepath


def build_local_filepath_for_radolan(
        datetime: dt.datetime,
        folder: Union[str, Path],
        time_resolution: TimeResolution
) -> Union[str, Path]:
    """

    Args:
        datetime:
        folder:
        time_resolution:

    Returns:

    """
    local_filepath = Path(
        folder,
        DWD_FOLDER_RADOLAN,
        time_resolution.value,
        f"{DWD_FILE_RADOLAN}_{time_resolution.value}_{datetime.strftime(DatetimeFormat.YMDHM.value)}"
    ).absolute()

    return local_filepath
