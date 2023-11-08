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

from wetterdienst.exceptions import MetaFileNotFoundError
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
from wetterdienst.util.polars_util import read_fwf_from_df

DWD_COLUMN_NAMES_MAPPING = {
    "column_0": Columns.STATION_ID.value,
    "column_1": Columns.START_DATE.value,
    "column_2": Columns.END_DATE.value,
    "column_3": Columns.HEIGHT.value,
    "column_4": Columns.LATITUDE.value,
    "column_5": Columns.LONGITUDE.value,
    "column_6": Columns.NAME.value,
    "column_7": Columns.STATE.value,
}

METADATA_COLUMNS = [
    Columns.STATION_ID.value,
    Columns.START_DATE.value,
    Columns.END_DATE.value,
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
        pl.col(Columns.START_DATE.value).str.to_datetime("%Y%m%d"),
        pl.col(Columns.END_DATE.value).str.to_datetime("%Y%m%d"),
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
    remote_files = list_remote_files_fsspec(url, settings=settings, ttl=CacheExpiry.METAINDEX)
    # Find the one meta file from the files listed on the server
    meta_file = _find_meta_file(remote_files, url, ["beschreibung", "txt"])
    payload = download_file(meta_file, settings=settings, ttl=CacheExpiry.METAINDEX)
    return _read_meta_df(payload)


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
        MetaFileNotFoundError - for the case no file was found
    """
    for file in files:
        file_strings = file.split("/")[-1].lower().replace(".", "_").split("_")
        if set(file_strings).issuperset(strings):
            return file
    else:
        raise MetaFileNotFoundError(f"No meta file was found amongst the files at {url}.")


def _read_meta_df(file: BytesIO) -> pl.LazyFrame:
    """Read metadata into DataFrame
    :param file: metadata file loaded in bytes
    :return: DataFrame with Stations
    """
    lines = file.readlines()[2:]
    first = lines[0].decode("latin-1").strip()
    if first.startswith("SP"):
        # Skip first line if it contains a header
        lines = lines[1:]
    content = BytesIO(b"\n".join(lines))
    df = pl.read_csv(source=content, encoding="latin-1", has_header=False, truncate_ragged_lines=True)
    column_specs = (
        (0, 5),
        (6, 14),
        (15, 24),
        (23, 38),
        (38, 50),
        (50, 60),
        (60, 102),
        (102, 200),
    )
    df = read_fwf_from_df(df, column_specs)
    return df.rename(mapping={k: v for k, v in DWD_COLUMN_NAMES_MAPPING.items() if k in df.columns}).lazy()


def _create_meta_index_for_subdaily_extreme_wind(period: Period, settings: Settings) -> pl.LazyFrame:
    """Create metadata DataFrame for subdaily wind extreme

    :param period: period for which metadata is acquired
    :return: pandas.DataFrame with combined information for both 3hourly (fx3) and 6hourly (fx6) wind extremes
    """
    parameter_path = build_path_to_parameter(DwdObservationDataset.WIND_EXTREME, Resolution.SUBDAILY, period)
    url = f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/{parameter_path}"
    remote_files = list_remote_files_fsspec(url, settings=settings, ttl=CacheExpiry.METAINDEX)
    # Find the one meta file from the files listed on the server
    meta_file_fx3 = _find_meta_file(remote_files, url, ["fx3", "beschreibung", "txt"])
    meta_file_fx6 = _find_meta_file(remote_files, url, ["fx6", "beschreibung", "txt"])
    payload_fx3 = download_file(meta_file_fx3, settings=settings, ttl=CacheExpiry.METAINDEX)
    payload_fx6 = download_file(meta_file_fx6, settings=settings, ttl=CacheExpiry.METAINDEX)
    df_fx3 = _read_meta_df(payload_fx3)
    df_fx6 = _read_meta_df(payload_fx6)
    df_fx6 = df_fx6.join(df_fx3.select(Columns.STATION_ID.value), on=[Columns.STATION_ID.value], how="inner")
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
            partial(download_file, settings=settings, ttl=CacheExpiry.NO_CACHE), metadata_file_paths
        )

    metadata_dfs = [_parse_geo_metadata((file, station_id)) for file, station_id in zip(metadata_files, station_ids)]

    meta_index_df = pl.concat(list(metadata_dfs))

    meta_index_df = meta_index_df.with_columns(
        pl.when(pl.col(Columns.END_DATE.value).str.strip_chars().eq(""))
        .then(pl.lit((dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")))
        .otherwise(pl.col(Columns.END_DATE.value))
        .alias(Columns.END_DATE.value)
    )

    # Drop empty state column again as it will be merged later on
    meta_index_df = meta_index_df.select(pl.exclude(Columns.STATE.value))

    # Make station id str
    return meta_index_df.with_columns(pl.col(Columns.STATION_ID.value).cast(str).str.rjust(5, "0"))


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
            "von_datum": Columns.START_DATE.value,
            "bis_datum": Columns.END_DATE.value,
            "Stationsname": Columns.NAME.value,
        }
    )

    df = df.with_columns(pl.col(Columns.START_DATE.value).first().cast(str), pl.col(Columns.END_DATE.value).cast(str))

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
