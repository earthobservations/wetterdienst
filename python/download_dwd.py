from ftputil import FTPHost as FTP
import os

import pydwd_functions


def download_data(files, folder="./dwd_data"):
    folder = pydwd_functions.correct_folder_path(folder)

    server, path, user, password = pydwd_functions.get_dwd_credentials()

    # Check for files
    if len(files) == 0:
        return(None)

    # Create folder for data
    pydwd_functions.create_dwd_folder(
        subfolder="stationdata", folder=folder)

    # Determine var, res and per from first filename
    var, res, per = pydwd_functions.determine_type(files[0])

    # Try to download the corresponding file to the folder
    try:
        target_files = []
        for file in files:
            source_file = "/{}/{}/{}/{}/{}".format(path, res, var, per, file)
            file_formatted = "{}_{}_{}_{}".format(
                var, res, per, file.split("/")[-1])
            target_file = "{}/{}/{}".format(folder,
                                            "stationdata",
                                            file_formatted)
            target_files.append(target_file)
            FTP(server, user, password).download(
                source=source_file,
                target=target_file)
        return(target_files)
    except Exception:
        files_in_folder = os.listdir("{}/{}/".format(folder, "stationdata"))
        for file in files:
            if file in files_in_folder:
                for file_in_folder in files_in_folder:
                    if file in file_in_folder:
                        os.remove(file_in_folder)

    return(None)
