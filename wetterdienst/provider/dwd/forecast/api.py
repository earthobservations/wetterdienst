# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from datetime import datetime
from enum import Enum
from io import StringIO
from typing import Dict, Generator, Optional, Tuple, Union
from urllib.parse import urljoin

import pandas as pd
import requests
from requests import HTTPError

from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.result import StationsResult, ValuesResult
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.dwd.forecast.access import KMLReader
from wetterdienst.provider.dwd.forecast.metadata import (
    DwdForecastDate,
    DwdMosmixParameter,
    DwdMosmixType,
)
from wetterdienst.provider.dwd.forecast.metadata.field_types import INTEGER_PARAMETERS
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.metadata.constants import (
    DWD_MOSMIX_L_SINGLE_PATH,
    DWD_MOSMIX_S_PATH,
    DWD_SERVER,
)
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import convert_dm_to_dd
from wetterdienst.util.network import list_remote_files

log = logging.getLogger(__name__)


class DwdMosmixDataset(Enum):
    SMALL = "small"
    LARGE = "large"


class DwdMosmixValues(ScalarValuesCore):
    """
    Fetch weather forecast data (KML/MOSMIX_S dataset).

    Parameters
    ----------
    station_id : List
        - If None, data for all stations is returned.
        - If not None, station_ids are a list of station ids for which data is desired.

    parameter: List
        - If None, data for all parameters is returned.
        - If not None, list of parameters, per MOSMIX definition, see
          https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_elemente_pdf.pdf?__blob=publicationFile&v=2  # noqa:E501,B950
    """

    _tz = Timezone.GERMANY
    _data_tz = Timezone.UTC
    _has_quality = False

    @property
    def _tidy(self) -> bool:
        return self.stations.tidy

    _irregular_parameters = tuple()
    _integer_parameters = INTEGER_PARAMETERS
    _string_parameters = tuple()

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """Method for creation of parameter name mappings based on
        self._parameter_base"""
        hcnm = {
            parameter.value: parameter.name
            for parameter in self.stations.stations._parameter_base[
                self.stations.stations.mosmix_type.name
            ]
        }

        return hcnm

    def __init__(self, stations: StationsResult) -> None:
        """"""
        super(DwdMosmixValues, self).__init__(stations=stations)

        parameter_base = self.stations.stations._parameter_base
        dataset_accessor = self.stations.stations._dataset_accessor

        parameter_ = []
        for parameter, dataset in self.stations.parameter:
            if parameter == dataset:
                parameter = [par.value for par in parameter_base[dataset_accessor]]
                parameter_.extend(parameter)
            else:
                parameter_.append(parameter.value)

        self.kml = KMLReader(
            station_ids=self.stations.station_id.tolist(),
            parameters=parameter_,
        )

    # TODO: add __eq__ and __str__

    @property
    def metadata(self) -> pd.DataFrame:
        """ Wrapper for forecast metadata """
        return self.stations.df

    def query(self) -> Generator[ValuesResult, None, None]:
        """Replace collect data method as all information is read once from kml file"""
        for forecast_df in self._collect_station_parameter():
            forecast_df = self._coerce_meta_fields(forecast_df)
            forecast_df = self._coerce_parameter_types(forecast_df)

            if self.stations.humanize:
                forecast_df = self._humanize(forecast_df)

            result = ValuesResult(stations=self.stations, df=forecast_df)

            yield result

    def _collect_station_parameter(self) -> Generator[pd.DataFrame, None, None]:
        """Wrapper of read_mosmix to collect forecast data (either latest or for
        defined dates)"""
        if self.stations.start_issue == DwdForecastDate.LATEST:
            df = next(self.read_mosmix(self.stations.stations.start_issue))

            df[Columns.QUALITY.value] = pd.NA

            yield df
        else:
            for date in pd.date_range(
                self.stations.stations.start_issue,
                self.stations.stations.end_issue,
                freq=self.stations.frequency.value,
            ):
                try:
                    df = next(self.read_mosmix(date))

                    df[Columns.QUALITY.value] = pd.NA

                    yield df
                except IndexError as e:
                    log.warning(e)
                    continue

    def read_mosmix(
        self, date: Union[datetime, DwdForecastDate]
    ) -> Generator[pd.DataFrame, None, None]:
        """
        Manage data acquisition for a given date that is used to filter the found files
        on the MOSMIX path of the DWD server.

        :param date: datetime or enumeration for latest MOSMIX forecast
        :return: DWDMosmixResult with gathered information
        """
        for df_forecast in self._read_mosmix(date):
            df_forecast = df_forecast.rename(
                columns={
                    "station_id": DwdColumns.STATION_ID.value,
                    "datetime": DwdColumns.DATE.value,
                }
            )

            if self.stations.tidy:
                df_forecast = df_forecast.melt(
                    id_vars=[
                        DwdColumns.STATION_ID.value,
                        DwdColumns.DATE.value,
                    ],
                    var_name=DwdColumns.PARAMETER.value,
                    value_name=DwdColumns.VALUE.value,
                )

            yield df_forecast

    def _read_mosmix(
        self, date: Union[DwdForecastDate, datetime]
    ) -> Generator[pd.DataFrame, None, None]:
        """Wrapper that either calls read_mosmix_s or read_mosmix_l depending on
        defined period type"""
        if self.stations.stations.mosmix_type == DwdMosmixType.SMALL:
            yield from self.read_mosmix_small(date)
        else:
            yield from self.read_mosmix_large(date)

    def read_mosmix_small(
        self, date: Union[DwdForecastDate, datetime]
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """Reads single MOSMIX-S file with all stations and returns every forecast that
        matches with one of the defined station ids."""
        url = urljoin(DWD_SERVER, DWD_MOSMIX_S_PATH)

        file_url = self.get_url_for_date(url, date)

        self.kml.read(file_url)

        for forecast in self.kml.get_forecasts():
            yield forecast

    def read_mosmix_large(
        self, date: Union[DwdForecastDate, datetime]
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """Reads multiple MOSMIX-L files with one per each station and returns a
        forecast per file."""
        url = urljoin(DWD_SERVER, DWD_MOSMIX_L_SINGLE_PATH)

        for station_id in self.stations.station_id:
            station_url = f"{url}{station_id}/kml"

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

        Args:
            url:    MOSMIX-S/MOSMIX-L path on the dwd server
            date:   date used for filtering of the available files

        Returns:
            file url based on the filtering
        """
        urls = list_remote_files(url, False)

        if date == DwdForecastDate.LATEST:
            try:
                url = list(filter(lambda url_: "LATEST" in url_.upper(), urls))[0]
                return url
            except IndexError as e:
                raise IndexError(f"Unable to find LATEST file within {url}") from e

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
    """ Implementation of sites for MOSMIX forecast sites """

    _url = (
        "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/"
        "mosmix_stationskatalog.cfg?view=nasPublication"
    )

    _colspecs = [
        (0, 5),
        (6, 11),
        (12, 17),
        (18, 22),
        (23, 44),
        (45, 51),
        (52, 58),
        (59, 64),
        (65, 71),
        (72, 76),
    ]

    _columns = [
        Columns.STATION_ID.value,
        Columns.ICAO_ID.value,
        Columns.FROM_DATE.value,
        Columns.TO_DATE.value,
        Columns.HEIGHT.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.STATION_NAME.value,
        Columns.STATE.value,
    ]

    _provider = Provider.DWD
    _tz = Timezone.GERMANY
    _parameter_base = DwdMosmixParameter
    _values = DwdMosmixValues

    _resolution_type = ResolutionType.FIXED
    _resolution_base = None
    _period_type = PeriodType.FIXED
    _period_base = None

    _has_datasets = True
    _unique_dataset = True
    _dataset_base = DwdMosmixDataset

    @property
    def _dataset_accessor(self) -> str:
        return self.mosmix_type.name

    @classmethod
    def _setup_discover_filter(cls, filter_):
        filter_ = pd.Series(filter_).apply(
            parse_enumeration_from_template, args=(cls._dataset_base,)
        ).tolist() or [*cls._dataset_base]

        return filter_

    _base_columns = [
        Columns.STATION_ID.value,
        Columns.ICAO_ID.value,
        Columns.FROM_DATE.value,
        Columns.TO_DATE.value,
        Columns.HEIGHT.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.STATION_NAME.value,
        Columns.STATE.value,
    ]

    @staticmethod
    def adjust_datetime(datetime_: datetime) -> datetime:
        """
        Adjust datetime to MOSMIX release frequency, which is required for MOSMIX-L
        that is only released very 6 hours (3, 9, 15, 21). Datetime is floored
        to closest release time e.g. if hour is 14, it will be rounded to 9

        Args:
            datetime_: datetime that is adjusted

        Returns:
            adjusted datetime with floored hour
        """
        regular_date = datetime_ + pd.offsets.DateOffset(hour=3)

        if regular_date > datetime_:
            regular_date -= pd.Timedelta(hours=6)

        delta_hours = (datetime_.hour - regular_date.hour) % 6

        datetime_adjusted = datetime_ - pd.Timedelta(hours=delta_hours)

        return datetime_adjusted

    def __init__(
        self,
        parameter: Optional[Tuple[Union[str, DwdMosmixParameter], ...]],
        mosmix_type: Union[str, DwdMosmixType],
        start_issue: Optional[
            Union[str, datetime, DwdForecastDate]
        ] = DwdForecastDate.LATEST,
        end_issue: Optional[Union[str, datetime]] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        humanize: bool = True,
        tidy: bool = True,
    ) -> None:
        self.mosmix_type = parse_enumeration_from_template(mosmix_type, DwdMosmixType)

        super().__init__(
            parameter=parameter,
            start_date=start_date,
            end_date=end_date,
            resolution=Resolution.HOURLY,
            period=Period.FUTURE,
        )

        # Parse issue date if not set to fixed "latest" string
        if start_issue is DwdForecastDate.LATEST and end_issue:
            log.info(
                "end_issue will be ignored as 'latest' was selected for issue date"
            )

        if start_issue is not DwdForecastDate.LATEST:
            if not start_issue and not end_issue:
                start_issue = DwdForecastDate.LATEST
            elif not end_issue:
                end_issue = start_issue
            elif not start_issue:
                start_issue = end_issue

            start_issue = pd.to_datetime(start_issue, infer_datetime_format=True).floor(
                "1H"
            )
            end_issue = pd.to_datetime(end_issue, infer_datetime_format=True).floor(
                "1H"
            )

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
        self.humanize = humanize
        self.tidy = tidy

    @property
    def issue_start(self):
        """ Required for typing """
        return self.issue_start

    @property
    def issue_end(self):
        """ Required for typing """
        return self.issue_end

    def _all(self) -> pd.DataFrame:
        """ Create meta data DataFrame from available station list """
        # TODO: Cache payload with FSSPEC
        payload = requests.get(self._url, headers={"User-Agent": ""})

        # List is unsorted with repeating interruptions with "TABLE" string in the
        # beginning of the line
        lines = payload.text.split("\n")
        table_lines = [i for i, line in enumerate(lines) if line.startswith("TABLE")]

        lines_filtered = []

        for start, end in zip(table_lines[:-1], table_lines[1:]):
            lines_filtered.extend(lines[(start + 3) : (end - 1)])

        data = StringIO("\n".join(lines_filtered))

        df = pd.read_fwf(
            data,
            colspecs=self._colspecs,
            na_values=["----"],
            header=None,
            dtype="str",
        )

        df = df.iloc[:, [2, 3, 4, 5, 6, 7]]

        df.columns = [
            Columns.STATION_ID.value,
            Columns.ICAO_ID.value,
            Columns.STATION_NAME.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
        ]

        # Convert coordinates from degree minutes to decimal degrees
        df[Columns.LATITUDE.value] = (
            df[Columns.LATITUDE.value].astype(float).apply(convert_dm_to_dd)
        )

        df[Columns.LONGITUDE.value] = (
            df[Columns.LONGITUDE.value].astype(float).apply(convert_dm_to_dd)
        )

        df = df.reindex(columns=self._columns)

        return df.copy()
