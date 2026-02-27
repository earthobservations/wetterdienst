# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""File index for DWD climate derived."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.extension import Extension
from wetterdienst.provider.dwd.derived.metadata import (
    RADIATION_DATASETS,
    SOIL_DATASETS,
    SUNSHINE_DURATION_DATASETS,
    TECHNICAL_DATASETS,
)
from wetterdienst.provider.dwd.observation.fileindex import _create_file_index_for_dwd_server

if TYPE_CHECKING:
    from wetterdienst.metadata.period import Period
    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.settings import Settings


STATION_ID_REGEX = r"_(\d{3,5})_"
SOIL_ID_REGEX = r"_(\d{3,5})."
DATE_RANGE_REGEX = r"_(\d{8}_\d{8})_"


def create_file_list_for_climate_derived(
    station_id: str,
    dataset: DatasetModel,
    period: Period,
    settings: Settings,
) -> pl.Series:
    """Create a list of files for a given station id, dataset and period.

    Date ranges are used to reduce the number of files to be downloaded based on the date range of the files.
    This is useful for hourly or more fine-grained data, where the number of files can be very large.
    """
    file_index = create_file_index_for_climate_derived(dataset, period, settings)
    file_index = file_index.filter(pl.col("station_id").eq(station_id))
    return file_index.collect().get_column("url")


def create_file_index_for_climate_derived(
    dataset: DatasetModel,
    period: Period,
    settings: Settings,
) -> pl.LazyFrame:
    """Create a file index for a given dataset and period."""
    url = _build_url_from_dataset_and_period(dataset, period)
    df_files = _create_file_index_for_dwd_server(url, settings, CacheExpiry.TWELVE_HOURS)
    # regarding the first filter (_), DWD has published some temporary files in the end of 2024
    # within https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/extreme_wind/now/
    # which are not valid files

    df_files = df_files.filter(pl.col("filename").str.split("/").list.last().str.starts_with("_").not_())

    if dataset in SOIL_DATASETS:
        df_files = df_files.filter(pl.col("filename").str.ends_with(Extension.TXT_GZ.value))
        station_regex = SOIL_ID_REGEX
    elif dataset in (RADIATION_DATASETS + SUNSHINE_DURATION_DATASETS):
        df_files = df_files.filter(pl.col("filename").str.ends_with(Extension.ZIP.value))
        station_regex = STATION_ID_REGEX
    elif dataset in TECHNICAL_DATASETS:
        df_files = df_files.filter(pl.col("filename").str.ends_with(Extension.CSV.value))
        station_regex = STATION_ID_REGEX

    df_files = df_files.with_columns(
        pl.col("filename")
        .str.split("/")
        .list.last()
        .str.extract(station_regex, 1)
        .str.pad_start(5, "0")
        .alias("station_id"),
    )
    df_files = df_files.filter(pl.col("station_id").is_not_null() & pl.col("station_id").ne("00000"))
    return df_files.sort(by=[pl.col("station_id"), pl.col("filename")])


def _build_url_from_dataset_and_period(
    dataset: DatasetModel,
    period: Period,
) -> str:
    """Build the URL for a given dataset."""
    if dataset in RADIATION_DATASETS:
        return f"https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/{dataset.name_original}/{period.value}"
    if dataset in TECHNICAL_DATASETS:
        base_url = (
            f"https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/{dataset.resolution.value.value}"
        )
        dataset_name = dataset.name
        if dataset_name == "heating_degreedays":
            return f"{base_url}/heating_degreedays/hdd_3807/{period.value}"
        if dataset_name == "cooling_degreehours_13":
            return f"{base_url}/cooling_degreehours/cdh_13/{period.value}"
        if dataset_name == "cooling_degreehours_16":
            return f"{base_url}/cooling_degreehours/cdh_16/{period.value}"
        if dataset_name == "cooling_degreehours_18":
            return f"{base_url}/cooling_degreehours/cdh_18/{period.value}"
        if dataset_name == "climate_correction_factor":
            return f"{base_url}/climate_correction_factor/{period.value}"
    elif dataset in SOIL_DATASETS:
        return f"https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/{dataset.resolution.value.value}/{period.value}/"

    msg = f"Unknown dataset {dataset}."
    raise ValueError(msg)
