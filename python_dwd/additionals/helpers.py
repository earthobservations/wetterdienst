""" A set of helping functions used by the main functions """
import re
import urllib
import zipfile
from typing import List, Tuple
from io import TextIOWrapper, BytesIO
from pathlib import Path, PurePosixPath
import pandas as pd
from multiprocessing import Pool
import ftplib

from python_dwd.constants.column_name_mapping import GERMAN_TO_ENGLISH_COLUMNS_MAPPING, METADATA_DTYPE_MAPPING
from python_dwd.constants.access_credentials import DWD_SERVER, DWD_PATH
from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.constants.metadata import METADATA_COLUMNS, METADATA_MATCHSTRINGS, FILELIST_NAME, FTP_METADATA_NAME, \
    METADATA_FIXED_COLUMN_WIDTH, STATION_DATA_SEP, NA_STRING, TRIES_TO_DOWNLOAD_FILE, \
    STATION_ID_REGEX, METADATA_1MIN_GEO_PREFIX, METADATA_1MIN_PAR_PREFIX
from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
from python_dwd.download.download_services import create_remote_file_name
from python_dwd.download.ftp_handling import FTP
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
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
                            dtype=str,
                            encoding="ISO-8859-1")

    # Fix column names, as header is not aligned to fixed column widths
    metaindex.columns = "".join(
        [column for column in metaindex.columns if "unnamed" not in column.lower()]).split(" ")

    metaindex = metaindex.rename(columns=str.upper).rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

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

    statids = [re.findall(STATION_ID_REGEX, file).pop(0) for file in metadata_filepaths]

    metaindex_df = pd.DataFrame(None, columns=METADATA_COLUMNS)

    metadata_files = Pool().map(download_metadata_file_for_1minute_data, metadata_filepaths)

    metadata_dfs = Pool().map(combine_geo_and_par_file_to_metadata_df, zip(metadata_files, statids))

    metaindex_df = metaindex_df.append(other=metadata_dfs, ignore_index=True)

    metaindex_df = metaindex_df.astype(METADATA_DTYPE_MAPPING)

    return metaindex_df.sort_values(DWDMetaColumns.STATION_ID.value).reset_index(drop=True)


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


def combine_geo_and_par_file_to_metadata_df(metadata_file_and_statid: Tuple[BytesIO, str]) -> pd.DataFrame:
    """ A function that analysis the given file (bytes) and extracts both the geography and the parameter file of
    a 1minute metadata zip and combines both files in a predefined way to catch the relevant information and create a
    similar file to those that can usually be found already prepared for other parameter combinations.

    Args:
        metadata_file_and_statid (BytesIO, str) - the file that holds the information and the statid of that file.

    Return:
        A pandas DataFrame with the combined data for one respective station.

    """
    metadata_file, statid = metadata_file_and_statid

    metadata_geo_filename = f"{METADATA_1MIN_GEO_PREFIX}{statid}.txt"
    metadata_par_filename = f"{METADATA_1MIN_PAR_PREFIX}{statid}.txt"

    with zipfile.ZipFile(metadata_file) as zip_file:
        with zip_file.open(metadata_geo_filename) as file_opened:
            metadata_geo_df = parse_zipped_data_into_df(file_opened)

        with zip_file.open(metadata_par_filename) as file_opened:
            metadata_par_df = parse_zipped_data_into_df(file_opened)

    metadata_geo_df = metadata_geo_df.rename(columns=str.upper).rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)
    metadata_par_df = metadata_par_df.rename(columns=str.upper).rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    metadata_geo_df = metadata_geo_df.iloc[[-1], :]
    metadata_par_df = metadata_par_df.loc[:, [DWDMetaColumns.FROM_DATE.value, DWDMetaColumns.TO_DATE.value]].dropna()

    metadata_geo_df[DWDMetaColumns.FROM_DATE.value] = metadata_par_df[DWDMetaColumns.FROM_DATE.value].min()
    metadata_geo_df[DWDMetaColumns.TO_DATE.value] = metadata_par_df[DWDMetaColumns.TO_DATE.value].max()

    return metadata_geo_df.reindex(columns=METADATA_COLUMNS)


def parse_zipped_data_into_df(file_opened: open) -> pd.DataFrame:
    """ A wrapper for read_csv of pandas library that has set the typically used parameters in the found data of the
    german weather service.

    Args:
        file_opened (open) - the file that will be read

    Return:
        A pandas DataFrame with the read data.

    """
    file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                       sep=STATION_DATA_SEP,
                       na_values=NA_STRING,
                       dtype=str)

    return file


def check_file_exist(file_path: Path) -> bool:
    """ checks if the file behind the path exists """
    return Path(file_path).is_file()


def create_stationdata_dtype_mapping(columns: List[str]) -> dict:
    """
    A function used to create a unique dtype mapping for a given list of column names. This function is needed as we
    want to ensure the expected dtypes of the returned DataFrame as well as for mapping data after reading it from a
    stored .h5 file. This is required as we want to store the data in this file with the same format which is a string,
    thus after reading data back in the dtypes have to be matched.
    
    Args:
        columns: the column names of the DataFrame whose data should be converted
    Return:
         a dictionary with column names and dtypes for each of them
    """
    stationdata_dtype_mapping = dict()

    """ Possible columns: STATION_ID, DATETIME, EOR, QN_ and other, measured values like rainfall """

    for column in columns:
        if column == DWDMetaColumns.STATION_ID.value:
            stationdata_dtype_mapping[column] = int
        elif column in (DWDMetaColumns.DATE.value, DWDMetaColumns.FROM_DATE.value, DWDMetaColumns.TO_DATE.value):
            stationdata_dtype_mapping[column] = "datetime64"
        elif column == DWDMetaColumns.EOR.value:
            stationdata_dtype_mapping[column] = str
        else:
            stationdata_dtype_mapping[column] = float

    return stationdata_dtype_mapping


def convert_datetime_hourly(value):
    return pd.to_datetime(value, format='%Y%m%d%H')
