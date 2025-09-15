# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API for DWD MOSMIX data."""

from __future__ import annotations

import contextlib
import datetime as dt
import logging
from dataclasses import dataclass
from enum import Enum
from io import StringIO
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

import polars as pl

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import convert_dm_to_dd
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

DWD_MOSMIX_S_PATH = "weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/"
DWD_MOSMIX_L_PATH = "weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/"
DWD_MOSMIX_L_SINGLE_PATH = "weather/local_forecasts/mos/MOSMIX_L/single_stations/{station_id}/kml/"


class DwdMosmixStationGroup(Enum):
    """Enumeration for pointing to different mosmix station groups."""

    SINGLE_STATIONS = "single_stations"
    ALL_STATIONS = "all_stations"


class DwdForecastDate(Enum):
    """Enumeration for pointing to different mosmix dates."""

    LATEST = "latest"


class DwdMosmixValues(TimeseriesValues):
    """Fetch weather mosmix data (KML/MOSMIX_S dataset)."""

    def __post_init__(self) -> None:
        """Post-initialization of the DwdMosmixValues class."""
        super().__post_init__()
        self.kml = KMLReader(
            station_ids=self.sr.station_id.to_list(),
            settings=self.sr.stations.settings,
        )

    @property
    def metadata(self) -> pl.DataFrame:
        """Get metadata DataFrame for the MOSMIX data."""
        return self.sr.df

    @staticmethod
    def adjust_datetime(datetime_: dt.datetime) -> dt.datetime:
        """Adjust datetime to MOSMIX release frequency.

        This is required for MOSMIX-L that is only released very 6 hours (3, 9, 15, 21).
        Datetime is floored to closest release time e.g. if hour is 14, it will be rounded to 9

        """
        regular_date = dt.datetime.fromordinal(datetime_.date().toordinal()).replace(hour=3, tzinfo=datetime_.tzinfo)
        if regular_date > datetime_:
            regular_date -= dt.timedelta(hours=6)
        delta_hours = (datetime_.hour - regular_date.hour) % 6
        return datetime_ - dt.timedelta(hours=delta_hours)

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect MOSMIX data for a given station and parameter or dataset."""
        # Shift issue date to 3, 9, 15, 21 hour format
        issue = self.sr.stations.issue
        if issue is not DwdForecastDate.LATEST and parameter_or_dataset == DwdMosmixMetadata.hourly.large:
            issue = self.adjust_datetime(issue)
        df = self.read_mosmix(station_id=station_id, dataset=parameter_or_dataset, date=issue)
        if df is None or df.is_empty():
            return pl.DataFrame()
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
            pl.col("date").str.to_datetime(format="%Y-%m-%dT%H:%M:%S.%fZ", time_zone="UTC"),
            "value",
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )

    def read_mosmix(self, station_id: str, dataset: DatasetModel, date: dt.datetime | DwdForecastDate) -> pl.DataFrame:
        """Read MOSMIX data from the DWD server."""
        if dataset == DwdMosmixMetadata.hourly.small:
            return self.read_mosmix_small(station_id, date)
        if dataset == DwdMosmixMetadata.hourly.large:
            return self.read_mosmix_large(station_id, date)
        msg = f"Dataset {dataset} not supported"
        raise KeyError(msg)

    def read_mosmix_small(self, station_id: str, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Read single MOSMIX-S file for all stations or multiple files for single stations."""
        url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_S_PATH)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def read_mosmix_large(
        self,
        station_id: str,
        date: DwdForecastDate | dt.datetime,
    ) -> pl.DataFrame:
        """Read single MOSMIX-L file for all stations or multiple files for single stations."""
        if self.sr.stations.station_group == DwdMosmixStationGroup.ALL_STATIONS:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_PATH)
        else:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_SINGLE_PATH).format(station_id=station_id)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def get_url_for_date(self, url: str, date: dt.datetime | DwdForecastDate) -> str:
        """Get the URL for a given date."""
        urls = list_remote_files_fsspec(url, self.sr.stations.settings, CacheExpiry.NO_CACHE)

        if date == DwdForecastDate.LATEST:
            try:
                return next(filter(lambda url_: "LATEST" in url_.upper(), urls))
            except IndexError as e:
                msg = f"Unable to find LATEST file within {url}"
                raise IndexError(msg) from e

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
            msg = f"Unable to find {date} file within {url}"
            raise IndexError(msg)

        return df.get_column("url").item()


@dataclass
class DwdMosmixRequest(TimeseriesRequest):
    """Request MOSMIX data from the DWD server."""

    metadata = DwdMosmixMetadata
    _values = DwdMosmixValues
    # parameters
    issue: str | dt.datetime | DwdForecastDate = DwdForecastDate.LATEST
    station_group: DwdMosmixStationGroup = DwdMosmixStationGroup.SINGLE_STATIONS

    _url = "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg?view=nasPublication"

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

    def __post_init__(self) -> None:
        """Post-initialization of the DwdMosmixRequest class."""
        super().__post_init__()
        self.station_group = (
            parse_enumeration_from_template(self.station_group, DwdMosmixStationGroup)
            or DwdMosmixStationGroup.SINGLE_STATIONS
        )
        issue = self.issue
        with contextlib.suppress(InvalidEnumerationError):
            issue = parse_enumeration_from_template(issue, DwdForecastDate)
        if issue is not DwdForecastDate.LATEST:
            if isinstance(issue, str):
                issue = dt.datetime.fromisoformat(issue)
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour, tzinfo=issue.tzinfo)
        self.issue = issue

    def _all(self) -> pl.LazyFrame:
        """Read the MOSMIX station catalog from the DWD server and return a DataFrame."""
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
        column_specs = ((0, 5), (6, 9), (11, 30), (32, 38), (39, 46), (48, 56))
        df_raw = read_fwf_from_df(df_raw, column_specs)
        df_raw.columns = [
            "station_id",
            "icao_id",
            "name",
            "latitude",
            "longitude",
            "height",
        ]
        df_raw = df_raw.with_columns(
            pl.col("icao_id").replace("----", None),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("start_date"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("end_date"),
            pl.col("latitude").cast(float).map_batches(convert_dm_to_dd, return_dtype=pl.Float64),
            pl.col("longitude").cast(float).map_batches(convert_dm_to_dd, return_dtype=pl.Float64),
            pl.col("height").cast(int),
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
