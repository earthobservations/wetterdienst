from pathlib import Path

from .additionals.classes import FTP

from .additionals.functions import correct_folder_path
from .additionals.functions import create_folder
from .additionals.functions import determine_parameters
from .additionals.functions import check_parameters

from .additionals.variables import DWD_SERVER, DWD_PATH
from .additionals.variables import MAIN_FOLDER, SUB_FOLDER_STATIONDATA

"""
###############################
### Function 'download_dwd' ###
###############################
This function is used to download the stationdata for which the link is
provided by the 'select_dwd' function. It checks the shortened filepath (just
the zipfile) for its parameters, creates the full filepath and downloads the
file(s) according to the set up folder.
"""


def download_dwd(files,
                 folder=MAIN_FOLDER):
    # Check the parameter input for its type
    assert isinstance(files, list)
    assert isinstance(folder, str)
    # assert isinstance(server, str)
    # assert isinstance(path, str)

    # Determine var, res and per from first filename (needed for creating full
    # filepath)
    var, res, per = determine_parameters(files[0])

    check_parameters(var, res, per)

    # Correct possible slashes at the end
    folder = correct_folder_path(folder)

    # Create folder for storing the downloaded data
    create_folder(subfolder=SUB_FOLDER_STATIONDATA,
                  folder=folder)

    # Try to download the corresponding file to the folder
    try:
        # Create an empty list in which the local filepaths are stored
        files_local = []

        # Loop over files list where every file is formatted (path) and
        # downloaded
        for file in files:
            # Only if the length of one filename is longer then zero it will be
            # examined
            if len(file) > 0:
                # The filepath to the server is created with the filename,
                # the parameters and the path
                file_server = Path('/',
                                   DWD_PATH,
                                   file)

                file_server = str(file_server)

                file_server = fr"{file_server}".replace("\\", "/")

                # The local filename consists of the set of parameters (easier
                # to analyse when looking at the filename) and the original filename
                filename = file.split('/')[-1]
                file_local = f'{var}_{res}_{per}_{filename}'

                # Then the local path is added to the file
                file_local = Path(folder,
                                  SUB_FOLDER_STATIONDATA,
                                  file_local)

                file_local = str(file_local).replace("\\", "/")

                # This final local path is stored in the list
                files_local.append(file_local)

                # Open connection with ftp server
                with FTP(DWD_SERVER) as ftp:
                    # Login
                    ftp.login()

                    # Now the download happens with two filepaths (server and
                    # local)
                    ftp.download(filepath_server=file_server,
                                 filepath_local=file_local)

            else:
                # Print a statement according to the empty filename
                print("Empty file is skipped.")

        return files_local

    # If anything goes wrong in between every file in the respective folder is
    # deleted. This should prevent a chunk of file from not being run
    # completely and instead should throw an error.
    except Exception:
        # List files in the download folder
        old_files = Path.glob(Path(folder, SUB_FOLDER_STATIONDATA))

        # f"{folder}/{SUB_FOLDER_STATIONDATA}/"

        # For every file in the folder list...
        for old_file in old_files:
            # For every file in the download list...
            for file in files:
                # If the file of the download list is in the folder list
                if file in old_file:
                    # Remove the corresponding file.
                    Path.unlink(Path(folder,
                                     SUB_FOLDER_STATIONDATA,
                                     old_file))
                # If any file is removed it returns to checking the file from
                # download folder.
                break

        filenames_joined = '\n'.join(files)

        # In the end raise an error naming the files that couldn't be loaded.
        raise NameError(
            f"One of the files\n {filenames_joined} \n couldn't be downloaded!")

    return None
