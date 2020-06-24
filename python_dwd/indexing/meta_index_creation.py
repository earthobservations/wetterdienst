import re
import urllib
import zipfile
from io import BytesIO, TextIOWrapper
from pathlib import PurePosixPath
import ftplib
from typing import Tuple
import pandas as pd
from multiprocessing import Pool
import functools
import datetime as dt

from python_dwd.additionals.functions import find_all_matchstrings_in_string
from python_dwd.constants.access_credentials import DWD_PATH, DWD_SERVER
from python_dwd.constants.column_name_mapping import GERMAN_TO_ENGLISH_COLUMNS_MAPPING, METADATA_DTYPE_MAPPING
from python_dwd.constants.metadata import METADATA_MATCHSTRINGS, METADATA_FIXED_COLUMN_WIDTH, FTP_METADATA_NAME, \
    STATID_REGEX, METADATA_COLUMNS, METADATA_1MIN_GEO_PREFIX, METADATA_1MIN_STA_PREFIX, STATIONDATA_SEP, NA_STRING
from python_dwd.download.download_services import create_remote_file_name
from python_dwd.download.ftp_handling import FTP
from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.path_handling import build_index_path


@functools.lru_cache(maxsize=None)
def create_meta_index_for_dwd_data(parameter: Parameter,
                                   time_resolution: TimeResolution,
                                   period_type: PeriodType) -> pd.DataFrame:
    """
    Wrapper function that either calls the regular meta index function for general parameters
    or the special function for 1minute precipitation historical where meta index is
    created in a more complex way.

    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: current, recent or historical files

    Returns:
        pandas.DataFrame with meta index for the selected set of arguments
    """
    cond = time_resolution == TimeResolution.MINUTE_1 and \
        period_type == PeriodType.HISTORICAL and \
        parameter == Parameter.PRECIPITATION

    if cond:
        return _create_meta_index_for_1minute__historical_precipitation()
    else:
        return _create_meta_index_for_dwd_data(parameter, time_resolution, period_type)


def _create_meta_index_for_dwd_data(parameter: Parameter,
                                    time_resolution: TimeResolution,
                                    period_type: PeriodType) -> pd.DataFrame:
    """ Function used to create meta index DataFrame parsed from the text files that are
    located in each data section of the station data directory of the weather service.

    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: current, recent or historical files
    Return:
        DataFrame with parsed columns of the corresponding text file. Columns are translated into English and data is
        not yet complete as file existence is not checked.

    """
    server_path = build_index_path(parameter, time_resolution, period_type)

    try:
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            files_server = ftp.list_files(remote_path=str(server_path), also_subfolders=False)

    except ftplib.all_errors as e:

        raise e("Creating file index currently not possible.")

    metafile_server = [file for file in files_server
                       if find_all_matchstrings_in_string(file.lower(), METADATA_MATCHSTRINGS)].pop(0)

    metafile_server = create_remote_file_name(
        metafile_server.replace(DWD_PATH + "/", ""))

    try:
        with urllib.request.urlopen(metafile_server) as request:
            file = BytesIO(request.read())

    except urllib.error.URLError as e:
        raise e(f"Error: reading metadata {metafile_server} file failed.")

    metaindex = pd.read_fwf(
        filepath_or_buffer=file,
        colspecs=METADATA_FIXED_COLUMN_WIDTH,
        skiprows=[1],
        dtype=str,
        encoding="ISO-8859-1"
    )

    # Fix column names, as header is not aligned to fixed column widths
    metaindex.columns = "".join(
        [column for column in metaindex.columns if "unnamed" not in column.lower()]).split(" ")

    metaindex = metaindex.rename(columns=str.upper)

    metaindex = metaindex.rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    return metaindex.astype(METADATA_DTYPE_MAPPING)


def _create_meta_index_for_1minute__historical_precipitation() -> pd.DataFrame:
    """
    A helping function to create a raw index of metadata for stations of the set of
    parameters as given. This raw metadata is then used by other functions. This
    second/alternative function must be used for high resolution data, where the
    metadata is not available as file but instead saved in external files per each
    station.
    - especially for precipitation/1_minute/historical!

    """
    metadata_path = PurePosixPath(
        DWD_PATH,
        TimeResolution.MINUTE_1.value,
        Parameter.PRECIPITATION.value,
        FTP_METADATA_NAME
    )

    with FTP(DWD_SERVER) as ftp:
        ftp.login()

        metadata_filepaths = ftp.list_files(remote_path=str(metadata_path), also_subfolders=False)

    metadata_filepaths = [create_remote_file_name(file.lstrip(DWD_PATH)) for file in metadata_filepaths]

    statids = [re.findall(STATID_REGEX, file).pop(0) for file in metadata_filepaths]

    metaindex_df = pd.DataFrame(None, columns=METADATA_COLUMNS)

    metadata_files = Pool().map(
        _download_metadata_file_for_1minute_precipitation, metadata_filepaths)

    metadata_dfs = Pool().map(
        _combine_geo_and_par_file_to_metadata_df, zip(metadata_files, statids))

    metaindex_df = metaindex_df.append(other=metadata_dfs, ignore_index=True)

    metaindex_df = metaindex_df.astype(METADATA_DTYPE_MAPPING)

    metaindex_df = metaindex_df.drop(labels=DWDMetaColumns.STATE.value, axis=1)

    return metaindex_df.sort_values(DWDMetaColumns.STATION_ID.value).reset_index(drop=True)


