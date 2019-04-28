import ftplib
from io import StringIO

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
    # Implement walk function from ftputil library (to reduce number of imports)
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
        for dir in ftp_dirs:
            # Try to list files in that directory
            try:
                dir_files = [dir_list[0]
                             for dir_list in list(self.mlsd(path + "/" + dir))]

                dir_files = list(
                    filter(lambda x: x not in ['.', '..'], dir_files))

                # [file
                #  for file in dir_files
                #  if file not in ['.', '..']]
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
        self.retrlines("RETR " + filepath_server,
                       lambda line: ftp_lines.write(line + '\n'))
        ftp_lines = ftp_lines.getvalue()

        ftp_lines = ftp_lines.split("\n")

        return ftp_lines

    # Implement a download function which simply takes to paths and builds a
    # command with the server path ("RETR "...) abd opens another path on the
    # local drive where the data is written to
    def download(self, filepath_server, filepath_local):
        with open(filepath_local, "wb") as file:
            self.retrbinary("RETR " + filepath_server, file.write)
