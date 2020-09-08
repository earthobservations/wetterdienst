""" functions to handle paths and file names"""
from pathlib import Path, PurePosixPath
from typing import Union, List, Optional
from datetime import datetime

from bs4 import BeautifulSoup

from wetterdienst.constants.access_credentials import (
    HTTPS_EXPRESSION,
    DWD_SERVER,
    DWD_CDC_PATH,
    DWDCDCBase,
    DWDWeatherBase
)
from wetterdienst.constants.metadata import (
    DWD_FOLDER_STATION_DATA,
    DWD_FILE_STATION_DATA,
    DataFormat,
    DWD_FOLDER_RADOLAN,
    DWD_FILE_RADOLAN,
)
from wetterdienst.download.https_handling import create_dwd_session
from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.radar_sites import RadarSites
from wetterdienst.enumerations.radar_data_types import RadarDataTypes

RADAR_PARAMETERS_SITES = \
    [Parameter.DX_REFLECTIVITY, Parameter.LMAX_VOLUME_SCAN,
     Parameter.PE_ECHO_TOP, Parameter.PF_REFLECTIVITY,
     Parameter.PX_REFLECTIVITY, Parameter.PL_VOLUME_SCAN,
     Parameter.PR_VELOCITY, Parameter.PX250_REFLECTIVITY,
     Parameter.PZ_CAPPI, Parameter.SWEEP_VOL_PRECIPITATION_V,
     Parameter.SWEEP_VOL_PRECIPITATION_Z,
     Parameter.SWEEP_VOL_VELOCITY_V, Parameter.SWEEP_VOL_VELOCITY_Z]
RADAR_PARAMETERS_COMPOSITES = [Parameter.PP_REFLECTIVITY, Parameter.PG_REFLECTIVITY,
                               Parameter.WX_REFLECTIVITY, Parameter.WN_REFLECTIVITY,
                               Parameter.RX_REFLECTIVITY]
RADAR_PARAMETERS_WITH_HDF5 = [Parameter.SWEEP_VOL_PRECIPITATION_V,
     Parameter.SWEEP_VOL_PRECIPITATION_Z,
     Parameter.SWEEP_VOL_VELOCITY_V, Parameter.SWEEP_VOL_VELOCITY_Z]


def build_path_to_parameter(
        parameter: Parameter,
        time_resolution: TimeResolution,
        period_type: Optional[PeriodType] = None,
        radar_site: Optional[RadarSites] = None,
        radar_data_type: Optional[RadarDataTypes] = None
) -> PurePosixPath:
    """
    Function to build a indexing file path
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        radar_site: Site of the radar if parameter is one of RADAR_PARAMETERS_SITES
        radar_data_type: Some radar data are available in different data types

    Returns:
        indexing file path relative to climate observations path
    """
    if parameter == Parameter.SOLAR and time_resolution in (
            TimeResolution.HOURLY,
            TimeResolution.DAILY,
    ):
        parameter_path = PurePosixPath(time_resolution.value, parameter.value)
    elif parameter in RADAR_PARAMETERS_COMPOSITES:
        parameter_path = PurePosixPath(parameter.value)
    elif parameter in RADAR_PARAMETERS_SITES:
        if radar_site is None:
            raise ValueError("You have choosen radar site data which "
                             "requires to pass a RadarSite")
        else:
            parameter_path = PurePosixPath(parameter.value,
                                           radar_site.value)
            if parameter in RADAR_PARAMETERS_WITH_HDF5:
                if radar_data_type is None:
                    raise ValueError("You have to define a RadarDataType [hdf5 or binary]")
                elif radar_data_type is RadarDataTypes.HDF5:
                    parameter_path = PurePosixPath.joinpath(parameter_path, radar_data_type.value)

    else:
        parameter_path = PurePosixPath(
            time_resolution.value, parameter.value, period_type.value
        )

    return parameter_path


def list_files_of_dwd_server(
        path: Union[PurePosixPath, str],
        dwd_base: Union[DWDCDCBase, DWDWeatherBase],
        recursive: bool
) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server

    Args:
        path: the path which should be searched for files (relative to climate
        observations Germany)
        dwd_base: base path e.g. climate observations/germany or just weather
        recursive: definition if the function should iteratively list files
        from subfolders

    Returns:
        a list of strings representing the files from the path
    """
    dwd_session = create_dwd_session()

    r = dwd_session.get(build_dwd_directory_data_path(path, dwd_base))
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
            list_files_of_dwd_server(folder, dwd_base, recursive) for folder in folders
        ]

        for files_in_folder in files_in_folders:
            files.extend(files_in_folder)

    return files


def build_dwd_directory_data_path(
        path: Union[PurePosixPath, str], dwd_base: Union[DWDCDCBase, DWDWeatherBase]
) -> str:
    """
    A function used to create the filepath consisting of the server, the
    climate observations path and the path of a subdirectory/file

    Args:
        path: the path of folder/file on the server
        dwd_base: the CDC base path e.g. "climate observations/germany"

    Returns:
        the path create from the given parameters
    """
    base_path = DWDCDCBase.PATH.value \
        if isinstance(dwd_base, DWDCDCBase) else DWDWeatherBase.PATH.value

    return f"{HTTPS_EXPRESSION}{PurePosixPath(DWD_SERVER, base_path, dwd_base.value, path)}"


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
        folder,
        DWD_FOLDER_STATION_DATA,
        f"{DWD_FILE_STATION_DATA}.{DataFormat.H5.value}",
    ).absolute()

    return local_filepath


def build_local_filepath_for_radar(
        parameter: Parameter,
        date_time: datetime,
        folder: Union[str, Path],
        time_resolution: TimeResolution
) -> Union[str, Path]:
    """

    Args:
        parameter: radar data parameter
        date_time: Timestamp of file
        folder:
        time_resolution:

    Returns:

    """
    local_filepath = Path(
        folder,
        parameter.value,
        time_resolution.value,
        f"{parameter.value}_{time_resolution.value}_"
        f"{date_time.strftime(DatetimeFormat.YMDHM.value)}",
    ).absolute()

    return local_filepath
