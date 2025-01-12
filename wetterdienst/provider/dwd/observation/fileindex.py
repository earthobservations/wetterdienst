# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.metadata import DatetimeFormat
from wetterdienst.provider.dwd.observation.metadata import DWD_URBAN_DATASETS, HIGH_RESOLUTIONS, DwdObservationMetadata
from wetterdienst.util.network import list_remote_files_fsspec

if TYPE_CHECKING:
    from wetterdienst.core.timeseries.metadata import DatasetModel
    from wetterdienst.settings import Settings

STATION_ID_REGEX = r"_(\d{3,5})_"
DATE_RANGE_REGEX = r"_(\d{8}_\d{8})_"


def create_file_list_for_climate_observations(
    station_id: str,
    dataset: DatasetModel,
    period: Period,
    settings: Settings,
    date_ranges: list[str] | None = None,
) -> pl.Series:
    """Create a list of files for a given station id, dataset and period.

    Date ranges are used to reduce the number of files to be downloaded based on the date range of the files.
    This is useful for hourly or more fine-grained data, where the number of files can be very large.
    """
    file_index = create_file_index_for_climate_observations(dataset, period, settings)
    file_index = file_index.filter(pl.col("station_id").eq(station_id))
    if date_ranges:
        file_index = file_index.filter(pl.col("date_range").is_in(date_ranges))
    return file_index.collect().get_column("filename")


def create_file_index_for_climate_observations(
    dataset: DatasetModel,
    period: Period,
    settings: Settings,
) -> pl.LazyFrame:
    """
    Function (cached) to create a file index of the DWD station data. The file index
    is created for an individual set of parameters.
    Args:
        dataset: parameter of Parameter enumeration
        resolution: time resolution of TimeResolution enumeration
        period: period type of PeriodType enumeration
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    if dataset in DWD_URBAN_DATASETS:
        file_index = _create_file_index_for_dwd_server(
            dataset,
            Period.RECENT,
            "observations_germany/climate_urban",
            settings,
        )
    else:
        file_index = _create_file_index_for_dwd_server(
            dataset,
            period,
            "observations_germany/climate",
            settings,
        )

    # regarding the first filter (_), DWD has published some temporary files in the end of 2024
    # within https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/now/
    # which are not valid files
    file_index = file_index.filter(
        pl.col("filename").str.split("/").list.last().str.starts_with("_").not_(),
        pl.col("filename").str.ends_with(Extension.ZIP.value),
    )

    file_index = file_index.with_columns(
        pl.col("filename")
        .str.split("/")
        .list.last()
        .str.extract(STATION_ID_REGEX, 1)
        .str.pad_start(5, "0")
        .alias("station_id"),
    )

    file_index = file_index.filter(pl.col("station_id").is_not_null() & pl.col("station_id").ne("00000"))

    if dataset.resolution.value in HIGH_RESOLUTIONS and period == Period.HISTORICAL:
        # Date range string for additional filtering of historical files
        file_index = file_index.with_columns(pl.col("filename").str.extract(DATE_RANGE_REGEX).alias("date_range"))
        file_index = file_index.with_columns(
            pl.col("date_range")
            .str.split("_")
            .list.first()
            .str.to_datetime(DatetimeFormat.YMD.value)
            .dt.replace_time_zone("Europe/Berlin")
            .alias(Columns.START_DATE.value),
            pl.col("date_range")
            .str.split("_")
            .list.last()
            .str.to_datetime(DatetimeFormat.YMD.value)
            .dt.replace_time_zone("Europe/Berlin")
            .map_batches(lambda dates: dates + dt.timedelta(days=1))
            .alias(Columns.END_DATE.value),
        )

        file_index = file_index.with_columns(
            pl.when(pl.col(Columns.START_DATE.value) > pl.col(Columns.END_DATE.value))
            .then(pl.col(Columns.START_DATE.value).min())
            .otherwise(pl.col(Columns.START_DATE.value)),
            pl.when(pl.col(Columns.START_DATE.value) > pl.col(Columns.END_DATE.value))
            .then(pl.col(Columns.END_DATE.value).min())
            .otherwise(pl.col(Columns.END_DATE.value)),
        )

    return file_index.sort(by=[pl.col("station_id"), pl.col("filename")])


def _create_file_index_for_dwd_server(
    dataset: DatasetModel,
    period: Period,
    cdc_base: str,
    settings: Settings,
) -> pl.LazyFrame:
    """
    Function to create a file index of the DWD station data, which usually is shipped as
    zipped/archived data. The file index is created for an individual set of parameters.
    Args:
        dataset: dwd dataset enumeration
        resolution: time resolution of TimeResolution enumeration
        period: period type of PeriodType enumeration
        cdc_base: base path e.g. climate_observations/germany
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    parameter_path = build_path_to_parameter(dataset, period)

    url = f"https://opendata.dwd.de/climate_environment/CDC/{cdc_base}/{parameter_path}"

    files_server = list_remote_files_fsspec(url, settings=settings, ttl=CacheExpiry.TWELVE_HOURS)

    if not files_server:
        raise FileNotFoundError(f"url {url} does not have a list of files")

    return pl.DataFrame(files_server, schema={"filename": pl.String}, orient="col").lazy()


def build_path_to_parameter(
    dataset: DatasetModel,
    period: Period,
) -> str:
    """
    Function to build a indexing file path
    Args:
        dataset: observation measure
        resolution: frequency/granularity of measurement interval
        period: recent or historical files

    Returns:
        indexing file path relative to climate observation path
    """
    if dataset in (
        DwdObservationMetadata.hourly.solar,
        DwdObservationMetadata.daily.solar,
    ):
        return f"{dataset.resolution.value.value}/{dataset.name_original}/"
    elif dataset in DWD_URBAN_DATASETS:
        return f"{dataset.resolution.value.value}/{dataset.name_original[6:]}/{period.value}/"
    else:
        return f"{dataset.resolution.value.value}/{dataset.name_original}/{period.value}/"
