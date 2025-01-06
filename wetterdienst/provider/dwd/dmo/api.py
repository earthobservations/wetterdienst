# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import logging
from enum import Enum
from io import StringIO
from typing import TYPE_CHECKING, Literal
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.dmo.metadata import DwdDmoMetadata
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.util.enumeration import parse_enumeration_from_template
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


class DwdForecastDate(Enum):
    """
    Enumeration for pointing to different mosmix dates.
    """

    LATEST = "latest"


class DwdDmoStationGroup(Enum):
    SINGLE_STATIONS = "single_stations"
    ALL_STATIONS = "all_stations"


class DwdDmoLeadTime(Enum):
    SHORT = 78
    LONG = 168


def add_date_from_filename(df: pl.DataFrame, current_date: dt.datetime) -> pl.DataFrame:
    """
    Add date column to dataframe based on filename
    :param df: Dataframe with url column
    :param current_date: Current date without timezone
    :return: Dataframe with date column
    """
    if len(df) < 2:
        raise ValueError("Dataframe must have at least 2 dates")
    # get month and year from current date
    year = current_date.year
    month = current_date.month
    # if current date is in the first 3 hours of the month, use previous month
    hours_since_month_start = (
        (current_date - current_date.replace(day=1, hour=1, minute=1, second=1)).total_seconds() / 60 / 60
    )
    if hours_since_month_start < 3:
        month = month - 1
        # if month is 0, set to 12 and decrease year
        if month == 0:
            month = 12
            year = year - 1
    df = df.with_columns(
        [
            pl.lit(year).alias("year"),
            pl.col("date_str").str.slice(offset=0, length=2).cast(int).alias("day"),
            pl.col("date_str").str.slice(offset=2, length=2).cast(int).alias("hour"),
        ],
    )
    days_difference = df.get_column("day").max() - df.get_column("day").min()
    if days_difference > 20:
        df = df.with_columns(
            pl.when(pl.col("day") > 25).then(month - 1 if month > 1 else 12).otherwise(month).alias("month"),
        )
    else:
        df = df.with_columns(pl.lit(month).alias("month"))
    months_difference = df.get_column("month").max() - df.get_column("month").min()
    if months_difference > 6:
        df = df.with_columns(pl.when(pl.col("month") > 6).then(year - 1).otherwise(year).alias("year"))
    else:
        df = df.with_columns(pl.lit(year).alias("year"))
    return df.select(
        [
            pl.all().exclude(["year", "month", "day", "hour"]),
            pl.struct(["year", "month", "day", "hour"])
            .map_elements(lambda s: dt.datetime(s["year"], s["month"], s["day"], s["hour"]), return_dtype=pl.Datetime)
            .alias("date"),
        ],
    )


