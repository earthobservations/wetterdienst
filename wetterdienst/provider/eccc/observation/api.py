# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import gzip
import logging
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Generator, Optional, Tuple, Union

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from requests_ftp.ftp import FTPSession
from urllib3 import Retry

from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.exceptions import FailedDownload
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.eccc.observation.metadata.dataset import (
    EcccObservationDataset,
    EcccObservationDatasetTree,
)
from wetterdienst.provider.eccc.observation.metadata.parameter import (
    EcccObservationParameter,
)
from wetterdienst.provider.eccc.observation.metadata.resolution import (
    EccObservationResolution,
)
from wetterdienst.provider.eccc.observation.metadata.unit import EcccObservationUnit
from wetterdienst.util.cache import payload_cache_twelve_hours

log = logging.getLogger(__name__)


class EcccObservationValues(ScalarValuesCore):

    _string_parameters = []
    _integer_parameters = []
    _irregular_parameters = []

    _data_tz = Timezone.UTC

    _has_quality = True

    _session = requests.Session()
    _session.mount(
        "https://", HTTPAdapter(max_retries=Retry(total=10, connect=5, read=5))
    )

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
        """ internal timeframe string for resolution """
        return self._timeframe_mapping.get(self.stations.stations.resolution)

    _time_step_mapping = {
        Resolution.HOURLY: "HLY",
        Resolution.DAILY: "DLY",
        Resolution.MONTHLY: "MLY",
        Resolution.ANNUAL: "ANL",
    }

    @property
    def _time_step(self):
        """ internal time step string for resolution """
        return self._time_step_mapping.get(self.stations.stations.resolution)

    def _create_humanized_parameters_mapping(self):
        # TODO: change to something general, depending on ._has_datasets
        hcnm = {
            parameter.value: parameter.name.lower()
            for parameter in self.stations.stations._parameter_base[
                self.stations.stations.resolution.name
            ]
        }

        return hcnm

    def _tidy_up_df(self, df: pd.DataFrame, dataset) -> pd.DataFrame:
        """
        Tidy up dataframe pairwise by column 'DATE', 'Temp (°C)', 'Temp Flag', ...

        :param df:
        :return:
        """

        data = []

        columns = df.columns
        for parameter_column, quality_column in zip(columns[1::2], columns[2::2]):
            df_parameter = pd.DataFrame(
                {
                    Columns.DATE.value: df[Columns.DATE.value],
                    Columns.VALUE.value: df[parameter_column],
                    Columns.QUALITY.value: df[quality_column],
                }
            )
            df_parameter[Columns.PARAMETER.value] = parameter_column
            data.append(df_parameter)

        try:
            df_tidy = pd.concat(data, ignore_index=True)
        except ValueError:
            df_tidy = pd.DataFrame()

        return df_tidy

    def _collect_station_parameter(
        self, station_id: str, parameter: EcccObservationParameter, dataset: Enum
    ) -> pd.DataFrame:
        """

        :param station_id: station id being queried
        :param parameter: parameter being queried
        :param dataset: dataset of query, can be skipped as ECCC has unique dataset
        :return: pandas.DataFrame with data
        """
        meta = self.stations.df[
            self.stations.df[Columns.STATION_ID.value] == station_id
        ]

        name, from_date, to_date = (
            meta[
                [
                    Columns.NAME.value,
                    Columns.FROM_DATE.value,
                    Columns.TO_DATE.value,
                ]
            ]
            .values.flatten()
            .tolist()
        )

        # start and end year from station
        start_year = None if pd.isna(from_date) else from_date.year
        end_year = None if pd.isna(to_date) else to_date.year

        # start_date and end_date from request
        start_date = self.stations.stations.start_date
        end_date = self.stations.stations.end_date

        start_year = start_year and max(
            start_year, start_date and start_date.year or start_year
        )
        end_year = end_year and min(end_year, end_date and end_date.year or end_year)

        # Following lines may partially be based on @Zeitsperre's canada-climate-python
        # code at https://github.com/Zeitsperre/canada-climate-python/blob/
        # master/ECCC_stations_fulldownload.py
        df = pd.DataFrame()

        # check that station has a first and last year value
        if start_year and end_year:
            for url in self._create_file_urls(station_id, start_year, end_year):
                log.info(f"Acquiring file from {url}")

                # TODO change this back to verify=True
                payload = self._session.get(url, timeout=60)

                df_temp = pd.read_csv(BytesIO(payload.content))

                df_temp = df_temp.rename(columns=str.lower)

                df_temp = df_temp.drop(
                    columns=[
                        "longitude (x)",
                        "latitude (y)",
                        "station name",
                        "climate id",
                        "year",
                        "month",
                        "day",
                        "time (lst)",
                    ],
                    errors="ignore",
                )

                df = df.append(df_temp)

            df = df.rename(
                columns={
                    "date/time (lst)": Columns.DATE.value,
                    "date/time": Columns.DATE.value,
                }
            )

            df = df.reset_index(drop=True)

        df = df.drop(columns=["data quality"], errors="ignore")

        df[Columns.STATION_ID.value] = station_id

        return df

    def _create_file_urls(
        self, station_id: str, start_year: int, end_year: int
    ) -> Generator[str, None, None]:
        """

        :param station_id:
        :param start_year:
        :param end_year:
        :return:
        """
        resolution = self.stations.stations.resolution

        freq = "Y"
        if resolution == Resolution.HOURLY:
            freq = "M"

        # For hourly data request only necessary data to reduce amount of data being
        # downloaded and parsed
        for date in pd.date_range(
            f"{start_year}-01-01", f"{end_year + 1}-01-01", freq=freq, closed=None
        ):
            url = self._base_url.format(int(station_id), self._timeframe)

            url += f"&Year={date.year}"

            if resolution == Resolution.HOURLY:
                url += f"&Month={date.month}"

            yield url


