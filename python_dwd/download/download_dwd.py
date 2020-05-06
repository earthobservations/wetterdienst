from pathlib import Path
from typing import List

from python_dwd.additionals.classes import FTP
from python_dwd.additionals.functions import check_parameters
from python_dwd.additionals.functions import create_folder
from python_dwd.additionals.functions import determine_parameters
from python_dwd.constants.ftp_credentials import DWD_SERVER, MAIN_FOLDER, SUB_FOLDER_STATIONDATA
from python_dwd.download.download_services import create_local_file_name, create_remote_file_name
from python_dwd.download.ftp_handling import ftp_file_download


def download_dwd_data(files: List[str],
                      folder=MAIN_FOLDER):
    """
    This function downloads the stationdata for which the link is
    provided by the 'select_dwd' function. It checks the shortened filepath (just
    the zipfile) for its parameters, creates the full filepath and downloads the
    file(s) according to the set up folder.

    Args:
        files:
        folder:

    Returns:
        stores data on local file system

    """
    assert isinstance(files, list)
    assert isinstance(folder, str)

    # Determine var, res and per from first filename (needed for creating full
    # filepath)
    var, res, per = determine_parameters(files[0])

    check_parameters(var, res, per)

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

                file_server = create_remote_file_name(file)
                file_local = create_local_file_name(file, folder)
                files_local.append(file_local)
                # Open connection with ftp server
                with FTP(DWD_SERVER) as ftp:
                    ftp_file_download(ftp, file_server, file_local)

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
