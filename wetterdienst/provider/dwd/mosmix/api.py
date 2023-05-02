# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import logging
from enum import Enum
from io import StringIO
from typing import Dict, Iterator, List, Optional, Tuple, Union
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import polars as pl
from backports.datetime_fromisoformat import MonkeyPatch
from requests import HTTPError

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.result import StationsResult, ValuesResult
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.exceptions import InvalidParameter
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.provider.dwd.mosmix.metadata import (
    DwdForecastDate,
    DwdMosmixParameter,
    DwdMosmixType,
)
from wetterdienst.provider.dwd.mosmix.metadata.unit import DwdMosmixUnit
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import convert_dm_to_dd
from wetterdienst.util.network import download_file, list_remote_files_fsspec
from wetterdienst.util.python import to_list

MonkeyPatch.patch_fromisoformat()
log = logging.getLogger(__name__)

DWD_MOSMIX_S_PATH = "weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/"
DWD_MOSMIX_L_PATH = "weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/"
DWD_MOSMIX_L_SINGLE_PATH = "weather/local_forecasts/mos/MOSMIX_L/single_stations/{station_id}/kml/"


class DwdMosmixPeriod(Enum):
    FUTURE = Period.FUTURE.value


class DwdMosmixDataset(Enum):
    SMALL = "small"
    LARGE = "large"


class DwdMosmixStationGroup(Enum):
    SINGLE_STATIONS = "single_stations"
    ALL_STATIONS = "all_stations"


