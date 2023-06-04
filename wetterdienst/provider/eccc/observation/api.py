# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import gzip
import logging
from enum import Enum
from io import BytesIO
from typing import Generator, List, Optional, Tuple, Union

import polars as pl

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.exceptions import FailedDownload
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.eccc.observation.metadata.parameter import (
    EcccObservationDataset,
    EcccObservationParameter,
)
from wetterdienst.provider.eccc.observation.metadata.resolution import (
    EcccObservationResolution,
)
from wetterdienst.provider.eccc.observation.metadata.unit import EcccObservationUnit
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file

log = logging.getLogger(__name__)


class EcccObservationPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class EcccObservationValues(TimeseriesValues):
    _data_tz = Timezone.UTC

    _base_url = (
        "https://climate.weather.gc.ca/climate_data/bulk_data_e.html?"
        "format=csv&stationID={0}&timeframe={1}"
        "&submit= Download+Data"
    )

    _timeframe_mapping = {
        Resolution.HOURLY: "1",
        Resolution.DAILY: "2",
        Resolution.MONTHLY: "3",
        Resolution.ANNUAL: "4",
    }

    @property
    def _timeframe(self) -> str:
        """internal timeframe string for resolution"""
        return self._timeframe_mapping.get(self.sr.stations.resolution)

    _time_step_mapping = {
        Resolution.HOURLY: "HLY",
        Resolution.DAILY: "DLY",
        Resolution.MONTHLY: "MLY",
        Resolution.ANNUAL: "ANL",
    }

    @property
    def _time_step(self):
        """internal time step string for resolution"""
        return self._time_step_mapping.get(self.sr.stations.resolution)

    @staticmethod
    def _tidy_up_df(df: pl.LazyFrame) -> pl.LazyFrame:
        """
        Tidy up dataframe pairwise by column 'DATE', 'Temp (°C)', 'Temp Flag', ...

        :param df: DataFrame with loaded data
        :return: tidied DataFrame
        """
        data = []

        columns = df.columns
        for parameter_column, quality_column in zip(columns[1::2], columns[2::2]):
            df_parameter = df.select(
                pl.col(Columns.DATE.value),
                pl.lit(parameter_column).alias(Columns.PARAMETER.value),
                pl.col(parameter_column).apply(lambda v: v if v != "" else None).alias(Columns.VALUE.value),
                pl.col(quality_column).apply(lambda v: v if v != "" else None).alias(Columns.QUALITY.value),
            )
            data.append(df_parameter)

        try:
            return pl.concat(data)
        except ValueError:
            return pl.LazyFrame()

    def _collect_station_parameter(
        self, station_id: str, parameter: EcccObservationParameter, dataset: Enum
    ) -> pl.DataFrame:
        """

        :param station_id: station id being queried
        :param parameter: parameter being queried
        :param dataset: dataset of query, can be skipped as ECCC has unique dataset
        :return: pandas.DataFrame with data
        """
        meta = self.sr.df.filter(pl.col(Columns.STATION_ID.value).eq(station_id))

        start_year, end_year = (
            meta.select(
                [
                    pl.col(Columns.FROM_DATE.value).dt.year(),
                    pl.col(Columns.TO_DATE.value).dt.year(),
                ]
            )
            .transpose()
            .to_series()
            .to_list()
        )

        # start_date and end_date from request
        start_date = self.sr.stations.start_date
        end_date = self.sr.stations.end_date

        start_year = start_year and max(start_year, start_date and start_date.year or start_year)
        end_year = end_year and min(end_year, end_date and end_date.year or end_year)

        # Following lines may partially be based on @Zeitsperre's canada-climate-python
        # code at https://github.com/Zeitsperre/canada-climate-python/blob/
        # master/ECCC_stations_fulldownload.py
        data = []

        # check that station has a first and last year value
        if start_year and end_year:
            for url in self._create_file_urls(station_id, start_year, end_year):
                log.info(f"Acquiring file from {url}")
                payload = download_file(url, self.sr.stations.settings, CacheExpiry.NO_CACHE)
                df = pl.read_csv(payload, infer_schema_length=0).lazy()
                df = df.rename(mapping={col: col.lower() for col in df.columns})
                droppable_columns = [
                    "longitude (x)",
                    "latitude (y)",
                    "station name",
                    "climate id",
                    "year",
                    "month",
                    "day",
                    "time (lst)",
                    "data quality",
                ]
                df = df.drop(
                    columns=[col for col in droppable_columns if col in df.columns],
                )
                data.append(df)

        try:
            df = pl.concat(data)
        except ValueError:
            df = pl.LazyFrame()

        df = df.rename(
            mapping={col: Columns.DATE.value for col in ["date/time (lst)", "date/time"] if col in df.columns}
        )

        df = self._tidy_up_df(df)

        return df.with_columns(
            pl.col(Columns.DATE.value).str.strptime(pl.Datetime(time_zone="UTC"), fmt="%Y-%m-%d"),
            pl.lit(station_id).alias(Columns.STATION_ID.value),
            pl.when(pl.col(Columns.VALUE.value).str.starts_with("<"))
            .then(pl.col(Columns.VALUE.value).str.slice(1))
            .otherwise(pl.col(Columns.VALUE.value))
            .alias(Columns.VALUE.value)
            .cast(pl.Float64),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        ).collect()

    def _create_file_urls(self, station_id: str, start_year: int, end_year: int) -> Generator[str, None, None]:
        """

        :param station_id:
        :param start_year:
        :param end_year:
        :return:
        """
        resolution = self.sr.stations.resolution

        freq = "1y"
        if resolution == Resolution.HOURLY:
            freq = "1mo"

        # For hourly data request only necessary data to reduce amount of data being
        # downloaded and parsed
        for date in pl.date_range(dt.datetime(start_year, 1, 1), dt.datetime(end_year + 1, 1, 1), interval=freq):
            url = self._base_url.format(int(station_id), self._timeframe)
            url += f"&Year={date.year}"
            if resolution == Resolution.HOURLY:
                url += f"&Month={date.month}"
            yield url


