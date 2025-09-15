# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD DMO API."""

from __future__ import annotations

import contextlib
import datetime as dt
import logging
from dataclasses import dataclass
from enum import Enum
from io import StringIO
from typing import TYPE_CHECKING, ClassVar, Literal
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.dmo.metadata import DwdDmoMetadata
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import download_file, list_remote_files_fsspec
from wetterdienst.util.polars_util import read_fwf_from_df

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)


class DwdForecastDate(Enum):
    """Enumeration for pointing to different mosmix dates."""

    LATEST = "latest"


class DwdDmoStationGroup(Enum):
    """Enumeration for DWD DMO station groups."""

    SINGLE_STATIONS = "single_stations"
    ALL_STATIONS = "all_stations"


class DwdDmoLeadTime(Enum):
    """Enumeration for DWD DMO lead times."""

    SHORT = 78
    LONG = 168


def add_date_from_filename(df: pl.DataFrame, current_date: dt.datetime) -> pl.DataFrame:
    """Add date from filename."""
    if len(df) < 2:
        msg = "Dataframe must have at least 2 dates"
        raise ValueError(msg)
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
            pl.lit(0).alias("minute"),
        ],
    )
    days_difference = df.get_column("day").cast(pl.Int8).max() - df.get_column("day").cast(pl.Int8).min()
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
    # format data
    df = df.with_columns(
        pl.col("day").cast(pl.String).str.pad_start(2, "0"),
        pl.col("month").cast(pl.String).str.pad_start(2, "0"),
        pl.col("minute").cast(pl.String).str.pad_start(2, "0"),
    )
    return df.select(
        [
            pl.all().exclude(["year", "month", "day", "hour"]),
            pl.concat_str([pl.col("year"), pl.col("month"), pl.col("day"), pl.col("hour"), pl.col("minute")])
            .str.to_datetime(format="%Y%m%d%H%M", time_zone=current_date.tzname())
            .alias("date"),
        ],
    )


class DwdDmoValues(TimeseriesValues):
    """Fetch DWD DMO data."""

    def __post_init__(self) -> None:
        """Post-initialize the DwdDmoValues class."""
        super().__post_init__()
        self.kml = KMLReader(
            station_ids=self.sr.station_id.to_list(),
            settings=self.sr.stations.settings,
        )

    def get_dwd_dmo_path(self, dataset: DatasetModel, station_id: str | None = None) -> str:
        """Get DWD DMO path."""
        path = f"weather/local_forecasts/dmo/{dataset.name_original}/{self.sr.stations.station_group.value}"
        if self.sr.stations.station_group == DwdDmoStationGroup.ALL_STATIONS:
            return f"{path}/kmz"
        return f"{path}/{station_id}/kmz/"

    @property
    def metadata(self) -> pl.DataFrame:
        """Get metadata DataFrame for DMO."""
        return self.sr.df

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        df = self.read_dmo(station_id=station_id, dataset=parameter_or_dataset, date=self.sr.stations.issue)
        if df.is_empty():
            return df
        df = df.unpivot(
            index=[
                "date",
            ],
            variable_name="parameter",
            value_name="value",
        )
        return df.select(
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            "parameter",
            pl.col("date").str.to_datetime(format="%Y-%m-%dT%H:%M:%S.000Z", time_zone="UTC"),
            "value",
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )

    def read_dmo(self, station_id: str, dataset: DatasetModel, date: dt.datetime | DwdForecastDate) -> pl.DataFrame:
        """Read DMO data."""
        if dataset == DwdDmoMetadata.hourly.icon_eu:
            return self.read_icon_eu(station_id, date)
        return self.read_icon(station_id, date)

    def read_icon_eu(self, station_id: str, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Read large icon_eu file with all stations."""
        dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon_eu)
        url = urljoin("https://opendata.dwd.de", dmo_path)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def read_icon(self, station_id: str, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Read either large icon file with all stations or small single station file."""
        if self.sr.stations.station_group == DwdDmoStationGroup.ALL_STATIONS:
            dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon)
        else:
            dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon, station_id=station_id)
        url = urljoin("https://opendata.dwd.de", dmo_path)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def get_url_for_date(self, url: str, date: dt.datetime | DwdForecastDate) -> str:
        """Get URL for a specific date."""
        urls = list_remote_files_fsspec(url, self.sr.stations.settings, CacheExpiry.NO_CACHE)
        df = pl.DataFrame({"url": urls}, orient="col")
        df = df.filter(pl.col("url").str.contains(self.sr.stations.lead_time.value))
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
            msg = f"Unable to find {date} file within {url}"
            raise IndexError(msg)
        return df.get_column("url").item()


