# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from functools import partial
from io import BytesIO
from typing import List, Optional, Union

import pandas as pd

# from s3fs import S3FileSystem
import polars as pl
from pandas.tseries.offsets import YearEnd
from s3fs import S3FileSystem
from tzfpy import get_tz

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.noaa.isd.parameter import (
    PARAMETER_MULTIPLICATION_FACTORS,
    NoaaIsdParameter,
)
from wetterdienst.provider.noaa.isd.unit import NoaaIsdUnit
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file, list_remote_files_fsspec


class NoaaGhcnDataset(Enum):
    HOURLY = "hourly"


class NoaaGhcnResolution(Enum):
    HOURLY = Resolution.HOURLY.value


class NoaaGhcnPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class NoaaGhcnValues(TimeseriesValues):
    _data_tz = Timezone.DYNAMIC
    _url = "https://www.ncei.noaa.gov/data/global-hourly/access/{year}/"
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
        if self.sr.start_date:
            years = list(range(self.sr.start_date.year, self.sr.end_date.year + 1))
        else:
            years = list(range(1901, dt.datetime.utcnow().year + 1))
        with ThreadPoolExecutor() as p:
            files = list(p.map(lambda url: list_remote_files_fsspec(url, self.sr.stations.settings, ttl=CacheExpiry.METAINDEX),
                               [self._url.format(year=year) for year in years]))
        files = [item for sublist in files for item in sublist]
        df_files = pl.DataFrame({"file": files})
        df_files = df_files.filter(
            pl.col("file").str.ends_with(".csv")
        )
        df_files = df_files.with_columns(
            [
                pl.col("file").str.split("/").list.last().str.rstrip(".csv").alias(Columns.STATION_ID.value),
            ]
        )
        df_files = df_files.filter(pl.col(Columns.STATION_ID.value) == station_id)
        with ThreadPoolExecutor() as p:
            data = list(ThreadPoolExecutor().map(
                lambda url: download_file(url, self.sr.stations.settings, ttl=CacheExpiry.TWELVE_HOURS),
                df_files.get_column("file").to_list())
            )
        dfs = []
        for payload in data:
            df = pl.read_csv(payload)
            dfs.append(df)

        df = pl.concat(dfs)
        print(df)
        # df = pd.read_csv(file, sep=",", header=None, dtype=str, compression="gzip")
        # df = df.iloc[:, :4]
        # df.columns = [Columns.STATION_ID.value, Columns.DATE.value, Columns.PARAMETER.value, Columns.VALUE.value]
        # df[Columns.PARAMETER.value] = df.loc[:, Columns.PARAMETER.value].str.lower()
        # return self._apply_factors(df)
        return df

    # @staticmethod
    # def _download_file(fs: S3FileSystem, url):
    #     payload = fs.cat(url)
    #     return BytesIO(payload)

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


class NoaaIsdRequest(TimeseriesRequest):
    _provider = Provider.NOAA
    _kind = Kind.OBSERVATION
    _dataset_base = NoaaGhcnDataset
    _parameter_base = NoaaIsdParameter
    _resolution_type = ResolutionType.FIXED
    _resolution_base = NoaaGhcnResolution
    _period_type = PeriodType.FIXED
    _period_base = NoaaGhcnPeriod
    _data_range = DataRange.FIXED
    _has_datasets = True
    _unique_dataset = True
    _unit_base = NoaaIsdUnit
    _values = NoaaGhcnValues
    _tz = Timezone.USA
    _url = "https://noaa-isd-pds.s3.amazonaws.com/isd-history.csv"
    _base_columns = (
        Columns.STATION_ID.value,
        Columns.USAF.value,
        Columns.WBAN.value,
        Columns.ICAO_ID.value,
        Columns.START_DATE.value,
        Columns.END_DATE.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.HEIGHT.value,
        Columns.NAME.value,
        Columns.STATE.value,
        Columns.COUNTRY.value,
    )

    def __init__(
        self,
        parameter: List[str],
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
            resolution=Resolution.HOURLY,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        """
        Method to acquire station listing,
        :return: DataFrame with all stations_result
        """
        payload = download_file(self._url, settings=self.settings, ttl=CacheExpiry.TWELVE_HOURS)

        df = pl.read_csv(
            payload,
            schema={
                "USAF": pl.Utf8,
                "WBAN": pl.Utf8,
                "STATION NAME": pl.Utf8,
                "CTRY": pl.Utf8,
                "STATE": pl.Utf8,
                "ICAO": pl.Utf8,
                "LAT": pl.Float64,
                "LON": pl.Float64,
                "ELEV(M)": pl.Float64,
                "BEGIN": pl.Utf8,
                "END": pl.Utf8,
            },
            null_values=[""],
        )

        df.columns = [
            Columns.USAF.value,
            Columns.WBAN.value,
            Columns.NAME.value,
            Columns.COUNTRY.value,
            Columns.STATE.value,
            Columns.ICAO_ID.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
            Columns.START_DATE.value,
            Columns.END_DATE.value,
        ]

        df = df.with_columns(
            [
                pl.struct([pl.col(Columns.USAF.value), pl.col(Columns.WBAN.value)]).apply(
                    lambda ids: f"{ids['usaf']}{ids['wban']}").alias(Columns.STATION_ID.value),
                pl.col(Columns.START_DATE.value).str.to_datetime(format="%Y%m%d"),
                pl.col(Columns.END_DATE.value).str.to_datetime(format="%Y%m%d"),
            ]
        )

        return df.lazy()


if __name__ == "__main__":
    request = NoaaIsdRequest(
        parameter="temperature_air_mean_200",
        start_date="1992-01-01",
    ).filter_by_station_id("09488099999")
    print(request.df)
    print(request.df.write_json(row_oriented=True))
    values = request.values.all()
    print(values.df)
