# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import logging
from enum import Enum
from io import StringIO
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import polars as pl

from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import convert_dm_to_dd
from wetterdienst.util.network import download_file, list_remote_files_fsspec
from wetterdienst.util.polars_util import read_fwf_from_df

if TYPE_CHECKING:
    from wetterdienst.core.timeseries.metadata import DatasetModel
    from wetterdienst.core.timeseries.result import StationsResult

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)

DWD_MOSMIX_S_PATH = "weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/"
DWD_MOSMIX_L_PATH = "weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/"
DWD_MOSMIX_L_SINGLE_PATH = "weather/local_forecasts/mos/MOSMIX_L/single_stations/{station_id}/kml/"


class DwdMosmixStationGroup(Enum):
    SINGLE_STATIONS = "single_stations"
    ALL_STATIONS = "all_stations"


class DwdForecastDate(Enum):
    """
    Enumeration for pointing to different mosmix dates.
    """

    LATEST = "latest"


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

    def __init__(self, stations_result: StationsResult) -> None:
        """

        :param stations_result:
        """
        super().__init__(stations_result=stations_result)

        self.kml = KMLReader(
            station_ids=self.sr.station_id.to_list(),
            settings=self.sr.stations.settings,
        )

    @property
    def metadata(self) -> pl.DataFrame:
        """
        Wrapper for mosmix metadata

        :return:
        """
        return self.sr.df

    @staticmethod
    def adjust_datetime(datetime_: dt.datetime) -> dt.datetime:
        """
        Adjust datetime to MOSMIX release frequency, which is required for MOSMIX-L
        that is only released very 6 hours (3, 9, 15, 21). Datetime is floored
        to closest release time e.g. if hour is 14, it will be rounded to 9

        :param datetime_: datetime that is adjusted
        :return: adjusted datetime with floored hour
        """
        regular_date = dt.datetime.fromordinal(datetime_.date().toordinal()).replace(hour=3, tzinfo=datetime_.tzinfo)
        if regular_date > datetime_:
            regular_date -= dt.timedelta(hours=6)
        delta_hours = (datetime_.hour - regular_date.hour) % 6
        return datetime_ - dt.timedelta(hours=delta_hours)

    def _collect_station_parameter_or_dataset(
        self, station_id: str, parameter_or_dataset: DatasetModel
    ) -> pl.DataFrame:
        """
        Wrapper of read_mosmix to collect mosmix data (either latest or for
        defined dates)

        :return: pandas DataFrame with data corresponding to station id and parameter
        """
        # Shift issue date to 3, 9, 15, 21 hour format
        issue = self.sr.stations.issue
        if issue is not DwdForecastDate.LATEST:
            if parameter_or_dataset == DwdMosmixMetadata.hourly.large:
                issue = self.adjust_datetime(issue)
        df = self.read_mosmix(station_id=station_id, dataset=parameter_or_dataset, date=issue)
        if df.is_empty():
            return df
        df = df.unpivot(
            index=[
                Columns.DATE.value,
            ],
            variable_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
        )
        return df.with_columns(
            pl.lit(station_id, dtype=pl.String).alias(Columns.STATION_ID.value),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )

    def read_mosmix(self, station_id: str, dataset: DatasetModel, date: dt.datetime | DwdForecastDate) -> pl.DataFrame:
        """
        Manage data acquisition for a given date that is used to filter the found files
        on the MOSMIX path of the DWD server.

        :param date: datetime or enumeration for latest MOSMIX mosmix
        :return: pandas DataFrame with gathered information
        """
        if dataset == DwdMosmixMetadata.hourly.small:
            return self.read_mosmix_small(station_id, date)
        elif dataset == DwdMosmixMetadata.hourly.large:
            return self.read_mosmix_large(station_id, date)
        else:
            raise KeyError(f"Dataset {dataset} not supported")

    def read_mosmix_small(self, station_id, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Reads single MOSMIX-S file for all stations."""
        url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_S_PATH)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def read_mosmix_large(
        self,
        station_id: str,
        date: DwdForecastDate | dt.datetime,
    ) -> pl.DataFrame:
        """Reads either a large MOSMIX-L file with all stations or a small MOSMIX-L file for a single station."""
        if self.sr.stations.station_group == DwdMosmixStationGroup.ALL_STATIONS:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_PATH)
        else:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_SINGLE_PATH).format(station_id=station_id)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def get_url_for_date(self, url: str, date: dt.datetime | DwdForecastDate) -> str:
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
                return list(filter(lambda url_: "LATEST" in url_.upper(), urls))[0]
            except IndexError as e:
                raise IndexError(f"Unable to find LATEST file within {url}") from e

        date = date.astimezone(dt.timezone.utc).replace(tzinfo=None)

        df = pl.DataFrame({"url": urls}, orient="col")

        df = df.with_columns(
            pl.col("url").str.split("/").list.last().str.split("_").list.gather(2).flatten().alias("date"),
        )

        df = df.filter(pl.col("date").ne("LATEST"))

        df = df.with_columns(
            pl.col("date").map_elements(lambda d: f"{d}00", return_dtype=pl.String).str.to_datetime("%Y%m%d%H%M"),
        )

        df = df.filter(pl.col("date").eq(date))

        if df.is_empty():
            raise IndexError(f"Unable to find {date} file within {url}")

        return df.get_column("url").item()


class DwdMosmixRequest(TimeseriesRequest):
    """Implementation of sites for MOSMIX mosmix sites"""

    metadata = DwdMosmixMetadata
    _values = DwdMosmixValues
    _url = "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg?view=nasPublication"

    _base_columns = [
        Columns.STATION_ID.value,
        Columns.ICAO_ID.value,
        Columns.START_DATE.value,
        Columns.END_DATE.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.HEIGHT.value,
        Columns.NAME.value,
        Columns.STATE.value,
    ]

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        issue: str | dt.datetime | DwdForecastDate | None = DwdForecastDate.LATEST,
        station_group: DwdMosmixStationGroup | None = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """
        :param parameters: parameter(s) to be collected
        :param start_date: start date for filtering returned dataframe
        :param end_date: end date
        :param issue: start of issue of mosmix which should be caught (Mosmix run at time XX:YY)
        """
        self.station_group = (
            parse_enumeration_from_template(station_group, DwdMosmixStationGroup)
            or DwdMosmixStationGroup.SINGLE_STATIONS
        )

        super().__init__(
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

        if not issue:
            issue = DwdForecastDate.LATEST

        try:
            issue = parse_enumeration_from_template(issue, DwdForecastDate)
        except InvalidEnumerationError:
            pass

        if issue is not DwdForecastDate.LATEST:
            if isinstance(issue, str):
                issue = dt.datetime.fromisoformat(issue)
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour, tzinfo=issue.tzinfo)

        self.issue = issue

    def _all(self) -> pl.LazyFrame:
        """
        Create meta data DataFrame from available station list

        :return:
        """
        log.info(f"Downloading file {self._url}.")
        payload = download_file(self._url, self.settings, CacheExpiry.METAINDEX)
        text = StringIO(payload.read().decode(encoding="latin-1"))
        lines = text.readlines()
        header = lines.pop(0)
        df = pl.DataFrame({"column_0": lines[1:]})
        df.columns = [header]
        column_specs = ((0, 5), (6, 9), (11, 30), (32, 38), (39, 46), (48, 56))
        df = read_fwf_from_df(df, column_specs)
        df.columns = [
            Columns.STATION_ID.value,
            Columns.ICAO_ID.value,
            Columns.NAME.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
        ]
        df = df.select(
            pl.col(Columns.STATION_ID.value),
            pl.col(Columns.ICAO_ID.value).replace("----", None),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias(Columns.START_DATE.value),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias(Columns.END_DATE.value),
            pl.col(Columns.LATITUDE.value).cast(float).map_batches(convert_dm_to_dd),
            pl.col(Columns.LONGITUDE.value).cast(float).map_batches(convert_dm_to_dd),
            pl.col(Columns.HEIGHT.value).cast(int),
            pl.col(Columns.NAME.value),
            pl.lit(None, pl.String).alias(Columns.STATE.value),
        )
        return df.lazy()
