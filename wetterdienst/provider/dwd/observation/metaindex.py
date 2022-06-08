# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO, StringIO
from typing import List, Tuple

import polars as pl
from fsspec.implementations.zip import ZipFileSystem
from requests.exceptions import InvalidURL

from wetterdienst.exceptions import MetaFileNotFound
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.fileindex import build_path_to_parameter
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    DWD_URBAN_DATASETS,
    DwdObservationDataset,
)
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file, list_remote_files_fsspec

DWD_COLUMN_NAMES_MAPPING = {
    "0": Columns.STATION_ID.value,
    "1": Columns.FROM_DATE.value,
    "2": Columns.TO_DATE.value,
    "3": Columns.HEIGHT.value,
    "4": Columns.LATITUDE.value,
    "5": Columns.LONGITUDE.value,
    "6": Columns.NAME.value,
    "7": Columns.STATE.value,
}

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
    dataset: DwdObservationDataset, resolution: Resolution, period: Period, settings: Settings
) -> pl.LazyFrame:
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
        meta_index = _create_meta_index_for_1minute_historical_precipitation(settings)
    elif cond2:
        meta_index = _create_meta_index_for_subdaily_extreme_wind(period, settings)
    elif cond3:
        meta_index = _create_meta_index_for_climate_observations(dataset, resolution, Period.RECENT, settings)
    else:
        meta_index = _create_meta_index_for_climate_observations(dataset, resolution, period, settings)

    # If no state column available, take state information from daily historical
    # precipitation
    if cond1:
        mdp = _create_meta_index_for_climate_observations(
            DwdObservationDataset.PRECIPITATION_MORE, Resolution.DAILY, Period.HISTORICAL, settings=settings
        )

        meta_index = meta_index.join(
            other=mdp.select([Columns.STATION_ID.value, Columns.STATE.value]),
            on=[Columns.STATION_ID.value],
            how="left",
        )

    meta_index = meta_index.with_columns(
        pl.col(Columns.FROM_DATE.value).str.strptime(pl.Datetime, "%Y%m%d"),
        pl.col(Columns.TO_DATE.value).str.strptime(pl.Datetime, "%Y%m%d"),
        pl.col(Columns.HEIGHT.value).cast(pl.Float64),
        pl.col(Columns.LATITUDE.value).cast(pl.Float64),
        pl.col(Columns.LONGITUDE.value).cast(pl.Float64),
    )

    return meta_index.sort(by=[pl.col(Columns.STATION_ID.value)])


def _create_meta_index_for_climate_observations(
    dataset: DwdObservationDataset, resolution: Resolution, period: Period, settings: Settings
) -> pl.LazyFrame:
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
        dwd_cdc_base = "observations_germany/climate_urban/"
    else:
        dwd_cdc_base = "observations_germany/climate/"

    url = f"https://opendata.dwd.de/climate_environment/CDC/{dwd_cdc_base}/{parameter_path}"

    files_server = list_remote_files_fsspec(url, settings=settings, ttl=CacheExpiry.METAINDEX)

    # Find the one meta file from the files listed on the server
    meta_file = _find_meta_file(files_server, url, ["beschreibung", "txt"])

    try:
        file = download_file(meta_file, settings=settings, ttl=CacheExpiry.METAINDEX)
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


def _read_meta_df(file: BytesIO) -> pl.LazyFrame:
    """Read metadata into DataFrame
    :param file: metadata file loaded in bytes
    :return: DataFrame with Stations
    """
    df = pl.read_csv(source=file, skip_rows=2, encoding="latin-1", has_header=False).lazy()

    colspecs = [
        (0, 5),
        (6, 8),
        (15, 9),
        (23, 15),
        (38, 12),
        (50, 10),
        (60, 42),
        (102, 98),
    ]

    df = df.with_columns(
        [
            pl.col("column_1").str.slice(slice_tuple[0], slice_tuple[1]).str.strip().alias(str(i))
            for i, slice_tuple in enumerate(colspecs)
        ]
    ).drop("column_1")

    return df.rename(mapping={k: v for k, v in DWD_COLUMN_NAMES_MAPPING.items() if k in df.columns})


