""" download scripts """
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
import zipfile
from io import BytesIO
from typing import List, Union
from multiprocessing import Pool
import pandas as pd

from python_dwd.file_path_handling.path_handling import create_folder
from python_dwd.constants.ftp_credentials import DWD_SERVER, MAIN_FOLDER,\
    SUB_FOLDER_STATIONDATA
from python_dwd.constants.metadata import STATIONDATA_MATCHSTRINGS
from python_dwd.download.download_services import create_local_file_name,\
    create_remote_file_name
from python_dwd.download.ftp_handling import ftp_file_download, FTP


def download_dwd_data(remote_files: pd.DataFrame,
                      parallel_download: bool = False) -> List[BytesIO]:
    """ wrapper for _download_dwd_data to provide a multiprocessing feature"""
    assert isinstance(remote_files, pd.DataFrame)
    assert isinstance(parallel_download, bool)

    remote_files = remote_files["FILENAME"].to_list()

    if parallel_download:
        return Pool().map(_download_dwd_data, remote_files)
    else:
        return [_download_dwd_data(remote_file) for remote_file in remote_files]

    # return [create_local_file_name(remote_file, folder) for
    #         remote_file in remote_files]


def _download_dwd_data(remote_file: Union[str, Path]) -> BytesIO:
    """
    This function downloads the stationdata for which the link is
    provided by the 'select_dwd' function. It checks the shortened filepath (just
    the zipfile) for its parameters, creates the full filepath and downloads the
    file(s) according to the set up folder.

    Args:
        download_specification: contains path to file that should be downloaded
            and the path to the folder to store the files

    Returns:
        stores data on local file system

    """
    assert isinstance(remote_file, str)

    file_server = create_remote_file_name(remote_file)

    try:
        request = urlopen(file_server)

        zip_file = zipfile.ZipFile(BytesIO(request.read()))

        produkt = [file_in_zip.filename
                   for file_in_zip in zip_file.filelist
                   if all([matchstring in file_in_zip.filename
                           for matchstring in STATIONDATA_MATCHSTRINGS])][0]

        return BytesIO(zip_file.open(produkt).read())

    except URLError as e:
        print(f"The file\n {file_server} \n couldn't be reached."
              f"Error: {str(e)}")

    except zipfile.BadZipFile as e:
        print(f"The zipfile seems to be corrupted."
              f"Error: {str(e)}")
