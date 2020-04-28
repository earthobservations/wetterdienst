from io import BytesIO
from pathlib import PurePosixPath
from typing import Union, List
import requests
from requests.adapters import HTTPAdapter
from lxml.html import document_fromstring  # lxml preferred over bs4, as it is about 50% faster
from functools import partial
from multiprocessing.dummy import Pool  # concurrent version, as parallel version does not work with sessions

HTTPS_EXPRESSION = "https://"
MAX_RETRIES = 3


def _create_dwd_session() -> requests.Session:
    """
    Function used to create a global session that is used for listing/downloading data from the DWD server.

    Returns:
        requests.Session object that then can be used for requests to the server
    """
    global _dwd_session

    try:
        _dwd_session
    except NameError:
        _dwd_session = requests.Session()
        _dwd_session.mount(HTTPS_EXPRESSION, HTTPAdapter(max_retries=MAX_RETRIES))

    return _dwd_session


def list_files(path: Union[PurePosixPath, str],
               base_url: Union[PurePosixPath, str],
               also_subfolders: bool) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server

    Args:
        path: the path which should be searched for files
        base_url: the base_url representing the part of the server which is worked with
        also_subfolders: definition if the function should iteratively list files from subfolders

    Returns:
        a list of strings representing the files from the path
    """
    dwd_session = _create_dwd_session()

    r = dwd_session.get(_build_path(path, base_url))
    r.raise_for_status()

    soup = document_fromstring(r.text)

    files_and_folders = [link.get("href") for link in soup.xpath("//a") if link.get("href") != "../"]

    files = []
    folders = []

    for f in files_and_folders:
        if not f.endswith("/"):
            files.append(str(PurePosixPath(path, f)))
        else:
            folders.append(PurePosixPath(path, f))

    if also_subfolders:
        files_in_folders = Pool().map(partial(list_files, base_url=base_url, also_subfolders=also_subfolders), folders)
        for files_in_folder in files_in_folders:
            files.extend(files_in_folder)

    return files


def download_file(filepath: Union[PurePosixPath, str],
                  base_url: Union[PurePosixPath, str]) -> BytesIO:
    """
    A function used to download a specified file from the server

    Args:
        filepath: the path that defines the file
        base_url: the base_url representing the part of the server which is worked with

    Returns:
        bytes of the file
    """
    dwd_session = _create_dwd_session()

    r = dwd_session.get(_build_path(filepath, base_url))
    r.raise_for_status()

    return BytesIO(r.content)


def _build_path(path: Union[PurePosixPath, str],
                base_url: Union[PurePosixPath, str]) -> str:
    """
    A function used to create the filepath consisting of the server, the observation path and the path of a
    subdirectory/file

    Args:
        path: the path of folder/file on the server

    Returns:
        the path create from the given parameters
    """
    return f"{HTTPS_EXPRESSION}{PurePosixPath(base_url, path)}"


if __name__ == "__main__":
    from python_dwd.constants.access_credentials import DWD_SERVER, DWD_CLIMATE_OBSERVATIONS

    path = "1_minute/precipitation/historical/"
    files = list_files(path, PurePosixPath(DWD_SERVER) / DWD_CLIMATE_OBSERVATIONS, True)

    print(files)