class DwdMosmixValues(TimeseriesValues):
    """
    Fetch weather mosmix data (KML/MOSMIX_S dataset).

    Parameters
    ----------
    station_id : List
        - If None, data for all stations_result is returned.
        - If not None, station_ids are a list of station ids for which data is desired.

    parameter: List
        - If None, data for all parameters is returned.
        - If not None, list of parameters, per MOSMIX definition, see
          https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_elemente_pdf.pdf?__blob=publicationFile&v=2
    """  # noqa:B950,E501

    _tz = Timezone.GERMANY
    _data_tz = Timezone.UTC

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """
        Method for creation of parameter name mappings based on
        self._parameter_base

        :return:
        """
        return {
            parameter.value: parameter.name.lower()
            for parameter in self.sr.stations._parameter_base[self.sr.stations.mosmix_type.name][
                self.sr.stations.mosmix_type.name
            ]
        }

    def __init__(self, stations_result: StationsResult) -> None:
        """

        :param stations_result:
        """
        super(DwdMosmixValues, self).__init__(stations_result=stations_result)

        parameter_base = self.sr.stations._parameter_base
        dataset_accessor = self.sr.stations._dataset_accessor

        parameter_ = []
        for parameter, dataset in self.sr.parameter:
            if parameter == dataset:
                parameter = [par.value for par in parameter_base[dataset_accessor][dataset_accessor]]
                parameter_.extend(parameter)
            else:
                parameter_.append(parameter.value)

        self.kml = KMLReader(
            station_ids=self.sr.station_id.to_list(), parameters=parameter_, settings=self.sr.stations.settings
        )

    @property
    def metadata(self) -> pl.DataFrame:
        """
        Wrapper for mosmix metadata

        :return:
        """
        return self.sr.df

    def query(self) -> Iterator[ValuesResult]:
        """
        Replace collect data method as all information is read once from kml file

        :return:
        """
        hpm = self._create_humanized_parameters_mapping()
        self.stations_counter = 0
        self.stations_collected = []

        for df in self._collect_station_parameter():
            df = self._tidy_up_df(df)
            station_id = df.get_column(Columns.STATION_ID.value).take(0).item()
            df = self._organize_df_columns(df, station_id, self.sr.stations.mosmix_type)

            if self.sr.humanize:
                df = self._humanize(df, hpm)

            # Filter for dates range if start_date and end_date are defined
            if not df.is_empty() and self.sr.start_date and self.sr.start_date != DwdForecastDate.LATEST:
                df = df.filter(pl.col(Columns.DATE.value).is_between(self.sr.start_date, self.sr.end_date))

            if not self.sr.tidy:
                df = self._tabulate_df(df)

            self.stations_counter += 1
            self.stations_collected.append(station_id)

            yield ValuesResult(stations=self.sr, values=self, df=df)

            if self.stations_counter == self.sr.rank:
                return

    def _collect_station_parameter(self) -> Iterator[pl.DataFrame]:
        """
        Wrapper of read_mosmix to collect mosmix data (either latest or for
        defined dates)

        :return: pandas DataFrame with data corresponding to station id and parameter
        """
        if self.sr.start_issue == DwdForecastDate.LATEST:
            for df in self.read_mosmix(self.sr.stations.start_issue):
                yield df
        else:
            for date in pl.date_range(
                self.sr.stations.start_issue,
                self.sr.stations.end_issue,
                interval=self.sr.frequency.value,
            ):
                try:
                    for df in self.read_mosmix(date):
                        yield df
                except IndexError as e:
                    log.warning(e)
                    continue

    @staticmethod
    def _tidy_up_df(df: pl.DataFrame) -> pl.DataFrame:
        """

        :param df: pandas DataFrame that is being tidied
        :param dataset: enum of dataset, used for writing dataset in pandas DataFrame
        :return: tidied pandas DataFrame
        """
        df = df.melt(
            id_vars=[
                Columns.STATION_ID.value,
                Columns.DATE.value,
            ],
            variable_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
        )

        return df.with_columns(pl.lit(value=None, dtype=pl.Float64).alias(Columns.QUALITY.value))

    def read_mosmix(self, date: Union[dt.datetime, DwdForecastDate]) -> Iterator[pl.DataFrame]:
        """
        Manage data acquisition for a given date that is used to filter the found files
        on the MOSMIX path of the DWD server.

        :param date: datetime or enumeration for latest MOSMIX mosmix
        :return: pandas DataFrame with gathered information
        """
        for df_forecast in self._read_mosmix(date):
            df_forecast = df_forecast.rename(
                mapping={
                    "datetime": Columns.DATE.value,
                }
            )

            yield df_forecast

    def _read_mosmix(self, date: Union[DwdForecastDate, dt.datetime]) -> Iterator[pl.DataFrame]:
        """
        Wrapper that either calls read_mosmix_s or read_mosmix_l depending on
        defined period type

        :param date: datetime or enumeration for latest MOSMIX mosmix
        :return: pandas DataFrame
        """
        if self.sr.stations.mosmix_type == DwdMosmixType.SMALL:
            yield from self.read_mosmix_small(date)
        else:
            yield from self.read_mosmix_large(date)

    def read_mosmix_small(self, date: Union[DwdForecastDate, dt.datetime]) -> Iterator[pl.DataFrame]:
        """
        Reads single MOSMIX-S file with all stations_result and returns every mosmix that
        matches with one of the defined station ids.

        :param date: datetime or enumeration for latest MOSMIX mosmix
        :return: pandas DataFrame with data
        """
        url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_S_PATH)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        for forecast in self.kml.get_forecasts():
            yield forecast

    def read_mosmix_large(
        self, date: Union[DwdForecastDate, dt.datetime]
    ) -> Iterator[Tuple[pl.DataFrame, pl.DataFrame]]:
        """
        Reads multiple MOSMIX-L files with one per each station and returns a
        mosmix per file.

        :param date:
        :return:
        """
        if self.sr.stations.station_group == DwdMosmixStationGroup.ALL_STATIONS:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_PATH)

            file_url = self.get_url_for_date(url, date)

            self.kml.read(file_url)

            for forecast in self.kml.get_forecasts():
                yield forecast
        else:
            for station_id in self.sr.station_id:
                station_url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_SINGLE_PATH).format(station_id=station_id)

                try:
                    file_url = self.get_url_for_date(station_url, date)
                except HTTPError:
                    log.warning(f"Files for {station_id} do not exist on the server")
                    continue

                self.kml.read(file_url)

                yield next(self.kml.get_forecasts())

    def get_url_for_date(self, url: str, date: Union[dt.datetime, DwdForecastDate]) -> str:
        """
        Method to get a file url based on the MOSMIX-S/MOSMIX-L url and the date that is
        used for filtering.

        :param url: MOSMIX-S/MOSMIX-L path on the dwd server
        :param date: date used for filtering of the available files
        :return: file url based on the filtering
        """
        urls = list_remote_files_fsspec(url, self.sr.stations.settings, CacheExpiry.NO_CACHE)

        if date == DwdForecastDate.LATEST:
            try:
                url = list(filter(lambda url_: "LATEST" in url_.upper(), urls))[0]
                return url
            except IndexError as e:
                raise IndexError(f"Unable to find LATEST file within {url}") from e

        date = date.astimezone(dt.timezone.utc).replace(tzinfo=None)

        df = pl.DataFrame({"url": urls})

        df = df.with_columns(pl.col("url").str.split("/").arr.last().str.split("_").arr.take(2).flatten().alias("date"))

        df = df.filter(pl.col("date").ne("LATEST"))

        df = df.with_columns(pl.col("date").str.strptime(pl.Datetime, fmt=DatetimeFormat.YMDH.value))

        df = df.filter(pl.col("date").eq(date))

        if df.is_empty():
            raise IndexError(f"Unable to find {date} file within {url}")

        return df.get_column("url").item()


