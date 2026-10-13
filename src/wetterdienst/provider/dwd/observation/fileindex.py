# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""File index for DWD climate observations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.metadata import (
    DWD_URBAN_DATASETS,
    DWD_URBAN_DATASETS_WITHOUT_PERIOD_DIRECTORIES,
    HIGH_RESOLUTIONS,
    DwdObservationMetadata,
)
from wetterdienst.util.network import list_remote_files_fsspec

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.settings import Settings

STATION_ID_REGEX = r"_(\d{3,5})_"
DATE_RANGE_REGEX = r"_(\d{8}_\d{8})_"
#: the 1-, 5- and 10-minute stamps are MEZ before this year and UTC from it
MEZ_UNTIL_YEAR = 2000


def is_mez_file(filename: str) -> bool:
    """Tell whether the stamps of a historical 1-, 5- or 10-minute file are MEZ, the fixed UTC+1, not UTC.

    The file as a whole is one or the other, by the first day its name gives: the files of 2000 and later are
    UTC, those that begin before are MEZ. The year of a stamp does not tell, as the files meet at the turn of
    the year with an overlap: the 10-minute files of 2000 begin at 23:00 UTC on 1999-12-31 (stamp 199912312300),
    and the wind file of 1999 holds MEZ stamps into 2000-01-01 00:50 (GH-2815).
    """
    match = re.search(DATE_RANGE_REGEX, filename)
    return match is not None and int(match.group(1)[:4]) < MEZ_UNTIL_YEAR


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
    result = file_index.collect(background=False)
    if not isinstance(result, pl.DataFrame):
        msg = "Expected DataFrame from collect()"
        raise TypeError(msg)
    return result.get_column("url")


def create_file_index_for_climate_observations(
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
    df_files = df_files.filter(
        pl.col("filename").str.split("/").list.last().str.starts_with("_").not_(),
        pl.col("filename").str.ends_with(Extension.ZIP.value),
    )
    df_files = df_files.with_columns(
        pl.col("filename")
        .str.split("/")
        .list.last()
        .str.extract(STATION_ID_REGEX, 1)
        .str.pad_start(5, "0")
        .alias("station_id"),
    )
    df_files = df_files.filter(pl.col("station_id").is_not_null() & pl.col("station_id").ne("00000"))
    if dataset.resolution.value in HIGH_RESOLUTIONS and period == Period.HISTORICAL:
        # Date range string for additional filtering of historical files
        df_files = df_files.with_columns(pl.col("filename").str.extract(DATE_RANGE_REGEX).alias("date_range"))
        # the file name's days are days of the stamps in the file: UTC from 2000, MEZ (the fixed UTC+1, never
        # Europe/Berlin with its summer time) before, which the values shift to UTC after reading (GH-2811)
        first_day = pl.col("date_range").str.split("_").list.first().str.to_datetime("%Y%m%d")
        last_day = pl.col("date_range").str.split("_").list.last().str.to_datetime("%Y%m%d")
        start = _midnight_in_utc(first_day)
        end = _midnight_in_utc(last_day, days=1)
        # the files of 1999 and of 2000 meet in an hour that both can hold (GH-2815): the 10 minute files of 2000
        # begin with the six stamps 23:00 to 23:50 UTC of 1999-12-31 (the wind file of 1999 ends with the same
        # instants as MEZ 00:00 to 00:50), and the 1- and 5-minute files of December 1999 hold stamps past their
        # MEZ midnight (1-minute: up to 00:59 MEZ, 5-minute: 00:00 MEZ), which are 23:00 to 23:59 UTC. The files
        # of 2000 begin at 00:00 UTC, but those of 10 minutes at 23:00 UTC
        utc_turn_of_the_year = pl.datetime(MEZ_UNTIL_YEAR, 1, 1, time_zone="UTC")
        end = pl.when(last_day.eq(pl.datetime(MEZ_UNTIL_YEAR - 1, 12, 31))).then(utc_turn_of_the_year).otherwise(end)
        if dataset.resolution.value == Resolution.MINUTE_10:
            start = (
                pl.when(first_day.eq(pl.datetime(MEZ_UNTIL_YEAR, 1, 1)))
                .then(start - pl.duration(hours=1))
                .otherwise(start)
            )
        df_files = df_files.with_columns(
            start.alias("start_timestamp"),
            end.alias("end_timestamp"),
        )
        df_files = df_files.with_columns(
            pl.when(pl.col("start_timestamp") > pl.col("end_timestamp"))
            .then(pl.col("start_timestamp").min())
            .otherwise(pl.col("start_timestamp")),
            pl.when(pl.col("start_timestamp") > pl.col("end_timestamp"))
            .then(pl.col("end_timestamp").min())
            .otherwise(pl.col("end_timestamp")),
        )
    return df_files.sort(by=[pl.col("station_id"), pl.col("filename")])


def _midnight_in_utc(day: pl.Expr, days: int = 0) -> pl.Expr:
    """Return the midnight of ``day`` (plus ``days``) as the UTC instant the stamps of the files mean by it.

    Stamps of 1999 and before are MEZ, a fixed UTC+1, so their midnight is 23:00 UTC of the day before.
    """
    return (
        pl.when(day.dt.year() < MEZ_UNTIL_YEAR)
        .then(day - pl.duration(hours=1))
        .otherwise(day)
        .dt.replace_time_zone("UTC")
        .dt.offset_by(f"{days}d")
    )


def _create_file_index_for_1minute_or_5minute_historical_precipitation_metadata(
    resolution: str, dataset: str, settings: Settings
) -> pl.LazyFrame:
    """Create metadata DataFrame for 1minute precipitation historical."""
    url = f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/{resolution}/{dataset}/meta_data/"
    df_files = _create_file_index_for_dwd_server(url, settings=settings, ttl=CacheExpiry.METAINDEX)
    return df_files.with_columns(
        pl.col("filename").str.split("_").list.last().str.strip_suffix(".zip").alias("station_id"),
    )


def _create_file_index_for_dwd_server(
    url: str,
    settings: Settings,
    ttl: CacheExpiry,
) -> pl.LazyFrame:
    urls = list_remote_files_fsspec(url, settings=settings, cache_expiry=ttl)
    if not urls:
        msg = f"url {url} does not have a list of files"
        raise FileNotFoundError(msg)
    df = pl.DataFrame({"url": urls}, schema={"url": pl.String}, orient="col")
    df = df.with_columns(
        pl.col("url").str.split("/").list.last().alias("filename"),
    )
    return df.lazy()


def _build_url_from_dataset_and_period(
    dataset: DatasetModel,
    period: Period,
) -> str:
    """Build the URL for a given dataset."""
    if dataset in DWD_URBAN_DATASETS:
        # the 10 minute urban datasets carry a directory per period like the non-urban ones, so the
        # requested period has to reach the URL -- pinning it to ``recent`` served yesterday's data
        # for a ``now`` request and made ``historical`` unreachable altogether.
        urban_period = Period.RECENT if dataset in DWD_URBAN_DATASETS_WITHOUT_PERIOD_DIRECTORIES else period
        return f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/{dataset.resolution.value.value}/{dataset.name_original.removeprefix('urban_')}/{urban_period.value}/"
    if dataset in (
        DwdObservationMetadata.hourly.solar,
        DwdObservationMetadata.daily.solar,
    ):
        return f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/{dataset.resolution.value.value}/{dataset.name_original}/"
    return f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/{dataset.resolution.value.value}/{dataset.name_original}/{period.value}/"
