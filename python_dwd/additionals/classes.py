import ftplib
from io import StringIO
from pathlib import Path

from tqdm import tqdm

"""
##############################
#### Class FTP (modified) ####
##############################
The standard FTP module is completed with two functions known from the ftputil
module. The first one is the 'walk' function which returns for a specific
directory all the subdirectories (including the main directory) plus their
files as a list of lists ([dir, [files in dir]]). The second function is the
download function which basically adds together 'RETR ' and a custom filename
and opens a file with 'open' and finally saves the binary there.
"""


class FTP(ftplib.FTP):

    def __init__(self):
        self.login()

    def list_files(self, path):
        server_files = []

        path_files = self.nlst(path)

        path_dirs = [path_files.pop(id)
                     for id, file in enumerate(path_files)
                     if "." not in file]

        for dir in path_dirs:
            server_files.extend(self.list_files(dir))

        server_files.extend(path_files)

        return server_files

    # Implement walk function from ftputil library(to reduce number of imports)
    def walk(self, path):
        # First list everything in the path including dirs and files
        ftp_list = list(self.mlsd(path))

        # Return everything excluding '..' (upper folder) and files (expecting
        # to be '.txt' or '.zip' files)
        ftp_dirs = [dir_dict[0]
                    for dir_dict in ftp_list
                    if ".." not in dir_dict[0]
                    and ".txt" not in dir_dict[0]
                    and ".zip" not in dir_dict[0]
                    and ".pdf" not in dir_dict[0]]

        # Create an empty list for the listing of directiory files
        ftp_files = []

        # Loop over directorys (remaining main directory '.' and additional)
        for dir in tqdm(ftp_dirs):
            # Try to list files in that directory
            try:
                dir_files = [dir_list[0]
                             for dir_list in list(self.mlsd(Path(path, dir)))]  # path + "/" + dir

                dir_files = [dir_file
                             for dir_file in dir_files
                             if dir_file not in ['.', '..']]

            # If throws an error (which it does if the dir is only a filename)
            # just append a list with empty strings
            except Exception:
                dir_files = ['']

            # Finally append the directory and its list of files
            ftp_files.append([dir, dir_files])

        # Return the list of directories and files
        return ftp_files

    # Implement the readlines function from ftputil to read in data of a file
    # (which is not zipped) directly into RAM without the need to download the
    # corresponding file first
    def readlines(self, filepath_server):
        ftp_lines = StringIO()
        self.retrlines(f"RETR {filepath_server}",
                       (lambda line: ftp_lines.write(line + "\n")))

        ftp_text = ftp_lines.getvalue()

        ftp_lines.close()

        ftp_text = ftp_text.split("\n")

        return ftp_text

    # Implement a download function which simply takes to paths and builds a
    # command with the server path ("RETR "...) abd opens another path on the
    # local drive where the data is written to
    def download(self,
                 remote_file_path: Path,
                 local_file_path: Path):
        with open(local_file_path, "wb") as file:
            self.retrbinary(f"RETR {remote_file_path}", file.write)