class EcccObservationRequest(TimeseriesRequest):
    """
    Download weather data from Environment and Climate Change Canada (ECCC).
    - https://www.canada.ca/en/environment-climate-change.html
    - https://www.canada.ca/en/services/environment/weather.html

    Original code by Trevor James Smith. Thanks!
    - https://github.com/Zeitsperre/canada-climate-python

    """

    _provider = Provider.ECCC
    _kind = Kind.OBSERVATION
    _tz = Timezone.UTC
    _dataset_base = EcccObservationDataset
    _parameter_base = EcccObservationParameter  # replace with parameter enumeration
    _unit_base = EcccObservationUnit
    _resolution_type = ResolutionType.MULTI
    _resolution_base = EcccObservationResolution
    _period_type = PeriodType.FIXED
    _period_base = EcccObservationPeriod
    _has_datasets = True
    _unique_dataset = True
    _data_range = DataRange.FIXED
    _values = EcccObservationValues

    @property
    def _columns_mapping(self) -> dict:
        cm = self._base_columns_mapping

        cm.update(self._dates_columns_mapping)

        return cm

    @property
    def _dates_columns_mapping(self) -> dict:
        dcm = {}

        from_date, to_date = None, None
        if self.resolution == Resolution.HOURLY:
            from_date, to_date = "hly first year", "hly last year"
        elif self.resolution == Resolution.DAILY:
            from_date, to_date = "dly first year", "dly last year"
        elif self.resolution == Resolution.MONTHLY:
            from_date, to_date = "mly first year", "mly last year"
        elif self.resolution == Resolution.ANNUAL:
            from_date, to_date = "first year", "last year"

        dcm.update(
            {
                from_date: Columns.FROM_DATE.value,
                to_date: Columns.TO_DATE.value,
            }
        )

        return dcm

    _base_columns_mapping: dict = {
        "station id": Columns.STATION_ID.value,
        "name": Columns.NAME.value,
        "province": Columns.STATE.value,
        # "CLIMATE_ID",
        # "WMO_ID",
        # "TC_ID",
        "latitude (decimal degrees)": Columns.LATITUDE.value,
        "longitude (decimal degrees)": Columns.LONGITUDE.value,
        "elevation (m)": Columns.HEIGHT.value,
    }

    def __init__(
        self,
        parameter: List[Union[str, EcccObservationParameter, Parameter]],
        resolution: Union[str, EcccObservationResolution, Resolution],
        start_date: Optional[Union[str, dt.datetime]] = None,
        end_date: Optional[Union[str, dt.datetime]] = None,
        settings: Optional[Settings] = None,
    ):
        """

        :param parameter: parameter or list of parameters that are being queried
        :param resolution: resolution of data
        :param start_date: start date for values filtering
        :param end_date: end date for values filtering
        """
        super(EcccObservationRequest, self).__init__(
            parameter=parameter,
            resolution=resolution,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        # Acquire raw CSV payload.
        csv_payload, source = self._download_stations()

        header = 2 if source else 3

        # Read into Pandas data frame.
        df = pl.read_csv(csv_payload, has_header=True, skip_rows=header, infer_schema_length=0).lazy()

        df = df.rename(mapping={col: col.lower() for col in df.columns})

        df = df.drop(columns=["latitude", "longitude"])

        df = df.rename(mapping=self._columns_mapping)

        df = df.with_columns(
            pl.col(Columns.FROM_DATE.value).apply(lambda v: v or None),
            pl.col(Columns.TO_DATE.value).apply(lambda v: v or None),
            pl.col(Columns.HEIGHT.value).apply(lambda v: v or None),
        )

        df = df.with_columns(
            pl.col(Columns.FROM_DATE.value).map(lambda s: s.fill_null(s.cast(int).min())),
            pl.col(Columns.TO_DATE.value).map(lambda s: s.fill_null(s.cast(int).max())),
        )

        df = df.with_columns(
            pl.col(Columns.FROM_DATE.value).str.strptime(datatype=pl.Datetime, fmt="%Y"),
            pl.col(Columns.TO_DATE.value)
            .cast(int)
            .map(lambda s: s + 1)
            .apply(lambda v: dt.datetime(v, 1, 1) - dt.timedelta(days=1)),
        )

        return df.filter(pl.col(Columns.LATITUDE.value).ne("") & pl.col(Columns.LONGITUDE.value).ne(""))

    def _download_stations(self) -> Tuple[BytesIO, int]:
        """
        Download station list from ECCC FTP server.

        :return: CSV payload, source identifier
        """

        gdrive_url = "https://drive.google.com/uc?id=1HDRnj41YBWpMioLPwAFiLlK4SK8NV72C"
        http_url = (
            "https://github.com/earthobservations/testdata/raw/main/ftp.tor.ec.gc.ca/Pub/"
            "Get_More_Data_Plus_de_donnees/Station%20Inventory%20EN.csv.gz"
        )

        payload = None
        source = None
        try:
            payload = download_file(gdrive_url, self.settings, CacheExpiry.METAINDEX)
            source = 0
        except Exception:
            log.exception(f"Unable to access Google drive server at {gdrive_url}")

            # Fall back to different source.
            try:
                response = download_file(http_url, self.settings, CacheExpiry.METAINDEX)
                with gzip.open(response, mode="rb") as f:
                    payload = BytesIO(f.read())
                source = 1
            except Exception:
                log.exception(f"Unable to access HTTP server at {http_url}")

        if payload is None:
            raise FailedDownload("Unable to acquire ECCC stations list")

        return payload, source
