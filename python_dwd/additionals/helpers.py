""" A set of helping functions used by the main functions """
import urllib
import zipfile
from typing import List
import os
from io import TextIOWrapper, BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import pandas as pd
import numpy as np
from numpy import datetime64
from tqdm import tqdm
from multiprocessing import Pool
import ftplib

from python_dwd.constants.column_name_mapping import STATION_ID_NAME, \
    FROM_DATE_NAME, TO_DATE_NAME,  GERMAN_TO_ENGLISH_COLUMNS_MAPPING, \
    FILENAME_NAME, FILEID_NAME, METADATA_DTYPE_MAPPING
from python_dwd.constants.ftp_credentials import DWD_SERVER, DWD_PATH, \
    MAIN_FOLDER, SUB_FOLDER_METADATA
from python_dwd.constants.metadata import METADATA_COLUMNS, \
    METADATA_MATCHSTRINGS, METADATA_1MIN_GEO_MATCHSTRINGS, \
    METADATA_1MIN_PAR_MATCHSTRINGS, FILELIST_NAME, FTP_METADATA_NAME, \
    ARCHIVE_FORMAT, DATA_FORMAT, METADATA_FIXED_COLUMN_WIDTH, STRING_STATID_COL, \
    STATE_NAME, STATIONDATA_SEP, NA_STRING, TRIES_TO_DOWNLOAD_FILE
from python_dwd.download.download_services import create_remote_file_name
from python_dwd.download.ftp_handling import FTP
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.path_handling import remove_old_file, \
    create_folder
from python_dwd.additionals.functions import find_all_matchstrings_in_string


def create_metaindex(parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType) -> pd.DataFrame:
    """ The function is used to create a simple metadata DataFrame parsed from the text files that are located in each
    data section of the station data directory of the weather service.

    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
    Return:
        DataFrame with parsed columns of the corresponding text file. Columns are translated into English and data is
        not yet complete as file existence is not checked.

    """
    server_path = PurePosixPath(DWD_PATH,
                                time_resolution.value,
                                parameter.value,
                                period_type.value)

    try:
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            files_server = ftp.list_files(remote_path=str(server_path), also_subfolders=False)

    except ftplib.all_errors as e:
        raise ftplib.all_errors("Error: couldn't retrieve filelist from server.\n"
                                f"{str(e)}")

    metafile_server = [file for file in files_server
                       if find_all_matchstrings_in_string(file.lower(), METADATA_MATCHSTRINGS)].pop(0)

    metafile_server = create_remote_file_name(metafile_server.lstrip(DWD_PATH))

    try:
        with urllib.request.urlopen(metafile_server) as request:
            file = BytesIO(request.read())

    except urllib.error.URLError as e:
        raise urllib.error.URLError("Error: reading metadata file failed.\n"
                                    f"{str(e)}")

    metaindex = pd.read_fwf(filepath_or_buffer=file,
                            colspecs=METADATA_FIXED_COLUMN_WIDTH,
                            skiprows=[1],
                            dtype=str)

    metaindex_colnames = [colname for colname in metaindex.columns if "unnamed" not in colname.lower()]
    metaindex_colnames_fixed = "".join(metaindex_colnames).split(" ")
    metaindex.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(name.upper(), name.upper())
                         for name in metaindex_colnames_fixed]

    return metaindex.astype(METADATA_DTYPE_MAPPING)


def metaindex_for_1minute_data(parameter: Parameter,
                               time_resolution: TimeResolution) -> pd.DataFrame:
    """
    A helping function to create a raw index of metadata for stations of the set of
    parameters as given. This raw metadata is then used by other functions. This
    second/alternative function must be used for high resolution data, where the
    metadata is not available as file but instead saved in external files per each
    station.
    - especially for precipitation/1_minute/historical!

    """

    assert time_resolution == TimeResolution.MINUTE_1, \
        "Wrong TimeResolution, only 1 minute is valid "

    metadata_path = PurePosixPath(DWD_PATH,
                                  time_resolution.value,
                                  parameter.value,
                                  FTP_METADATA_NAME)

    with FTP(DWD_SERVER) as ftp:
        ftp.login()

        metadata_filepaths = ftp.list_files(remote_path=str(metadata_path), also_subfolders=False)

    metadata_filepaths = [create_remote_file_name(file.lstrip(DWD_PATH)) for file in metadata_filepaths]

    metaindex_df = pd.DataFrame(None, columns=METADATA_COLUMNS)

    metadata_files = Pool().map(download_metadata_file_for_1minute_data, metadata_filepaths)

    metadata_dfs = Pool().map(combine_geo_and_par_file_to_metadata_df, metadata_files)

    metaindex_df = metaindex_df.append(other=metadata_dfs, ignore_index=True)

    metaindex_df.loc[:, STATE_NAME] = np.nan

    metaindex_df = metaindex_df.astype(METADATA_DTYPE_MAPPING)

    return metaindex_df.sort_values(STATION_ID_NAME).reset_index(drop=True)


