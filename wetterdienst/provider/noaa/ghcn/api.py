# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""NOAA GHCN api."""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.noaa.ghcn.metadata import (
    DAILY_PARAMETER_MULTIPLICATION_FACTORS,
    NoaaGhcnMetadata,
)
from wetterdienst.util.network import download_file
from wetterdienst.util.polars_util import read_fwf_from_df

if TYPE_CHECKING:
    from wetterdienst.core.timeseries.metadata import DatasetModel

log = logging.getLogger(__name__)


class NoaaGhcnValues(TimeseriesValues):
    """Values class for NOAA GHCN data provider."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        if parameter_or_dataset.resolution.value == Resolution.HOURLY:
            return self._collect_station_parameter_for_hourly(station_id=station_id, dataset=parameter_or_dataset)
        return self._collect_station_parameter_for_daily(station_id=station_id)

    def _collect_station_parameter_for_hourly(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        url = f"https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-station/GHCNh_{station_id}_por.psv"
        file = url.format(station_id=station_id)
        log.info(f"Downloading file {file}.")
        try:
            payload = download_file(file, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        except FileNotFoundError:
            return pl.DataFrame()
        time_zone = self._get_timezone_from_station(station_id)
        df = pl.read_csv(payload, skip_rows=1, separator="|", has_header=False)
        df.columns = [
            "station_id",
            "name",
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "latitude",
            "longitude",
            "elevation",
            "temperature",
            "temperature_measurement_code",
            "temperature_quality_code",
            "temperature_report_type",
            "temperature_source_code",
            "temperature_source_station_id",
            "dew_point_temperature",
            "dew_point_temperature_measurement_code",
            "dew_point_temperature_quality_code",
            "dew_point_temperature_report_type",
            "dew_point_temperature_source_code",
            "dew_point_temperature_source_station_id",
            "station_level_pressure",
            "station_level_pressure_measurement_code",
            "station_level_pressure_quality_code",
            "station_level_pressure_report_type",
            "station_level_pressure_source_code",
            "station_level_pressure_source_station_id",
            "sea_level_pressure",
            "sea_level_pressure_measurement_code",
            "sea_level_pressure_quality_code",
            "sea_level_pressure_report_type",
            "sea_level_pressure_source_code",
            "sea_level_pressure_source_station_id",
            "wind_direction",
            "wind_direction_measurement_code",
            "wind_direction_quality_code",
            "wind_direction_report_type",
            "wind_direction_source_code",
            "wind_direction_source_station_id",
            "wind_speed",
            "wind_speed_measurement_code",
            "wind_speed_quality_code",
            "wind_speed_report_type",
            "wind_speed_source_code",
            "wind_speed_source_station_id",
            "wind_gust",
            "wind_gust_measurement_code",
            "wind_gust_quality_code",
            "wind_gust_report_type",
            "wind_gust_source_code",
            "wind_gust_source_station_id",
            "precipitation",
            "precipitation_measurement_code",
            "precipitation_quality_code",
            "precipitation_report_type",
            "precipitation_source_code",
            "precipitation_source_station_id",
            "relative_humidity",
            "relative_humidity_measurement_code",
            "relative_humidity_quality_code",
            "relative_humidity_report_type",
            "relative_humidity_source_code",
            "relative_humidity_source_station_id",
            "wet_bulb_temperature",
            "wet_bulb_temperature_measurement_code",
            "wet_bulb_temperature_quality_code",
            "wet_bulb_temperature_report_type",
            "wet_bulb_temperature_source_code",
            "wet_bulb_temperature_source_station_id",
            "pres_wx_mw1",
            "pres_wx_mw1_measurement_code",
            "pres_wx_mw1_quality_code",
            "pres_wx_mw1_report_type",
            "pres_wx_mw1_source_code",
            "pres_wx_mw1_source_station_id",
            "pres_wx_mw2",
            "pres_wx_mw2_measurement_code",
            "pres_wx_mw2_quality_code",
            "pres_wx_mw2_report_type",
            "pres_wx_mw2_source_code",
            "pres_wx_mw2_source_station_id",
            "pres_wx_mw3",
            "pres_wx_mw3_measurement_code",
            "pres_wx_mw3_quality_code",
            "pres_wx_mw3_report_type",
            "pres_wx_mw3_source_code",
            "pres_wx_mw3_source_station_id",
            "pres_wx_au1",
            "pres_wx_au1_measurement_code",
            "pres_wx_au1_quality_code",
            "pres_wx_au1_report_type",
            "pres_wx_au1_source_code",
            "pres_wx_au1_source_station_id",
            "pres_wx_au2",
            "pres_wx_au2_measurement_code",
            "pres_wx_au2_quality_code",
            "pres_wx_au2_report_type",
            "pres_wx_au2_source_code",
            "pres_wx_au2_source_station_id",
            "pres_wx_au3",
            "pres_wx_au3_measurement_code",
            "pres_wx_au3_quality_code",
            "pres_wx_au3_report_type",
            "pres_wx_au3_source_code",
            "pres_wx_au3_source_station_id",
            "pres_wx_aw1",
            "pres_wx_aw1_measurement_code",
            "pres_wx_aw1_quality_code",
            "pres_wx_aw1_report_type",
            "pres_wx_aw1_source_code",
            "pres_wx_aw1_source_station_id",
            "pres_wx_aw2",
            "pres_wx_aw2_measurement_code",
            "pres_wx_aw2_quality_code",
            "pres_wx_aw2_report_type",
            "pres_wx_aw2_source_code",
            "pres_wx_aw2_source_station_id",
            "pres_wx_aw3",
            "pres_wx_aw3_measurement_code",
            "pres_wx_aw3_quality_code",
            "pres_wx_aw3_report_type",
            "pres_wx_aw3_source_code",
            "pres_wx_aw3_source_station_id",
            "snow_depth",
            "snow_depth_measurement_code",
            "snow_depth_quality_code",
            "snow_depth_report_type",
            "snow_depth_source_code",
            "snow_depth_source_station_id",
            "visibility",
            "visibility_measurement_code",
            "visibility_quality_code",
            "visibility_report_type",
            "visibility_source_code",
            "visibility_source_station_id",
            "altimeter",
            "altimeter_measurement_code",
            "altimeter_quality_code",
            "altimeter_report_type",
            "altimeter_source_code",
            "altimeter_source_station_id",
            "pressure_3hr_change",
            "pressure_3hr_change_measurement_code",
            "pressure_3hr_change_quality_code",
            "pressure_3hr_change_report_type",
            "pressure_3hr_change_source_code",
            "pressure_3hr_change_source_station_id",
            "sky_cover_1",
            "sky_cover_1_measurement_code",
            "sky_cover_1_quality_code",
            "sky_cover_1_report_type",
            "sky_cover_1_source_code",
            "sky_cover_1_source_station_id",
            "sky_cover_2",
            "sky_cover_2_measurement_code",
            "sky_cover_2_quality_code",
            "sky_cover_2_report_type",
            "sky_cover_2_source_code",
            "sky_cover_2_source_station_id",
            "sky_cover_3",
            "sky_cover_3_measurement_code",
            "sky_cover_3_quality_code",
            "sky_cover_3_report_type",
            "sky_cover_3_source_code",
            "sky_cover_3_source_station_id",
            "sky_cover_baseht_1",
            "sky_cover_baseht_1_measurement_code",
            "sky_cover_baseht_1_quality_code",
            "sky_cover_baseht_1_report_type",
            "sky_cover_baseht_1_source_code",
            "sky_cover_baseht_1_source_station_id",
            "sky_cover_baseht_2",
            "sky_cover_baseht_2_measurement_code",
            "sky_cover_baseht_2_quality_code",
            "sky_cover_baseht_2_report_type",
            "sky_cover_baseht_2_source_code",
            "sky_cover_baseht_2_source_station_id",
            "sky_cover_baseht_3",
            "sky_cover_baseht_3_measurement_code",
            "sky_cover_baseht_3_quality_code",
            "sky_cover_baseht_3_report_type",
            "sky_cover_baseht_3_source_code",
            "sky_cover_baseht_3_source_station_id",
            "precipitation_3_hour",
            "precipitation_3_hour_measurement_code",
            "precipitation_3_hour_quality_code",
            "precipitation_3_hour_report_type",
            "precipitation_3_hour_source_code",
            "precipitation_3_hour_source_station_id",
            "precipitation_6_hour",
            "precipitation_6_hour_measurement_code",
            "precipitation_6_hour_quality_code",
            "precipitation_6_hour_report_type",
            "precipitation_6_hour_source_code",
            "precipitation_6_hour_source_station_id",
            "precipitation_9_hour",
            "precipitation_9_hour_measurement_code",
            "precipitation_9_hour_quality_code",
            "precipitation_9_hour_report_type",
            "precipitation_9_hour_source_code",
            "precipitation_9_hour_source_station_id",
            "precipitation_12_hour",
            "precipitation_12_hour_measurement_code",
            "precipitation_12_hour_quality_code",
            "precipitation_12_hour_report_type",
            "precipitation_12_hour_source_code",
            "precipitation_12_hour_source_station_id",
            "precipitation_15_hour",
            "precipitation_15_hour_measurement_code",
            "precipitation_15_hour_quality_code",
            "precipitation_15_hour_report_type",
            "precipitation_15_hour_source_code",
            "precipitation_15_hour_source_station_id",
            "precipitation_18_hour",
            "precipitation_18_hour_measurement_code",
            "precipitation_18_hour_quality_code",
            "precipitation_18_hour_report_type",
            "precipitation_18_hour_source_code",
            "precipitation_18_hour_source_station_id",
            "precipitation_21_hour",
            "precipitation_21_hour_measurement_code",
            "precipitation_21_hour_quality_code",
            "precipitation_21_hour_report_type",
            "precipitation_21_hour_source_code",
            "precipitation_21_hour_source_station_id",
            "precipitation_24_hour",
            "precipitation_24_hour_measurement_code",
            "precipitation_24_hour_quality_code",
            "precipitation_24_hour_report_type",
            "precipitation_24_hour_source_code",
            "precipitation_24_hour_source_station_id",
            "remarks",
            "remarks_measurement_code",
            "remarks_quality_code",
            "remarks_report_type",
            "remarks_source_code",
            "remarks_source_station_id",
        ]
        parameters = [parameter.name_original for parameter in dataset]
        df = df.select(
            "station_id",
            pl.concat_str(["year", "month", "day", "hour", "minute"], separator="-")
            .map_elements(
                lambda date: dt.datetime.strptime(date, "%Y-%m-%d-%H-%M")
                .replace(tzinfo=ZoneInfo(time_zone))
                .astimezone(ZoneInfo("UTC")),
                return_dtype=pl.Datetime,
            )
            .alias("date"),
            *parameters,
        )
        df = df.with_columns(pl.col(Columns.DATE.value).dt.replace_time_zone("UTC"))
        df = df.unpivot(
            index=["station_id", "date"],
            on=parameters,
            variable_name="parameter",
            value_name="value",
        )
        return df.with_columns(
            pl.col("parameter").str.to_lowercase(),
            pl.col("value").cast(pl.Float64),
            pl.lit(value=None, dtype=pl.Float64).alias("quality"),
        )

    def _collect_station_parameter_for_daily(
        self,
        station_id: str,
    ) -> pl.DataFrame:
        """Collect station parameter for daily resolution."""
        url = "http://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/{station_id}.csv.gz"
        file = url.format(station_id=station_id)
        log.info(f"Downloading file {file}.")
        payload = download_file(file, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        df = pl.read_csv(
            source=payload,
            separator=",",
            has_header=False,
            infer_schema_length=0,
            storage_options={"compression": "gzip"},
        )
        df = df.rename(
            mapping={
                "column_1": Columns.STATION_ID.value,
                "column_2": Columns.DATE.value,
                "column_3": Columns.PARAMETER.value,
                "column_4": Columns.VALUE.value,
            },
        )
        time_zone = self._get_timezone_from_station(station_id)
        df = df.with_columns(
            pl.col(Columns.DATE.value).map_elements(
                lambda date: dt.datetime.strptime(date, "%Y%m%d")
                .replace(tzinfo=ZoneInfo(time_zone))
                .astimezone(ZoneInfo("UTC")),
                return_dtype=pl.Datetime,
            ),
            pl.col(Columns.PARAMETER.value).str.to_lowercase(),
            pl.col(Columns.VALUE.value).cast(float),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )
        df = df.with_columns(pl.col(Columns.DATE.value).dt.replace_time_zone("UTC"))
        df = self._apply_daily_factors(df)
        return df.select(
            pl.col(Columns.STATION_ID.value),
            pl.col(Columns.DATE.value),
            pl.col(Columns.PARAMETER.value),
            pl.col(Columns.VALUE.value),
            pl.col(Columns.QUALITY.value),
        )

    @staticmethod
    def _apply_daily_factors(df: pl.DataFrame) -> pl.DataFrame:
        """Apply given factors on parameters that have been converted to integers.

        Make their unit one tenth e.g. 2.0 [°C] becomes 20 [1/10 °C]
        """
        data = []
        for (parameter,), df_group in df.group_by([Columns.PARAMETER.value]):
            factor = DAILY_PARAMETER_MULTIPLICATION_FACTORS.get(parameter)
            if factor:
                df_group = df_group.with_columns(pl.col(Columns.VALUE.value).cast(float).mul(factor))
            data.append(df_group)
        return pl.concat(data)


class NoaaGhcnRequest(TimeseriesRequest):
    """Request class for NOAA GHCN data provider."""

    metadata = NoaaGhcnMetadata
    _values = NoaaGhcnValues

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """Initialize the request for the NOAA GHCN data provider.

        Args:
            parameters: requested parameters
            start_date: start date
            end_date: end date
            settings: settings for the request

        """
        super().__init__(
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        resolution = self.parameters[0].dataset.resolution.value
        if resolution == Resolution.HOURLY:
            return self._create_metaindex_for_ghcn_hourly()
        return self._create_metaindex_for_ghcn_daily()

    def _create_metaindex_for_ghcn_hourly(self) -> pl.LazyFrame:
        file = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh-station-list.csv"
        log.info(f"Downloading file {file}.")
        payload = download_file(file, settings=self.settings, ttl=CacheExpiry.METAINDEX)
        df = pl.read_csv(
            payload,
            has_header=False,
            columns=[
                "column_1",
                "column_2",
                "column_3",
                "column_4",
                "column_5",
                "column_6",
            ],
        )
        df.columns = [
            "station_id",
            "latitude",
            "longitude",
            "elevation",
            "state",
            "name",
        ]
        df = df.with_columns(
            pl.all().str.strip_chars(),
        )
        return df.lazy()

    def _create_metaindex_for_ghcn_daily(self) -> pl.LazyFrame:
        """Acquire station listing for ghcn daily.

        station listing
        | Variable     | Columns | Type      | Example     |
        |--------------|---------|-----------|-------------|
        | ID           | 1-11    | Character | EI000003980 |
        | LATITUDE     | 13-20   | Real      | 55.3717     |
        | LONGITUDE    | 22-30   | Real      | -7.3400     |
        | ELEVATION    | 32-37   | Real      | 21.0        |
        | STATE        | 39-40   | Character |             |
        | NAME         | 42-71   | Character | MALIN HEAD  |
        | GSN FLAG     | 73-75   | Character | GSN         |
        | HCN/CRN FLAG | 77-79   | Character |             |
        | WMO ID       | 81-85   | Character | 03980       |

        inventory listing
        | Variable  | Columns | Type      |
        |-----------|---------|-----------|
        | ID        | 1-11    | CHARACTER |
        | LATITUDE  | 13-20   | REAL      |
        | LONGITUDE | 22-30   | REAL      |
        | ELEMENT   | 32-35   | CHARACTER |
        | FIRSTYEAR | 37-40   | INTEGER   |
        | LASTYEAR  | 42-45   | INTEGER   |
        """
        listings_url = "http://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-stations.txt"
        log.info(f"Downloading file {listings_url}.")
        listings_file = download_file(listings_url, settings=self.settings, ttl=CacheExpiry.TWELVE_HOURS)
        df = pl.read_csv(listings_file, has_header=False, truncate_ragged_lines=True)
        column_specs = ((0, 10), (12, 19), (21, 29), (31, 36), (38, 39), (41, 70), (80, 84))
        df = read_fwf_from_df(df, column_specs)
        df.columns = [
            Columns.STATION_ID.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
            Columns.STATE.value,
            Columns.NAME.value,
            Columns.WMO_ID.value,
        ]

        inventory_url = "http://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-inventory.txt"
        log.info(f"Downloading file {inventory_url}.")
        inventory_file = download_file(inventory_url, settings=self.settings, ttl=CacheExpiry.TWELVE_HOURS)
        inventory_df = pl.read_csv(inventory_file, has_header=False, truncate_ragged_lines=True)
        column_specs = ((0, 10), (36, 39), (41, 44))
        inventory_df = read_fwf_from_df(inventory_df, column_specs)
        inventory_df.columns = [Columns.STATION_ID.value, Columns.START_DATE.value, Columns.END_DATE.value]
        inventory_df = inventory_df.with_columns(
            pl.col(Columns.START_DATE.value).cast(int),
            pl.col(Columns.END_DATE.value).cast(int),
        )
        inventory_df = inventory_df.group_by([Columns.STATION_ID.value]).agg(
            pl.col(Columns.START_DATE.value).min(),
            pl.col(Columns.END_DATE.value).max(),
        )
        inventory_df = inventory_df.with_columns(
            pl.col(Columns.START_DATE.value).cast(str).str.to_datetime("%Y"),
            pl.col(Columns.END_DATE.value)
            .map_batches(lambda s: s + 1)
            .cast(str)
            .str.to_datetime("%Y")
            .map_batches(lambda s: s - dt.timedelta(days=1)),
        )
        return df.join(other=inventory_df, how="left", on=[Columns.STATION_ID.value]).lazy()
