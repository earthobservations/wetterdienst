""" helping functions for downloading german weather service data """
from pathlib import Path, PurePosixPath
from typing import Union

from python_dwd.constants.access_credentials import DWD_FOLDER_STATIONDATA, DWD_SERVER, DWD_PATH, HTTPS_EXPRESSION


def create_local_file_name(remote_file_path: Union[Path, str],
                           local_folder: Union[Path, str]) -> Path:
    """
    The local filename consists of the set of parameters (easier
    to analyse when looking at the filename) and the original filename

    """
    return Path(local_folder,
                DWD_FOLDER_STATIONDATA,
                str(remote_file_path).split('/')[-1])


def create_remote_file_name(file: str) -> str:
    """
    The filepath to the server is created with the filename,
     the parameters and the path
    Args:
        file: data file name on server

    Returns:
        complete Path to the required data

    """
    file_server = PurePosixPath(DWD_SERVER,
                                DWD_PATH,
                                file)

    return f"{HTTPS_EXPRESSION}{file_server}"
