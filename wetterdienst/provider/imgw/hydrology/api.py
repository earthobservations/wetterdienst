# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IMGW hydrology provider."""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from io import BytesIO, StringIO
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

log = logging.getLogger(__name__)


ImgwHydrologyMetadata = {
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
                    "name": "hydrology",
                    "name_original": "hydrology",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "discharge",
                            "name_original": "przepływ",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "temperature_water",
                            "name_original": "temperatura wody",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "stage",
                            "name_original": "stan wody",
                            "unit_type": "length_short",
                            "unit": "centimeter",
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
                    "name": "hydrology",
                    "name_original": "hydrology",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "discharge_max",
                            "name_original": "maksymalna przepływ",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_mean",
                            "name_original": "średnia przepływ",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_min",
                            "name_original": "minimalna przepływ",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "temperature_water_max",
                            "name_original": "maksymalna temperatura wody",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_water_mean",
                            "name_original": "średnia temperatura wody",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_water_min",
                            "name_original": "minimalna temperatura wody",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "stage_max",
                            "name_original": "maksymalna stan wody",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "stage_mean",
                            "name_original": "średnia stan wody",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "stage_min",
                            "name_original": "minimalna stan wody",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
ImgwHydrologyMetadata = build_metadata_model(ImgwHydrologyMetadata, "ImgwHydrologyMetadata")


class ImgwHydrologyValues(TimeseriesValues):
    """Values class for hydrological data from IMGW."""

    _endpoint = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/{resolution}/"
    _file_schema: ClassVar = {
        Resolution.DAILY: {
            "hydrology": {
                "codz.*.csv": {
                    "column_1": "station_id",
                    "column_4": "year",
                    "column_5": "month",
                    "column_6": "day",
                    "column_7": "stan wody",
                    "column_8": "przepływ",
                    "column_9": "temperatura wody",
                },
            },
        },
        Resolution.MONTHLY: {
            "hydrology": {
                "mies.*.csv": {
                    "column_1": "station_id",
                    "column_4": "year",
                    "column_5": "month",
                    "column_6": "extremity",
                    "column_7": "stan wody",
                    "column_8": "przepływ",
                    "column_9": "temperatura wody",
                },
            },
        },
    }

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect hydrological data for a single station and dataset."""
        urls = self._get_urls(parameter_or_dataset)
        print(urls)
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
                dataset=parameter_or_dataset,
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
        dataset: DatasetModel,
        file_schema: dict,
    ) -> pl.DataFrame:
        """Parse hydrological data from a single file."""
        zfs = ZipFileSystem(file.content)
        data = []
        files = zfs.glob("*")
        for file_pattern, schema in file_schema.items():
            file = None
            for f in files:
                if re.match(file_pattern, f):
                    file = f
                    break
            df = self.__parse_file(file=zfs.read_bytes(file), station_id=station_id, dataset=dataset, schema=schema)
            if not df.is_empty():
                data.append(df)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        if df.is_empty():
            return pl.DataFrame()
        return df.unique(subset=["parameter", "date"], keep="first")

    def __parse_file(self, file: bytes, station_id: str, dataset: DatasetModel, schema: dict) -> pl.DataFrame:
        """Parse hydrological data from a single file."""
        df = pl.read_csv(
            file,
            encoding="latin-1",
            separator=",",
            has_header=False,
            infer_schema_length=0,
            null_values=["9999", "99999.999", "99.9"],
        )
        df = df.select(list(schema.keys())).rename(schema)
        df = df.with_columns(pl.col("station_id").str.strip_chars())
        df = df.filter(pl.col("station_id").eq(station_id))
        if df.is_empty():
            return df
        df = df.with_columns(pl.col("year").cast(pl.Int64), pl.col("month").cast(pl.Int64))
        # shift hydrological year to regular year
        df = df.with_columns(
            pl.when(pl.col("month") <= 2).then(pl.col("year") - 1).otherwise(pl.col("year")).alias("year"),
            pl.when(pl.col("month").add(10).gt(12)).then(pl.col("month").sub(2)).otherwise(pl.col("month").add(10)),
        )
        if dataset.resolution.value == Resolution.DAILY:
            df = df.with_columns(pl.col("day").cast(pl.Int64))
            exp1 = pl.all().exclude(["year", "month", "day"])
            exp2 = pl.datetime("year", "month", "day").alias("date")
        else:
            exp1 = pl.all().exclude(["year", "month"])
            exp2 = pl.datetime("year", "month", 1).alias("date")
        df = df.select(exp1, exp2)
        if dataset.resolution.value == Resolution.DAILY:
            index = ["station_id", "date"]
        else:
            # monthly data includes extrimity column (1: min, 2: mean, 3: max)
            index = ["station_id", "date", "extremity"]
        df = df.unpivot(index=index, variable_name="parameter", value_name="value")
        df = df.with_columns(pl.col("value").cast(pl.Float64))
        if dataset.resolution.value == Resolution.MONTHLY:
            df = df.select(
                pl.col("station_id"),
                pl.col("date"),
                pl.concat_str(
                    exprs=[
                        pl.col("extremity").replace({"1": "minimalna", "2": "średnia", "3": "maksymalna"}),
                        pl.col("parameter"),
                    ],
                    separator=" ",
                ).alias("parameter"),
                pl.col("value"),
            )
        return df

    @staticmethod
    def _get_start_and_end_date(
        start_date: dt.date,
        end_date: dt.date,
    ) -> tuple[dt.date, dt.date]:
        min_hydro_start_date = dt.date(1951, 1, 1)
        today = dt.date.today()
        if today.month >= 10:
            max_hydro_end_date = dt.date(today.year + 1, today.month - 10, 1)
        else:
            max_hydro_end_date = dt.date(today.year, today.month + 2, 1)
        given_hydro_start_date = None
        if start_date:
            # convert regular start_date to hydrological year
            if start_date.month <= 10:
                given_hydro_start_date = dt.date(start_date.year, start_date.month + 2, start_date.day)
            else:
                given_hydro_start_date = dt.date(start_date.year + 1, start_date.month - 10, start_date.day)
        given_hydro_end_date = None
        if end_date:
            # convert regular end_date to hydrological year
            end_date = end_date
            if end_date.month <= 10:
                given_hydro_end_date = dt.date(end_date.year, end_date.month + 2, end_date.day)
            else:
                given_hydro_end_date = dt.date(end_date.year + 1, end_date.month - 10, end_date.day)
        return max(given_hydro_start_date or min_hydro_start_date, min_hydro_start_date), min(
            given_hydro_end_date or max_hydro_end_date, max_hydro_end_date
        )

    def _get_urls(self, dataset: DatasetModel) -> list[str]:
        """Get all urls for the given dataset."""
        url = self._endpoint.format(resolution=dataset.resolution.name_original, dataset=dataset.name_original)
        start_date, end_date = self._get_start_and_end_date(self.sr.start_date, self.sr.end_date)
        files = []
        if dataset.resolution.value == Resolution.DAILY:
            for date in pl.date_range(start_date, end_date, interval="1mo", eager=True):
                file_name = f"{date.year}/codz_{date.year}_{date.month:02d}.zip"
                files.append(f"{url}{file_name}")
        elif dataset.resolution.value == Resolution.MONTHLY:
            for date in pl.date_range(start_date, end_date, interval="1y", eager=True):
                file_name = f"{date.year}/mies_{date.year}.zip"
                files.append(f"{url}{file_name}")
        return files


@dataclass
class ImgwHydrologyRequest(TimeseriesRequest):
    """Request class for hydrological data from IMGW."""

    metadata = ImgwHydrologyMetadata
    _values = ImgwHydrologyValues
    _endpoint = "https://dane.imgw.pl/datastore/getfiledown/Arch/Telemetria/Hydro/kody_stacji.csv"

    def _all(self) -> pl.LazyFrame:
        """:return:"""
        file = download_file(
            url=self._endpoint,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        file.raise_if_exception()
        # skip empty lines in the csv file
        lines = file.content.read().decode("latin-1").replace("\r", "").split("\n")
        lines = [line for line in lines if line]
        payload = StringIO("\n".join(lines))
        df_raw = pl.read_csv(
            payload,
            encoding="latin-1",
            has_header=False,
            separator=";",
            skip_rows=1,
            infer_schema_length=0,
            truncate_ragged_lines=True,
        )
        df_raw = df_raw[:, [1, 2, 4, 5]]
        df_raw.columns = [
            "station_id",
            "name",
            "latitude",
            "longitude",
        ]
        # TODO: remove the following workaround once the data is fixed upstream
        # since somewhere in 2024-02 one station of the station list is bugged
        # 603;150190400;CZ�STOCHOWA 2;Kucelinka;50 48 22;19 09 15
        # 604;150190410;CZ�STOCHOWA 3;Warta;50 48 50	19;07 58  <-- this is the bugged line
        # 605;152140100;DOLSK;My�la;52 48 10;14 50 35
        df_raw = df_raw.with_columns(
            pl.when(pl.col("station_id") == "150190410")
            .then(pl.lit("50 48 50").alias("latitude"))
            .otherwise(pl.col("latitude")),
            pl.when(pl.col("station_id") == "150190410")
            .then(pl.lit("19 07 58").alias("longitude"))
            .otherwise(pl.col("longitude")),
        )
        df_raw = df_raw.with_columns(
            pl.col("latitude").map_batches(convert_dms_string_to_dd),
            pl.col("longitude").map_batches(convert_dms_string_to_dd),
        )
        df_raw = df_raw.lazy()
        data = []
        # combinations of resolution and dataset
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name) for parameter in self.parameters
        }
        # for each combination of resolution and dataset create a new DataFrame with the columns
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df_raw.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        return pl.concat(data)
