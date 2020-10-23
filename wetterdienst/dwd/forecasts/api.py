import logging
from datetime import datetime, timedelta
from typing import List, Union, Optional, Generator, Tuple, Dict
from dataclasses import dataclass

from urllib.parse import urljoin
import pandas as pd
from pandas._libs.tslibs.timestamps import Timestamp
from requests import HTTPError

from wetterdienst.core.data import WDDataCore
from wetterdienst.core.sites import WDSitesCore
from wetterdienst.dwd.forecasts.metadata.column_types import (
    DATE_FIELDS_REGULAR,
    INTEGER_FIELDS,
)
from wetterdienst.dwd.forecasts.metadata import (
    DWDForecastDate,
    DWDForecastParameter,
    DWDMosmixType,
)
from wetterdienst.dwd.forecasts.stations import metadata_for_forecasts
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.constants import (
    DWD_SERVER,
    DWD_MOSMIX_S_PATH,
    DWD_MOSMIX_L_SINGLE_PATH,
)
from wetterdienst.dwd.forecasts.access import KMLReader
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.util.network import list_remote_files

log = logging.getLogger(__name__)


@dataclass
class DWDMosmixResult:
    """
    Result object encapsulating metadata, station information and forecast data.
    """

    metadata: pd.DataFrame
    forecast: pd.DataFrame


