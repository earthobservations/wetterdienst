# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Metadata for DWD climate observations."""

from __future__ import annotations

import datetime as dt
import logging
from io import StringIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.exceptions import MetaFileNotFoundError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation.fileindex import (
    _build_url_from_dataset_and_period,
    _create_file_index_for_dwd_server,
)
from wetterdienst.provider.dwd.observation.metadata import DWD_URBAN_DATASETS, DwdObservationMetadata
from wetterdienst.util.network import File, download_file, download_files

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

DWD_COLUMN_NAMES_MAPPING = {
    "column_1": "station_id",
    "column_2": "start_date",
    "column_3": "end_date",
    "column_4": "height",
    "column_5": "latitude",
    "column_6": "longitude",
    "column_7": "name",
    "column_8": "state",
}


def create_meta_index_for_climate_observations(
    dataset: DatasetModel,
    period: Period,
    settings: Settings,
) -> pl.LazyFrame:
    """Create metadata DataFrame for climate observations."""
    cond1 = dataset == DwdObservationMetadata["minute_1"]["precipitation"] and period == Period.HISTORICAL
    cond2 = dataset == DwdObservationMetadata["subdaily"]["wind_extreme"]
    cond3 = dataset in DWD_URBAN_DATASETS
    if cond1:
        meta_index = _create_meta_index_for_1minute_historical_precipitation(settings)
    elif cond2:
        meta_index = _create_meta_index_for_subdaily_extreme_wind(period, settings)
    elif cond3:
        meta_index = _create_meta_index_for_climate_observations(dataset, Period.RECENT, settings)
    else:
        meta_index = _create_meta_index_for_climate_observations(dataset, period, settings)
    # If no state column available, take state information from daily historical
    # precipitation
    if cond1:
        mdp = _create_meta_index_for_climate_observations(
            DwdObservationMetadata["daily"]["precipitation_more"],
            Period.HISTORICAL,
            settings=settings,
        )
        meta_index = meta_index.join(
            other=mdp.select(["station_id", "state"]),
            on=["station_id"],
            how="left",
        )
    meta_index = meta_index.sort(by=["station_id"])
    return meta_index.select(
        pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
        pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
        "station_id",
        pl.col("start_date").str.to_datetime("%Y%m%d", time_zone="UTC"),
        pl.col("end_date").str.to_datetime("%Y%m%d", time_zone="UTC"),
        pl.col("height").cast(pl.Float64),
        pl.col("latitude").cast(pl.Float64),
        pl.col("longitude").cast(pl.Float64),
        "name",
        "state",
    )


def _create_meta_index_for_climate_observations(
    dataset: DatasetModel,
    period: Period,
    settings: Settings,
) -> pl.LazyFrame:
    """Create metadata DataFrame for climate observations."""
    url = _build_url_from_dataset_and_period(dataset, period)
    df_files = _create_file_index_for_dwd_server(url, settings=settings, ttl=CacheExpiry.METAINDEX)
    # TODO: remove workaround once station list at https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/5_minutes/precipitation/historical/2022/ is removed  # noqa: E501
    if dataset == DwdObservationMetadata.minute_5.precipitation and period == Period.HISTORICAL:
        df_files = df_files.filter(pl.col("url").str.split("/").list.get(-2) != "2022")
    # Find the one meta file from the files listed on the server
    df_files = df_files.filter(pl.col("filename").str.to_lowercase().str.contains(r".*beschreibung.*\.txt"))
    df_files = df_files.collect()
    if df_files.is_empty():
        msg = f"No meta file was found amongst the files at {url}."
        raise MetaFileNotFoundError(msg)
    meta_file = df_files.get_column("url").to_list()[0]
    file = download_file(
        url=meta_file,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.METAINDEX,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
    )
    file.raise_if_exception()
    return _read_meta_df(file)


def _read_meta_df(file: File) -> pl.LazyFrame:
    """Read meta file into DataFrame."""
    lines = file.content.readlines()[2:]
    first = lines[0].decode("latin-1")
    if first.startswith("SP"):
        # Skip first line if it contains a header
        lines = lines[1:]
    lines = [line.decode("latin-1") for line in lines]
    lines_split = [line.split() for line in lines]
    # TODO: check if this is still necessary
    # drop last column if "Frei"
    lines_split = [line[:-1] if line[-1] == "Frei" else line for line in lines_split]
    lines_csv = [_create_csv_line(line) for line in lines_split]
    text = "\n".join(lines_csv)
    df = pl.read_csv(StringIO(text), has_header=False, infer_schema_length=0)
    return df.rename(mapping=lambda col: DWD_COLUMN_NAMES_MAPPING.get(col, col)).lazy()


