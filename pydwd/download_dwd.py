from pathlib import Path

from .additionals.generic_classes import FTP

from .additionals.generic_functions import correct_folder_path
from .additionals.generic_functions import create_folder
from .additionals.generic_functions import determine_parameters
from .additionals.generic_functions import check_parameters

from .additionals.generic_variables import DWD_SERVER, DWD_PATH
from .additionals.generic_variables import MAIN_FOLDER, SUB_FOLDER_STATIONDATA

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
                 folder=MAIN_FOLDER,
                 server=DWD_SERVER,
                 path=DWD_PATH):
    # Check the parameter input for its type
    assert isinstance(files, list)
    assert isinstance(folder, str)
    assert isinstance(server, str)
    assert isinstance(path, str)

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
                file_server = "/{}/{}/{}/{}/{}".format(path,
                                                       res,
                                                       var,
                                                       per,
                                                       file)

                # The local filename consists of the set of parameters (easier
                # to analyse when looking at the filename) and the original
                file_local = "{}_{}_{}_{}".format(
                    var, res, per, file.split("/")[-1])

                # Then the local path is added to the file
                file_local = "{}/{}/{}".format(folder,
                                               SUB_FOLDER_STATIONDATA,
                                               file_local)
                # This final local path is stored in the list
                files_local.append(file_local)

                # Open connection with ftp server
                with FTP(server) as ftp:
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
        old_files = Path.glob("{}/{}/".format(folder,
                                              SUB_FOLDER_STATIONDATA))
        # For every file in the folder list...
        for old_file in old_files:
            # For every file in the download list...
            for file in files:
                # If the file of the download list is in the folder list
                if file in old_file:
                    # Remove the corresponding file.
                    Path.unlink("{}/{}/{}".format(folder,
                                                  SUB_FOLDER_STATIONDATA,
                                                  old_file))
                # If any file is removed it returns to checking the file from
                # download folder.
                break

        # In the end raise an error naming the files that couldn't be loaded.
        raise NameError(
            "One of the files\n {} \n couldn't be downloaded!".format(
                "\n".join(files)))

    return None
