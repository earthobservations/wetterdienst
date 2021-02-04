# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from datetime import datetime
from enum import Enum
from io import StringIO
from typing import Generator, Optional, Tuple, Union
from urllib.parse import urljoin

import pandas as pd
import requests
from requests import HTTPError

from wetterdienst.core.scalar import ScalarStationsCore, ScalarValuesCore
from wetterdienst.dwd.forecasts.access import KMLReader
from wetterdienst.dwd.forecasts.metadata import (
    DWDForecastDate,
    DWDMosmixParameter,
    DWDMosmixType,
)
from wetterdienst.dwd.forecasts.metadata.column_types import INTEGER_PARAMETERS
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.constants import (
    DWD_MOSMIX_L_SINGLE_PATH,
    DWD_MOSMIX_S_PATH,
    DWD_SERVER,
)
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.result import Result
from wetterdienst.metadata.source import Source
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import convert_dm_to_dd
from wetterdienst.util.network import list_remote_files

log = logging.getLogger(__name__)


MOSMIX_STATION_LIST = (
    "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/"
    "mosmix_stationskatalog.cfg?view=nasPublication"
)
MOSMIX_STATION_LIST_COLSPECS = [
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
MOSMIX_METADATA_COLUMNS = [
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


class DWDMosmixValues(ScalarValuesCore):
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

    @property
    def _source(self) -> Source:
        return Source.DWD

    @property
    def _tz(self) -> Timezone:
        return Timezone.GERMANY

    @property
    def _data_tz(self) -> Timezone:
        return Timezone.UTC

    @property
    def _has_quality(self) -> bool:
        return False

    @property
    def _tidy(self) -> bool:
        return self.tidy_data

    @property
    def _parameter_base(self) -> Enum:
        return DWDMosmixParameter

    @property
    def _irregular_parameters(self) -> Tuple[str]:
        return tuple()

    @property
    def _integer_parameters(self) -> Tuple[str]:
        return INTEGER_PARAMETERS

    @property
    def _string_parameters(self) -> Tuple[str]:
        return tuple()

    _resolution_type = ResolutionType.FIXED
    _resolution_base = None
    _period_type = PeriodType.FIXED
    _period_base = None

    def __init__(
        self,
        station_id: Tuple[str],
        mosmix_type: Union[str, DWDMosmixType],
        parameter: Optional[Tuple[Union[str, DWDMosmixParameter]]] = None,
        start_issue: Optional[
            Union[str, datetime, DWDForecastDate]
        ] = DWDForecastDate.LATEST,
        end_issue: Optional[Union[str, datetime]] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        humanize_parameters: bool = False,
        tidy_data: bool = True,
    ) -> None:
        """

        :param station_id: station ids which are being queried from the MOSMIX foreacst
        :param mosmix_type: type of forecast, either small (MOSMIX-S) or large
                            (MOSMIX-L), as string or enumeration
        :param parameter: optional parameters for which the forecasts are filtered
        :param start_issue: start date of the MOSMIX forecast, can be used in
                            combination with end_issue to query multiple MOSMIX
                            forecasts, or instead used with enumeration to only query
                            LATEST MOSMIX forecast
        :param end_issue: end issue of MOSMIX forecast, can be used to query multiple
                          MOSMIX forecasts available on the server
        :param start_date: start date to limit the returned data to specified datetimes
        :param end_date: end date to limit the returned data to specified datetimes
        :param humanize_parameters: boolean if parameters shall be renamed to human
                                    readable names
        :param tidy_data: boolean if pandas.DataFrame shall be tidied and
                            values put in rows
        """
        # Use all parameters if none are given
        parameter = parameter or [*self._parameter_base]

        super(DWDMosmixValues, self).__init__(
            station_id=station_id,
            parameter=parameter,
            resolution=Resolution.HOURLY,
            period=Period.FUTURE,
            start_date=start_date,
            end_date=end_date,
            humanize_parameters=humanize_parameters,
            tidy_data=tidy_data,
        )
        self.mosmix_type = parse_enumeration_from_template(mosmix_type, DWDMosmixType)

        # Parse issue date if not set to fixed "latest" string
        if start_issue is DWDForecastDate.LATEST and end_issue:
            log.info(
                "end_issue will be ignored as 'latest' was selected for issue date"
            )

        if start_issue is not DWDForecastDate.LATEST:
            if not start_issue and not end_issue:
                start_issue = DWDForecastDate.LATEST
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
            if mosmix_type == DWDMosmixType.LARGE:
                start_issue = self.adjust_datetime(start_issue)
                end_issue = self.adjust_datetime(end_issue)

        self.start_issue = start_issue
        self.end_issue = end_issue
        self.humanize_parameters = humanize_parameters
        self.tidy_data = tidy_data

        # TODO: this should be replaced by the freq property in the main class
        if self.mosmix_type == DWDMosmixType.SMALL:
            self.freq = "1H"  # short forecasts released every hour
        else:
            self.freq = "6H"

        self.kml = KMLReader(station_ids=self.station_ids, parameters=self.parameters)

    # TODO: add __eq__ and __str__

    @property
    def metadata(self) -> pd.DataFrame:
        """ Wrapper for forecast metadata """
        return DWDMosmixStations().all()

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

    def query(self) -> Generator[Result, None, None]:
        """Replace collect data method as all information is read once from kml file"""
        for metadata_df, forecast_df in self._collect_station_parameter():
            forecast_df = self._coerce_meta_fields(forecast_df)
            forecast_df = self._coerce_parameter_types(forecast_df)

            if self.humanize_parameters:
                forecast_df = self._humanize(forecast_df)

            # Complement metadata
            station_id = forecast_df[DWDMetaColumns.STATION_ID.value].iloc[0]

            station_metadata = self.metadata[
                self.metadata[DWDMetaColumns.STATION_ID.value] == station_id
            ].reset_index(drop=True)

            metadata_df = metadata_df.rename(columns=str.upper).reset_index(drop=True)

            metadata_df = metadata_df.join(station_metadata)

            result = Result(metadata_df, forecast_df)

            yield result

    def _collect_station_parameter(self) -> Generator[Result, None, None]:
        """Wrapper of read_mosmix to collect forecast data (either latest or for
        defined dates)"""
        if self.start_issue == DWDForecastDate.LATEST:
            yield from self.read_mosmix(self.start_issue)
        else:
            for date in pd.date_range(self.start_issue, self.end_issue, freq=self.freq):
                try:
                    yield from self.read_mosmix(date)
                except IndexError as e:
                    log.warning(e)
                    continue

    def read_mosmix(self, date: Union[datetime, DWDForecastDate]) -> Result:
        """
        Manage data acquisition for a given date that is used to filter the found files
        on the MOSMIX path of the DWD server.

        :param date: datetime or enumeration for latest MOSMIX forecast
        :return: DWDMosmixResult with gathered information
        """
        for df_metadata, df_forecast in self._read_mosmix(date):
            df_forecast = df_forecast.rename(
                columns={
                    "station_id": DWDMetaColumns.STATION_ID.value,
                    "datetime": DWDMetaColumns.DATE.value,
                }
            )

            if self.tidy_data:
                df_forecast = df_forecast.melt(
                    id_vars=[
                        DWDMetaColumns.STATION_ID.value,
                        DWDMetaColumns.DATE.value,
                    ],
                    var_name=DWDMetaColumns.PARAMETER.value,
                    value_name=DWDMetaColumns.VALUE.value,
                )

            yield df_metadata, df_forecast

    def _read_mosmix(
        self, date: Union[DWDForecastDate, datetime]
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """Wrapper that either calls read_mosmix_s or read_mosmix_l depending on
        defined period type"""
        if self.mosmix_type == DWDMosmixType.SMALL:
            yield from self.read_mosmix_small(date)
        else:
            yield from self.read_mosmix_large(date)

    def read_mosmix_small(
        self, date: Union[DWDForecastDate, datetime]
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """Reads single MOSMIX-S file with all stations and returns every forecast that
        matches with one of the defined station ids."""
        url = urljoin(DWD_SERVER, DWD_MOSMIX_S_PATH)

        file_url = self.get_url_for_date(url, date)

        self.kml.read(file_url)

        for forecast in self.kml.get_forecasts():
            yield self.kml.get_metadata(), forecast

    def read_mosmix_large(
        self, date: Union[DWDForecastDate, datetime]
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """Reads multiple MOSMIX-L files with one per each station and returns a
        forecast per file."""
        url = urljoin(DWD_SERVER, DWD_MOSMIX_L_SINGLE_PATH)

        for station_id in self.station_ids:
            station_url = f"{url}{station_id}/kml"

            try:
                file_url = self.get_url_for_date(station_url, date)
            except HTTPError:
                log.warning(f"Files for {station_id} do not exist on the server")
                continue

            self.kml.read(file_url)

            yield self.kml.get_metadata(), next(self.kml.get_forecasts())

    @staticmethod
    def get_url_for_date(url: str, date: Union[datetime, DWDForecastDate]) -> str:
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

        if date == DWDForecastDate.LATEST:
            try:
                url = list(filter(lambda url_: "LATEST" in url_.upper(), urls))[0]
                return url
            except IndexError as e:
                raise IndexError(f"Unable to find LATEST file within {url}") from e

        df_urls = pd.DataFrame({"URL": urls})

        df_urls[DWDMetaColumns.DATE.value] = df_urls["URL"].apply(
            lambda url_: url_.split("/")[-1].split("_")[2].replace(".kmz", "")
        )

        df_urls = df_urls[df_urls[DWDMetaColumns.DATE.value] != "LATEST"]

        df_urls[DWDMetaColumns.DATE.value] = pd.to_datetime(
            df_urls[DWDMetaColumns.DATE.value], format=DatetimeFormat.YMDH.value
        )

        df_urls = df_urls.loc[df_urls[DWDMetaColumns.DATE.value] == date]

        if df_urls.empty:
            raise IndexError(f"Unable to find {date} file within {url}")

        return df_urls["URL"].item()


class DWDMosmixStations(ScalarStationsCore):
    """ Implementation of sites for MOSMIX forecast sites """

    @property
    def _source(self) -> Source:
        return Source.DWD

    @property
    def _tz(self) -> Timezone:
        return Timezone.GERMANY

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

    _resolution_type = ResolutionType.FIXED
    _resolution_base = None
    _period_type = PeriodType.FIXED
    _period_base = None

    def __init__(self) -> None:
        super().__init__(
            start_date=None,
            end_date=None,
            resolution=Resolution.HOURLY,
            period=Period.FUTURE,
        )

    def _all(self):
        """ Create meta data DataFrame from available station list """
        # TODO: Cache payload with FSSPEC
        payload = requests.get(MOSMIX_STATION_LIST, headers={"User-Agent": ""})

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
            colspecs=MOSMIX_STATION_LIST_COLSPECS,
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

        df = df.reindex(columns=MOSMIX_METADATA_COLUMNS)

        return df
