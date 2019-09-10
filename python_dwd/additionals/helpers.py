""" A set of helping functions used by the main functions """
import os
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from tqdm import tqdm

from python_dwd.constants.column_name_mapping import STATION_ID_NAME, FROM_DATE_NAME, TO_DATE_NAME, \
    GERMAN_TO_ENGLISH_COLUMNS_MAPPING, FILENAME_NAME, FILEID_NAME
from python_dwd.constants.ftp_credentials import DWD_SERVER, DWD_PATH, MAIN_FOLDER, SUB_FOLDER_METADATA
from python_dwd.constants.metadata import METADATA_1MIN_COLUMNS, METADATA_MATCHSTRINGS, METADATA_1MIN_GEO_MATCHSTRINGS, \
    METADATA_1MIN_PAR_MATCHSTRINGS, FILELIST_NAME, FTP_METADATA_NAME, ARCHIVE_FORMAT, DATA_FORMAT
from .classes import FTP
from .functions import create_folder
from .functions import remove_old_file
from .variables import STRING_STATID_COL


def create_metaindex(parameter: str,
                     time_resolution: str,
                     period_type: str):
    """

    Args:
        parameter:
        time_resolution:
        period_type:

    Returns:

    """
    server_path = Path(DWD_PATH,
                       time_resolution,
                       parameter,
                       period_type)

    server_path = f"{server_path}{os.sep}"

    server_path = server_path.replace('\\', '/')

    # Try downloading metadata file under given local link
    try:
        # Open connection with ftp server
        with FTP(DWD_SERVER) as ftp:
            # Login
            ftp.login()

            # Establish connection with server
            files_server = ftp.list_files(path=server_path)

    # If there's a problem with the connection throw an error
    except Exception:
        raise NameError("Couldn't retrieve filelist from server")

    metafile_server = [file
                       for file in files_server
                       if all([matchstring in file.lower()
                               for matchstring in METADATA_MATCHSTRINGS])]

    metafile_server = metafile_server.pop(0)

    try:
        # Open connection with ftp server
        with FTP(DWD_SERVER) as ftp:
            # Login
            ftp.login()

            # Download file into folder path
            metaindex = ftp.readlines(metafile_server)

    # If not possible raise an error
    except Exception:
        raise NameError(
            "Reading metadata file currently is not possible. Try again!")

    return metaindex


def fix_metaindex(metaindex):
    """
        A helping function to fix the raw index of metadata by some string operations
        so that every information is in the right column.

    """
    # Convert data to pandas dataframe
    metaindex = pd.DataFrame(metaindex)
    # Split the data into columns by any spaces
    metaindex = metaindex.iloc[:, 0].str.split(expand=True)

    # Get the column names
    column_names = metaindex.iloc[0, :]

    # Remove Nones
    column_names = [name
                    for name in column_names
                    if name is not None]

    # Make them upper ones
    column_names = [name.upper()
                    for name in column_names]

    # Replace names by english aquivalent
    column_names = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(name, name)
                    for name in column_names]

    # Skip first two lines (header and seperating line)
    metaindex = metaindex.iloc[2:-1, :]

    # Create dataframe with strings to fix
    metaindex_to_fix = metaindex.iloc[:, 6:]

    # Reduce the original dataframe by those columns
    metaindex = metaindex.iloc[:, :6]

    # Index is fixed by string operations (put together all except the last
    # string which refers to state)
    metaindex_to_fix = metaindex_to_fix \
                           .agg(lambda data: [string
                                              for string in data
                                              if string is not None], 1) \
                           .to_frame() \
                           .iloc[:, 0] \
        .agg(lambda data: [' '.join(data[:-1]), data[-1]]) \
        .apply(pd.Series)

    # Finally put together again the original frame and the fixed data
    metaindex = pd.concat([metaindex, metaindex_to_fix], axis=1)

    # Overwrite the columns
    metaindex.columns = column_names

    # Fix datatypes
    metaindex.iloc[:, 0] = metaindex.iloc[:, 0].apply(int)
    metaindex.iloc[:, 1] = metaindex.iloc[:, 1].apply(int)
    metaindex.iloc[:, 1] = metaindex.iloc[:, 1].apply(str)
    metaindex.iloc[:, 1] = metaindex.iloc[:, 1].apply(pd.to_datetime)
    metaindex.iloc[:, 2] = metaindex.iloc[:, 2].apply(int)
    metaindex.iloc[:, 2] = metaindex.iloc[:, 2].apply(str)
    metaindex.iloc[:, 2] = metaindex.iloc[:, 2].apply(pd.to_datetime)
    metaindex.iloc[:, 3] = metaindex.iloc[:, 3].apply(int)
    metaindex.iloc[:, 4] = metaindex.iloc[:, 4].apply(float)
    metaindex.iloc[:, 5] = metaindex.iloc[:, 5].apply(float)
    metaindex.iloc[:, 6] = metaindex.iloc[:, 6].apply(str)
    metaindex.iloc[:, 7] = metaindex.iloc[:, 7].apply(str)

    return metaindex


