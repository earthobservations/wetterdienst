# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IMGW meteorology data provider."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from io import BytesIO
from typing import ClassVar
from zoneinfo import ZoneInfo

import polars as pl
import portion
from dateutil.relativedelta import relativedelta
from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, build_metadata_model
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.imgw.metadata import _METADATA
from wetterdienst.util.geo import convert_dms_string_to_dd
from wetterdienst.util.network import File, download_file, download_files, list_remote_files_fsspec

ImgwMeteorologyMetadata = {
    **_METADATA,
    "kind": "observation",
    "timezone": "Europe/Warsaw",
    "timezone_data": "UTC",
    "resolutions": [
        {
            "name": "daily",
            "name_original": "dobowe",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": "climate",
                    "name_original": "klimat",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_cover_total",
                            "name_original": "średnie dobowe zachmurzenie ogólne",
                            "unit_type": "fraction",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "humidity",
                            "name_original": "średnia dobowa wilgotność względna",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "suma dobowa opadów",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "wysokość pokrywy śnieżnej",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "maksymalna temperatura dobowa",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "temperatura minimalna przy gruncie",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "średnia dobowa temperatura",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "minimalna temperatura dobowa",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "średnia dobowa prędkość wiatru",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                    ],
                },
                {
                    "name": "precipitation",
                    "name_original": "opad",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "suma dobowa opadów",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "wysokość pokrywy śnieżnej",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "wysokość świeżospałego śniegu",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                    ],
                },
                {
                    "name": "synop",
                    "name_original": "synop",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_cover_total",
                            "name_original": "średnie dobowe zachmurzenie ogólne",
                            "unit_type": "fraction",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "humidity",
                            "name_original": "średnia dobowa wilgotność względna",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height_day",
                            "name_original": "suma opadu dzień",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_night",
                            "name_original": "suma opadu noc",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "średnia dobowe ciśnienie na poziomie stacji",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "średnie dobowe ciśnienie na pozimie morza",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "średnia dobowe ciśnienie pary wodnej",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "średnia dobowa temperatura",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "średnia dobowa prędkość wiatru",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                    ],
                },
            ],
        },
        {
            "name": "monthly",
            "name_original": "miesieczne",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": "climate",
                    "name_original": "klimat",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_cover_total",
                            "name_original": "średnie miesięczne zachmurzenie ogólne",
                            "unit_type": "fraction",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "humidity",
                            "name_original": "średnia miesięczna wilgotność względna",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "miesieczna suma opadów",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "opad maksymalny",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth_max",
                            "name_original": "maksymalna wysokość pokrywy śnieżnej",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "absolutna temperatura maksymalna",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m_mean",
                            "name_original": "średnia temperatura maksymalna",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "średnia miesięczna temperatura",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "minimalna temperatura przy gruncie",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "absolutna temperatura minimalna",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_mean",
                            "name_original": "średnia temperatura minimalna",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "średnia miesięczna prędkość wiatru",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                    ],
                },
                {
                    "name": "precipitation",
                    "name_original": "opad",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "miesięczna suma opadów",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "opad maksymalny",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                    ],
                },
                {
                    "name": "synop",
                    "name_original": "synop",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_cover_total",
                            "name_original": "średnie miesięczne zachmurzenie ogólne",
                            "unit_type": "fraction",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "humidity",
                            "name_original": "średnia miesięczna wilgotność względna",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "miesięczna suma opadów",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_day",
                            "name_original": "suma opadu dzień",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "maksymalna dobowa suma opadów",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_night",
                            "name_original": "suma opadu noc",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "średnie miesięczne ciśnienie na poziomie stacji",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "średnie miesięczne ciśnienie na pozimie morza",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "średnie miesięczne ciśnienie pary wodnej",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "snow_depth_max",
                            "name_original": "maksymalna wysokość pokrywy śnieżnej",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "absolutna temperatura maksymalna",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m_mean",
                            "name_original": "średnia temperatura maksymalna",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "absolutna temperatura minimalna",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_mean",
                            "name_original": "średnia temperatura minimalna",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "minimalna temperatura przy gruncie",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "średnia miesięczna temperatura",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "średnia miesięczna prędkość wiatru",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                    ],
                },
            ],
        },
    ],
}
ImgwMeteorologyMetadata = build_metadata_model(ImgwMeteorologyMetadata, "ImgwMeteorologyMetadata")