def _create_csv_line(columns: list[str]) -> str:
    """Create a CSV line from a list of columns.

    The length of the columns list is checked and if it is greater than 8, the station name is
    concatenated from the last columns and the columns are adjusted accordingly.
    """
    num_columns = len(columns)
    if num_columns > 8:
        excess_columns = num_columns - 8
        station_name = " ".join(columns[-excess_columns - 2 : -1])
        columns = [*columns[: -excess_columns - 2], station_name, *columns[-1:]]
    if num_columns == 7:
        # if there are only 7 columns, fill up to_date with empty string
        columns.insert(2, "")
    station_name = columns[-2]
    if "," in station_name:
        columns[-2] = f'"{station_name}"'
    return ",".join(columns)


def _create_meta_index_for_subdaily_extreme_wind(period: Period, settings: Settings) -> pl.LazyFrame:
    """Create metadata DataFrame for subdaily wind extreme."""
    dataset = DwdObservationMetadata.subdaily.wind_extreme
    url = _build_url_from_dataset_and_period(dataset, period)
    df_files = _create_file_index_for_dwd_server(url, settings, CacheExpiry.TWELVE_HOURS)
    df_files = df_files.filter(pl.col("filename").str.to_lowercase().str.contains(r".*beschreibung.*\.txt"))
    # Find the one meta file from the files listed on the server
    meta_file_fx3 = (
        df_files.filter(pl.col("filename").str.to_lowercase().str.contains("fx3", literal=True))
        .collect()
        .get_column("url")
        .first()
    )
    meta_file_fx6 = (
        df_files.filter(pl.col("filename").str.to_lowercase().str.contains("fx6", literal=True))
        .collect()
        .get_column("url")
        .first()
    )
    file_fx3 = download_file(
        url=meta_file_fx3,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.METAINDEX,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
    )
    file_fx6 = download_file(
        url=meta_file_fx6,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.METAINDEX,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
    )
    df_fx3 = _read_meta_df(file_fx3)
    df_fx6 = _read_meta_df(file_fx6)
    df_fx6 = df_fx6.join(df_fx3.select("station_id"), on=["station_id"], how="inner")
    return pl.concat([df_fx3, df_fx6])


def _create_meta_index_for_1minute_historical_precipitation(settings: Settings) -> pl.LazyFrame:
    """Create metadata DataFrame for 1minute precipitation historical."""
    url = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/precipitation/meta_data/"
    )
    df_files = _create_file_index_for_dwd_server(url, settings=settings, ttl=CacheExpiry.METAINDEX)
    df_files = df_files.with_columns(
        pl.col("filename").str.split("_").list.last().str.split(".").list.first().alias("station_id"),
    )
    urls_and_station_ids = df_files.select(["url", "station_id"]).collect().rows()
    log.info(f"Downloading {len(urls_and_station_ids)} files for 1minute precipitation historical metadata.")
    remote_files = [url for url, _ in urls_and_station_ids]
    files = download_files(
        urls=remote_files,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.NO_CACHE,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
    )
    dfs = [
        _parse_geo_metadata(file=file, station_id=station_id)
        for file, (_, station_id) in zip(files, urls_and_station_ids, strict=False)
    ]
    df = pl.concat(dfs)
    df = df.with_columns(
        pl.when(pl.col("end_date").str.strip_chars().eq(""))
        .then(pl.lit((dt.datetime.now(ZoneInfo("UTC")).date() - dt.timedelta(days=1)).strftime("%Y%m%d")))
        .otherwise(pl.col("end_date"))
        .alias("end_date"),
    )
    df = df.with_columns(pl.all().str.strip_chars())
    # Make station id str
    return df.with_columns(pl.col("station_id").cast(str).str.pad_start(5, "0"))


def _parse_geo_metadata(file: File, station_id: str) -> pl.LazyFrame:
    """Parse metadata file into DataFrame."""
    zfs = ZipFileSystem(file.content, mode="r")
    file = zfs.open(f"Metadaten_Geographie_{station_id}.txt").read()
    df = _parse_zipped_data_into_df(file)
    df = df.rename(
        mapping={
            "Stations_id": "station_id",
            "Stationshoehe": "height",
            "Geogr.Breite": "latitude",
            "Geogr.Laenge": "longitude",
            "von_datum": "start_date",
            "bis_datum": "end_date",
            "Stationsname": "name",
        },
    )
    df = df.with_columns(pl.col("start_date").first().cast(str), pl.col("end_date").cast(str))
    df = df.last()
    return df.select(
        pl.col("station_id"),
        pl.col("start_date"),
        pl.col("end_date"),
        pl.col("height"),
        pl.col("latitude"),
        pl.col("longitude"),
        pl.col("name"),
    )


def _parse_zipped_data_into_df(file: bytes) -> pl.LazyFrame:
    """Parse zipped data into DataFrame."""
    try:
        file_decoded = file.decode("utf-8")
    except UnicodeDecodeError:
        file_decoded = file.decode("ISO-8859-1")
    return pl.read_csv(
        source=StringIO(file_decoded),
        separator=";",
        null_values=["-999"],
    ).lazy()