class DWDMosmixData(WDDataCore):
    """
    Fetch weather forecast data (KML/MOSMIX_S dataset).

    Parameters
    ----------
    station_ids : List
        - If None, data for all stations is returned.
        - If not None, station_ids are a list of station ids for which data is desired.

    parameters: List
        - If None, data for all parameters is returned.
        - If not None, list of parameters, per MOSMIX definition, see
          https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_elemente_pdf.pdf?__blob=publicationFile&v=2  # noqa:E501,B950
    """

    def __init__(
        self,
        mosmix_type: DWDMosmixType,
        station_ids: List[str],
        parameters: Optional[List[Union[str, DWDForecastParameter]]] = None,
        start_date: Optional[
            Union[str, datetime, DWDForecastDate]
        ] = DWDForecastDate.LATEST,
        end_date: Optional[Union[str, datetime, timedelta]] = None,
        tidy_data: bool = True,
        humanize_column_names: bool = False,
    ) -> None:
        """

        Args:
            mosmix_type: type of forecast, either small (MOSMIX-S) or large
                (MOSMIX-L), as string or enumeration
            station_ids: station ids which are being queried from the MOSMIX foreacst
            parameters: optional parameters for which the forecasts are filtered
            start_date: start date of the MOSMIX forecast, can be used in combination
                with end date to query multiple MOSMIX forecasts, or instead used with
                enumeration to only query LATEST MOSMIX forecast
            end_date: end date of MOSMIX forecast, can be used to query multiple MOSMIX
                forecasts available on the server
            tidy_data: boolean if pandas.DataFrame shall be tidied and values put in
                rows
            humanize_column_names: boolean if parameters shall be renamed to human
                readable names
        """

        if mosmix_type not in DWDMosmixType:
            raise ValueError(
                "period_type should be one of FORECAST_SHORT or FORECAST_LONG"
            )
        if station_ids:
            station_ids = pd.Series(station_ids).astype(str).tolist()
        if parameters:
            parameters = (
                pd.Series(parameters)
                .apply(
                    parse_enumeration_from_template,
                    args=(DWDForecastParameter,),
                )
                .tolist()
            )

        if not start_date and not end_date:
            start_date = DWDForecastDate.LATEST
        elif not end_date:
            end_date = start_date
        elif not start_date:
            start_date = end_date

        if start_date is not DWDForecastDate.LATEST:
            start_date = pd.to_datetime(start_date, infer_datetime_format=True).floor(
                "1H"
            )
            end_date = pd.to_datetime(end_date, infer_datetime_format=True).floor("1H")

            if not start_date <= end_date:
                raise StartDateEndDateError(
                    "end_date should be same or later then start_date"
                )

            # Shift dates to 3, 9, 15, 21 hour format
            if mosmix_type == DWDMosmixType.LARGE:
                start_date = self.adjust_datetime(start_date)
                end_date = self.adjust_datetime(end_date)

        self.forecast_type = mosmix_type
        self.station_ids = station_ids
        self.parameters = parameters
        self.start_date = start_date
        self.end_date = end_date
        self.tidy_data = tidy_data
        self.humanize_column_names = humanize_column_names

        if mosmix_type == DWDMosmixType.SMALL:
            self.freq = "1H"  # short forecasts released every hour
        else:
            self.freq = "6H"

        self.kml = KMLReader(station_ids=self.station_ids, parameters=self.parameters)

    @property
    def metadata(self):
        """ Wrapper for forecast metadata """
        return metadata_for_forecasts()

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

    def collect_data(self) -> Generator[DWDMosmixResult, None, None]:
        """Wrapper of read_mosmix to collect forecast data (either latest or for
        defined dates)"""
        if self.start_date == DWDForecastDate.LATEST:
            yield from self.read_mosmix(self.start_date)
        else:
            for date in pd.date_range(self.start_date, self.end_date, freq=self.freq):
                try:
                    yield from self.read_mosmix(date)
                except IndexError as e:
                    log.warning(e)
                    continue

    def read_mosmix(self, date: Union[datetime, DWDForecastDate]) -> DWDMosmixResult:
        """
        Manage data acquisition for a given date that is used to filter the found files
        on the MOSMIX path of the DWD server.

        Args:
            date: datetime or enumeration for latest MOSMIX forecast

        Returns:
            DWDMosmixResult with gathered information
        """
        for df_metadata, df_forecast in self._read_mosmix(date):
            df_forecast = df_forecast.rename(
                columns={
                    "station_id": DWDMetaColumns.STATION_ID.value,
                    "datetime": DWDMetaColumns.DATETIME.value,
                }
            )

            self.coerce_columns(df_forecast)

            if self.tidy_data:
                df_forecast = df_forecast.melt(
                    id_vars=[
                        DWDMetaColumns.STATION_ID.value,
                        DWDMetaColumns.DATETIME.value,
                    ],
                    var_name=DWDMetaColumns.ELEMENT.value,
                    value_name=DWDMetaColumns.VALUE.value,
                )

            if self.humanize_column_names:
                hcnm = self._create_humanized_column_names_mapping()

                if self.tidy_data:
                    df_forecast[DWDMetaColumns.ELEMENT.value] = df_forecast[
                        DWDMetaColumns.ELEMENT.value
                    ].apply(lambda x: hcnm[x])
                else:
                    df_forecast = df_forecast.rename(columns=hcnm)

            # Complement metadata
            station_id = df_forecast[DWDMetaColumns.STATION_ID.value].iloc[0]

            station_metadata = self.metadata[
                self.metadata[DWDMetaColumns.WMO_ID.value] == station_id
            ].reset_index(drop=True)

            df_metadata = df_metadata.rename(columns=str.upper).reset_index(drop=True)

            df_metadata = df_metadata.join(station_metadata)

            result = DWDMosmixResult(df_metadata, df_forecast)

            yield result

    def _read_mosmix(
        self, date: Union[DWDForecastDate, datetime]
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """Wrapper that either calls read_mosmix_s or read_mosmix_l depending on
        defined period type"""
        if self.forecast_type == DWDMosmixType.SMALL:
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

        df_urls[DWDMetaColumns.DATETIME.value] = df_urls["URL"].apply(
            lambda url_: url_.split("/")[-1].split("_")[2].replace(".kmz", "")
        )

        df_urls = df_urls[df_urls[DWDMetaColumns.DATETIME.value] != "LATEST"]

        df_urls[DWDMetaColumns.DATETIME.value] = pd.to_datetime(
            df_urls[DWDMetaColumns.DATETIME.value], format=DatetimeFormat.YMDH.value
        )

        df_urls = df_urls.loc[df_urls[DWDMetaColumns.DATETIME.value] == date]

        if df_urls.empty:
            raise IndexError(f"Unable to find {date} file within {url}")

        return df_urls["URL"].item()

    @staticmethod
    def coerce_columns(df):
        """ Column type coercion helper """
        for column in df.columns:
            if column == DWDMetaColumns.STATION_ID.value:
                df[column] = df[column].astype(str)
            elif column in DATE_FIELDS_REGULAR:
                df[column] = pd.to_datetime(
                    df[column], infer_datetime_format=True, utc=False
                )
            elif column in INTEGER_FIELDS:
                df[column] = df[column].astype(pd.Int64Dtype())
            else:
                df[column] = df[column].astype(float)

    def _create_humanized_column_names_mapping(self) -> Dict[str, str]:
        """Create humanized column names mapping from DWDForecastParameters
        enumeration"""
        hcnm = {
            forecast_parameter.name: forecast_parameter.value
            for forecast_parameter in DWDForecastParameter
        }

        return hcnm


class DWDMosmixSites(WDSitesCore):
    """ Implementation of sites for MOSMIX forecast sites """

    def __init__(
        self,
        start_date: Union[None, str, Timestamp] = None,
        end_date: Union[None, str, Timestamp] = None,
    ) -> None:
        super().__init__(
            start_date=start_date,
            end_date=end_date,
        )

    def _all(self):
        return metadata_for_forecasts()
