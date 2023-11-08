# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from enum import Enum
from typing import List, Optional, Union

import pandas as pd
import polars as pl
from zoneinfo import ZoneInfo

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.noaa.ghcn.parameter import (
    PARAMETER_MULTIPLICATION_FACTORS,
    NoaaGhcnParameter,
)
from wetterdienst.provider.noaa.ghcn.unit import NoaaGhcnUnit
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.polars_util import read_fwf_from_df


class NoaaGhcnDataset(Enum):
    DAILY = "daily"


class NoaaGhcnResolution(Enum):
    DAILY = Resolution.DAILY.value


class NoaaGhcnPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class NoaaGhcnValues(TimeseriesValues):
    _data_tz = Timezone.DYNAMIC
    _base_url = "http://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/{station_id}.csv.gz"
    # use to get timezones from stations_result
    # multiplication factors
    _mp_factors = PARAMETER_MULTIPLICATION_FACTORS

    def _collect_station_parameter(self, station_id: str, parameter, dataset) -> pl.DataFrame:
        """
        Collection method for NOAA GHCN data. Parameter and dataset can be ignored as data
        is provided as a whole.

        :param station_id: station id of the station being queried
        :param parameter: parameter being queried
        :param dataset: dataset being queried
        :return: dataframe with read data
        """
        url = self._base_url.format(station_id=station_id)
        file = download_file(url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        df = pl.read_csv(
            source=file, separator=",", has_header=False, infer_schema_length=0, storage_options={"compression": "gzip"}
        )
        df = df.rename(
            mapping={
                "column_1": Columns.STATION_ID.value,
                "column_2": Columns.DATE.value,
                "column_3": Columns.PARAMETER.value,
                "column_4": Columns.VALUE.value,
            }
        )
        time_zone = self._get_timezone_from_station(station_id)
        df = df.with_columns(
            pl.col(Columns.DATE.value)
            .str.to_datetime("%Y%m%d")
            .map_elements(lambda date: date.replace(tzinfo=ZoneInfo(time_zone))),
            pl.col(Columns.PARAMETER.value).str.to_lowercase(),
            pl.col(Columns.VALUE.value).cast(float),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )
        df = df.with_columns(pl.col(Columns.DATE.value).dt.replace_time_zone("UTC"))
        df = df.filter(
            ~pl.col(Columns.PARAMETER.value).is_in(
                (
                    NoaaGhcnParameter.DAILY.TIME_WIND_GUST_MAX.value,
                    NoaaGhcnParameter.DAILY.TIME_WIND_GUST_MAX_1MILE_OR_1MIN.value,
                )
            )
        )
        df = self._apply_factors(df)
        return df.select(
            pl.col(Columns.STATION_ID.value),
            pl.col(Columns.DATE.value),
            pl.col(Columns.PARAMETER.value),
            pl.col(Columns.VALUE.value),
            pl.col(Columns.QUALITY.value),
        )

    def _apply_factors(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Method to apply given factors on parameters that have been
        converted to integers by making their unit one tenth e.g.
        2.0 [°C] becomes 20 [1/10 °C]
        :param df: DataFrame with given values
        :return: DataFrame with applied factors
        """
        data = []
        for parameter, group in df.group_by(pl.col(Columns.PARAMETER.value)):
            factor = self._mp_factors.get(parameter)
            if factor:
                group = group.with_columns(pl.col(Columns.VALUE.value).cast(float).mul(factor))
            data.append(group)
        return pl.concat(data)


class NoaaGhcnRequest(TimeseriesRequest):
    _provider = Provider.NOAA
    _kind = Kind.OBSERVATION
    _tz = Timezone.USA
    _dataset_base = NoaaGhcnDataset
    _parameter_base = NoaaGhcnParameter
    _unit_base = NoaaGhcnUnit
    _resolution_type = ResolutionType.FIXED
    _resolution_base = NoaaGhcnResolution
    _period_type = PeriodType.FIXED
    _period_base = NoaaGhcnPeriod
    _has_datasets = True
    _unique_dataset = True
    _data_range = DataRange.FIXED
    _values = NoaaGhcnValues

    def __init__(
        self,
        parameter: List[Union[str, NoaaGhcnParameter, Parameter]],
        start_date: Optional[Union[str, dt.datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, dt.datetime, pd.Timestamp]] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """

        :param parameter: list of parameter strings or parameter enums being queried
        :param start_date: start date for request or None if all data is requested
        :param end_date: end date for request or None if all data is requested
        """
        super().__init__(
            parameter=parameter,
            resolution=Resolution.DAILY,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        """
        Method to acquire station listing
        # https://github.com/awslabs/open-data-docs/tree/main/docs/noaa/noaa-ghcn
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
        :return: DataFrame with all stations_result
        """
        listings_url = "http://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-stations.txt"
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
        inventory_file = download_file(inventory_url, settings=self.settings, ttl=CacheExpiry.TWELVE_HOURS)
        inventory_df = pl.read_csv(inventory_file, has_header=False, truncate_ragged_lines=True)
        column_specs = ((0, 10), (36, 39), (41, 44))
        inventory_df = read_fwf_from_df(inventory_df, column_specs)
        inventory_df.columns = [Columns.STATION_ID.value, Columns.START_DATE.value, Columns.END_DATE.value]
        inventory_df = inventory_df.with_columns(
            pl.col(Columns.START_DATE.value).cast(int), pl.col(Columns.END_DATE.value).cast(int)
        )
        inventory_df = inventory_df.group_by(Columns.STATION_ID.value).agg(
            pl.col(Columns.START_DATE.value).min(), pl.col(Columns.END_DATE.value).max()
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