def _create_meta_index_for_subdaily_extreme_wind(period: Period, settings: Settings) -> pl.LazyFrame:
    """Create metadata DataFrame for subdaily wind extreme

    :param period: period for which metadata is acquired
    :return: pandas.DataFrame with combined information for both 3hourly (fx3) and 6hourly (fx6) wind extremes
    """
    parameter_path = build_path_to_parameter(DwdObservationDataset.WIND_EXTREME, Resolution.SUBDAILY, period)

    url = f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/{parameter_path}"

    files_server = list_remote_files_fsspec(url, settings=settings, ttl=CacheExpiry.METAINDEX)

    # Find the one meta file from the files listed on the server
    meta_file_fx3 = _find_meta_file(files_server, url, ["fx3", "beschreibung", "txt"])
    meta_file_fx6 = _find_meta_file(files_server, url, ["fx6", "beschreibung", "txt"])

    try:
        meta_file_fx3 = download_file(meta_file_fx3, settings=settings, ttl=CacheExpiry.METAINDEX)
    except InvalidURL as e:
        raise InvalidURL(f"Error: reading metadata {meta_file_fx3} file failed.") from e

    try:
        meta_file_fx6 = download_file(meta_file_fx6, settings=settings, ttl=CacheExpiry.METAINDEX)
    except InvalidURL as e:
        raise InvalidURL(f"Error: reading metadata {meta_file_fx6} file failed.") from e

    df_fx3 = _read_meta_df(meta_file_fx3)
    df_fx6 = _read_meta_df(meta_file_fx6)

    df_fx6 = df_fx6.join(df_fx3.get_column(Columns.STATION_ID.value), on=[Columns.STATION_ID.value], how="inner")

    return pl.concat([df_fx3, df_fx6])


def _create_meta_index_for_1minute_historical_precipitation(settings: Settings) -> pl.LazyFrame:
    """
    A helping function to create a raw index of metadata for stations_result of the set of
    parameters as given. This raw metadata is then used by other functions. This
    second/alternative function must be used for high resolution data, where the
    metadata is not available as file but instead saved in external files per each
    station.
    - especially for precipitation/1_minute/historical!

    """
    parameter_path = f"{Resolution.MINUTE_1.value}/" f"{DwdObservationDataset.PRECIPITATION.value}/"
    url = f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/{parameter_path}/meta_data/"
    metadata_file_paths = list_remote_files_fsspec(url, settings=settings, ttl=CacheExpiry.METAINDEX)
    station_ids = [re.findall(STATION_ID_REGEX, file).pop(0) for file in metadata_file_paths]

    with ThreadPoolExecutor() as executor:
        metadata_files = executor.map(
            partial(_download_metadata_file_for_1minute_precipitation, settings=settings), metadata_file_paths
        )

    metadata_dfs = [_parse_geo_metadata((file, station_id)) for file, station_id in zip(metadata_files, station_ids)]

    meta_index_df = pl.concat(list(metadata_dfs))

    meta_index_df = meta_index_df.with_columns(
        pl.when(pl.col(Columns.TO_DATE.value).str.strip() == "")
        .then((dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d"))
        .otherwise(pl.col(Columns.TO_DATE.value))
        .alias(Columns.TO_DATE.value)
    )

    # Drop empty state column again as it will be merged later on
    meta_index_df = meta_index_df.select(pl.exclude(Columns.STATE.value))

    # Make station id str
    return meta_index_df.with_columns(pl.col(Columns.STATION_ID.value).cast(str).str.rjust(5, "0"))


def _download_metadata_file_for_1minute_precipitation(metadata_file: str, settings: Settings) -> BytesIO:
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
        return download_file(metadata_file, settings=settings, ttl=CacheExpiry.NO_CACHE)
    except InvalidURL as e:
        raise InvalidURL(f"Reading metadata {metadata_file} file failed.") from e


def _parse_geo_metadata(metadata_file_and_station_id: Tuple[BytesIO, str]) -> pl.LazyFrame:
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

    zfs = ZipFileSystem(metadata_file, mode="r")

    file = zfs.open(f"Metadaten_Geographie_{station_id}.txt").read()

    df = _parse_zipped_data_into_df(file)

    df = df.rename(
        mapping={
            "Stations_id": Columns.STATION_ID.value,
            "Stationshoehe": Columns.HEIGHT.value,
            "Geogr.Breite": Columns.LATITUDE.value,
            "Geogr.Laenge": Columns.LONGITUDE.value,
            "von_datum": Columns.FROM_DATE.value,
            "bis_datum": Columns.TO_DATE.value,
            "Stationsname": Columns.NAME.value,
        }
    )

    df = df.with_columns(pl.col(Columns.FROM_DATE.value).first().cast(str), pl.col(Columns.TO_DATE.value).cast(str))

    df = df.last()

    return df.select([col for col in METADATA_COLUMNS if col != Columns.STATE.value])


def _parse_zipped_data_into_df(file: bytes) -> pl.LazyFrame:
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

    return pl.read_csv(
        source=StringIO(file_decoded),
        separator=";",
        null_values=["-999"],
    ).lazy()
