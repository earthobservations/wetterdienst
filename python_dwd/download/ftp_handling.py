""" helping functions for ftp connection """
import ftplib
from io import BytesIO
from pathlib import Path
from typing import Union, List


class FTP(ftplib.FTP):
    """
    A modified FTP class that has the capabilities to scan a ftp directory
    and provide easy to use download functions with out the need to build
    request strings or similiar stuff.
    """

    def list_files(self,
                   remote_path: Union[Path, str],
                   also_subfolders: bool) -> List[str]:
        """

        Args:
            remote_path(str): a path that is searched for files
            also_subfolders(bool): a bool that defines if subfolders should also be searched for files

        Returns:
            list of strings of all files (and files of subfolders) that can be found in a given directory

        """
        server_files = []

        path_files = self.nlst(remote_path)

        path_directories = [path_files.pop(file_id)
                            for file_id, file in enumerate(path_files)
                            if "." not in file]

        if also_subfolders:
            for directory in path_directories:
                server_files.extend(self.list_files(remote_path=directory,
                                                    also_subfolders=also_subfolders))

        server_files.extend(path_files)

        return server_files

    def read_file_to_bytes(self,
                           remote_file_path: Union[Path, str]) -> BytesIO:
        """

        Args:
            remote_file_path:

        Returns:

        """
        file = BytesIO()

        self.retrbinary(f"RETR {remote_file_path}", file.write)

        file.seek(0)

        return file

    def download(self,
                 remote_file_path: Path,
                 local_file_path: Path):
        with open(local_file_path, "wb") as file:
            self.retrbinary(f"RETR {remote_file_path}", file.write)


def ftp_file_download(ftp_connection: FTP,
                      remote_file_path: Path,
                      local_file_path: Path):
    """

    Args:
        ftp_connection: connection to an ftp server
        remote_file_path: path to the file on the server
        local_file_path: path where the file should be stored

    Returns:
        store file on local file system

    """
    ftp_connection.download(remote_file_path,
                            local_file_path)
