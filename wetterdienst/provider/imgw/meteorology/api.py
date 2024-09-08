# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import portion as P
from dateutil.relativedelta import relativedelta
from fsspec.implementations.zip import ZipFileSystem

from wetterdienst import Kind, Parameter, Period, Provider, Resolution, Settings
from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.period import PeriodType
from wetterdienst.metadata.resolution import ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.geo import convert_dms_string_to_dd
from wetterdienst.util.network import download_file, list_remote_files_fsspec
from wetterdienst.util.parameter import DatasetTreeCore

if TYPE_CHECKING:
    from collections.abc import Sequence


class ImgwMeteorologyParameter(DatasetTreeCore):
    class DAILY(DatasetTreeCore):
        class CLIMATE(Enum):
            CLOUD_COVER_TOTAL = "średnie dobowe zachmurzenie ogólne"  # kdt
            HUMIDITY = "średnia dobowa wilgotność względna"  # kdt
            PRECIPITATION_HEIGHT = "suma dobowa opadów"  # kd
            SNOW_DEPTH = "wysokość pokrywy śnieżnej"  # kd
            TEMPERATURE_AIR_MAX_2M = "maksymalna temperatura dobowa"  # kd
            TEMPERATURE_AIR_MEAN_0_05M = "temperatura minimalna przy gruncie"  # kd
            TEMPERATURE_AIR_MEAN_2M = "średnia dobowa temperatura"  # kdt, kd
            TEMPERATURE_AIR_MIN_2M = "minimalna temperatura dobowa"  # kd
            WIND_SPEED = "średnia dobowa prędkość wiatru"  # kdt

        class PRECIPITATION(Enum):
            PRECIPITATION_HEIGHT = "suma dobowa opadów"
            SNOW_DEPTH = "wysokość pokrywy śnieżnej"
            SNOW_DEPTH_NEW = "wysokość świeżospałego śniegu"

        class SYNOP(Enum):
            CLOUD_COVER_TOTAL = "średnie dobowe zachmurzenie ogólne"
            HUMIDITY = "średnia dobowa wilgotność względna"
            PRECIPITATION_HEIGHT_DAY = "suma opadu dzień"
            PRECIPITATION_HEIGHT_NIGHT = "suma opadu noc"
            PRESSURE_AIR_SITE = "średnia dobowe ciśnienie na poziomie stacji"
            PRESSURE_AIR_SEA_LEVEL = "średnie dobowe ciśnienie na pozimie morza"
            PRESSURE_VAPOR = "średnia dobowe ciśnienie pary wodnej"
            TEMPERATURE_AIR_MEAN_2M = "średnia dobowa temperatura"
            WIND_SPEED = "średnia dobowa prędkość wiatru"

        CLOUD_COVER_TOTAL = SYNOP.CLOUD_COVER_TOTAL
        HUMIDITY = CLIMATE.HUMIDITY
        PRECIPITATION_HEIGHT = PRECIPITATION.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_DAY = SYNOP.PRECIPITATION_HEIGHT_DAY
        PRECIPITATION_HEIGHT_NIGHT = SYNOP.PRECIPITATION_HEIGHT_NIGHT
        PRESSURE_AIR_SITE = SYNOP.PRESSURE_AIR_SITE
        PRESSURE_AIR_SEA_LEVEL = SYNOP.PRESSURE_AIR_SEA_LEVEL
        PRESSURE_VAPOR = SYNOP.PRESSURE_VAPOR
        SNOW_DEPTH = PRECIPITATION_HEIGHT.SNOW_DEPTH
        SNOW_DEPTH_NEW = PRECIPITATION_HEIGHT.SNOW_DEPTH_NEW
        TEMPERATURE_AIR_MAX_2M = CLIMATE.TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_AIR_MEAN_0_05M = CLIMATE.TEMPERATURE_AIR_MEAN_0_05M
        TEMPERATURE_AIR_MEAN_2M = CLIMATE.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_AIR_MIN_2M = CLIMATE.TEMPERATURE_AIR_MIN_2M
        WIND_SPEED = SYNOP.WIND_SPEED

    class MONTHLY(DatasetTreeCore):
        class CLIMATE(Enum):
            CLOUD_COVER_TOTAL = "średnie miesięczne zachmurzenie ogólne"
            HUMIDITY = "średnia miesięczna wilgotność względna"
            PRECIPITATION_HEIGHT = "miesieczna suma opadów"
            PRECIPITATION_HEIGHT_MAX = "maksymalna dobowa suma opadóww"
            SNOW_DEPTH_MAX = "maksymalna wysokość pokrywy śnieżnej"
            TEMPERATURE_AIR_MAX_2M = "absolutna temperatura maksymalna"
            TEMPERATURE_AIR_MAX_2M_MEAN = "średnia temperatura maksymalna"
            TEMPERATURE_AIR_MEAN_2M = "średnia miesięczna temperatura"
            TEMPERATURE_AIR_MIN_0_05M = "minimalna temperatura przy gruncie"
            TEMPERATURE_AIR_MIN_2M = "absolutna temperatura minimalna"
            TEMPERATURE_AIR_MIN_2M_MEAN = "średnia temperatura minimalna"
            WIND_SPEED = "średnia miesięczna prędkość wiatru"

        class PRECIPITATION(Enum):
            PRECIPITATION_HEIGHT = "miesięczna suma opadów"
            PRECIPITATION_HEIGHT_MAX = "opad maksymalny"

        class SYNOP(Enum):
            CLOUD_COVER_TOTAL = "średnie miesięczne zachmurzenie ogólne"
            HUMIDITY = "średnia miesięczna wilgotność względna"
            PRECIPITATION_HEIGHT = "miesięczna suma opadów"
            PRECIPITATION_HEIGHT_DAY = "suma opadu dzień"
            PRECIPITATION_HEIGHT_MAX = "maksymalna dobowa suma opadów"
            PRECIPITATION_HEIGHT_NIGHT = "suma opadu noc"
            PRESSURE_AIR_SITE = "średnie miesięczne ciśnienie na poziomie stacji"
            PRESSURE_AIR_SEA_LEVEL = "średnie miesięczne ciśnienie na pozimie morza"
            PRESSURE_VAPOR = "średnie miesięczne ciśnienie pary wodnej"
            SNOW_DEPTH_MAX = "maksymalna wysokość pokrywy śnieżnej"
            TEMPERATURE_AIR_MAX_2M = "absolutna temperatura maksymalna"
            TEMPERATURE_AIR_MAX_2M_MEAN = "średnia temperatura maksymalna"
            TEMPERATURE_AIR_MEAN_2M = "średnia miesięczna temperatura"
            TEMPERATURE_AIR_MIN_0_05M = "minimalna temperatura przy gruncie"
            TEMPERATURE_AIR_MIN_2M = "absolutna temperatura minimalna"
            TEMPERATURE_AIR_MIN_2M_MEAN = "średnia temperatura minimalnaj"
            WIND_SPEED = "średnia miesięczna prędkość wiatru"

        CLOUD_COVER_TOTAL = SYNOP.CLOUD_COVER_TOTAL
        HUMIDITY = SYNOP.HUMIDITY
        PRECIPITATION_HEIGHT = PRECIPITATION.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_DAY = SYNOP.PRECIPITATION_HEIGHT_DAY
        PRECIPITATION_HEIGHT_MAX = PRECIPITATION.PRECIPITATION_HEIGHT_MAX
        PRECIPITATION_HEIGHT_NIGHT = SYNOP.PRECIPITATION_HEIGHT_NIGHT
        PRESSURE_AIR_SITE = SYNOP.PRESSURE_AIR_SITE
        PRESSURE_AIR_SEA_LEVEL = SYNOP.PRESSURE_AIR_SEA_LEVEL
        PRESSURE_VAPOR = SYNOP.PRESSURE_VAPOR
        SNOW_DEPTH_MAX = SYNOP.SNOW_DEPTH_MAX
        TEMPERATURE_AIR_MAX_2M = SYNOP.TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_AIR_MAX_2M_MEAN = SYNOP.TEMPERATURE_AIR_MAX_2M_MEAN
        TEMPERATURE_AIR_MEAN_2M = SYNOP.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_AIR_MIN_0_05M = SYNOP.TEMPERATURE_AIR_MIN_0_05M
        TEMPERATURE_AIR_MIN_2M = SYNOP.TEMPERATURE_AIR_MIN_2M
        TEMPERATURE_AIR_MIN_2M_MEAN = SYNOP.TEMPERATURE_AIR_MIN_2M_MEAN
        WIND_SPEED = SYNOP.WIND_SPEED


