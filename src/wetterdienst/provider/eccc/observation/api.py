# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""ECCC observation data provider."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.eccc.observation.metadata import EcccObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel

log = logging.getLogger(__name__)


class EcccObservationValues(TimeseriesValues):
    """Values class for Environment and Climate Change Canada (ECCC) observation data."""

    _endpoint = "https://api.weather.gc.ca"

    _resolution_to_dataset_mapping: ClassVar[dict[Resolution, str]] = {
        Resolution.HOURLY: "climate-hourly",
        Resolution.DAILY: "climate-daily",
        Resolution.MONTHLY: "climate-monthly",
    }

    @staticmethod
    def _tidy_up_df(df: pl.LazyFrame) -> pl.LazyFrame:
        """Convert wide-format dataframe to long format, pairing value columns with their *_flag quality columns."""
        # Normalize column names to lowercase and rename LOCAL_DATE -> date
        flag_columns = {col for col in df.columns if col.endswith("_flag")}
        value_columns = [col for col in df.columns if col != "local_date" and col not in flag_columns]
        if not value_columns:
            return pl.LazyFrame()
        # Unpivot value columns to long format
        df_values = df.select(["local_date", *value_columns]).unpivot(
            on=value_columns,
            index="local_date",
            variable_name="parameter",
            value_name="value",
        )
        # Unpivot flag columns (strip _flag suffix so parameter names align)
        df_flags = df.select(["local_date", *flag_columns]).rename(
            {col: col.removesuffix("_flag") for col in flag_columns}
        )
        flag_value_columns = [col for col in df_flags.columns if col != "local_date"]
        df_flags = df_flags.unpivot(
            on=flag_value_columns,
            index="local_date",
            variable_name="parameter",
            value_name="quality",
        )
        return df_values.join(df_flags, on=["local_date", "parameter"], how="left").with_columns(
            pl.col("value").cast(pl.Float64),
        )

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect station dataset."""
        station_meta = self.sr.df.filter(pl.col("station_id") == station_id).to_dicts()[0]
        station_tz = self._get_timezone_from_station(station_id)
        data = []
        start_year = self.sr.start_date.year if self.sr.start_date else station_meta["start_date"].year
        end_year = self.sr.end_date.year if self.sr.end_date else station_meta["end_date"].year
        for year in range(start_year, end_year + 1):
            # shamefully (almost just) copied from meteostat/meteostat
            # source: https://github.com/meteostat/meteostat/blob/a5fd7970e41cd0e76a4cc5a1cb4e2cc2caea9c86/meteostat/providers/eccc/hourly.py#L58C1-L67C6
            # start with buffer
            start = (
                (dt.datetime(year, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")))
                .astimezone(ZoneInfo(station_tz))
                .strftime("%Y-%m-%dT%H:%M:%S")
            )
            # end with buffer
            end = (
                (dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=ZoneInfo("UTC")))
                .astimezone(ZoneInfo(station_tz))
                .strftime("%Y-%m-%dT%H:%M:%S")
            )
            url = (
                f"{self._endpoint}/collections/"
                f"{self._resolution_to_dataset_mapping[parameter_or_dataset.resolution.value]}/"
                f"items?STN_ID={station_id}&datetime={start}/{end}&f=json"
            )
            file = download_file(
                url=url,
                cache_dir=self.sr.stations.settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES,
                client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
                cache_disable=self.sr.stations.settings.cache_disable,
                use_certifi=self.sr.stations.settings.use_certifi,
            )
            if parameter_or_dataset.resolution.value in (Resolution.HOURLY, Resolution.DAILY):
                parameters = [
                    "COOLING_DEGREE_DAYS",
                    "COOLING_DEGREE_DAYS_FLAG",
                    "DIRECTION_MAX_GUST",
                    "DIRECTION_MAX_GUST_FLAG",
                    "HEATING_DEGREE_DAYS",
                    "HEATING_DEGREE_DAYS_FLAG",
                    "MAX_REL_HUMIDITY",
                    "MAX_REL_HUMIDITY_FLAG",
                    "MAX_TEMPERATURE",
                    "MAX_TEMPERATURE_FLAG",
                    "MEAN_TEMPERATURE",
                    "MEAN_TEMPERATURE_FLAG",
                    "MIN_REL_HUMIDITY",
                    "MIN_REL_HUMIDITY_FLAG",
                    "MIN_TEMPERATURE",
                    "MIN_TEMPERATURE_FLAG",
                    "SNOW_ON_GROUND",
                    "SNOW_ON_GROUND_FLAG",
                    "SPEED_MAX_GUST",
                    "SPEED_MAX_GUST_FLAG",
                    "TOTAL_PRECIPITATION",
                    "TOTAL_PRECIPITATION_FLAG",
                    "TOTAL_RAIN",
                    "TOTAL_RAIN_FLAG",
                    "TOTAL_SNOW",
                    "TOTAL_SNOW_FLAG",
                ]
            else:
                parameters = [
                    "BRIGHT_SUNSHINE",
                    "COOLING_DEGREE_DAYS",
                    "DAYS_WITH_PRECIP_GE_1MM",
                    "DAYS_WITH_VALID_MAX_TEMP",
                    "DAYS_WITH_VALID_MEAN_TEMP",
                    "DAYS_WITH_VALID_MIN_TEMP",
                    "DAYS_WITH_VALID_PRECIP",
                    "DAYS_WITH_VALID_SNOWFALL",
                    "DAYS_WITH_VALID_SUNSHINE",
                    "HEATING_DEGREE_DAYS",
                    "MAX_TEMPERATURE",
                    "MEAN_TEMPERATURE",
                    "MIN_TEMPERATURE",
                    "NORMAL_MEAN_TEMPERATURE",
                    "NORMAL_PRECIPITATION",
                    "NORMAL_SNOWFALL",
                    "NORMAL_SUNSHINE",
                    "SNOW_ON_GROUND_LAST_DAY",
                    "TOTAL_PRECIPITATION",
                    "TOTAL_SNOWFALL",
                ]

            _properties_schema = pl.Struct(
                {
                    "LOCAL_DATE": pl.String,
                }
                | {parameter: (pl.String if parameter.endswith("FLAG") else pl.Float64) for parameter in parameters}
            )
            df = pl.read_json(
                file.content,
                schema=pl.Schema(
                    {
                        "features": pl.List(
                            pl.Struct(
                                {
                                    "properties": _properties_schema,
                                }
                            )
                        ),
                    }
                ),
            )
            df = df.lazy()
            df = df.select(pl.col("features").explode().struct.field("properties")).unnest("properties")
            df = df.rename(str.lower)
            df = self._tidy_up_df(df)
            df = df.select(
                pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
                "parameter",
                pl.lit(station_id, dtype=pl.String).alias("station_id"),
                pl.col("local_date")
                .str.to_datetime("%Y-%m-%d %H:%M:%S")
                .dt.replace_time_zone(station_tz)
                .dt.convert_time_zone("UTC")
                .alias("date"),
                "value",
                pl.lit(None, dtype=pl.Float64).alias("quality"),
            )
            data.append(df)
        return pl.concat(data).collect()


@dataclass
class EcccObservationRequest(TimeseriesRequest):
    """Download weather data from Environment and Climate Change Canada (ECCC).

    - https://www.canada.ca/en/environment-climate-change.html
    - https://www.canada.ca/en/services/environment/weather.html

    Original code by Trevor James Smith. Thanks!
    - https://github.com/Zeitsperre/canada-climate-python

    """

    _endpoint = "https://api.weather.gc.ca"

    metadata = EcccObservationMetadata
    _values = EcccObservationValues

    # Mapping of Canadian timezone abbreviations to IANA timezone identifiers
    _timezone_mapping: ClassVar[dict] = {
        "ADT": "America/Halifax",  # Atlantic Daylight Time
        "AST": "America/Halifax",  # Atlantic Standard Time
        "CDT": "America/Winnipeg",  # Central Daylight Time
        "CST": "America/Winnipeg",  # Central Standard Time
        "EDT": "America/Toronto",  # Eastern Daylight Time
        "EST": "America/Toronto",  # Eastern Standard Time
        "MDT": "America/Edmonton",  # Mountain Daylight Time
        "MST": "America/Edmonton",  # Mountain Standard Time
        "NDT": "America/St_Johns",  # Newfoundland Daylight Time
        "NST": "America/St_Johns",  # Newfoundland Standard Time
        "PDT": "America/Vancouver",  # Pacific Daylight Time
        "PST": "America/Vancouver",  # Pacific Standard Time
        "YDT": "America/Whitehorse",  # Yukon Daylight Time
        "YST": "America/Whitehorse",  # Yukon Standard Time
    }

    def _all(self) -> pl.LazyFrame:
        file = download_file(
            url=f"{self._endpoint}/collections/climate-stations/items",
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
            use_certifi=self.settings.use_certifi,
        )
        df_raw = pl.read_json(
            file.content,
            schema=pl.Schema(
                {
                    "features": pl.List(
                        pl.Struct(
                            {
                                "type": pl.String,
                                "properties": pl.Struct(
                                    {
                                        "STN_ID": pl.Int64,
                                        "STATION_NAME": pl.String,
                                        "PROV_STATE_TERR_CODE": pl.String,  # alternative: ENG_PROV_NAME
                                        "LATITUDE": pl.Int64,
                                        "LONGITUDE": pl.Int64,
                                        "TIMEZONE": pl.String,
                                        "ELEVATION": pl.String,
                                        "FIRST_DATE": pl.String,
                                        "LAST_DATE": pl.String,
                                    }
                                ),
                            }
                        )
                    ),
                }
            ),
        )
        df_raw = df_raw.lazy()
        df_raw = df_raw.select(pl.col("features").explode())
        df_raw = df_raw.select(
            pl.col("features").struct.field("properties").struct.field("STN_ID").alias("station_id"),
            pl.col("features").struct.field("properties").struct.field("STATION_NAME").alias("name"),
            pl.col("features").struct.field("properties").struct.field("PROV_STATE_TERR_CODE").alias("state"),
            pl.col("features").struct.field("properties").struct.field("LATITUDE").alias("latitude"),
            pl.col("features").struct.field("properties").struct.field("LONGITUDE").alias("longitude"),
            pl.col("features").struct.field("properties").struct.field("ELEVATION").alias("height"),
            pl.col("features").struct.field("properties").struct.field("FIRST_DATE").alias("start_date"),
            pl.col("features").struct.field("properties").struct.field("LAST_DATE").alias("end_date"),
            pl.col("features").struct.field("properties").struct.field("TIMEZONE").alias("timezone"),
        )
        # Map timezone abbreviations to IANA timezone names
        df_raw = df_raw.with_columns(
            pl.col("timezone").replace(self._timezone_mapping, default=pl.col("timezone")),
        )
        # parse start_date and end_date to datetime with timezone from timezone column
        # First parse as naive datetime, then convert to proper timezone per row
        df_raw = df_raw.with_columns(
            pl.col("station_id").cast(pl.String),
            pl.col("start_date").str.to_datetime("%Y-%m-%d %H:%M:%S"),
            pl.col("end_date").str.to_datetime("%Y-%m-%d %H:%M:%S"),
            pl.col("height").cast(pl.Float64),
        )
        # Convert datetime to the timezone from the timezone column
        df_raw = df_raw.with_columns(
            pl.struct(["start_date", "timezone"])
            .map_elements(
                lambda row: row["start_date"].replace(tzinfo=ZoneInfo(row["timezone"])),
                return_dtype=pl.Datetime(time_zone="UTC"),
            )
            .alias("start_date"),
            pl.struct(["end_date", "timezone"])
            .map_elements(
                lambda row: row["end_date"].replace(tzinfo=ZoneInfo(row["timezone"])),
                return_dtype=pl.Datetime(time_zone="UTC"),
            )
            .alias("end_date"),
        )
        df_raw = df_raw.with_columns(
            pl.col("latitude") / 10_000_000,
            pl.col("longitude") / 10_000_000,
        )
        df_raw = df_raw.select(pl.all().exclude("timezone"))
        # combinations of resolution and dataset
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name) for parameter in self.parameters
        }
        data = []
        # for each combination of resolution and dataset create a new DataFrame with the columns
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df_raw.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        return pl.concat(data)
