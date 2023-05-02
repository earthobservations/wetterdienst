# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import TYPE_CHECKING, Optional

import polars as pl

from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    DWD_URBAN_DATASETS,
)
from wetterdienst.provider.dwd.observation.metadata.resolution import HIGH_RESOLUTIONS
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from wetterdienst.provider.dwd.observation.metadata.dataset import DwdObservationDataset


STATION_ID_REGEX = r"_(\d{3,5})_"
DATE_RANGE_REGEX = r"_(\d{8}_\d{8})_"


def create_file_list_for_climate_observations(
    station_id: str,
    dataset: "DwdObservationDataset",
    resolution: Resolution,
    period: Period,
    settings: Settings,
    date_range: Optional[str] = None,
) -> pl.Series:
    """
    Function for selecting datafiles (links to archives) for given
    station_ids, parameter, time_resolution and period_type under consideration of a
    created list of files that are
    available online.
    Args:
        station_id: station id for the weather station to ask for data
        dataset: observation measure
        resolution: frequency/granularity of measurement interval
        period: recent or historical files
        date_range:
    Returns:
        List of path's to file
    """
    file_index = create_file_index_for_climate_observations(dataset, resolution, period, settings)

    file_index = file_index.collect()

    file_index = file_index.filter(pl.col("station_id").eq(station_id))

    if date_range:
        file_index = file_index.filter(pl.col("date_range").eq(date_range))

    return file_index.get_column("filename")


def create_file_index_for_climate_observations(
    dataset: "DwdObservationDataset", resolution: Resolution, period: Period, settings: Settings
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
            dataset, resolution, Period.RECENT, "observations_germany/climate_urban", settings
        )
    else:
        file_index = _create_file_index_for_dwd_server(
            dataset, resolution, period, "observations_germany/climate", settings
        )

    file_index = file_index.filter(pl.col("filename").str.ends_with(Extension.ZIP.value))

    file_index = file_index.with_columns(
        pl.col("filename")
        .str.split("/")
        .arr.last()
        .str.extract(STATION_ID_REGEX, 1)
        .str.rjust(5, "0")
        .alias("station_id")
    )

    file_index = file_index.filter(pl.col("station_id").is_not_null() & pl.col("station_id").ne("00000"))

    if resolution in HIGH_RESOLUTIONS and period == Period.HISTORICAL:
        # Date range string for additional filtering of historical files
        file_index = file_index.with_columns(pl.col("filename").str.extract(DATE_RANGE_REGEX).alias("date_range"))
        file_index = file_index.with_columns(
            pl.col("date_range")
            .str.split("_")
            .arr.first()
            .str.strptime(datatype=pl.Datetime, fmt=DatetimeFormat.YMD.value)
            .dt.replace_time_zone("Europe/Berlin")
            .alias(Columns.FROM_DATE.value),
            pl.col("date_range")
            .str.split("_")
            .arr.last()
            .str.strptime(datatype=pl.Datetime, fmt=DatetimeFormat.YMD.value)
            .dt.replace_time_zone("Europe/Berlin")
            .map(lambda dates: dates + pl.duration(days=1))
            .alias(Columns.TO_DATE.value),
        )

        file_index = file_index.with_columns(
            pl.when(pl.col(Columns.FROM_DATE.value) > pl.col(Columns.TO_DATE.value))
            .then(pl.col(Columns.FROM_DATE.value).min())
            .otherwise(pl.col(Columns.FROM_DATE.value)),
            pl.when(pl.col(Columns.FROM_DATE.value) > pl.col(Columns.TO_DATE.value))
            .then(pl.col(Columns.TO_DATE.value).min())
            .otherwise(pl.col(Columns.TO_DATE.value)),
        )

    return file_index.sort(by=[pl.col("station_id"), pl.col("filename")])
