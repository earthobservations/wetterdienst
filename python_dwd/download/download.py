""" download scripts """
from typing import List, Union, Tuple
from functools import partial
from pathlib import Path
import urllib
import zipfile
from io import BytesIO
# Advanced libs
from multiprocessing import Pool
import pandas as pd
import xarray

from python_dwd.file_path_handling.path_handling import create_folder
from python_dwd.constants.access_credentials import DWD_SERVER, MAIN_FOLDER,\
    SUB_FOLDER_STATIONDATA
from python_dwd.constants.metadata import STATIONDATA_MATCHSTRINGS, DWDDATA_NAME, NCDF4_FORMAT
from python_dwd.download.download_services import create_local_file_name,\
    create_remote_file_name
from python_dwd.download.ftp_handling import ftp_file_download, FTP
from python_dwd.additionals.functions import find_all_matchstrings_in_string


def download_dwd_data(remote_files: pd.DataFrame,
                      write_file: bool = False,
                      prefer_local: bool = False,
                      parallel_download: bool = False,
                      folder: str = MAIN_FOLDER) -> List[Tuple[str, BytesIO]]:
    """ wrapper for _download_dwd_data to provide a multiprocessing feature"""

    remote_files: List[str] = remote_files["FILENAME"].to_list()

    if parallel_download:
        return list(
            zip(
                remote_files,
                Pool().map(_download_dwd_data, remote_files)
            )
        )
    else:
        return [
            (remote_file, _download_dwd_data(remote_file))
            for remote_file in remote_files
        ]


def _download_dwd_data(remote_file: Union[str, Path]) -> BytesIO:
    """
    This function downloads the stationdata for which the link is
    provided by the 'select_dwd' function. It checks the shortened filepath (just
    the zipfile) for its parameters, creates the full filepath and downloads the
    file(s) according to the set up folder.

    Args:
        remote_file: contains path to file that should be downloaded
            and the path to the folder to store the files

    Returns:
        stores data on local file system

    """

    file_server = create_remote_file_name(remote_file)

    try:
        with urllib.request.urlopen(file_server) as url_request:
            zip_file = BytesIO(url_request.read())
    except urllib.error.URLError as e:
        raise urllib.error.URLError(f"Error: the stationdata {file_server} couldn't be reached.\n"
                                    f"{str(e)}")
    except urllib.error.HTTPERROR:
        pass

    try:
        with zipfile.ZipFile(zip_file) as zip_file_opened:
            produkt_file = [file_in_zip
                            for file_in_zip in zip_file_opened.namelist()
                            if find_all_matchstrings_in_string(file_in_zip, STATIONDATA_MATCHSTRINGS)][0]
        file = BytesIO(zip_file_opened.open(produkt_file).read())
    except zipfile.BadZipFile as e:
        raise zipfile.BadZipFile(f"Error: The zipfile seems to be corrupted.\n"
                                 f"{str(e)}")

    return file
