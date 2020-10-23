import re
import zipfile
from functools import reduce
from io import BytesIO
from typing import Tuple, List
from concurrent.futures import ThreadPoolExecutor
import datetime as dt

from urllib.parse import urljoin
import pandas as pd
from requests.exceptions import InvalidURL

from wetterdienst.util.cache import metaindex_cache
from wetterdienst.dwd.metadata.constants import (
    DWDCDCBase,
    DWD_SERVER,
    DWD_CDC_PATH,
    STATION_ID_REGEX,
    NA_STRING,
    STATION_DATA_SEP,
)
from wetterdienst.dwd.metadata.column_map import (
    GERMAN_TO_ENGLISH_COLUMNS_MAPPING,
    METADATA_DTYPE_MAPPING,
)
from wetterdienst.dwd.network import download_file_from_dwd
from wetterdienst.dwd.index import build_path_to_parameter
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
)
from wetterdienst.exceptions import MetaFileNotFound
from wetterdienst.util.network import list_remote_files

METADATA_COLUMNS = [
    DWDMetaColumns.STATION_ID.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
    DWDMetaColumns.STATION_HEIGHT.value,
    DWDMetaColumns.LATITUDE.value,
    DWDMetaColumns.LONGITUDE.value,
    DWDMetaColumns.STATION_NAME.value,
    DWDMetaColumns.STATE.value,
]

META_FILE_IDENTIFIERS = ["beschreibung", "txt"]

METADATA_1MIN_GEO_PREFIX = "Metadaten_Geographie_"

META_DATA_FOLDER = "meta_data/"

METADATA_FIXED_COLUMN_WIDTH = [
    (0, 5),
    (5, 14),
    (14, 23),
    (23, 38),
    (38, 50),
    (50, 60),
    (60, 102),
    (102, 200),
]


@metaindex_cache.cache_on_arguments()
def create_meta_index_for_climate_observations(
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
) -> pd.DataFrame:
    """
    Wrapper function that either calls the regular meta index function for general
    parameters or the special function for 1minute precipitation historical where meta
    index is created in a more complex way.

    Args:
        parameter: observation measure
        resolution: frequency/granularity of measurement interval
        period: current, recent or historical files

    Returns:
        pandas.DataFrame with meta index for the selected set of arguments
    """
    cond = (
        resolution == DWDObservationResolution.MINUTE_1
        and period == DWDObservationPeriod.HISTORICAL
        and parameter_set == DWDObservationParameterSet.PRECIPITATION
    )

    if cond:
        meta_index = _create_meta_index_for_1minute_historical_precipitation()
    else:
        meta_index = _create_meta_index_for_climate_observations(
            parameter_set, resolution, period
        )

    # If no state column available, take state information from daily historical
    # precipitation
    if DWDMetaColumns.STATE.value not in meta_index:
        mdp = _create_meta_index_for_climate_observations(
            DWDObservationParameterSet.PRECIPITATION_MORE,
            DWDObservationResolution.DAILY,
            DWDObservationPeriod.HISTORICAL,
        )

        meta_index = pd.merge(
            left=meta_index,
            right=mdp.loc[
                :, [DWDMetaColumns.STATION_ID.value, DWDMetaColumns.STATE.value]
            ],
            how="left",
        )

    meta_index[DWDMetaColumns.FROM_DATE.value] = pd.to_datetime(
        meta_index[DWDMetaColumns.FROM_DATE.value], format="%Y%m%d"
    )

    meta_index[DWDMetaColumns.TO_DATE.value] = pd.to_datetime(
        meta_index[DWDMetaColumns.TO_DATE.value], format="%Y%m%d"
    )

    return meta_index.sort_values(DWDMetaColumns.STATION_ID.value).reset_index(
        drop=True
    )


def _create_meta_index_for_climate_observations(
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
) -> pd.DataFrame:
    """Function used to create meta index DataFrame parsed from the text files that are
    located in each data section of the station data directory of the weather service.

    Args:
        parameter_set: observation measure
        resolution: frequency/granularity of measurement interval
        period: current, recent or historical files
    Return:
        DataFrame with parsed columns of the corresponding text file. Columns are
        translated into English and data is not yet complete as file existence is
        not checked.

    """
    parameter_path = build_path_to_parameter(parameter_set, resolution, period)

    url = reduce(
        urljoin,
        [
            DWD_SERVER,
            DWD_CDC_PATH,
            DWDCDCBase.CLIMATE_OBSERVATIONS.value,
            parameter_path,
        ],
    )

    files_server = list_remote_files(url, recursive=True)

    # Find the one meta file from the files listed on the server
    meta_file = _find_meta_file(files_server, url)

    try:
        file = download_file_from_dwd(meta_file)
    except InvalidURL as e:
        raise InvalidURL(f"Error: reading metadata {meta_file} file failed.") from e

    meta_index = pd.read_fwf(
        filepath_or_buffer=file,
        colspecs=METADATA_FIXED_COLUMN_WIDTH,
        skiprows=[1],
        dtype=str,
        encoding="ISO-8859-1",
    )

    # Fix column names, as header is not aligned to fixed column widths
    meta_index.columns = "".join(
        [column for column in meta_index.columns if "unnamed" not in column.lower()]
    ).split(" ")

    meta_index = meta_index.rename(columns=str.upper)

    meta_index = meta_index.rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    return meta_index.astype(METADATA_DTYPE_MAPPING)