def download_metadata_file_for_1minute_data(metadatafile: str) -> BytesIO:
    """ A function that simply opens a filepath with help of the urllib library and then writes the content to a BytesIO
    object and returns this object. For this case as it opens lots of requests (there are approx 1000 different files
    to open for 1minute data), it will do the same at most three times for one file to assure success reading the file.

    Args:
        metadatafile (str) - the file that shall be downloaded and returned as bytes.

    Return:
        A BytesIO object to which the opened file was written beforehand.

    """
    for _ in range(TRIES_TO_DOWNLOAD_FILE):
        try:
            with urllib.request.urlopen(metadatafile) as url_request:
                file = BytesIO(url_request.read())
            break
        except urllib.error.URLError:
            continue

    return file


def combine_geo_and_par_file_to_metadata_df(metadata_file: BytesIO) -> pd.DataFrame:
    """ A function that analysis the given file (bytes) and extracts both the geography and the parameter file of
    a 1minute metadata zip and combines both files in a predefined way to catch the relevant information and create a
    similar file to those that can usually be found already prepared for other parameter combinations.

    Args:
        metadata_file (str) - the file that holds the information.

    Return:
        A pandas DataFrame with the combined data for one respective station.

    """
    with zipfile.ZipFile(metadata_file) as zip_file:
        files_in_zipfile = zip_file.namelist()

        files_of_geo_and_par = {}
        dfs_of_geo_and_par = {}

        for file in files_in_zipfile:
            if find_all_matchstrings_in_string(file.lower(), METADATA_1MIN_GEO_MATCHSTRINGS):
                files_of_geo_and_par["geo_file"] = file
            elif find_all_matchstrings_in_string(file.lower(), METADATA_1MIN_PAR_MATCHSTRINGS):
                files_of_geo_and_par["par_file"] = file

        for filetype, file in files_of_geo_and_par.items():
            with zip_file.open(file) as file_opened:

                df = parse_zipped_data_into_df(file_opened)

            df.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(
                name.strip().upper(), name.strip().upper())
                for name in df.columns]

            dfs_of_geo_and_par[filetype] = df

    dfs_of_geo_and_par["geo_file"] = dfs_of_geo_and_par["geo_file"].iloc[[-1], :]

    dfs_of_geo_and_par["par_file"] = dfs_of_geo_and_par["par_file"].loc[:, [FROM_DATE_NAME, TO_DATE_NAME]].dropna()

    dfs_of_geo_and_par["geo_file"][FROM_DATE_NAME] = dfs_of_geo_and_par["par_file"][FROM_DATE_NAME].min()
    dfs_of_geo_and_par["geo_file"][TO_DATE_NAME] = dfs_of_geo_and_par["par_file"][TO_DATE_NAME].max()

    return dfs_of_geo_and_par["geo_file"].loc[:, METADATA_COLUMNS]


def parse_zipped_data_into_df(file_opened: open) -> pd.DataFrame:
    """ A wrapper for read_csv of pandas library that has set the typically used parameters in the found data of the
    german weather service.

    Args:
        file_opened (open) - the file that will be read

    Return:
        A pandas DataFrame with the read data.

    """
    file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                       sep=STATIONDATA_SEP,
                       na_values=NA_STRING,
                       dtype=str)

    return file


def create_fileindex(parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType,
                     folder: str = MAIN_FOLDER) -> None:
    """
        A function to receive current files on server as list excluding description
        files and only containing those files that have measuring data.

    """
    # Check for folder and create if necessary
    create_folder(subfolder=SUB_FOLDER_METADATA,
                  folder=folder)

    filelist_local_path = Path(folder,
                               SUB_FOLDER_METADATA,
                               f"{FILELIST_NAME}_{parameter.value}_"
                               f"{time_resolution.value}_"
                               f"{period_type.value}{DATA_FORMAT}")

    server_path = PurePosixPath(DWD_PATH,
                                time_resolution.value,
                                parameter.value,
                                period_type.value)

    try:
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            files_server = ftp.list_files(remote_path=str(server_path),
                                          also_subfolders=True)

    except ftplib.all_errors as e:
        raise ftplib.all_errors("Error: creating a filelist currently not possible.\n"
                                f"{str(e)}")

    files_server = pd.DataFrame(files_server, columns=[FILENAME_NAME])

    files_server.loc[:, FILENAME_NAME] = files_server.loc[:, FILENAME_NAME] \
        .apply(str)

    files_server.loc[:, FILENAME_NAME] = files_server.loc[:, FILENAME_NAME].apply(
        lambda filename: filename.lstrip(DWD_PATH + '/'))

    files_server = files_server[files_server.FILENAME.str.contains(
        ARCHIVE_FORMAT)]

    files_server[FILEID_NAME] = files_server.index

    files_server[STATION_ID_NAME] = files_server.iloc[:, 0].str.split("/")\
        .apply(lambda string: string[-1]).str.split("_")\
        .apply(lambda string: string[STRING_STATID_COL])

    files_server = files_server.iloc[:, [1, 2, 0]]

    files_server.iloc[:, 1] = files_server.iloc[:, 1].apply(int)

    files_server = files_server.sort_values(by=[STATION_ID_NAME])

    remove_old_file(file_type=FILELIST_NAME,
                    parameter=parameter,
                    time_resolution=time_resolution,
                    period_type=period_type,
                    file_postfix=DATA_FORMAT,
                    folder=folder,
                    subfolder=SUB_FOLDER_METADATA)

    files_server.to_csv(path_or_buf=str(filelist_local_path),
                        header=True,
                        index=False)


def check_file_exist(file_path: Path) -> bool:
    """ checks if the file behind the path exists """
    return Path(file_path).is_file()
