# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IMGW meteorology data provider."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl
import portion
from dateutil.relativedelta import relativedelta
from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel, build_metadata_model
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.imgw.fileindex import list_files_for_interval
from wetterdienst.provider.imgw.metadata import _METADATA
from wetterdienst.util.geo import convert_dms_string_to_dd
from wetterdienst.util.network import File, download_file, download_files

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

# The names _file_schema maps that are not measurements, and so have no status column beside them.
_STRUCTURAL_COLUMNS = frozenset({"station_id", "year", "month", "day"})
# IMGW writes a status column immediately after every measurement column -- documented per file in
# the `*_format.txt` beside the data, and generally in `Opis.txt`: a space means the value is a
# measurement, "8" that there is none, "9" that the phenomenon did not occur, and o_d's "Z" that the
# value is an `opad zbiorczy`, a sum over the preceding days that were not measured.
#
# Neither code can be taken from the value column, because the files do not write it the same way
# twice. Where "8" appears the value is not left empty but holds a literal ".0" -- which is why the
# status has to be read at all, to tell a station that measured nothing from one that measured zero.
# Where "9" appears, `o_d_01_2024` writes ".0" and `o_d_07_2024` leaves the cell empty, for the same
# parameter three files apart, so "9" is written as the zero it means rather than passed through.
#
# One reading of "9" is not a zero: `s_m_d_format.txt` says that for a `Liczba dni z` aggregation it
# means the station does not observe the phenomenon at all. None of those columns is declared -- they
# are the counts in `_STATUSLESS_COLUMNS` -- and declaring one would need its own branch here.
_STATUS_NO_MEASUREMENT = "8"
_STATUS_NO_PHENOMENON = "9"
# The status, carried into `quality` the way `metoffice/observation` carries MIDAS's `MESQL` flag. "8"
# and "9" are IMGW's own codes; `quality` is a float column and `Z` is a letter, so `Z` is reported as
# 10 -- the one value here this library assigns itself, documented on the provider's page. A blank
# status is a plain measurement and stays null, which is what every other value carries.
_STATUS_QUALITY = {"8": 8.0, "9": 9.0, "Z": 10.0}
# What a status is called between the rename and the unpivot, to keep it apart from the value of the
# same name. No IMGW column name can collide with it: they are Polish prose.
_STATUS_SUFFIX = "__status"
# The raw positions IMGW publishes with no status column beside them, by the file pattern that reads
# them, taken from each `*_format.txt`. They hold the fields that are not measurements: `ROOP`, the
# kind of precipitation, `SGR`, the state of the ground, the `DN1`/`DN2` days a monthly maximum fell
# on, and the day counts `k_m_d` ends with. None is declared today, so this changes nothing about
# what is read now. Declaring one without it would read the neighbour as a status, because the
# neighbour is another field: `k_m_d`'s `PSDN` would take `DESD`, a count of days with rain, as the
# status of a count of days with snow cover, and null the snow days of every month that had exactly
# eight days of rain. The files whose fields are all value/status pairs are absent -- `k_d_t`,
# `s_d_t`, `k_m_t` and `s_m_t` -- as is `PSDN` in `s_m_d`, which unlike `k_m_d` does carry a status.
_STATUSLESS_COLUMNS: dict[str, frozenset[int]] = {
    "k_d_[^t].*.csv": frozenset({16}),
    "o_d.*.csv": frozenset({8}),
    "s_d_[^t].*.csv": frozenset({16, 59}),
    "k_m_d.*.csv": frozenset({21, 22, 25, 26, 27}),
    "o_m.*.csv": frozenset({11, 12}),
    "s_m_d.*.csv": frozenset({21, 22}),
}

