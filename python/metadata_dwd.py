import pandas as pd
from ftputil import FTPHost as FTP

import pydwd_functions


def get_metaindex(var,
                  res,
                  per):
    # Check for combination of parameters
    pydwd_functions.check_dwd_structure(var=var, res=res, per=per)

    # Get server and path from dwd
    server, path, user, password = pydwd_functions.get_dwd_credentials()

    # Try downloading metadata file under given local link
    try:
        # Establish connection with server
        files_server = FTP(server, user, password).walk(
            "/{}/{}/{}/{}".format(path, res, var, per))
    except Exception:
        raise NameError("Couldn't retrieve filelist from server")

    files_server = [file for root, dir, file in files_server]

    # Select metadata filename from server
    metafile_server = [
        file for file in files_server[0]
        if ".txt" in file and "beschreibung" in file.lower()]

    metafile_server = metafile_server[0]

    # Create full path of server file
    metafile_server_path = "{}/{}/{}/{}/{}".format(
        path, res, var, per, metafile_server)

    try:
        # Download file into folder path
        metafile_raw = FTP(server, user, password).open(
            metafile_server_path, mode="r").readlines()

    # If not possible raise an error
    except Exception:
        raise NameError(
            "Reading metadata file currently is not possible. Try again!")

    return(metafile_raw)


def fix_metadata(metafile_raw):
    # Remove first two lines of data (header plus underline ----)
    metafile_raw = metafile_raw[2:]

    file_format = []

    for data_line in metafile_raw:
        # data_line = data_lines[0]
        data_line_split = data_line.split(" ")
        data_line_fixed = [value for value in data_line_split if value != ""]
        data_line_short = data_line_fixed[:-1]

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

    return(metafile_df)


def metadata_dwd(var,
                 res,
                 per,
                 folder="./dwd_data",
                 write_file=True):
    # Check for the combination of requested parameters
    pydwd_functions.check_dwd_structure(var=var, res=res, per=per)

    # Correct folder so that it doesn't end with slash
    folder = pydwd_functions.correct_folder_path(folder)

    # Get new metadata as unformated file
    metadata_raw = get_metaindex(var=var, res=res, per=per)

    # Format raw metadata, remove old file (and replace it with formatted)
    metainfo = fix_metadata(metadata_raw)

    if write_file:
        # Check for folder and create if necessary
        pydwd_functions.create_dwd_folder(subfolder="metadata", folder=folder)

        # Create filename for metafile
        metafile_local = "metadata_{}_{}_{}".format(var, res, per)

        # Create filepath with filename and including extension
        metafile_local_path = "{}/{}/{}{}".format(folder,
                                                  "metadata",
                                                  metafile_local,
                                                  ".csv")

        # Check for possible old files and remove them
        pydwd_functions.remove_dwdfile(
            file_type="metadata", var=var, res=res, per=per, folder=folder)

        pd.DataFrame.to_csv(metainfo, metafile_local_path, header=True,
                            index=False)

    return(metainfo)
