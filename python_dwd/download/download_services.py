""" helping functions for downloading german weather service data """
from pathlib import Path

from python_dwd.constants.ftp_credentials import SUB_FOLDER_STATIONDATA, DWD_PATH


def create_local_file_name(file: str, folder: str) -> str:
    """
    The local filename consists of the set of parameters (easier
    to analyse when looking at the filename) and the original filename

    """
    filename = file.split('/')[-1]
    file_local = f"{var}_{res}_{per}_{filename}"
    # Then the local path is added to the file
    file_local = Path(folder,
                      SUB_FOLDER_STATIONDATA,
                      file_local)
    return str(file_local).replace("\\", "/")


def create_remote_file_name(file: str) -> str:
    """
    The filepath to the server is created with the filename,
     the parameters and the path
    Args:
        file:

    Returns:

    """
    file_server = Path('/',
                       DWD_PATH,
                       file)
    return f"{file_server}".replace("\\", "/")