@dataclass
class DwdDmoRequest(TimeseriesRequest):
    """Implementation of sites for dmo sites."""

    metadata = DwdDmoMetadata
    _values = DwdDmoValues
    # required parameters
    issue: str | dt.datetime | DwdForecastDate = DwdForecastDate.LATEST
    station_group: str | DwdDmoStationGroup | None = None
    lead_time: Literal["short", "long"] | DwdDmoLeadTime | None = None

    _url = (
        "https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/"
        "dmo_stationsliste_txt.asc?__blob=publicationFile&v=1"
    )
    _base_columns: ClassVar = [
        "resolution",
        "dataset",
        "station_id",
        "icao_id",
        "start_date",
        "end_date",
        "latitude",
        "longitude",
        "height",
        "name",
        "state",
    ]

    @staticmethod
    def adjust_datetime(datetime_: dt.datetime) -> dt.datetime:
        """Adjust datetime to DMO release frequency (9/12 hours).

        Datetime is floored to closest release time e.g. if hour is 14, it will be rounded to 12

        """
        adjusted_date = datetime_.replace(minute=0, second=0, microsecond=0)
        delta_hours = adjusted_date.hour % 12
        if delta_hours > 0:
            return adjusted_date.replace(hour=12)
        return adjusted_date

    def __post_init__(self) -> None:
        """Post-initialize the DwdDmoRequest class."""
        super().__post_init__()
        self.station_group = (
            parse_enumeration_from_template(self.station_group, DwdDmoStationGroup)
            or DwdDmoStationGroup.SINGLE_STATIONS
        )
        self.lead_time = parse_enumeration_from_template(self.lead_time, DwdDmoLeadTime) or DwdDmoLeadTime.SHORT
        with contextlib.suppress(InvalidEnumerationError):
            issue = parse_enumeration_from_template(self.issue, DwdForecastDate)
        if issue is not DwdForecastDate.LATEST:
            if isinstance(issue, str):
                issue = dt.datetime.fromisoformat(self.issue)
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour, tzinfo=ZoneInfo("UTC"))
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
        """Get all stations from DMO."""
        file = download_file(
            url=self._url,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        file.raise_if_exception()
        text = StringIO(file.content.read().decode(encoding="latin-1"))
        lines = text.readlines()
        header = lines.pop(0)
        df_raw = pl.DataFrame({"column_0": lines[1:]})
        df_raw.columns = [header]
        column_specs = ((0, 4), (5, 9), (10, 30), (31, 38), (39, 46), (48, 56))
        df_raw = read_fwf_from_df(df_raw, column_specs)
        df_raw.columns = [
            "station_id",
            "icao_id",
            "name",
            "latitude",
            "longitude",
            "height",
        ]
        df_raw = df_raw.join(self._station_patches.select("station_id"), how="anti", on="station_id")
        df_raw = pl.concat([df_raw, self._station_patches])
        df_raw = df_raw.with_columns(
            pl.col("icao_id").replace("----", None),
            pl.col("latitude").str.replace(" ", "").cast(pl.Float64),
            pl.col("longitude").str.replace(" ", "").cast(pl.Float64),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("start_date"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("end_date"),
            pl.lit(None, pl.String).alias("state"),
        )
        # combinations of resolution and dataset
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name) for parameter in self.parameters
        }
        data = []
        # for each combination of resolution and dataset create a new DataFrame with the columns
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df_raw.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        df = pl.concat(data)
        df = df.select(self._base_columns)
        return df.lazy()
