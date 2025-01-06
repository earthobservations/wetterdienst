# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import polars as pl
import portion as P
from dateutil.relativedelta import relativedelta
from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.core.timeseries.metadata import DatasetModel, build_metadata_model
from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.imgw.metadata import _METADATA
from wetterdienst.util.geo import convert_dms_string_to_dd
from wetterdienst.util.network import download_file, list_remote_files_fsspec

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
                }
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
                }
            ],
        },
    ],
}
ImgwHydrologyMetadata = build_metadata_model(ImgwHydrologyMetadata, "ImgwHydrologyMetadata")


class ImgwHydrologyValues(TimeseriesValues):
    _endpoint = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/{resolution}/"
    _file_schema = {
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
        self, station_id: str, parameter_or_dataset: DatasetModel
    ) -> pl.DataFrame:
        """

        :param station_id:
        :param parameter:
        :param dataset:
        :return:
        """
        urls = self._get_urls(parameter_or_dataset)
        with ThreadPoolExecutor() as p:
            files_in_bytes = p.map(
                lambda file: download_file(url=file, settings=self.sr.settings, ttl=CacheExpiry.FIVE_MINUTES),
                urls,
            )
        data = []
        file_schema = self._file_schema[parameter_or_dataset.resolution.value][parameter_or_dataset.name]
        for file_in_bytes in files_in_bytes:
            df = self._parse_file(
                file_in_bytes=file_in_bytes,
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
        return df.with_columns(
            pl.col("date").dt.replace_time_zone("UTC"),
            pl.col("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )

    def _parse_file(
        self, file_in_bytes: bytes, station_id: str, dataset: DatasetModel, file_schema: dict
    ) -> pl.DataFrame:
        """Function to parse hydrological zip file, parses all files and combines
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
        """Function to parse a single file out of the zip file

        :param file: unzipped file bytes
        :return: polars.DataFrame with parsed data
        """
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
            exp2 = pl.datetime("year", "month", "day").alias(Columns.DATE.value)
        else:
            exp1 = pl.all().exclude(["year", "month"])
            exp2 = pl.datetime("year", "month", 1).alias(Columns.DATE.value)
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

    def _get_urls(self, dataset: DatasetModel) -> pl.Series:
        """Get file urls from server

        :param dataset: dataset for which the filelist is retrieved
        :return:
        """
        url = self._endpoint.format(resolution=dataset.resolution.name_original, dataset=dataset.name_original)
        files = list_remote_files_fsspec(url, self.sr.settings)
        df_files = pl.DataFrame({"url": files})
        df_files = df_files.with_columns(pl.col("url").str.split("/").list.last().alias("file"))
        df_files = df_files.filter(pl.col("file").str.ends_with(".zip") & ~pl.col("file").str.starts_with("zjaw"))
        if self.sr.start_date:
            interval = P.closed(self.sr.start_date, self.sr.end_date)
            if dataset.resolution.value == Resolution.DAILY:
                df_files = df_files.with_columns(
                    pl.col("file").str.strip_chars_end(".zip").str.split("_").list.slice(1).alias("year_month"),
                )
                df_files = df_files.with_columns(
                    pl.col("year_month").list.first().cast(pl.Int64).alias("year"),
                    pl.col("year_month").list.last().cast(pl.Int64).alias("month"),
                )
                df_files = df_files.with_columns(
                    pl.when(pl.col("month") <= 2).then(pl.col("year") - 1).otherwise(pl.col("year")).alias("year"),
                    pl.when(pl.col("month").add(10).gt(12))
                    .then(pl.col("month").sub(2))
                    .otherwise(pl.col("month"))
                    .alias("month"),
                )
                df_files = df_files.with_columns(
                    pl.struct(["year", "month"])
                    .map_elements(
                        lambda x: [
                            dt.datetime(x["year"], x["month"], 1),
                            dt.datetime(x["year"], x["month"], 1) + relativedelta(months=1) - relativedelta(days=1),
                        ],
                        return_dtype=pl.Array(pl.Datetime, shape=2),
                    )
                    .alias("date_range"),
                )
            else:
                df_files = df_files.with_columns(
                    pl.col("file")
                    .str.strip_chars_end(".zip")
                    .str.split("_")
                    .list.last()
                    .str.to_datetime("%Y", time_zone="UTC", strict=False)
                    .map_elements(
                        lambda d: [d - relativedelta(months=2), d + relativedelta(months=11) - relativedelta(days=1)],
                        return_dtype=pl.Array(pl.Datetime, shape=2),
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
                .map_elements(lambda dates: P.closed(dates["start_date"], dates["end_date"]), return_dtype=pl.Object)
                .alias("interval"),
            )
            df_files = df_files.filter(
                pl.col("interval").map_elements(lambda i: i.overlaps(interval), return_dtype=pl.Boolean)
            )
        return df_files.get_column("url")


class ImgwHydrologyRequest(TimeseriesRequest):
    metadata = ImgwHydrologyMetadata
    _values = ImgwHydrologyValues
    _endpoint = "https://dane.imgw.pl/datastore/getfiledown/Arch/Telemetria/Hydro/kody_stacji.csv"

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ):
        super().__init__(
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        """

        :return:
        """
        log.info(f"Downloading file {self._endpoint}.")
        payload = download_file(self._endpoint, settings=self.settings, ttl=CacheExpiry.METAINDEX)
        # skip empty lines in the csv file
        lines = payload.read().decode("latin-1").replace("\r", "").split("\n")
        lines = [line for line in lines if line]
        payload = StringIO("\n".join(lines))
        df = pl.read_csv(
            payload,
            encoding="latin-1",
            has_header=False,
            separator=";",
            skip_rows=1,
            infer_schema_length=0,
            truncate_ragged_lines=True,
        )
        df = df[:, [1, 2, 4, 5]]
        df.columns = [
            Columns.STATION_ID.value,
            Columns.NAME.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
        ]
        # TODO: remove the following workaround once the data is fixed upstream
        # since somewhere in 2024-02 one station of the station list is bugged
        # 603;150190400;CZ�STOCHOWA 2;Kucelinka;50 48 22;19 09 15
        # 604;150190410;CZ�STOCHOWA 3;Warta;50 48 50	19;07 58  <-- this is the bugged line
        # 605;152140100;DOLSK;My�la;52 48 10;14 50 35
        df = df.with_columns(
            pl.when(pl.col(Columns.STATION_ID.value) == "150190410")
            .then(pl.lit("50 48 50").alias(Columns.LATITUDE.value))
            .otherwise(pl.col(Columns.LATITUDE.value)),
            pl.when(pl.col(Columns.STATION_ID.value) == "150190410")
            .then(pl.lit("19 07 58").alias(Columns.LONGITUDE.value))
            .otherwise(pl.col(Columns.LONGITUDE.value)),
        )
        df = df.lazy()
        return df.with_columns(
            pl.col(Columns.LATITUDE.value).map_batches(convert_dms_string_to_dd),
            pl.col(Columns.LONGITUDE.value).map_batches(convert_dms_string_to_dd),
        )
