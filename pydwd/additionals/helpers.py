import pandas as pd

from .generic_classes import FTP
from .generic_functions import (check_parameters as _check_parameters,
                                correct_folder_path as _correct_folder_path,
                                create_folder as _create_folder,
                                remove_old_file as _remove_old_file)
from pydwd import select_dwd

from .dwd_credentials import SERVER, PATH

"""
################################
### Function 'get_metaindex' ###
################################
"""


def create_metaindex(var,
                     res,
                     per,
                     server=SERVER,
                     path=PATH):
    # Check for combination of parameters
    _check_parameters(var=var, res=res, per=per)

    # Try downloading metadata file under given local link
    try:
        # Open connection with ftp server
        with FTP(server) as ftp:
            # Login
            ftp.login()

            # Establish connection with server
            files_server = ftp.walk(
                path="{}/{}/{}/{}".format(path, res, var, per))

    # If there's a problem with the connection throw an error
    except Exception:
        raise NameError("Couldn't retrieve filelist from server")

    files_server = [file
                    for dir, filelist in files_server
                    for file in filelist if dir == '.']

    # Select metadata filename from server
    metafile_server = [
        file for file in files_server
        if ".txt" in file and "beschreibung" in file.lower()]

    metafile_server = metafile_server[0]

    # Create full path of server file
    metafile_server_path = "{}/{}/{}/{}/{}".format(
        path, res, var, per, metafile_server)

    try:
        # Open connection with ftp server
        with FTP(server) as ftp:
            # Login
            ftp.login()

            # Download file into folder path
            metaindex = ftp.readlines(metafile_server_path)

    # If not possible raise an error
    except Exception:
        raise NameError(
            "Reading metadata file currently is not possible. Try again!")

    return metaindex


def fix_metaindex(metaindex):
    # Remove first two lines of data (header plus underline ----)
    # Also last line (if empty)
    metaindex = metaindex[2:]

    if metaindex[-1] == '':
        metaindex = metaindex[:-1]

    file_format = []

    for data_line in metaindex:
        # data_line = data_lines[0]
        data_line_short = data_line.split(" ")
        # data_line_fixed = [value for value in data_line_split if value != ""]
        # data_line_short = data_line_fixed[:-1]

        if len(data_line_short) > 8:
            data_line_return = data_line_short[:6]

            value_fixed = ""
            for value_id in range(len(data_line_short) - 8 + 1):
                value_fixed += " " + data_line_short[(6 + value_id)]
            value_fixed_stripped = value_fixed.strip()
            data_line_return.append(value_fixed_stripped)

            data_line_return.append(data_line_short[-1])

        else:
            data_line_return = data_line_short

        file_format.append(data_line_return)

    metafile_df = pd.DataFrame(file_format)
    header = ["STATID", "FROM", "TO", "HEIGHT",
              "LAT", "LON", "STATNAME", "STATE"]
    metafile_df.columns = header

    # Statid to int without leading zeros
    metafile_df.iloc[:, 0] = [int(statid) for statid in metafile_df.iloc[:, 0]]

    metafile_df.iloc[:, 1] = pd.to_datetime(
        metafile_df.iloc[:, 1], format="%Y%m%d")

    metafile_df.iloc[:, 2] = pd.to_datetime(
        metafile_df.iloc[:, 2], format="%Y%m%d")

    return metafile_df


"""
##############################
### Function add_fileexist ###
##############################
"""


def add_filepresence(metainfo,
                     var,
                     res,
                     per,
                     folder,
                     create_new_filelist):

    metainfo["HAS_FILE"] = False

    for statid in metainfo["STATID"]:
        files = select_dwd(statid=statid,
                           var=var,
                           res=res,
                           per=per,
                           folder=folder,
                           create_new_filelist=create_new_filelist)

        if len(files) > 1:
            metainfo.iloc[metainfo["STATID"] == statid, -1] = True

    return metainfo


"""
Function to receive current files on server as list excluding description files
"""


def create_fileindex(var,
                     res,
                     per,
                     folder="./dwd_data",
                     server=SERVER,
                     path=PATH):
    # Check for the combination of requested parameters
    _check_parameters(var=var, res=res, per=per)

    folder = _correct_folder_path(folder)

    # Check for folder and create if necessary
    _create_folder(subfolder="metadata", folder=folder)

    # Create filename for local metadata file containing information of date
    filelist_local = "{}_{}_{}_{}".format("filelist", var, res, per)

    # Create filename
    filelist_local_path = "{}/{}/{}{}".format(folder,
                                              "metadata",
                                              filelist_local,
                                              ".csv")

    # Try listing files under given path
    try:
        # Open connection with ftp server
        with FTP(server) as ftp:
            # Login
            ftp.login()

            # Get files for set of paramters
            files_server = ftp.walk(
                "/{}/{}/{}/{}/".format(path, res, var, per))

    # If not possible raise an error
    except Exception:
        print("Download of fileslist file currently not possible. Try again!")
        raise Exception()

    # Put together dirs and filenames
    files_server = ["{}/{}".format(dir, single_file)
                    for dir, file in files_server
                    for single_file in file]

    files_server = [file if file[:2] != "./" else file[2:]
                    for file in files_server]

    # Select zip files (which contain the measured data) from server
    filelist = [
        file for file in files_server if ".zip" in file]

    if per == "historical":
        statid_col = -4
    elif per == "recent":
        statid_col = -2
    elif per == "now":
        statid_col = -2
    else:
        statid_col = None

    filelist_df = pd.DataFrame(
        {"FILEID": range(len(filelist)),
         "STATID": [int(file.split("_")[statid_col]) for file in filelist],
         "FILENAME": filelist}
    )

    filelist_df = filelist_df.sort_values(by=["STATID"])

    filelist_df["FILEID"] = range(len(filelist_df["STATID"]))

    # Remove old file
    _remove_old_file(file_type="filelist",
                     var=var,
                     res=res,
                     per=per,
                     folder=folder)

    # Write new file
    pd.DataFrame.to_csv(
        filelist_df, filelist_local_path, header=True, index=False)

    return None


def reduce_to_values(data):
    pass
