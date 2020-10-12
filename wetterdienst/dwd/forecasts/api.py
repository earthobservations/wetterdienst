import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Union, Optional, Generator, Tuple
from urllib.parse import urljoin

import pandas as pd
from pandas._libs.tslibs.timestamps import Timestamp
from requests import HTTPError

from wetterdienst import Parameter, TimeResolution, PeriodType
from wetterdienst.core.sites import WDSitesCore
from wetterdienst.dwd.forecasts.metadata import ForecastDate
from wetterdienst.dwd.forecasts.stations import metadata_for_forecasts
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.constants import (
    DWD_SERVER,
    DWD_MOSMIX_S_PATH,
    DWD_MOSMIX_L_PATH,
    DWD_MOSMIX_L_SINGLE_PATH,
)
from wetterdienst.dwd.forecasts.access import KMLReader
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.util.network import list_remote_files

log = logging.getLogger(__name__)


@dataclass
class DWDMosmixResult:
    """
    Result object encapsulating metadata, station information and forecast data.
    """

    metadata: pd.DataFrame
    forecast: pd.DataFrame

    def to_dict(self):
        data = dict()

        data["metadata"] = self.metadata.to_dict(orient="records")[0]
        data["forecast"] = self.forecast.to_dict(orient="records")

        return data