class EcccObservationRequest(ScalarRequestCore):
    """
    Download weather data from Environment and Climate Change Canada (ECCC).
    - https://www.canada.ca/en/environment-climate-change.html
    - https://www.canada.ca/en/services/environment/weather.html

    Original code by Trevor James Smith. Thanks!
    - https://github.com/Zeitsperre/canada-climate-python

    """

    provider = Provider.ECCC
    kind = Kind.OBSERVATION

    _tz = Timezone.UTC

    _resolution_base = EccObservationResolution
    _resolution_type = ResolutionType.MULTI
    _period_type = PeriodType.FIXED
    _period_base = Period.HISTORICAL
    _parameter_base = EcccObservationParameter  # replace with parameter enumeration
    _data_range = DataRange.LOOSELY
    _has_datasets = True
    _dataset_base = EcccObservationDataset
    _dataset_tree = EcccObservationDatasetTree
    _unique_dataset = True

    _unit_tree = EcccObservationUnit

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
        parameter: Tuple[Union[str, EcccObservationParameter]],
        resolution: Union[EccObservationResolution, Resolution],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        humanize: bool = True,
        tidy: bool = True,
        si_units: bool = True,
    ):
        super(EcccObservationRequest, self).__init__(
            parameter=parameter,
            resolution=resolution,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
            humanize=humanize,
            tidy=tidy,
            si_units=si_units,
        )

    def _all(self) -> pd.DataFrame:
        # Acquire raw CSV payload.
        csv_payload = self._download_stations()

        # Read into Pandas data frame.
        df = pd.read_csv(BytesIO(csv_payload), header=2, dtype=str)

        df = df.rename(columns=str.lower)

        df = df.drop(columns=["latitude", "longitude"])

        df = df.rename(columns=self._columns_mapping)

        return df

    @staticmethod
    @payload_cache_twelve_hours.cache_on_arguments()
    def _download_stations() -> bytes:
        """
        Download station list from ECCC FTP server.

        :return: CSV payload
        """

        ftp_url = (
            "ftp://client_climate:foobar@ftp.tor.ec.gc.ca"
            "/Pub/Get_More_Data_Plus_de_donnees/Station Inventory EN.csv"
        )

        http_url = (
            "https://raw.githubusercontent.com/earthobservations/testdata"
            "/main/ftp.tor.ec.gc.ca/Pub/Get_More_Data_Plus_de_donnees"
            "/Station%20Inventory%20EN.csv.gz"
        )

        payload = None

        # Try original source.
        session = FTPSession()
        try:
            response = session.retr(ftp_url)
            payload = response.content
        except Exception:
            log.exception(f"Unable to access FTP server at {ftp_url}")

            # Fall back to different source.
            try:
                response = requests.get(http_url)
                response.raise_for_status()
                with gzip.open(BytesIO(response.content), mode="rb") as f:
                    payload = f.read()
            except Exception:
                log.exception(f"Unable to access HTTP server at {http_url}")

        if payload is None:
            raise FailedDownload("Unable to acquire ECCC stations list")

        return payload