class DwdDmoValues(TimeseriesValues):
    """
    Fetch DWD DMO data.

    Parameters
    ----------
    station_id : List
        - If None, data for all stations_result is returned.
        - If not None, station_ids are a list of station ids for which data is desired.

    parameter: List
        - If None, data for all parameters is returned.
        - If not None, list of parameters, per DMO definition, see
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

    def get_dwd_dmo_path(self, dataset: DatasetModel, station_id: str | None = None) -> str:
        path = f"weather/local_forecasts/dmo/{dataset.name_original}/{self.sr.stations.station_group.value}"
        if self.sr.stations.station_group == DwdDmoStationGroup.ALL_STATIONS:
            return f"{path}/kmz"
        return f"{path}/{station_id}/kmz/"

    @property
    def metadata(self) -> pl.DataFrame:
        """
        Wrapper for dmo metadata

        :return:
        """
        return self.sr.df

    def _collect_station_parameter_or_dataset(
        self, station_id: str, parameter_or_dataset: DatasetModel
    ) -> pl.DataFrame:
        df = self.read_dmo(station_id=station_id, dataset=parameter_or_dataset, date=self.sr.stations.issue)
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

    def read_dmo(self, station_id: str, dataset: DatasetModel, date: dt.datetime | DwdForecastDate) -> pl.DataFrame:
        if dataset == DwdDmoMetadata.hourly.icon_eu:
            return self.read_icon_eu(station_id, date)
        else:
            return self.read_icon(station_id, date)

    def read_icon_eu(self, station_id: str, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Reads large icon_eu file with all stations."""
        dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon_eu)
        url = urljoin("https://opendata.dwd.de", dmo_path)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def read_icon(self, station_id: str, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Reads either large icon file with all stations or small single station file."""
        if self.sr.stations.station_group == DwdDmoStationGroup.ALL_STATIONS:
            dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon)
        else:
            dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon, station_id=station_id)
        url = urljoin("https://opendata.dwd.de", dmo_path)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def get_url_for_date(self, url: str, date: dt.datetime | DwdForecastDate) -> str:
        """
        Method to get a file url based on the dmo url and the date that is
        used for filtering.

        :param url: dmo path on the dwd server
        :param date: date used for filtering of the available files
        :return: file url based on the filtering
        """
        urls = list_remote_files_fsspec(url, self.sr.stations.settings, CacheExpiry.NO_CACHE)
        df = pl.DataFrame({"url": urls}, orient="col")
        df = df.filter(pl.col("url").str.contains(str(self.sr.stations.lead_time.value)))
        df = df.with_columns(
            pl.col("url")
            .str.split("/")
            .list.last()
            .str.split("_")
            .list.last()
            .map_elements(lambda s: s[:-4], return_dtype=pl.String)
            .alias("date_str"),
        )
        df = add_date_from_filename(df, dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None))
        if date == DwdForecastDate.LATEST:
            date = df.get_column("date").max()
        df = df.filter(pl.col("date").eq(date))
        if df.is_empty():
            raise IndexError(f"Unable to find {date} file within {url}")
        return df.get_column("url").item()


class DwdDmoRequest(TimeseriesRequest):
    """Implementation of sites for dmo sites"""

    metadata = DwdDmoMetadata
    _values = DwdDmoValues

    _url = (
        "https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/"
        "dmo_stationsliste_txt.asc?__blob=publicationFile&v=1"
    )

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

    @staticmethod
    def adjust_datetime(datetime_: dt.datetime) -> dt.datetime:
        """
        Adjust datetime to DMO release frequency (9/12 hours). Datetime is floored
        to closest release time e.g. if hour is 14, it will be rounded to 12

        :param datetime_: datetime that is adjusted
        :return: adjusted datetime with floored hour
        """
        adjusted_date = datetime_.replace(minute=0, second=0, microsecond=0)
        delta_hours = adjusted_date.hour % 12
        if delta_hours > 0:
            return adjusted_date.replace(hour=12)
        return adjusted_date

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        issue: str | dt.datetime | DwdForecastDate = DwdForecastDate.LATEST,
        station_group: str | DwdDmoStationGroup | None = None,
        lead_time: Literal["short", "long"] | DwdDmoLeadTime | None = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """
        :param parameters: parameter(s) to be collected
        :param start_date: start date for filtering returned dataframe
        :param end_date: end date
        :param issue: issue of dmo which should be caught (DMO run at time XX:YY)
        """
        self.station_group = (
            parse_enumeration_from_template(station_group, DwdDmoStationGroup) or DwdDmoStationGroup.SINGLE_STATIONS
        )
        self.lead_time = parse_enumeration_from_template(lead_time, DwdDmoLeadTime) or DwdDmoLeadTime.SHORT

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
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour)
            # Shift issue date to 0, 12 hour format
            issue = self.adjust_datetime(issue)

        self.issue = issue

    # required patches for stations as data is corrupted for these at least atm
    _station_patches = pl.DataFrame(
        [
            {
                "station_id": "03779",
                "icao_id": "EGRB",
                "name": "LONDON WEATHER CENT.",
                "latitude": "51.31",
                "longitude": "-0.12",
                "height": "5",
            },
            {
                "station_id": "03781",
                "icao_id": "----",
                "name": "KENLEY",
                "latitude": "51.18",
                "longitude": "-0.08",
                "height": "170",
            },
            {
                "station_id": "61226",
                "icao_id": "GAGO",
                "name": "GAO",
                "latitude": "16.16",
                "longitude": "-0.05",
                "height": "265",
            },
            {
                "station_id": "82106",
                "icao_id": "SBUA",
                "name": "SAO GABRIEL CACHOEI",
                "latitude": "-0.13",
                "longitude": "-67.04",
                "height": "90",
            },
            {
                "station_id": "84071",
                "icao_id": "SEQU",
                "name": "QUITO",
                "latitude": "-0.15",
                "longitude": "-78.29",
                "height": "2794",
            },
            {
                "station_id": "F9766",
                "icao_id": "SEQM",
                "name": "QUITO/MARISCAL SUCRE",
                "latitude": "-0.1",
                "longitude": "-78.21",
                "height": "2400",
            },
            {
                "station_id": "P0478",
                "icao_id": "EGLC",
                "name": "LONDON/CITY INTL",
                "latitude": "51.29",
                "longitude": "0.12",
                "height": "5",
            },
        ],
    )

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
        column_specs = ((0, 4), (5, 9), (10, 30), (31, 38), (39, 46), (48, 56))
        df = read_fwf_from_df(df, column_specs)
        df.columns = [
            Columns.STATION_ID.value,
            Columns.ICAO_ID.value,
            Columns.NAME.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
        ]
        df = df.filter(pl.col("station_id").is_in(self._station_patches.get_column("station_id")).not_())
        df = pl.concat([df, self._station_patches])
        df = df.lazy()
        return df.with_columns(
            pl.col(Columns.ICAO_ID.value).replace("----", None),
            pl.col(Columns.LATITUDE.value).str.replace(" ", "").cast(pl.Float64),
            pl.col(Columns.LONGITUDE.value).str.replace(" ", "").cast(pl.Float64),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias(Columns.START_DATE.value),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias(Columns.END_DATE.value),
            pl.lit(None, pl.String).alias(Columns.STATE.value),
        )