def _find_meta_file(files: List[str], url: str) -> str:
    """
    Function used to find meta file based on predefined strings that are usually found
    in those files
    Args:
        files: list of files found on server path
        url: the path that was searched for a meta file

    Returns:
        the matching file
    Raises:
        MetaFileNotFound - for the case no file was found
    """
    for file in files:
        file_strings = file.split("/")[-1].lower().replace(".", "_").split("_")
        if set(file_strings).issuperset(META_FILE_IDENTIFIERS):
            return file

    raise MetaFileNotFound(f"No meta file was found amongst the files at {url}.")


def _create_meta_index_for_1minute_historical_precipitation() -> pd.DataFrame:
    """
    A helping function to create a raw index of metadata for stations of the set of
    parameters as given. This raw metadata is then used by other functions. This
    second/alternative function must be used for high resolution data, where the
    metadata is not available as file but instead saved in external files per each
    station.
    - especially for precipitation/1_minute/historical!

    """

    parameter_path = (
        f"{DWDObservationResolution.MINUTE_1.value}/"
        f"{DWDObservationParameterSet.PRECIPITATION.value}/"
    )

    url = reduce(
        urljoin,
        [
            DWD_SERVER,
            DWD_CDC_PATH,
            DWDCDCBase.CLIMATE_OBSERVATIONS.value,
            parameter_path,
            META_DATA_FOLDER,
        ],
    )

    metadata_file_paths = list_remote_files(url, recursive=False)

    station_ids = [
        re.findall(STATION_ID_REGEX, file).pop(0) for file in metadata_file_paths
    ]

    meta_index_df = pd.DataFrame(columns=METADATA_COLUMNS)

    with ThreadPoolExecutor() as executor:
        metadata_files = executor.map(
            _download_metadata_file_for_1minute_precipitation, metadata_file_paths
        )

    with ThreadPoolExecutor() as executor:
        metadata_dfs = executor.map(
            _parse_geo_metadata, zip(metadata_files, station_ids)
        )

    meta_index_df = meta_index_df.append(other=list(metadata_dfs), ignore_index=True)

    missing_to_date_index = pd.isnull(meta_index_df[DWDMetaColumns.TO_DATE.value])

    meta_index_df.loc[
        missing_to_date_index, DWDMetaColumns.TO_DATE.value
    ] = pd.Timestamp(dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")

    meta_index_df = meta_index_df.astype(METADATA_DTYPE_MAPPING)

    # Drop empty state column again as it will be merged later on
    meta_index_df = meta_index_df.drop(labels=DWDMetaColumns.STATE.value, axis=1)

    return meta_index_df


def _download_metadata_file_for_1minute_precipitation(metadata_file: str) -> BytesIO:
    """A function that simply opens a filepath with help of the urllib library and then
    writes the content to a BytesIO object and returns this object. For this case as it
    opens lots of requests (there are approx 1000 different files to open for
    1minute data), it will do the same at most three times for one file to assure
    success reading the file.

    Args:
        metadata_file (str) - the file that shall be downloaded and returned as bytes.

    Return:
        A BytesIO object to which the opened file was written beforehand.

    """
    try:
        file = download_file_from_dwd(metadata_file)
    except InvalidURL as e:
        raise InvalidURL(f"Reading metadata {metadata_file} file failed.") from e

    return file


def _parse_geo_metadata(
    metadata_file_and_station_id: Tuple[BytesIO, str]
) -> pd.DataFrame:
    """A function that analysis the given file (bytes) and extracts geography of
    1minute metadata zip and catches the relevant information and create a similar file
    to those that can usually be found already prepared for other
    parameter combinations.

    Args:
        metadata_file_and_station_id (BytesIO, str) - the file that holds the
        information and the station id of that file.

    Return:
        A pandas DataFrame with the combined data for one respective station.

    """
    metadata_file, station_id = metadata_file_and_station_id

    metadata_geo_filename = f"{METADATA_1MIN_GEO_PREFIX}{station_id}.txt"

    with zipfile.ZipFile(metadata_file, mode="r") as zip_file:
        metadata_geo_bytes = BytesIO(zip_file.read(metadata_geo_filename))

    metadata_geo_df = _parse_zipped_data_into_df(metadata_geo_bytes)

    metadata_geo_df = metadata_geo_df.rename(columns=str.upper)

    metadata_geo_df = metadata_geo_df.rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    metadata_geo_df[DWDMetaColumns.FROM_DATE.value] = metadata_geo_df.loc[
        0, DWDMetaColumns.FROM_DATE.value
    ]

    metadata_geo_df = metadata_geo_df.iloc[[-1], :]

    return metadata_geo_df.reindex(columns=METADATA_COLUMNS)


def _parse_zipped_data_into_df(file: BytesIO) -> pd.DataFrame:
    """A wrapper for read_csv of pandas library that has set the typically used
    parameters in the found data of the
    german weather service.

    Args:
        file - the file that will be read

    Return:
        A pandas DataFrame with the read data.

    """
    try:
        # First try utf-8
        file = pd.read_csv(
            filepath_or_buffer=file,
            sep=STATION_DATA_SEP,
            na_values=NA_STRING,
            dtype=str,
            skipinitialspace=True,
            encoding="utf-8",
        )
    except UnicodeDecodeError:
        file.seek(0)

        file = pd.read_csv(
            filepath_or_buffer=file,
            sep=STATION_DATA_SEP,
            na_values=NA_STRING,
            dtype=str,
            skipinitialspace=True,
            encoding="ISO-8859-1",
        )

    return file


def reset_meta_index_cache() -> None:
    """ Function to reset cache of meta index """
    metaindex_cache.invalidate()