"""
####################################
### Function 'create_metaindex2' ###
####################################
A helping function to create a raw index of metadata for stations of the set of
parameters as given. This raw metadata is then used by other functions. This 
second/alternative function must be used for high resolution data, where the 
metadata is not available as file but instead saved in external files per each 
station.
- especially for precipitation/1_minute/historical!
"""


def create_metaindex2(var,
                      res,
                      per,
                      folder):
    metadata_path = Path(DWD_PATH,
                         res,
                         var,
                         FTP_METADATA_NAME)

    metadata_path = str(metadata_path).replace("\\", "/")

    with FTP(DWD_SERVER) as ftp:
        ftp.login()

        metadata_server = ftp.nlst(metadata_path)

    metadata_server = [metadata_file.replace("\\", "/")
                       for metadata_file in metadata_server]

    metadata_local = [str(Path(folder,
                               SUB_FOLDER_METADATA,
                               metadata_file.split("/")[-1])).replace("\\", "/")
                      for metadata_file in metadata_server]

    metadata_df = pd.DataFrame(None,
                               columns=METADATA_1MIN_COLUMNS)

    for metafile_server, metafile_local in tqdm(zip(metadata_server, metadata_local), total=len(metadata_server)):
        with FTP(DWD_SERVER) as ftp:
            ftp.login()

            ftp.download(metafile_server,
                         metafile_local)

        with ZipFile(metafile_local) as zip_file:
            # List of fileitems in zipfile
            zip_file_files = zip_file.infolist()

            # List of filenames of fileitems
            zip_file_files = [zip_file_file.filename
                              for zip_file_file in zip_file_files]

            # Filter file with 'produkt' in filename
            file_geo = [zip_file_file
                        for zip_file_file in zip_file_files
                        if all([matchstring in zip_file_file.lower()
                                for matchstring in METADATA_1MIN_GEO_MATCHSTRINGS])]

            # List to filename
            file_geo = file_geo.pop(0)

            file_par = [zip_file_file
                        for zip_file_file in zip_file_files
                        if all([matchstring in zip_file_file.lower()
                                for matchstring in METADATA_1MIN_PAR_MATCHSTRINGS])]

            # List to filename
            file_par = file_par.pop(0)

            # Read data into a dataframe
            with zip_file.open(file_geo) as file_opened:
                try:
                    geo_file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                                           sep=";",
                                           na_values="-999")
                except UnicodeDecodeError:
                    geo_file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                                           sep=";",
                                           na_values="-999",
                                           engine="python")

            with zip_file.open(file_par) as file_opened:
                try:
                    par_file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                                           sep=";",
                                           na_values="-999")

                except UnicodeDecodeError:
                    par_file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                                           sep=";",
                                           na_values="-999",
                                           engine="python")

        # Remove file
        Path(metafile_local).unlink()

        # Clean names
        geo_file.columns = [name.strip().upper()
                            for name in geo_file.columns]

        # Replace them
        geo_file.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(name, name)
                            for name in geo_file.columns]

        # Clean names
        par_file.columns = [name.strip().upper()
                            for name in par_file.columns]

        # Replace them
        par_file.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(name, name)
                            for name in par_file.columns]

        # List for DataFrame return
        geo_file = geo_file.iloc[[-1], :]

        par_file = par_file.loc[:, [FROM_DATE_NAME, TO_DATE_NAME]].dropna()

        geo_file[FROM_DATE_NAME] = par_file[FROM_DATE_NAME].min()
        geo_file[TO_DATE_NAME] = par_file[TO_DATE_NAME].max()

        geo_file = geo_file.loc[:, METADATA_1MIN_COLUMNS]

        metadata_df = metadata_df.append(geo_file,
                                         ignore_index=True)

    metadata_df = metadata_df.reset_index(drop=True)

    # Fix datatypes
    metadata_df.iloc[:, 0] = metadata_df.iloc[:, 0].apply(int)
    metadata_df.iloc[:, 1] = metadata_df.iloc[:, 1].apply(int)
    metadata_df.iloc[:, 1] = metadata_df.iloc[:, 1].apply(str)
    metadata_df.iloc[:, 1] = metadata_df.iloc[:, 1].apply(pd.to_datetime)
    metadata_df.iloc[:, 2] = metadata_df.iloc[:, 2].apply(int)
    metadata_df.iloc[:, 2] = metadata_df.iloc[:, 2].apply(str)
    metadata_df.iloc[:, 2] = metadata_df.iloc[:, 2].apply(pd.to_datetime)
    metadata_df.iloc[:, 3] = metadata_df.iloc[:, 3].apply(int)
    metadata_df.iloc[:, 4] = metadata_df.iloc[:, 4].apply(float)
    metadata_df.iloc[:, 5] = metadata_df.iloc[:, 5].apply(float)
    metadata_df.iloc[:, 6] = metadata_df.iloc[:, 6].apply(str)

    metadata_df = metadata_df.sort_values(
        STATION_ID_NAME).reset_index(drop=True)

    return metadata_df


