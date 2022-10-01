# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor
from functools import reduce
from io import BytesIO, StringIO
from typing import List, Tuple
from urllib.parse import urljoin

import pandas as pd
from fsspec.implementations.zip import ZipFileSystem
from requests.exceptions import InvalidURL

from wetterdienst.exceptions import MetaFileNotFound
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.index import build_path_to_parameter
from wetterdienst.provider.dwd.metadata.column_map import (
    GERMAN_TO_ENGLISH_COLUMNS_MAPPING,
)
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.metadata.constants import (
    DWD_CDC_PATH,
    DWD_SERVER,
    DWDCDCBase,
)
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    DWD_URBAN_DATASETS,
    DwdObservationDataset,
)
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file, list_remote_files_fsspec

METADATA_COLUMNS = [
    Columns.STATION_ID.value,
    Columns.FROM_DATE.value,
    Columns.TO_DATE.value,
    Columns.HEIGHT.value,
    Columns.LATITUDE.value,
    Columns.LONGITUDE.value,
    Columns.NAME.value,
    Columns.STATE.value,
]

STATION_ID_REGEX = r"(?<!\d)\d{5}(?!\d)"


def create_meta_index_for_climate_observations(
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
) -> pd.DataFrame:
    """
    Wrapper function that either calls the regular meta index function for general
    parameters or the special function for 1minute precipitation historical where meta
    index is created in a more complex way.

    Args:
        dataset: observation measure
        resolution: frequency/granularity of measurement interval
        period: current, recent or historical files

    Returns:
        pandas.DataFrame with meta index for the selected set of arguments
    """
    cond1 = (
        resolution == Resolution.MINUTE_1
        and period == Period.HISTORICAL
        and dataset == DwdObservationDataset.PRECIPITATION
    )

    cond2 = resolution == Resolution.SUBDAILY and dataset == DwdObservationDataset.WIND_EXTREME
    cond3 = dataset in DWD_URBAN_DATASETS
    if cond1:
        meta_index = _create_meta_index_for_1minute_historical_precipitation()
    elif cond2:
        meta_index = _create_meta_index_for_subdaily_extreme_wind(period)
    elif cond3:
        meta_index = _create_meta_index_for_climate_observations(dataset, resolution, Period.RECENT)
    else:
        meta_index = _create_meta_index_for_climate_observations(dataset, resolution, period)

    # If no state column available, take state information from daily historical
    # precipitation
    if DwdColumns.STATE.value not in meta_index:
        mdp = _create_meta_index_for_climate_observations(
            DwdObservationDataset.PRECIPITATION_MORE,
            Resolution.DAILY,
            Period.HISTORICAL,
        )

        meta_index = pd.merge(
            left=meta_index,
            right=mdp.loc[:, [Columns.STATION_ID.value, Columns.STATE.value]],
            how="left",
        )

    return meta_index.sort_values(Columns.STATION_ID.value).reset_index(drop=True)


def _create_meta_index_for_climate_observations(
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
) -> pd.DataFrame:
    """Function used to create meta index DataFrame parsed from the text files that are
    located in each data section of the station data directory of the weather service.

    Args:
        dataset: observation measure
        resolution: frequency/granularity of measurement interval
        period: current, recent or historical files
    Return:
        DataFrame with parsed columns of the corresponding text file. Columns are
        translated into English and data is not yet complete as file existence is
        not checked.

    """
    parameter_path = build_path_to_parameter(dataset, resolution, period)

    if dataset in DWD_URBAN_DATASETS:
        dwd_cdc_base = DWDCDCBase.CLIMATE_URBAN_OBSERVATIONS.value
    else:
        dwd_cdc_base = DWDCDCBase.CLIMATE_OBSERVATIONS.value

    url = reduce(
        urljoin,
        [
            DWD_SERVER,
            DWD_CDC_PATH,
            dwd_cdc_base,
            parameter_path,
        ],
    )

    files_server = list_remote_files_fsspec(url, ttl=CacheExpiry.METAINDEX)

    # Find the one meta file from the files listed on the server
    meta_file = _find_meta_file(files_server, url, ["beschreibung", "txt"])

    try:
        file = download_file(meta_file, ttl=CacheExpiry.METAINDEX)
    except InvalidURL as e:
        raise InvalidURL(f"Error: reading metadata {meta_file} file failed.") from e

    return _read_meta_df(file)


def _find_meta_file(files: List[str], url: str, strings: List[str]) -> str:
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
        if set(file_strings).issuperset(strings):
            return file

    raise MetaFileNotFound(f"No meta file was found amongst the files at {url}.")


def _read_meta_df(file: BytesIO) -> pd.DataFrame:
    """Read metadata into pandas.DataFrame
    :param file: metadata file loaded in bytes
    :return: pandas.DataFrame with Stations
    """
    df = pd.read_fwf(
        filepath_or_buffer=file,
        colspecs=[
            (0, 5),
            (5, 14),
            (14, 23),
            (23, 38),
            (38, 50),
            (50, 60),
            (60, 102),
            (102, 200),
        ],
        skiprows=[1],
        dtype=str,
        encoding="ISO-8859-1",
    )

    # Fix column names, as header is not aligned to fixed column widths
    df.columns = "".join([column for column in df.columns if "unnamed" not in column.lower()]).split(" ")

    return df.rename(columns=str.lower).rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)


