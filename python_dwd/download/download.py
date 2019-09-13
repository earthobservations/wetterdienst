""" download scripts """
from pathlib import Path
from typing import List, Union, Tuple
from multiprocessing import Pool

from python_dwd.file_path_handling.path_handling import create_folder
from python_dwd.constants.ftp_credentials import DWD_SERVER, MAIN_FOLDER,\
    SUB_FOLDER_STATIONDATA
from python_dwd.download.download_services import create_local_file_name,\
    create_remote_file_name
from python_dwd.download.ftp_handling import ftp_file_download, FTP


def download_dwd_data(remote_files: List[str],
                      folder: str = MAIN_FOLDER,
                      parallel_download: bool = False) -> List[Path]:
    """ wrapper for _download_dwd_data to provide a multiprocessing feature"""

    assert isinstance(remote_files, list)

    if parallel_download:
        combined_data = [(file, folder) for file in remote_files]
        Pool().map(_download_dwd_data, combined_data)
    else:
        for remote_file in remote_files:
            _download_dwd_data((remote_file, folder))

    return [create_local_file_name(remote_file, folder) for
            remote_file in remote_files]


def _download_dwd_data(download_specification: Tuple[Union[str, Path],
                                                     Union[str, Path]]):
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
    remote_file, folder = download_specification

    create_folder(subfolder=SUB_FOLDER_STATIONDATA,
                  folder=folder)

    file_server = create_remote_file_name(remote_file)
    file_local = create_local_file_name(remote_file, folder)

    try:
        # Open connection with ftp server
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            ftp_file_download(ftp,
                              Path(file_server),
                              Path(file_local))

    except Exception:
        # In the end raise an error naming the files that couldn't be loaded.
        raise NameError(
            f"The file\n {file_local} \n couldn't be downloaded!")