def create_fileindex(parameter: str,
                     time_resolution: str,
                     period_type: str,
                     folder: str = MAIN_FOLDER):
    """
        A function to receive current files on server as list excluding description
        files and only containing those files that have measuring data.

    """
    # Check for folder and create if necessary
    create_folder(subfolder=SUB_FOLDER_METADATA,
                  folder=folder)

    # Create filename for local metadata file containing information of date
    filelist_local = f"{FILELIST_NAME}_{parameter}_{time_resolution}_{period_type}"

    # Create filename with dataformat
    filelist_local_with_format = f"{filelist_local}{DATA_FORMAT}"

    # Create filename
    filelist_local_path = Path(folder,
                               SUB_FOLDER_METADATA,
                               filelist_local_with_format)

    filelist_local_path = str(filelist_local_path).replace('\\', '/')

    server_path = Path(DWD_PATH,
                       time_resolution,
                       parameter,
                       period_type)

    server_path = f"{server_path}{os.sep}"

    server_path = server_path.replace('\\', '/')

    # Try listing files under given path
    try:
        # Open connection with ftp server
        with FTP(DWD_SERVER) as ftp:
            # Login
            ftp.login()

            # Get files for set of paramters
            files_server = ftp.list_files(path=server_path)

    # If not possible raise an error
    except Exception:
        raise NameError(
            "Download of fileslist file currently not possible. Try again!")

    files_server = pd.DataFrame(files_server)

    files_server.columns = [FILENAME_NAME]

    files_server.loc[:, FILENAME_NAME] = files_server.loc[:, FILENAME_NAME] \
        .apply(str)

    files_server.loc[:, FILENAME_NAME] = files_server.loc[:, FILENAME_NAME].apply(
        lambda filename: filename.lstrip(DWD_PATH + '/'))

    files_server = files_server[files_server.FILENAME.str.contains(
        ARCHIVE_FORMAT)]

    files_server \
        .insert(loc=1,
                column=FILEID_NAME,
                value=files_server.index)

    files_server \
        .insert(loc=2,
                column=STATION_ID_NAME,
                value=files_server.iloc[:, 0].str.split('_')
                .apply(lambda string: string[STRING_STATID_COL.get(period_type, None)]))

    files_server = files_server.iloc[:, [1, 2, 0]]

    files_server.iloc[:, 1] = files_server.iloc[:, 1].apply(int)

    files_server = files_server.sort_values(by=[STATION_ID_NAME])

    # Remove old file
    remove_old_file(file_type=FILELIST_NAME,
                    parameter=parameter,
                    time_resolution=time_resolution,
                    period_type=period_type,
                    fileformat=DATA_FORMAT,
                    folder=folder,
                    subfolder=SUB_FOLDER_METADATA)

    # Write new file
    files_server.to_csv(path_or_buf=filelist_local_path,
                        header=True,
                        index=False)

    return None
