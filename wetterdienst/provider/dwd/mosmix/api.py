# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from datetime import datetime
from enum import Enum
from io import StringIO
from typing import Dict, Generator, Optional, Tuple, Union
from urllib.parse import urljoin

import pandas as pd
import pytz
from requests import HTTPError

from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.result import StationsResult, ValuesResult
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.exceptions import InvalidParameter
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.metadata.constants import (
    DWD_MOSMIX_L_PATH,
    DWD_MOSMIX_L_SINGLE_PATH,
    DWD_MOSMIX_S_PATH,
    DWD_SERVER,
)
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.provider.dwd.mosmix.metadata import (
    DwdForecastDate,
    DwdMosmixParameter,
    DwdMosmixType,
)
from wetterdienst.provider.dwd.mosmix.metadata.unit import DwdMosmixUnit
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import convert_dm_to_dd
from wetterdienst.util.network import download_file, list_remote_files_fsspec

log = logging.getLogger(__name__)


class DwdMosmixDataset(Enum):
    SMALL = "small"
    LARGE = "large"


class DwdMosmixStationGroup(Enum):
    SINGLE_STATIONS = "single_stations"
    ALL_STATIONS = "all_stations"


class DwdMosmixValues(ScalarValuesCore):
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
    _has_quality = False

    _irregular_parameters = ()
    _string_parameters = ()
    _date_parameters = ()

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """
        Method for creation of parameter name mappings based on
        self._parameter_base

        :return:
        """
        return {
            parameter.value: parameter.name.lower()
            for parameter in self.sr.stations._parameter_base[self.sr.stations.mosmix_type.name]
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
                parameter = [par.value for par in parameter_base[dataset_accessor]]
                parameter_.extend(parameter)
            else:
                parameter_.append(parameter.value)

        self.kml = KMLReader(
            station_ids=self.sr.station_id.tolist(),
            parameters=parameter_,
        )

    # TODO: add __eq__ and __str__

    @property
    def metadata(self) -> pd.DataFrame:
        """
        Wrapper for mosmix metadata

        :return:
        """
        return self.sr.df

    def query(self) -> Generator[ValuesResult, None, None]:
        """
        Replace collect data method as all information is read once from kml file

        :return:
        """
        hpm = self._create_humanized_parameters_mapping()

        for df in self._collect_station_parameter():
            df = self._coerce_parameter_types(df)

            if self.sr.stations.tidy:
                df = self.tidy_up_df(df, self.sr.stations.mosmix_type)

            station_id = df[Columns.STATION_ID.value].iloc[0]

            df = self._organize_df_columns(df, station_id, self.sr.stations.mosmix_type)

            df = self._coerce_meta_fields(df)

            if self.sr.humanize:
                df = self._humanize(df, hpm)

            # Filter for dates range if start_date and end_date are defined
            if not df.empty and self.sr.start_date and self.sr.start_date != DwdForecastDate.LATEST:
                df = df.loc[
                    (df[Columns.DATE.value] >= self.sr.start_date) & (df[Columns.DATE.value] <= self.sr.end_date),
                    :,
                ]

            yield ValuesResult(stations=self.sr, df=df)

    def _collect_station_parameter(self) -> Generator[pd.DataFrame, None, None]:
        """
        Wrapper of read_mosmix to collect mosmix data (either latest or for
        defined dates)

        :return: pandas DataFrame with data corresponding to station id and parameter
        """
        if self.sr.start_issue == DwdForecastDate.LATEST:
            for df in self.read_mosmix(self.sr.stations.start_issue):
                yield df
        else:
            for date in pd.date_range(
                self.sr.stations.start_issue,
                self.sr.stations.end_issue,
                freq=self.sr.frequency.value,
            ):
                try:
                    for df in self.read_mosmix(date):
                        yield df
                except IndexError as e:
                    log.warning(e)
                    continue

    def _tidy_up_df(self, df: pd.DataFrame, dataset: Enum) -> pd.DataFrame:
        """

        :param df: pandas DataFrame that is being tidied
        :param dataset: enum of dataset, used for writing dataset in pandas DataFrame
        :return: tidied pandas DataFrame
        """
        df_tidy = df.melt(
            id_vars=[
                Columns.STATION_ID.value,
                Columns.DATE.value,
            ],
            var_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
        )

        df_tidy[Columns.QUALITY.value] = pd.Series(dtype=float)

        return df_tidy

    def read_mosmix(self, date: Union[datetime, DwdForecastDate]) -> Generator[pd.DataFrame, None, None]:
        """
        Manage data acquisition for a given date that is used to filter the found files
        on the MOSMIX path of the DWD server.

        :param date: datetime or enumeration for latest MOSMIX mosmix
        :return: pandas DataFrame with gathered information
        """
        for df_forecast in self._read_mosmix(date):
            df_forecast = df_forecast.rename(
                columns={
                    "station_id": DwdColumns.STATION_ID.value,
                    "datetime": DwdColumns.DATE.value,
                }
            )

            yield df_forecast

    def _read_mosmix(self, date: Union[DwdForecastDate, datetime]) -> Generator[pd.DataFrame, None, None]:
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

    def read_mosmix_small(self, date: Union[DwdForecastDate, datetime]) -> Generator[pd.DataFrame, None, None]:
        """
        Reads single MOSMIX-S file with all stations_result and returns every mosmix that
        matches with one of the defined station ids.

        :param date: datetime or enumeration for latest MOSMIX mosmix
        :return: pandas DataFrame with data
        """
        url = urljoin(DWD_SERVER, DWD_MOSMIX_S_PATH)

        file_url = self.get_url_for_date(url, date)

        self.kml.read(file_url)

        for forecast in self.kml.get_forecasts():
            yield forecast

    def read_mosmix_large(
        self, date: Union[DwdForecastDate, datetime]
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """
        Reads multiple MOSMIX-L files with one per each station and returns a
        mosmix per file.

        :param date:
        :return:
        """
        if self.sr.stations.station_group == DwdMosmixStationGroup.ALL_STATIONS:
            url = urljoin(DWD_SERVER, DWD_MOSMIX_L_PATH)

            file_url = self.get_url_for_date(url, date)

            self.kml.read(file_url)

            for forecast in self.kml.get_forecasts():
                yield forecast
        else:
            for station_id in self.sr.station_id:
                station_url = urljoin(DWD_SERVER, DWD_MOSMIX_L_SINGLE_PATH).format(station_id=station_id)

                try:
                    file_url = self.get_url_for_date(station_url, date)
                except HTTPError:
                    log.warning(f"Files for {station_id} do not exist on the server")
                    continue

                self.kml.read(file_url)

                yield next(self.kml.get_forecasts())

    @staticmethod
    def get_url_for_date(url: str, date: Union[datetime, DwdForecastDate]) -> str:
        """
        Method to get a file url based on the MOSMIX-S/MOSMIX-L url and the date that is
        used for filtering.

        :param url: MOSMIX-S/MOSMIX-L path on the dwd server
        :param date: date used for filtering of the available files
        :return: file url based on the filtering
        """
        urls = list_remote_files_fsspec(url, CacheExpiry.NO_CACHE)

        if date == DwdForecastDate.LATEST:
            try:
                url = list(filter(lambda url_: "LATEST" in url_.upper(), urls))[0]
                return url
            except IndexError as e:
                raise IndexError(f"Unable to find LATEST file within {url}") from e

        date = date.astimezone(pytz.UTC).replace(tzinfo=None)

        df_urls = pd.DataFrame({"URL": urls})

        df_urls[DwdColumns.DATE.value] = df_urls["URL"].apply(
            lambda url_: url_.split("/")[-1].split("_")[2].replace(".kmz", "")
        )

        df_urls = df_urls[df_urls[DwdColumns.DATE.value] != "LATEST"]

        df_urls[DwdColumns.DATE.value] = pd.to_datetime(
            df_urls[DwdColumns.DATE.value], format=DatetimeFormat.YMDH.value
        )

        df_urls = df_urls.loc[df_urls[DwdColumns.DATE.value] == date]

        if df_urls.empty:
            raise IndexError(f"Unable to find {date} file within {url}")

        return df_urls["URL"].item()


class DwdMosmixRequest(ScalarRequestCore):
    """Implementation of sites for MOSMIX mosmix sites"""

    provider = Provider.DWD
    kind = Kind.FORECAST

    _tz = Timezone.GERMANY
    _parameter_base = DwdMosmixParameter
    _values = DwdMosmixValues

    _resolution_type = ResolutionType.FIXED
    _resolution_base = Resolution  # use general Resolution for fixed Resolution
    _period_type = PeriodType.FIXED
    _period_base = Period.FUTURE
    _data_range = DataRange.FIXED
    _has_datasets = True
    _unique_dataset = True
    _has_tidy_data = False

    _dataset_base = DwdMosmixDataset
    _unit_tree = DwdMosmixUnit

    _url = "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg?view=nasPublication"

    @property
    def _dataset_accessor(self) -> str:
        """
        Implementation for tidying mosmix data

        :return:
        """
        return self.mosmix_type.name

    @classmethod
    def _setup_discover_filter(cls, filter_):
        """
        Use SMALL and LARGE instead of resolution, which is fixed for Mosmix

        :param filter_:
        :return:
        """
        return pd.Series(filter_, dtype=object).apply(
            parse_enumeration_from_template, args=(cls._dataset_base,)
        ).tolist() or [*cls._dataset_base]

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
    def adjust_datetime(datetime_: datetime) -> datetime:
        """
        Adjust datetime to MOSMIX release frequency, which is required for MOSMIX-L
        that is only released very 6 hours (3, 9, 15, 21). Datetime is floored
        to closest release time e.g. if hour is 14, it will be rounded to 9

        :param datetime_: datetime that is adjusted
        :return: adjusted datetime with floored hour
        """
        regular_date = datetime_ + pd.offsets.DateOffset(hour=3)

        if regular_date > datetime_:
            regular_date -= pd.Timedelta(hours=6)

        delta_hours = (datetime_.hour - regular_date.hour) % 6

        return datetime_ - pd.Timedelta(hours=delta_hours)

    def __init__(
        self,
        parameter: Optional[Tuple[Union[str, DwdMosmixParameter], ...]],
        mosmix_type: Union[str, DwdMosmixType],
        start_issue: Optional[Union[str, datetime, DwdForecastDate]] = DwdForecastDate.LATEST,
        end_issue: Optional[Union[str, datetime]] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        station_group: Optional[DwdMosmixStationGroup] = None,
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

            start_issue = pd.to_datetime(start_issue, infer_datetime_format=True).floor("1H")
            end_issue = pd.to_datetime(end_issue, infer_datetime_format=True).floor("1H")

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

    def _all(self) -> pd.DataFrame:
        """
        Create meta data DataFrame from available station list

        :return:
        """
        payload = download_file(self._url, CacheExpiry.METAINDEX)

        df = pd.read_fwf(
            StringIO(payload.read().decode(encoding="latin-1")),
            skiprows=4,
            skip_blank_lines=True,
            colspecs=[
                (0, 5),
                (6, 11),
                (12, 17),
                (18, 22),
                (23, 44),
                (44, 51),
                (51, 58),
                (59, 64),
                (65, 71),
                (72, 76),
            ],
            na_values=["----"],
            header=None,
            dtype="str",
        )

        df = df[(df.iloc[:, 0] != "=====") & (df.iloc[:, 0] != "TABLE") & (df.iloc[:, 0] != "clu")]

        df = df.iloc[:, [2, 3, 4, 5, 6, 7]]

        df.columns = [
            Columns.STATION_ID.value,
            Columns.ICAO_ID.value,
            Columns.NAME.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
        ]

        # Convert coordinates from degree minutes to decimal degrees
        df[Columns.LATITUDE.value] = df[Columns.LATITUDE.value].astype(float).apply(convert_dm_to_dd)
        df[Columns.LONGITUDE.value] = df[Columns.LONGITUDE.value].astype(float).apply(convert_dm_to_dd)

        return df.reindex(columns=self._base_columns)
