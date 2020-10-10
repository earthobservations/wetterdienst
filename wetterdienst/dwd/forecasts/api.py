from dataclasses import dataclass
from typing import List, Union, Optional
from urllib.parse import urljoin

import pandas as pd
from pandas._libs.tslibs.timestamps import Timestamp

from wetterdienst import Parameter, TimeResolution, PeriodType
from wetterdienst.core.sites import WDSitesCore
from wetterdienst.dwd.forecasts.stations import metadata_for_forecasts
from wetterdienst.dwd.metadata.constants import (
    DWD_SERVER,
    DWD_MOSMIX_S_PATH,
    DWD_MOSMIX_L_PATH,
    DWD_MOSMIX_L_SINGLE_PATH,
)
from wetterdienst.dwd.forecasts.access import KMLReader
from wetterdienst.util.network import list_remote_files


@dataclass
class MOSMIXResult:
    """
    Result object encapsulating metadata, station information and forecast data.
    """

    metadata: pd.DataFrame
    stations: pd.DataFrame
    forecasts: pd.DataFrame


class MOSMIXRequest:
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
            station_ids: Optional[List] = None,
            parameters: Optional[List] = None
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

        self.period_type = period_type
        self.station_ids = station_ids
        self.parameters = parameters

        self.kml = KMLReader(station_ids=self.station_ids, parameters=self.parameters)

    def read_mosmix_s_latest(self) -> MOSMIXResult:
        """
        Fetch weather forecast data (KML/MOSMIX_S dataset).
        """
        url = urljoin(DWD_SERVER, DWD_MOSMIX_S_PATH)

        return self.read_mosmix_single(url)

    def read_mosmix_l_latest(self) -> MOSMIXResult:
        """
        Fetch weather forecast data (KML/MOSMIX_L dataset).
        """
        if self.station_ids is None:  # pragma: no cover
            url = urljoin(DWD_SERVER, DWD_MOSMIX_L_PATH)
            return self.read_mosmix_single(url)
        else:
            url = urljoin(DWD_SERVER, DWD_MOSMIX_L_SINGLE_PATH)
            return self.read_mosmix_multi(url)

    def read_mosmix_single(self, url) -> MOSMIXResult:

        url = self.get_url_latest(url)
        self.kml.read(url)

        result = MOSMIXResult(
            metadata=self.kml.get_metadata(),
            stations=self.kml.get_stations(),
            forecasts=self.get_forecasts(),
        )

        return result

    def read_mosmix_multi(self, url) -> MOSMIXResult:
        for station_id in self.station_ids:
            station_url = url.format(station_id=station_id)
            station_url = self.get_url_latest(station_url)
            self.kml.read(station_url)

        result = MOSMIXResult(
            metadata=self.kml.get_metadata(),
            stations=self.kml.get_stations(),
            forecasts=self.get_forecasts(),
        )

        return result

    def get_url_latest(self, url):
        urls = list_remote_files(url, False)
        try:
            url = list(filter(lambda url: "LATEST" in url, urls))[0]
            return url
        except:  # noqa:E722,B001
            raise KeyError(f"Unable to find LATEST file within {url}")

    def get_forecasts(self):
        df = self.kml.get_forecasts()
        self.coerce_columns(df)
        return df

    def coerce_columns(self, df):
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