ImgwMeteorologyMetadata = {
    **_METADATA,
    "kind": "observation",
    "timezone": "Europe/Warsaw",
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
                            "unit": "one_eighth",
                        },
                        {
                            "name": "humidity",
                            "name_original": "średnia dobowa wilgotność względna",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "suma dobowa opadów",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "wysokość pokrywy śnieżnej",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "maksymalna temperatura dobowa",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "średnia dobowa temperatura",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "temperatura minimalna przy gruncie",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "minimalna temperatura dobowa",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "średnia dobowa prędkość wiatru",
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
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "wysokość pokrywy śnieżnej",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "wysokość świeżospałego śniegu",
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
                            "unit": "one_eighth",
                        },
                        {
                            "name": "humidity",
                            "name_original": "średnia dobowa wilgotność względna",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "suma dobowa opadów",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_day",
                            "name_original": "suma opadu dzień",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_night",
                            "name_original": "suma opadu noc",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "średnia dobowe ciśnienie na poziomie stacji",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "średnie dobowe ciśnienie na pozimie morza",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "średnia dobowe ciśnienie pary wodnej",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "wysokość pokrywy śnieżnej",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "maksymalna temperatura dobowa",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "średnia dobowa temperatura",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "temperatura minimalna przy gruncie",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "minimalna temperatura dobowa",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "średnia dobowa prędkość wiatru",
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
                            "unit": "one_eighth",
                        },
                        {
                            "name": "humidity",
                            "name_original": "średnia miesięczna wilgotność względna",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "miesieczna suma opadów",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "maksymalna dobowa suma opadów",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth_max",
                            "name_original": "maksymalna wysokość pokrywy śnieżnej",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "absolutna temperatura maksymalna",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m_mean",
                            "name_original": "średnia temperatura maksymalna",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "średnia miesięczna temperatura",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "minimalna temperatura przy gruncie",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "absolutna temperatura minimalna",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_mean",
                            "name_original": "średnia temperatura minimalna",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "średnia miesięczna prędkość wiatru",
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
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "opad maksymalny",
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
                            "unit": "one_eighth",
                        },
                        {
                            "name": "humidity",
                            "name_original": "średnia miesięczna wilgotność względna",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "miesięczna suma opadów",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_day",
                            "name_original": "suma opadu dzień",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "maksymalna dobowa suma opadów",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_night",
                            "name_original": "suma opadu noc",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "średnie miesięczne ciśnienie na poziomie stacji",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "średnie miesięczne ciśnienie na pozimie morza",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "średnie miesięczne ciśnienie pary wodnej",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "snow_depth_max",
                            "name_original": "maksymalna wysokość pokrywy śnieżnej",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "absolutna temperatura maksymalna",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m_mean",
                            "name_original": "średnia temperatura maksymalna",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "absolutna temperatura minimalna",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_mean",
                            "name_original": "średnia temperatura minimalna",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "minimalna temperatura przy gruncie",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "średnia miesięczna temperatura",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "średnia miesięczna prędkość wiatru",
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
                    "column_6": "suma dobowa opadów",
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
                    "column_19": "maksymalna dobowa suma opadów",
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
                    "column_9": "opad maksymalny",
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
                    "column_11": "średnia temperatura minimalna",
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

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect data for the given station and dataset."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.stations.settings)
        urls = self._get_urls(parameter_or_dataset, station_id)
        files = download_files(
            urls=urls,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
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
            pl.col("quality"),
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
            matched_path: str | None = None
            for f in files:
                if re.match(file_pattern, f):
                    matched_path = f
                    break
            df = self._parse_csv(
                file=zfs.read_bytes(matched_path),
                station_id=station_id,
                resolution=resolution,
                schema=schema,
                statusless=_STATUSLESS_COLUMNS.get(file_pattern, frozenset()),
            )
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
    def _parse_csv(
        file: bytes,
        station_id: str,
        resolution: Resolution,
        schema: dict,
        statusless: frozenset[int] = frozenset(),
    ) -> pl.DataFrame:
        """Parse a single file from the meteorological zip file."""
        df = pl.read_csv(file, encoding="latin-1", separator=",", has_header=False, infer_schema_length=0)
        status_columns = {}
        for column, name in schema.items():
            position = int(column.removeprefix("column_"))
            if name in _STRUCTURAL_COLUMNS or position in statusless:
                continue
            status = f"column_{position + 1}"
            if status in df.columns and status not in schema:
                status_columns[column] = status
        df = df.select(*schema, *status_columns.values())
        df = df.with_columns(
            pl.when(pl.col(status).str.strip_chars().eq(_STATUS_NO_MEASUREMENT))
            .then(None)
            .when(pl.col(status).str.strip_chars().eq(_STATUS_NO_PHENOMENON))
            .then(pl.lit("0"))
            .otherwise(pl.col(column))
            .alias(column)
            for column, status in status_columns.items()
        )
        # A status is named after the value it belongs to, suffixed, so that stripping the suffix
        # unpivots it to the same parameter and the join below carries it to its own value.
        statuses = {status: schema[column] + _STATUS_SUFFIX for column, status in status_columns.items()}
        df = df.rename({**schema, **statuses})
        df = df.with_columns(pl.col("station_id").str.strip_chars())
        df = df.filter(pl.col("station_id").eq(station_id))
        if df.is_empty():
            return pl.DataFrame()
        values = ImgwMeteorologyValues._unpivot(df.select(list(schema.values())), resolution, "value")
        values = values.with_columns(pl.col("value").cast(pl.Float64))
        if not statuses:
            return values.with_columns(pl.lit(None, dtype=pl.Float64).alias("quality"))
        structural = [name for name in schema.values() if name in _STRUCTURAL_COLUMNS]
        quality = ImgwMeteorologyValues._unpivot(df.select(*structural, *statuses.values()), resolution, "quality")
        quality = quality.with_columns(pl.col("parameter").str.strip_suffix(_STATUS_SUFFIX))
        quality = quality.with_columns(
            pl.col("quality").str.strip_chars().replace_strict(_STATUS_QUALITY, default=None, return_dtype=pl.Float64),
        )
        return values.join(quality, on=["station_id", "date", "parameter"], how="left")

    @staticmethod
    def _unpivot(df: pl.DataFrame, resolution: Resolution, value_name: str) -> pl.DataFrame:
        """Turn the year/month[/day] columns into a date and the remaining columns into rows."""
        if resolution == Resolution.DAILY:
            exp1 = pl.all().exclude(["year", "month", "day"])
            exp2 = pl.datetime("year", "month", "day").alias("date")
        else:
            exp1 = pl.all().exclude(["year", "month"])
            exp2 = pl.datetime("year", "month", 1).alias("date")
        df = df.select(exp1, exp2)
        return df.unpivot(index=["station_id", "date"], variable_name="parameter", value_name=value_name)

    def _get_urls(self, dataset: DatasetModel, station_id: str) -> list[str]:
        """Get URLs for the given dataset."""
        url = self._endpoint.format(resolution=dataset.resolution.name_original, dataset=dataset.name_original)
        interval = portion.closed(self.sr.start_date, self.sr.end_date) if self.sr.start_date else None
        files = list_files_for_interval(url, self.sr.settings, interval)
        df_files = pl.DataFrame({"url": files})
        df_files = df_files.with_columns(pl.col("url").str.split("/").list.last().alias("file"))
        df_files = df_files.filter(pl.col("file").str.ends_with(".zip"))
        if dataset.resolution.value == Resolution.DAILY and dataset.name == "synop":
            # unlike every other IMGW meteorology dataset, synop daily is archived per
            # station rather than per month: one file per period (year, or decade for
            # older data) *per station*, e.g. "2024_100_s.zip" for the station whose
            # 9-digit id ends in "100", not "2024_08_k.zip" for August across all stations
            station_code = station_id[-3:]
            df_files = df_files.filter(pl.col("file").str.contains(rf"_{station_code}_"))
            return df_files.get_column("url").to_list()
        if interval is not None:
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
                pl.col("date_range").arr.first().cast(pl.Datetime(time_zone="UTC")).alias("start_date"),
                pl.col("date_range").arr.last().cast(pl.Datetime(time_zone="UTC")).alias("end_date"),
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
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._endpoint,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df = pl.read_csv(file.content, encoding="utf8", separator=";", skip_rows=1, infer_schema_length=0)
        df = df[:, 1:]
        # drop the "Rok założenia" (station founding year) column, which isn't part of our schema
        df = df.drop(df.columns[3])
        df.columns = [
            "station_id",
            "name",
            "state",
            "latitude",
            "longitude",
            "height",
        ]
        df = df.with_columns(
            pl.col("latitude").map_batches(convert_dms_string_to_dd, return_dtype=pl.Float64),
            pl.col("longitude").map_batches(convert_dms_string_to_dd, return_dtype=pl.Float64),
            pl.col("height").str.replace(" ", "").cast(pl.Float64, strict=False),
        )
        # the station list is shared across all datasets, so tag each row once per requested resolution/dataset
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        data = [
            df.with_columns(
                pl.lit(resolution, pl.String).alias("resolution"),
                pl.lit(dataset, pl.String).alias("dataset"),
            )
            for resolution, dataset in resolutions_and_datasets
        ]
        if not data:
            return pl.LazyFrame()
        return pl.concat(data).lazy()