class ImgwMeteorologyUnit(DatasetTreeCore):
    class DAILY(DatasetTreeCore):
        class CLIMATE(UnitEnum):
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            TEMPERATURE_AIR_MAX_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_0_05M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

        class PRECIPITATION(UnitEnum):
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value

        class SYNOP(UnitEnum):
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_DAY = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_NIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

    class MONTHLY(DatasetTreeCore):
        class CLIMATE(UnitEnum):
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            SNOW_DEPTH_MAX = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            TEMPERATURE_AIR_MAX_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MAX_2M_MEAN = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_0_05M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M_MEAN = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

        class PRECIPITATION(UnitEnum):
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value

        class SYNOP(UnitEnum):
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_DAY = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_NIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            SNOW_DEPTH_MAX = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            TEMPERATURE_AIR_MAX_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MAX_2M_MEAN = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M_MEAN = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_0_05M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value


class ImgwMeteorologyDataset(Enum):
    CLIMATE = "klimat"
    PRECIPITATION = "opad"
    SYNOP = "synop"


class ImgwMeteorologyResolution(Enum):
    DAILY = "dobowe"
    MONTHLY = "miesieczne"


class ImgwMeteorologyPeriod(Enum):
    HISTORICAL = Period.HISTORICAL


class ImgwMeteorologyValues(TimeseriesValues):
    _data_tz = Timezone.UTC
    _endpoint = (
        "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/{resolution}/{dataset}/"
    )
    _file_schema = {
        "daily": {
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
        "monthly": {
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

    def _collect_station_parameter(
        self,
        station_id: str,
        parameter: Enum,  # noqa: ARG002
        dataset: Enum,
    ) -> pl.DataFrame:
        """

        :param station_id:
        :param parameter:
        :param dataset:
        :return:
        """
        urls = self._get_urls(dataset)
        with ThreadPoolExecutor() as p:
            files_in_bytes = p.map(
                lambda file: download_file(url=file, settings=self.sr.settings, ttl=CacheExpiry.FIVE_MINUTES),
                urls,
            )
        data = []
        file_schema = self._file_schema[self.sr.resolution.name.lower()][dataset.name.lower()]
        for file_in_bytes in files_in_bytes:
            df = self._parse_file(file_in_bytes, station_id, file_schema)
            if not df.is_empty():
                data.append(df)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        if df.is_empty():
            return pl.DataFrame()
        return df.with_columns(
            pl.col("date").dt.replace_time_zone("UTC"),
            pl.col("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )

    def _parse_file(self, file_in_bytes: bytes, station_id, file_schema: dict) -> pl.DataFrame:
        """Function to parse meteorological zip file, parses all files and combines
        them

        :param file_in_bytes:
        :param file_schema:
        :return:
        """
        zfs = ZipFileSystem(file_in_bytes)
        data = []
        files = zfs.glob("*")
        for file_pattern, schema in file_schema.items():
            file = None
            for f in files:
                if re.match(file_pattern, f):
                    file = f
                    break
            df = self.__parse_file(zfs.read_bytes(file), station_id, schema)
            if not df.is_empty():
                data.append(df)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        if df.is_empty():
            return pl.DataFrame()
        return df.unique(subset=["parameter", "date"], keep="first")

    def __parse_file(self, file: bytes, station_id: str, schema: dict) -> pl.DataFrame:
        """Function to parse a single file out of the zip file

        :param file:
        :return:
        """
        df = pl.read_csv(file, encoding="latin-1", separator=",", has_header=False, infer_schema_length=0)
        df = df.select(list(schema.keys())).rename(schema)
        df = df.with_columns(pl.col("station_id").str.strip_chars())
        df = df.filter(pl.col("station_id").eq(station_id))
        if df.is_empty():
            return df
        if self.sr.resolution == Resolution.DAILY:
            exp1 = pl.all().exclude(["year", "month", "day"])
            exp2 = pl.datetime("year", "month", "day").alias(Columns.DATE.value)
        else:
            exp1 = pl.all().exclude(["year", "month"])
            exp2 = pl.datetime("year", "month", 1).alias(Columns.DATE.value)
        df = df.select(exp1, exp2)
        df = df.unpivot(index=["station_id", "date"], variable_name="parameter", value_name="value")
        return df.with_columns(pl.col("value").cast(pl.Float64))

    def _get_urls(self, dataset: Enum) -> pl.Series:
        """Get file urls from server

        :param dataset: dataset for which the filelist is retrieved
        :return:
        """
        res = self.sr.stations._resolution_base[self.sr.resolution.name]
        url = self._endpoint.format(resolution=res.value, dataset=dataset.value)
        files = list_remote_files_fsspec(url, self.sr.settings)
        df_files = pl.DataFrame({"url": files})
        df_files = df_files.with_columns(pl.col("url").str.split("/").list.last().alias("file"))
        df_files = df_files.filter(pl.col("file").str.ends_with(".zip"))
        if self.sr.start_date:
            interval = P.closed(self.sr.start_date, self.sr.end_date)
            if self.sr.resolution == Resolution.MONTHLY:
                df_files = df_files.with_columns(
                    pl.when(pl.col("file").str.split("_").list.len() == 3)
                    .then(pl.col("file").str.split("_").list.first().map_elements(lambda y: [y, y]))
                    .otherwise(pl.col("file").str.split("_").list.slice(0, 2))
                    .map_elements(
                        lambda years: [
                            dt.datetime(int(years[0]), 1, 1, tzinfo=ZoneInfo("UTC")),
                            dt.datetime(int(years[1]), 1, 1, tzinfo=ZoneInfo("UTC"))
                            + relativedelta(years=1)
                            - relativedelta(days=1),
                        ],
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
                        .map_elements(lambda d: [d, d + relativedelta(years=1) - relativedelta(days=1)]),
                    )
                    .otherwise(
                        pl.col("file")
                        .str.split("_")
                        .list.slice(0, 2)
                        .list.join("_")
                        .str.to_datetime("%Y_%m", time_zone="UTC", strict=False)
                        .map_elements(lambda d: [d, d + relativedelta(months=1) - relativedelta(days=1)]),
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
                .map_elements(lambda dates: P.closed(dates["start_date"], dates["end_date"]))
                .alias("interval"),
            )
            df_files = df_files.filter(pl.col("interval").map_elements(lambda i: i.overlaps(interval)))
        return df_files.get_column("url")


class ImgwMeteorologyRequest(TimeseriesRequest):
    _provider = Provider.IMGW
    _kind = Kind.OBSERVATION
    _parameter_base = ImgwMeteorologyParameter
    _unit_base = ImgwMeteorologyUnit
    _dataset_base = ImgwMeteorologyDataset
    _has_datasets = True
    _unique_dataset = True
    _resolution_base = ImgwMeteorologyResolution
    _resolution_type = ResolutionType.MULTI
    _period_base = ImgwMeteorologyPeriod
    _period_type = PeriodType.FIXED
    _tz = Timezone.POLAND
    _data_range = DataRange.FIXED
    _values = ImgwMeteorologyValues
    _endpoint = "https://dane.imgw.pl/datastore/getfiledown/Arch/Telemetria/Meteo/kody_stacji.csv"

    def __init__(
        self,
        parameter: str | ImgwMeteorologyParameter | Parameter | Sequence[str | ImgwMeteorologyParameter | Parameter],
        resolution: str | ImgwMeteorologyResolution | Resolution,
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
        settings: Settings | None = None,
    ):
        super().__init__(
            parameter=parameter,
            resolution=resolution,
            start_date=start_date,
            end_date=end_date,
            period=Period.HISTORICAL,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        """

        :return:
        """
        payload = download_file(self._endpoint, settings=self.settings, ttl=CacheExpiry.METAINDEX)
        df = pl.read_csv(payload, encoding="latin-1", separator=";", skip_rows=1, infer_schema_length=0)
        df = df[:, 1:]
        df.columns = [
            Columns.STATION_ID.value,
            Columns.NAME.value,
            Columns.STATE.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
        ]
        df = df.lazy()
        return df.with_columns(
            pl.col(Columns.LATITUDE.value).map_batches(convert_dms_string_to_dd),
            pl.col(Columns.LONGITUDE.value).map_batches(convert_dms_string_to_dd),
            pl.col(Columns.HEIGHT.value).str.replace(" ", "").cast(pl.Float64, strict=False),
        )