class ImgwMeteorologyValues(TimeseriesValues):
    """Values for the meteorological data from the Institute of Meteorology and Water Management."""

    _endpoint = (
        "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/{resolution}/{dataset}/"
    )
    _file_schema: ClassVar = {
        Resolution.DAILY: {
            "climate": {
                "k_d_t.*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "day",
                    "column_6": "średnia dobowa temperatura",
                    "column_8": "średnia dobowa wilgotność względna",
                    "column_10": "średnia dobowa prędkość wiatru",
                    "column_12": "średnie dobowe zachmurzenie ogólne",
                },
                "k_d_[^t].*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "day",
                    "column_6": "maksymalna temperatura dobowa",
                    "column_8": "minimalna temperatura dobowa",
                    "column_10": "średnia dobowa temperatura",
                    "column_12": "temperatura minimalna przy gruncie",
                    "column_14": "suma dobowa opadów",
                    "column_17": "wysokość pokrywy śnieżnej",
                },
            },
            "precipitation": {
                "o_d.*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "day",
                    "column_6": "średnia dobowa temperatura",
                    "column_9": "wysokość pokrywy śnieżnej",
                    "column_11": "wysokość świeżospałego śniegu",
                },
            },
            "synop": {
                "s_d_t.*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "day",
                    "column_6": "średnie dobowe zachmurzenie ogólne",
                    "column_8": "średnia dobowa prędkość wiatru",
                    "column_10": "średnia dobowa temperatura",
                    "column_12": "średnia dobowe ciśnienie pary wodnej",
                    "column_14": "średnia dobowa wilgotność względna",
                    "column_16": "średnia dobowe ciśnienie na poziomie stacji",
                    "column_18": "średnie dobowe ciśnienie na pozimie morza",
                    "column_20": "suma opadu dzień",
                    "column_22": "suma opadu noc",
                },
                "s_d_[^t].*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "day",
                    "column_6": "maksymalna temperatura dobowa",
                    "column_8": "minimalna temperatura dobowa",
                    "column_10": "średnia dobowa temperatura",
                    "column_12": "temperatura minimalna przy gruncie",
                    "column_14": "suma dobowa opadów",
                    "column_17": "wysokość pokrywy śnieżnej",
                },
            },
        },
        Resolution.MONTHLY: {
            "climate": {
                "k_m_d.*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "absolutna temperatura maksymalna",
                    "column_7": "średnia temperatura maksymalna",
                    "column_9": "absolutna temperatura minimalna",
                    "column_11": "średnia temperatura minimalna",
                    "column_13": "średnia miesięczna temperatura",
                    "column_15": "minimalna temperatura przy gruncie",
                    "column_17": "miesieczna suma opadów",
                    "column_19": "maksymalna dobowa suma opadóww",
                    "column_23": "maksymalna wysokość pokrywy śnieżnej",
                },
                "k_m_t.*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "średnia miesięczna temperatura",
                    "column_7": "średnia miesięczna wilgotność względna",
                    "column_9": "średnia miesięczna prędkość wiatru",
                    "column_11": "średnie miesięczne zachmurzenie ogólne",
                },
            },
            "precipitation": {
                "o_m.*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "miesięczna suma opadów",
                    "column_7": "opad maksymalny",
                },
            },
            "synop": {
                "s_m_d.*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "absolutna temperatura maksymalna",
                    "column_7": "średnia temperatura maksymalna",
                    "column_9": "absolutna temperatura minimalna",
                    "column_11": "średnia temperatura minimalnaj",
                    "column_13": "średnia miesięczna temperatura",
                    "column_15": "minimalna temperatura przy gruncie",
                    "column_17": "miesięczna suma opadów",
                    "column_19": "maksymalna dobowa suma opadów",
                    "column_25": "maksymalna wysokość pokrywy śnieżnej",
                },
                "s_m_t.*.csv": {
                    "column_1": "station_id",
                    "column_3": "year",
                    "column_4": "month",
                    "column_5": "średnie miesięczne zachmurzenie ogólne",
                    "column_7": "średnia miesięczna prędkość wiatru",
                    "column_9": "średnia miesięczna temperatura",
                    "column_11": "średnie miesięczne ciśnienie pary wodnej",
                    "column_13": "średnia miesięczna wilgotność względna",
                    "column_15": "średnie miesięczne ciśnienie na poziomie stacji",
                    "column_17": "średnie miesięczne ciśnienie na pozimie morza",
                    "column_19": "suma opadu dzień",
                    "column_21": "suma opadu noc",
                },
            },
        },
    }

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect data for the given station and dataset."""
        urls = self._get_urls(parameter_or_dataset)
        files = download_files(
            urls=urls,
            cache_dir=self.sr.stations.settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
            cache_disable=self.sr.stations.settings.cache_disable,
        )
        files = [file for file in files if isinstance(file.content, BytesIO)]
        data = []
        file_schema = self._file_schema[parameter_or_dataset.resolution.value][parameter_or_dataset.name]
        for file in files:
            df = self._parse_file(
                file=file,
                station_id=station_id,
                resolution=parameter_or_dataset.resolution.value,
                file_schema=file_schema,
            )
            if not df.is_empty():
                data.append(df)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        if df.is_empty():
            return pl.DataFrame()
        return df.select(
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.col("station_id"),
            pl.col("date").dt.replace_time_zone("UTC"),
            pl.col("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )

    def _parse_file(
        self,
        file: File,
        station_id: str,
        resolution: Resolution,
        file_schema: dict,
    ) -> pl.DataFrame:
        """Parse the meteorological zip file."""
        zfs = ZipFileSystem(file.content)
        data = []
        files = zfs.glob("*")
        for file_pattern, schema in file_schema.items():
            file = None
            for f in files:
                if re.match(file_pattern, f):
                    file = f
                    break
            df = self.__parse_file(zfs.read_bytes(file), station_id, resolution, schema)
            if not df.is_empty():
                data.append(df)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        if df.is_empty():
            return pl.DataFrame()
        return df.unique(subset=["parameter", "date"], keep="first")

    @staticmethod
    def __parse_file(file: bytes, station_id: str, resolution: Resolution, schema: dict) -> pl.DataFrame:
        """Parse a single file from the meteorological zip file."""
        df = pl.read_csv(file, encoding="latin-1", separator=",", has_header=False, infer_schema_length=0)
        df = df.select(list(schema.keys())).rename(schema)
        df = df.with_columns(pl.col("station_id").str.strip_chars())
        df = df.filter(pl.col("station_id").eq(station_id))
        if df.is_empty():
            return df
        if resolution == Resolution.DAILY:
            exp1 = pl.all().exclude(["year", "month", "day"])
            exp2 = pl.datetime("year", "month", "day").alias("date")
        else:
            exp1 = pl.all().exclude(["year", "month"])
            exp2 = pl.datetime("year", "month", 1).alias("date")
        df = df.select(exp1, exp2)
        df = df.unpivot(index=["station_id", "date"], variable_name="parameter", value_name="value")
        return df.with_columns(pl.col("value").cast(pl.Float64))

    def _get_urls(self, dataset: DatasetModel) -> list[str]:
        """Get URLs for the given dataset."""
        url = self._endpoint.format(resolution=dataset.resolution.name_original, dataset=dataset.name_original)
        files = list_remote_files_fsspec(url, self.sr.settings)
        df_files = pl.DataFrame({"url": files})
        df_files = df_files.with_columns(pl.col("url").str.split("/").list.last().alias("file"))
        df_files = df_files.filter(pl.col("file").str.ends_with(".zip"))
        if self.sr.start_date:
            interval = portion.closed(self.sr.start_date, self.sr.end_date)
            if dataset.resolution.value == Resolution.MONTHLY:
                df_files = df_files.with_columns(
                    pl.when(pl.col("file").str.split("_").list.len() == 3)
                    .then(
                        pl.col("file")
                        .str.split("_")
                        .list.first()
                        .map_elements(lambda y: [y, y], return_dtype=pl.Array(pl.Int64, shape=2)),
                    )
                    .otherwise(pl.col("file").str.split("_").list.slice(0, 2))
                    .map_elements(
                        lambda years: [
                            dt.datetime(int(years[0]), 1, 1, tzinfo=ZoneInfo("UTC")),
                            dt.datetime(int(years[1]), 1, 1, tzinfo=ZoneInfo("UTC"))
                            + relativedelta(years=1)
                            - relativedelta(days=1),
                        ],
                        return_dtype=pl.Array(pl.Datetime(time_zone="UTC"), shape=2),
                    )
                    .alias("date_range"),
                )
            else:
                df_files = df_files.with_columns(
                    pl.when(pl.col("file").str.split("_").list.len() == 2)
                    .then(
                        pl.col("file")
                        .str.split("_")
                        .list.first()
                        .str.to_datetime("%Y", time_zone="UTC", strict=False)
                        .map_elements(
                            lambda d: [d, d + relativedelta(years=1) - relativedelta(days=1)],
                            return_dtype=pl.Array(pl.Datetime(time_zone="UTC"), shape=2),
                        ),
                    )
                    .otherwise(
                        pl.col("file")
                        .str.split("_")
                        .list.slice(0, 2)
                        .list.join("_")
                        .str.to_datetime("%Y_%m", time_zone="UTC", strict=False)
                        .map_elements(
                            lambda d: [d, d + relativedelta(months=1) - relativedelta(days=1)],
                            return_dtype=pl.Array(pl.Datetime(time_zone="UTC"), shape=2),
                        ),
                    )
                    .alias("date_range"),
                )
            df_files = df_files.select(
                pl.col("url"),
                pl.col("date_range").list.first().cast(pl.Datetime(time_zone="UTC")).alias("start_date"),
                pl.col("date_range").list.last().cast(pl.Datetime(time_zone="UTC")).alias("end_date"),
            )
            df_files = df_files.with_columns(
                pl.struct(["start_date", "end_date"])
                .map_elements(
                    lambda dates: portion.closed(dates["start_date"], dates["end_date"]),
                    return_dtype=pl.Object,
                )
                .alias("interval"),
            )
            df_files = df_files.filter(
                pl.col("interval").map_elements(lambda i: i.overlaps(interval), return_dtype=pl.Boolean),
            )
        return df_files.get_column("url").to_list()


@dataclass
class ImgwMeteorologyRequest(TimeseriesRequest):
    """Request for meteorological data from the Institute of Meteorology and Water Management."""

    metadata = ImgwMeteorologyMetadata
    _values = ImgwMeteorologyValues
    _endpoint = "https://dane.imgw.pl/datastore/getfiledown/Arch/Telemetria/Meteo/kody_stacji.csv"

    def _all(self) -> pl.LazyFrame:
        """Get all available stations."""
        file = download_file(
            url=self._endpoint,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        file.raise_if_exception()
        df = pl.read_csv(file.content, encoding="latin-1", separator=";", skip_rows=1, infer_schema_length=0)
        df = df[:, 1:]
        df.columns = [
            "station_id",
            "name",
            "state",
            "latitude",
            "longitude",
            "height",
        ]
        df = df.lazy()
        return df.with_columns(
            pl.col("latitude").map_batches(convert_dms_string_to_dd),
            pl.col("longitude").map_batches(convert_dms_string_to_dd),
            pl.col("height").str.replace(" ", "").cast(pl.Float64, strict=False),
        )
