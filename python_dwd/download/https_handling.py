from io import BytesIO
from pathlib import PurePosixPath
from typing import Union, List
import requests
from requests.adapters import HTTPAdapter
from lxml.html import document_fromstring  # lxml preferred over bs4, as it is about 50% faster
from functools import partial
from multiprocessing.dummy import Pool  # concurrent version, as parallel version does not work with sessions

from python_dwd.constants.access_credentials import DWD_SERVER, HTTPS_EXPRESSION


class DWDSession:
    """ Session class used all over the library to interact with the DWD server """
    def __init__(self,
                 observations_path: str) -> None:
        """

        Args:
            observations_path: the path that relates to the service of DWD, e.g. climate observations
        """
        global _dwd_session

        try:
            _dwd_session
        except NameError:
            _dwd_session = requests.Session()
            _dwd_session.mount(DWD_SERVER, HTTPAdapter(max_retries=3))

        self._dwd_session = _dwd_session
        self._dwd_server = DWD_SERVER
        self._dwd_observations_path = observations_path
        self._https_expression = HTTPS_EXPRESSION

    def list_files(self,
                   path: Union[PurePosixPath, str],
                   also_subfolders: bool) -> List[str]:
        """
        A function used to create a listing of all files of a given path on the server

        Args:
            path: the path which should be searched for files
            also_subfolders: definition if the function should iteratively list files from subfolders

        Returns:
            a list of strings representing the files from the path
        """
        r = self._dwd_session.get(self._build_path(path))
        r.raise_for_status()

        soup = document_fromstring(r.text)

        files_and_folders = [link.get("href") for link in soup.xpath("//a") if link.get("href") != "../"]

        files = []
        folders = []

        for f in files_and_folders:
            if not f.endswith("/"):
                files.append(str(PurePosixPath(remote_path, f)))
            else:
                folders.append(PurePosixPath(remote_path, f))

        if also_subfolders:
            files_in_folders = Pool().map(partial(self.list_files, also_subfolders=also_subfolders), folders)
            for files_in_folder in files_in_folders:
                files.extend(files_in_folder)

        return files

    def download_file(self,
                      filepath: str) -> BytesIO:
        """
        A function used to download a specified file from the server

        Args:
            filepath: the path that defines the file

        Returns:
            bytes of the file
        """
        r = self._dwd_session.get(self._build_path(filepath))
        r.raise_for_status()

        return BytesIO(r.content)

    def _build_path(self, path: str) -> str:
        """
        A function used to create the filepath consisting of the server, the observation path and the path of a
        subdirectory/file

        Args:
            path: the path of folder/file on the server

        Returns:
            the path create from the given parameters
        """
        return f"{self._https_expression}{PurePosixPath(self._dwd_server, self._dwd_observations_path, path)}"


if __name__ == "__main__":
    dwd_obs_path = 'climate_environment/CDC/observations_germany/climate'
    dwd_session = DWDSession(dwd_obs_path)

    remote_path = "1_minute/precipitation/historical/"
    files = dwd_session.list_files(remote_path, True)

    print(files)