def _download_metadata_file_for_1minute_precipitation(metadatafile: str) -> BytesIO:
    """ A function that simply opens a filepath with help of the urllib library and then writes the content to a BytesIO
    object and returns this object. For this case as it opens lots of requests (there are approx 1000 different files
    to open for 1minute data), it will do the same at most three times for one file to assure success reading the file.

    Args:
        metadatafile (str) - the file that shall be downloaded and returned as bytes.

    Return:
        A BytesIO object to which the opened file was written beforehand.

    """
    try:
        with urllib.request.urlopen(metadatafile) as url_request:
            file = BytesIO(url_request.read())

    except urllib.error.URLError as e:
        raise e(f"Could not download metadata file {metadatafile}")

    return file


def _combine_geo_and_par_file_to_metadata_df(metadata_file_and_station_id: Tuple[BytesIO, str]) -> pd.DataFrame:
    """ A function that analysis the given file (bytes) and extracts both the geography and the parameter file of
    a 1minute metadata zip and combines both files in a predefined way to catch the relevant information and create a
    similar file to those that can usually be found already prepared for other parameter combinations.

    Args:
        metadata_file_and_station_id (BytesIO, str) - the file that holds the information and the statid of that file.

    Return:
        A pandas DataFrame with the combined data for one respective station.

    """
    metadata_file, station_id = metadata_file_and_station_id

    metadata_geo_filename = f"{METADATA_1MIN_GEO_PREFIX}{station_id}.txt"
    metadata_sta_filename = f"{METADATA_1MIN_STA_PREFIX}{station_id}.txt"

    with zipfile.ZipFile(metadata_file) as zip_file:
        with zip_file.open(metadata_geo_filename) as file_opened:
            metadata_geo_df = _parse_zipped_data_into_df(file_opened)

        with zip_file.open(metadata_sta_filename) as file_opened:
            metadata_sta_df = _parse_zipped_data_into_df(file_opened)

    metadata_geo_df = metadata_geo_df.rename(columns=str.upper).rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)
    metadata_sta_df = metadata_sta_df.rename(columns=str.upper).rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    metadata_geo_df = metadata_geo_df.iloc[[-1], :]
    metadata_sta_df = metadata_sta_df.loc[:, [DWDMetaColumns.FROM_DATE.value, DWDMetaColumns.TO_DATE.value]]\

    if pd.isnull(metadata_sta_df[DWDMetaColumns.TO_DATE.value].iloc[-1]):
        metadata_sta_df[DWDMetaColumns.TO_DATE.value].iloc[-1] = (
                dt.date.today() - dt.timedelta(days=1)).strftime(format="%Y%m%d")

    metadata_sta_df = metadata_sta_df.dropna()

    metadata_geo_df[DWDMetaColumns.FROM_DATE.value] = metadata_sta_df[DWDMetaColumns.FROM_DATE.value].min()
    metadata_geo_df[DWDMetaColumns.TO_DATE.value] = metadata_sta_df[DWDMetaColumns.TO_DATE.value].max()

    return metadata_geo_df.reindex(columns=METADATA_COLUMNS)


def _parse_zipped_data_into_df(file_opened: open) -> pd.DataFrame:
    """ A wrapper for read_csv of pandas library that has set the typically used parameters in the found data of the
    german weather service.

    Args:
        file_opened (open) - the file that will be read

    Return:
        A pandas DataFrame with the read data.

    """
    file = pd.read_csv(
        filepath_or_buffer=TextIOWrapper(file_opened),
        sep=STATIONDATA_SEP,
        na_values=NA_STRING,
        dtype=str,
        encoding="cp1252"
    )

    return file


def reset_meta_index_cache() -> None:
    """ Function to reset cache of meta index """
    create_meta_index_for_dwd_data.cache_clear()