class DwdMosmixRequest(TimeseriesRequest):
    """Implementation of sites for MOSMIX mosmix sites"""

    _provider = Provider.DWD
    _kind = Kind.FORECAST
    _tz = Timezone.GERMANY
    _dataset_base = DwdMosmixDataset
    _parameter_base = DwdMosmixParameter
    _unit_base = DwdMosmixUnit
    _resolution_type = ResolutionType.FIXED
    _resolution_base = Resolution  # use general Resolution for fixed Resolution
    _period_type = PeriodType.FIXED
    _period_base = DwdMosmixPeriod
    _has_datasets = True
    _unique_dataset = True
    _data_range = DataRange.FIXED
    _values = DwdMosmixValues

    _url = "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg?view=nasPublication"

    @property
    def _dataset_accessor(self) -> str:
        """
        Implementation for tidying mosmix data

        :return:
        """
        return self.mosmix_type.name

    @classmethod
    def _setup_resolution_filter(cls, resolution):
        """
        Use SMALL and LARGE instead of resolution, which is fixed for Mosmix

        :param resolution:
        :return:
        """
        return (
            [parse_enumeration_from_template(res, intermediate=cls._dataset_base) for res in to_list(resolution)]
            if resolution
            else [*cls._dataset_base]
        )

    _base_columns = [
        Columns.STATION_ID.value,
        Columns.ICAO_ID.value,
        Columns.FROM_DATE.value,
        Columns.TO_DATE.value,
        Columns.HEIGHT.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.NAME.value,
        Columns.STATE.value,
    ]

    @staticmethod
    def adjust_datetime(datetime_: dt.datetime) -> dt.datetime:
        """
        Adjust datetime to MOSMIX release frequency, which is required for MOSMIX-L
        that is only released very 6 hours (3, 9, 15, 21). Datetime is floored
        to closest release time e.g. if hour is 14, it will be rounded to 9

        :param datetime_: datetime that is adjusted
        :return: adjusted datetime with floored hour
        """
        regular_date = dt.datetime.fromordinal(datetime_.date().toordinal()).replace(hour=3)

        if regular_date > datetime_:
            regular_date -= dt.timedelta(hours=6)

        delta_hours = (datetime_.hour - regular_date.hour) % 6

        return datetime_ - dt.timedelta(hours=delta_hours)

    def __init__(
        self,
        parameter: Optional[List[Union[str, DwdMosmixParameter, Parameter]]],
        mosmix_type: Union[str, DwdMosmixType],
        start_issue: Optional[Union[str, dt.datetime, DwdForecastDate]] = DwdForecastDate.LATEST,
        end_issue: Optional[Union[str, dt.datetime]] = None,
        start_date: Optional[Union[str, dt.datetime]] = None,
        end_date: Optional[Union[str, dt.datetime]] = None,
        station_group: Optional[DwdMosmixStationGroup] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """

        :param parameter: parameter(s) to be collected
        :param mosmix_type: mosmix type, either small or large
        :param start_issue: start of issue of mosmix which should be caught (Mosmix run at time XX:YY)
        :param end_issue: end of issue
        :param start_date: start date for filtering returned dataframe
        :param end_date: end date
        """
        self.mosmix_type = parse_enumeration_from_template(mosmix_type, DwdMosmixType)

        if self.mosmix_type == DwdMosmixType.SMALL:
            self.station_group = DwdMosmixStationGroup.ALL_STATIONS
        else:
            self.station_group = (
                parse_enumeration_from_template(station_group, DwdMosmixStationGroup)
                or DwdMosmixStationGroup.SINGLE_STATIONS
            )

        super().__init__(
            parameter=parameter,
            start_date=start_date,
            end_date=end_date,
            resolution=Resolution.HOURLY,
            period=Period.FUTURE,
            settings=settings,
        )

        if not start_issue:
            start_issue = DwdForecastDate.LATEST

        try:
            start_issue = parse_enumeration_from_template(start_issue, DwdForecastDate)
        except (InvalidParameter, KeyError, ValueError):
            pass

        # Parse issue date if not set to fixed "latest" string
        if start_issue is DwdForecastDate.LATEST and end_issue:
            log.info("end_issue will be ignored as 'latest' was selected for issue date")

        if start_issue is not DwdForecastDate.LATEST:
            if not start_issue and not end_issue:
                start_issue = DwdForecastDate.LATEST
            elif not end_issue:
                end_issue = start_issue
            elif not start_issue:
                start_issue = end_issue
            if type(start_issue) == str:
                start_issue = dt.datetime.fromisoformat(start_issue)
            start_issue = dt.datetime(start_issue.year, start_issue.month, start_issue.day, start_issue.hour)
            if type(end_issue) == str:
                end_issue = dt.datetime.fromisoformat(end_issue)
            end_issue = dt.datetime(end_issue.year, end_issue.month, end_issue.day, end_issue.hour)

            # Shift start date and end date to 3, 9, 15, 21 hour format
            if mosmix_type == DwdMosmixType.LARGE:
                start_issue = self.adjust_datetime(start_issue)
                end_issue = self.adjust_datetime(end_issue)

        # TODO: this should be replaced by the freq property in the main class
        if self.mosmix_type == DwdMosmixType.SMALL:
            self.resolution = Resolution.HOURLY
        else:
            self.resolution = Resolution.HOUR_6

        self.start_issue = start_issue
        self.end_issue = end_issue

    @property
    def issue_start(self):
        """Required for typing"""
        return self.issue_start

    @property
    def issue_end(self):
        """Required for typing"""
        return self.issue_end

    def _all(self) -> pl.LazyFrame:
        """
        Create meta data DataFrame from available station list

        :return:
        """
        payload = download_file(self._url, self.settings, CacheExpiry.METAINDEX)

        df = pd.read_fwf(
            StringIO(payload.read().decode(encoding="latin-1")),
            skiprows=2,
            skip_blank_lines=True,
            # When inferring colspecs, make sure to look at the whole file. Otherwise,
            # > this messes things up quite often and columns where strings get longer
            # > towards the end of the data may get messed up and truncated.
            # https://github.com/pandas-dev/pandas/issues/21970#issuecomment-480273621
            colspecs="infer",
            infer_nrows=np.Infinity,
            na_values=["----"],
            header=None,
            dtype="str",
        )

        df = pl.from_pandas(df)

        df.columns = [
            Columns.STATION_ID.value,
            Columns.ICAO_ID.value,
            Columns.NAME.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
        ]

        df = df.lazy()

        df = df.with_columns(
            pl.col(Columns.LATITUDE.value).cast(float).map(convert_dm_to_dd),
            pl.col(Columns.LONGITUDE.value).cast(float).map(convert_dm_to_dd),
        )

        return df.select([pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in self._base_columns])
