""" helping functions for ftp connection """
from pathlib import Path

from python_dwd.additionals.classes import FTP


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
