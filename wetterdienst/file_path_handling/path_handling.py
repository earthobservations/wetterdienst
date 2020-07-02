""" functions to handle paths and file names"""
from pathlib import Path, PurePosixPath
from typing import Union, List
from bs4 import BeautifulSoup

from wetterdienst.constants.access_credentials import HTTPS_EXPRESSION, DWD_SERVER, \
    DWD_CDC_PATH, DWD_CLIM_OBS_GERMANY_PATH
from wetterdienst.constants.metadata import DWD_FOLDER_STATION_DATA, DWD_FILE_STATION_DATA, H5_FORMAT
from wetterdienst.download.https_handling import create_dwd_session
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


def build_path_to_parameter(parameter: Parameter,
                            time_resolution: TimeResolution,
                            period_type: PeriodType) -> PurePosixPath:
    """
    Function to build a indexing file path
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    Returns:
        indexing file path relative to climate observations path
    """
    if parameter == Parameter.SOLAR and time_resolution in (TimeResolution.HOURLY, TimeResolution.DAILY):
        parameter_path = PurePosixPath(time_resolution.value, parameter.value)
    else:
        parameter_path = PurePosixPath(
            time_resolution.value, parameter.value, period_type.value)

    return parameter_path


def list_files_of_climate_observations(path: Union[PurePosixPath, str],
                                       recursive: bool) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server

    Args:
        path: the path which should be searched for files (relative to climate observations Germany)
        recursive: definition if the function should iteratively list files from subfolders

    Returns:
        a list of strings representing the files from the path
    """
    dwd_session = create_dwd_session()

    r = dwd_session.get(build_climate_observations_path(path))
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    files_and_folders = [link.get("href") for link in soup.find_all("a") if link.get("href") != "../"]

    files = []
    folders = []

    for f in files_and_folders:
        if not f.endswith("/"):
            files.append(str(PurePosixPath(path, f)))
        else:
            folders.append(PurePosixPath(path, f))

    if recursive:
        files_in_folders = [
            list_files_of_climate_observations(folder, recursive) for folder in folders]
        for files_in_folder in files_in_folders:
            files.extend(files_in_folder)

    return files


def build_climate_observations_path(path: Union[PurePosixPath, str]) -> str:
    """
    A function used to create the filepath consisting of the server, the climate observations
    path and the path of a subdirectory/file

    Args:
        path: the path of folder/file on the server

    Returns:
        the path create from the given parameters
    """
    return f"{HTTPS_EXPRESSION}{PurePosixPath(DWD_SERVER, DWD_CDC_PATH, DWD_CLIM_OBS_GERMANY_PATH, path)}"


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
        folder, DWD_FOLDER_STATION_DATA, f"{DWD_FILE_STATION_DATA}{H5_FORMAT}").absolute()

    return local_filepath