class DWDMosmixData:
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
            period_type: PeriodType,
            station_ids: List[str],
            parameters: Optional[List] = None,
            start_date: Optional[Union[str, datetime, ForecastDate]] = ForecastDate.LATEST,
            end_date: Optional[Union[str, datetime, timedelta]] = None,
            tidy_data: bool = True,
            humanize_column_names: bool = False,
    ) -> None:
        """

        Args:
            period_type:
            station_ids:
            parameters:
        """
        if period_type not in (PeriodType.FORECAST_SHORT, PeriodType.FORECAST_LONG):
            raise ValueError(
                "period_type should be one of FORECAST_SHORT or FORECAST_LONG")
        station_ids = None if not station_ids else pd.Series(
            station_ids).astype(str).tolist()
        parameters = None if not parameters else pd.Series(
            parameters).astype(str).tolist()

        if not start_date and not end_date:
            start_date = ForecastDate.LATEST
        elif not end_date:
            end_date = start_date
        elif not start_date:
            start_date = end_date

        if start_date is not ForecastDate.LATEST:
            start_date = pd.to_datetime(
                start_date, infer_datetime_format=True).floor("1H")
            end_date = pd.to_datetime(
                end_date, infer_datetime_format=True).floor("1H")

            # Shift dates to 3, 9, 15, 21 hour format
            if period_type == PeriodType.FORECAST_LONG:
                start_date = self.adjust_datetime(start_date)
                end_date = self.adjust_datetime(end_date)

        self.period_type = period_type
        self.station_ids = station_ids
        self.parameters = parameters
        self.start_date = start_date
        self.end_date = end_date
        self.tidy_data = tidy_data
        self.humanize_column_names = humanize_column_names

        if period_type == PeriodType.FORECAST_SHORT:
            self.freq = "1H"  # short forecasts released every hour
        else:
            self.freq = "6H"

        # Add fixed attributes
        self.time_resolution = TimeResolution.HOURLY
        # Take climate summary as it matches best to MOSMIX
        self.parameter = Parameter.CLIMATE_SUMMARY

        self.kml = KMLReader(station_ids=self.station_ids, parameters=self.parameters)

    @property
    def metadata(self):
        return metadata_for_forecasts()

    @staticmethod
    def adjust_datetime(datetime_: datetime) -> datetime:
        regular_date = datetime_ + pd.offsets.DateOffset(hour=3)

        if regular_date > datetime_:
            regular_date -= pd.Timedelta(hours=6)

        delta_hours = (datetime_.hour - regular_date.hour) % 6

        datetime_adjusted = datetime_ - pd.Timedelta(hours=delta_hours)

        return datetime_adjusted

    def collect_data(self) -> Generator[DWDMosmixResult, None, None]:
        if self.start_date == ForecastDate.LATEST:
            yield from self.read_mosmix(self.start_date)
        else:
            for date in pd.date_range(self.start_date, self.end_date, freq=self.freq):
                try:
                    yield from self.read_mosmix(date)
                except IndexError as e:
                    log.warning(e)
                    continue

    def read_mosmix(self, date):
        for metadata, forecast in self._read_mosmix(date):
            forecast = forecast.rename(
                columns={
                    "station_id": DWDMetaColumns.STATION_ID.value,
                    "datetime": DWDMetaColumns.DATETIME.value
                })

            self.coerce_columns(forecast)

            if self.tidy_data:
                forecast = forecast.melt(
                    id_vars=[DWDMetaColumns.STATION_ID.value,
                             DWDMetaColumns.DATETIME.value],
                    value_name=DWDMetaColumns.VALUE.value
                )

            # Complement metadata
            station_id = forecast[DWDMetaColumns.STATION_ID.value].iloc[0]

            station_metadata = self.metadata[
                self.metadata[DWDMetaColumns.WMO_ID.value] == station_id]

            metadata = metadata.rename(columns=str.upper)

            metadata = pd.concat([metadata, station_metadata], axis=1)

            result = DWDMosmixResult(
                metadata,
                forecast
            )

            yield result

    def _read_mosmix(self, date: Union[ForecastDate, datetime]) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        if self.period_type == PeriodType.FORECAST_SHORT:
            yield from self.read_mosmix_s(date)
        else:
            yield from self.read_mosmix_l(date)

    # def read_mosmix_s_latest(self) -> DWDMosmixResult:
    #     """
    #     Fetch weather forecast data (KML/MOSMIX_S dataset).
    #     """
    #     url = urljoin(DWD_SERVER, DWD_MOSMIX_S_PATH)
    #
    #     return self.read_mosmix_single(url)
    #
    # def read_mosmix_l_latest(self) -> DWDMosmixResult:
    #     """
    #     Fetch weather forecast data (KML/MOSMIX_L dataset).
    #     """
    #     if self.station_ids is None:  # pragma: no cover
    #         url = urljoin(DWD_SERVER, DWD_MOSMIX_L_PATH)
    #         return self.read_mosmix_single(url)
    #     else:
    #         url = urljoin(DWD_SERVER, DWD_MOSMIX_L_SINGLE_PATH)
    #         return self.read_mosmix_multi(url)

    def read_mosmix_s(self, date) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        url = urljoin(DWD_SERVER, DWD_MOSMIX_S_PATH)

        file_url = self.get_url_for_date(url, date)

        self.kml.read(file_url)

        for forecast in self.kml.get_forecasts():
            yield self.kml.get_metadata(), forecast

    def read_mosmix_l(self, date) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
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
    def get_url_for_date(url, date) -> str:
        urls = list_remote_files(url, False)

        if date == ForecastDate.LATEST:
            try:
                url = list(filter(lambda url_: "LATEST" in url.upper(), urls))[0]
                return url
            except IndexError as e:
                raise IndexError(f"Unable to find LATEST file within {url}") from e

        df_urls = pd.DataFrame({"URL": urls})

        df_urls[DWDMetaColumns.DATETIME.value] = df_urls["URL"].apply(
            lambda url_: url_.split("/")[-1].split("_")[2].replace(".kmz", ""))

        df_urls = df_urls[df_urls[DWDMetaColumns.DATETIME.value] != "LATEST"]

        df_urls[DWDMetaColumns.DATETIME.value] = pd.to_datetime(
            df_urls[DWDMetaColumns.DATETIME.value], format=DatetimeFormat.YMDH.value)

        df_urls = df_urls.loc[df_urls[DWDMetaColumns.DATETIME.value] == date]

        if df_urls.empty:
            raise IndexError(f"Unable to find {date} file within {url}")

        return df_urls["URL"].item()

    @staticmethod
    def coerce_columns(df):
        for column in df.columns:
            if column == "W1W2" or column.startswith("WPc") or column in ["ww", "ww3"]:
                df[column] = df[column].astype("Int64")


class DWDForecastSites(WDSitesCore):
    def __init__(
            self,
            start_date: Union[None, str, Timestamp] = None,
            end_date: Union[None, str, Timestamp] = None,
    ) -> None:
        super().__init__(
            parameter=Parameter.CLIMATE_SUMMARY,
            time_resolution=TimeResolution.HOURLY,
            period_type=[PeriodType.FORECAST_SHORT, PeriodType.FORECAST_LONG],
            start_date=start_date,
            end_date=end_date
        )

    @staticmethod
    def _check_parameters(**kwargs):
        pass

    def _all(self):
        return metadata_for_forecasts()


if __name__ == "__main__":
    mosmix_request = DWDMosmixData(
        period_type=PeriodType.FORECAST_LONG,
        station_ids=['EW002'],
        parameters=None,
        start_date="2020-10-11 14:00",
        end_date="2020-10-11 22:00",
        tidy_data=True
    )

    for item in mosmix_request.collect_data():
        print(item.to_json())
