# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from enum import Enum
from typing import List, Optional, Union

import pandas as pd
from pandas.tseries.offsets import YearEnd
from timezonefinder import TimezoneFinder

from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.noaa.ghcn.parameter import (
    PARAMETER_MULTIPLICATION_FACTORS,
    NoaaGhcnParameter,
)
from wetterdienst.provider.noaa.ghcn.unit import NoaaGhcnUnit
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file


class NoaaGhcnDataset(Enum):
    DAILY = "daily"


class NoaaGhcnResolution(Enum):
    DAILY = Resolution.DAILY.value


class NoaaGhcnPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class NoaaGhcnValues(ScalarValuesCore):
    _string_parameters = ()
    _irregular_parameters = ()
    _date_parameters = (
        NoaaGhcnParameter.DAILY.TIME_WIND_GUST_MAX.value,
        NoaaGhcnParameter.DAILY.TIME_WIND_GUST_MAX_1MILE_OR_1MIN.value,
    )

    _data_tz = Timezone.DYNAMIC

    _base_url = "http://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/{station_id}.csv.gz"

    # use to get timezones from stations_result
    _tf = TimezoneFinder()

    # multiplication factors
    _mp_factors = PARAMETER_MULTIPLICATION_FACTORS

    def _collect_station_parameter(self, station_id: str, parameter, dataset) -> pd.DataFrame:
        """
        Collection method for NOAA GHCN data. Parameter and dataset can be ignored as data
        is provided as a whole.

        :param station_id: station id of the station being queried
        :param parameter: parameter being queried
        :param dataset: dataset being queried
        :return: dataframe with read data
        """
        url = self._base_url.format(station_id=station_id)
        file = download_file(url, CacheExpiry.FIVE_MINUTES)
        df = pd.read_csv(file, sep=",", header=None, dtype=str, compression="gzip")
        df = df.iloc[:, :4]
        df.columns = [Columns.STATION_ID.value, Columns.DATE.value, Columns.PARAMETER.value, Columns.VALUE.value]
        df[Columns.PARAMETER.value] = df.loc[:, Columns.PARAMETER.value].str.lower()
        return self._apply_factors(df)

    def _apply_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Method to apply given factors on parameters that have been
        converted to integers by making their unit one tenth e.g.
        2.0 [°C] becomes 20 [1/10 °C]
        :param df: DataFrame with given values
        :return: DataFrame with applied factors
        """
        data = []

        for parameter, group in df.groupby(Columns.PARAMETER.value):
            factor = self._mp_factors.get(parameter)
            if factor:
                group[Columns.VALUE.value] = group[Columns.VALUE.value].astype(float) * factor

            data.append(group)

        return pd.concat(data)


class NoaaGhcnRequest(ScalarRequestCore):
    provider = Provider.NOAA
    kind = Kind.OBSERVATION

    _dataset_base = NoaaGhcnDataset
    _parameter_base = NoaaGhcnParameter

    _resolution_type = ResolutionType.FIXED
    _resolution_base = NoaaGhcnResolution
    _period_type = PeriodType.FIXED
    _period_base = NoaaGhcnPeriod
    _data_range = DataRange.FIXED

    _has_datasets = True
    _unique_dataset = True
    _has_tidy_data = True

    _unit_tree = NoaaGhcnUnit

    _values = NoaaGhcnValues

    _tz = Timezone.USA

    def __init__(
        self,
        parameter: List[str],
        start_date: Optional[Union[str, dt.datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, dt.datetime, pd.Timestamp]] = None,
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
        )

    def _all(self) -> pd.DataFrame:
        """
        Method to acquire station listing,
        :return: DataFrame with all stations_result
        """
        listings_url = "http://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-stations.txt"

        listings_file = download_file(listings_url, CacheExpiry.TWELVE_HOURS)

        # https://github.com/awslabs/open-data-docs/tree/main/docs/noaa/noaa-ghcn
        df = pd.read_fwf(
            listings_file,
            dtype=str,
            header=None,
            colspecs=[(0, 11), (12, 20), (21, 30), (31, 37), (38, 40), (41, 71), (80, 85)],
        )

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

        inventory_file = download_file(inventory_url, CacheExpiry.TWELVE_HOURS)

        inventory_df = pd.read_fwf(
            inventory_file,
            header=None,
            colspecs=[(0, 11), (36, 40), (41, 45)],
        )

        inventory_df.columns = [Columns.STATION_ID.value, Columns.FROM_DATE.value, Columns.TO_DATE.value]

        inventory_df = (
            inventory_df.groupby(Columns.STATION_ID.value)
            .agg({Columns.FROM_DATE.value: min, Columns.TO_DATE.value: max})
            .reset_index()
        )

        inventory_df[Columns.FROM_DATE.value] = pd.to_datetime(
            inventory_df[Columns.FROM_DATE.value], format="%Y", errors="coerce"
        )
        inventory_df[Columns.TO_DATE.value] = pd.to_datetime(
            inventory_df[Columns.TO_DATE.value], format="%Y", errors="coerce"
        )

        inventory_df[Columns.TO_DATE.value] += YearEnd()

        return df.merge(inventory_df, how="left", left_on=Columns.STATION_ID.value, right_on=Columns.STATION_ID.value)