def _create_meta_index_for_subdaily_extreme_wind(period: Period) -> pd.DataFrame:
    """Create metadata DataFrame for subdaily wind extreme

    :param period: period for which metadata is acquired
    :return: pandas.DataFrame with combined information for both 3hourly (fx3) and 6hourly (fx6) wind extremes
    """
    parameter_path = build_path_to_parameter(DwdObservationDataset.WIND_EXTREME, Resolution.SUBDAILY, period)

    url = reduce(
        urljoin,
        [
            DWD_SERVER,
            DWD_CDC_PATH,
            DWDCDCBase.CLIMATE_OBSERVATIONS.value,
            parameter_path,
        ],
    )

    files_server = list_remote_files_fsspec(url, ttl=CacheExpiry.METAINDEX)

    # Find the one meta file from the files listed on the server
    meta_file_fx3 = _find_meta_file(files_server, url, ["fx3", "beschreibung", "txt"])
    meta_file_fx6 = _find_meta_file(files_server, url, ["fx6", "beschreibung", "txt"])

    try:
        meta_file_fx3 = download_file(meta_file_fx3, ttl=CacheExpiry.METAINDEX)
    except InvalidURL as e:
        raise InvalidURL(f"Error: reading metadata {meta_file_fx3} file failed.") from e

    try:
        meta_file_fx6 = download_file(meta_file_fx6, ttl=CacheExpiry.METAINDEX)
    except InvalidURL as e:
        raise InvalidURL(f"Error: reading metadata {meta_file_fx6} file failed.") from e

    df_fx3 = _read_meta_df(meta_file_fx3)
    df_fx6 = _read_meta_df(meta_file_fx6)

    df_fx6 = df_fx6.loc[df_fx6[Columns.STATION_ID.value].isin(df_fx3[Columns.STATION_ID.value].tolist()), :]

    return pd.concat([df_fx3, df_fx6])


def _create_meta_index_for_1minute_historical_precipitation() -> pd.DataFrame:
    """
    A helping function to create a raw index of metadata for stations_result of the set of
    parameters as given. This raw metadata is then used by other functions. This
    second/alternative function must be used for high resolution data, where the
    metadata is not available as file but instead saved in external files per each
    station.
    - especially for precipitation/1_minute/historical!

    """

    parameter_path = f"{Resolution.MINUTE_1.value}/" f"{DwdObservationDataset.PRECIPITATION.value}/"

    url = reduce(
        urljoin,
        [
            DWD_SERVER,
            DWD_CDC_PATH,
            DWDCDCBase.CLIMATE_OBSERVATIONS.value,
            parameter_path,
            "meta_data/",
        ],
    )

    metadata_file_paths = list_remote_files_fsspec(url, ttl=CacheExpiry.METAINDEX)

    station_ids = [re.findall(STATION_ID_REGEX, file).pop(0) for file in metadata_file_paths]

    meta_index_df = pd.DataFrame(columns=METADATA_COLUMNS)

    with ThreadPoolExecutor() as executor:
        metadata_files = executor.map(_download_metadata_file_for_1minute_precipitation, metadata_file_paths)

    with ThreadPoolExecutor() as executor:
        metadata_dfs = executor.map(_parse_geo_metadata, zip(metadata_files, station_ids))

    meta_index_df = pd.concat([meta_index_df] + list(metadata_dfs), ignore_index=True)

    missing_to_date_index = pd.isnull(meta_index_df[Columns.TO_DATE.value])

    meta_index_df.loc[missing_to_date_index, Columns.TO_DATE.value] = pd.Timestamp(
        dt.date.today() - dt.timedelta(days=1)
    ).strftime("%Y%m%d")

    # Drop empty state column again as it will be merged later on
    meta_index_df = meta_index_df.drop(labels=Columns.STATE.value, axis=1)

    # Make station id str
    meta_index_df[Columns.STATION_ID.value] = meta_index_df[Columns.STATION_ID.value].str.pad(5, "left", "0")

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
        return download_file(metadata_file, ttl=CacheExpiry.NO_CACHE)
    except InvalidURL as e:
        raise InvalidURL(f"Reading metadata {metadata_file} file failed.") from e


def _parse_geo_metadata(metadata_file_and_station_id: Tuple[BytesIO, str]) -> pd.DataFrame:
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

    metadata_geo_filename = f"Metadaten_Geographie_{station_id}.txt"

    zfs = ZipFileSystem(metadata_file, mode="r")

    file = zfs.open(metadata_geo_filename).read()

    df = _parse_zipped_data_into_df(file)

    df = df.rename(columns=str.lower).rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    df[Columns.FROM_DATE.value] = df.loc[0, Columns.FROM_DATE.value]

    df = df.iloc[[-1], :]

    return df.reindex(columns=METADATA_COLUMNS)


def _parse_zipped_data_into_df(file: bytes) -> pd.DataFrame:
    """A wrapper for read_csv of pandas library that has set the typically used
    parameters in the found data of the
    german weather service.

    Args:
        file - the file that will be read

    Return:
        A pandas DataFrame with the read data.

    """
    try:
        file_decoded = file.decode("utf-8")
    except UnicodeDecodeError:
        file_decoded = file.decode("ISO-8859-1")

    return pd.read_csv(
        filepath_or_buffer=StringIO(file_decoded),
        sep=";",
        na_values="-999",
        dtype=str,
        skipinitialspace=True,
    )
