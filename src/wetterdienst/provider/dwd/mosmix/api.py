# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API for DWD MOSMIX data."""

from __future__ import annotations

import contextlib
import datetime as dt
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

import polars as pl

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.catalogue import MOSMIX_STATION_CATALOGUE_URL, read_mosmix_station_catalogue
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import list_remote_files_fsspec

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.settings import Settings

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


# what a forecast is called. `.kmz` and not `.km[lz]`, though the directory is named `kml/` and an
# uncompressed forecast would be the plainer thing to publish in it: `KMLReader.fetch` hands every
# download to `ZipFileSystem`, which raises `BadZipFile: File is not a zip file` on a plain KML. So
# accepting `.kml` here would resolve to a file the reader cannot open -- and where DWD published
# both forms during a migration, prefer the one that fails. Widening this means teaching the reader
# first; until then the rule matches what can actually be read
_FORECAST_FILE = r"\.kmz$"
_LATEST_FILE = re.compile(r"LATEST.*" + _FORECAST_FILE, re.IGNORECASE)


def _run_stamp(urls: pl.Expr) -> pl.Expr:
    """Read the run a forecast file is named for, or null where the name does not carry one.

    The name says the run in three layouts -- ``MOSMIX_L_2026092203_01001.kmz`` for one station,
    ``MOSMIX_L_2026092203.kmz`` for all of them, ``MOSMIX_S_2026092205_240.kmz`` for S -- and taking
    the third ``_``-separated part read the first as a run, the second as ``2026092203.kmz`` with
    the extension still on it, and the ``LATEST`` alias of the second as ``LATEST.kmz``, which the
    filter written to drop ``LATEST`` does not match. Every row then met `conversion from str to
    datetime failed`, so the all-stations layout could not be asked for a run at all.

    Reading the ten digits DWD stamps a run with covers all three, and says null for a name that
    does not carry one: the ``LATEST`` alias of any layout, a README. Case-insensitive, as the
    alias rule beside it is -- DWD is consistently lowercase, and two rules that claim to be one
    rule should not differ in a dimension neither of them cares about.

    The forecast's own extension is part of the rule rather than "a name with ten digits in it
    somewhere", so that a companion file *carrying* the run stamp is dropped too. A
    ``MOSMIX_L_2026092203_01001.kmz.sha256`` beside its forecast would otherwise survive, two rows
    would match one run. Two forms of the same forecast do that legitimately -- `.kml` beside
    `.kmz` while DWD migrates -- so the caller sorts and takes the first rather than the
    `IndexError` written for a run with no file. DWD publishes no such sidecar today, which is what
    makes this the kind of thing to settle while the rule is being written rather than after.
    """
    return urls.str.split("/").list.last().str.extract(rf"(?i)_(\d{{10}})(?:_[^.]*)?{_FORECAST_FILE}", 1)


class DwdMosmixValues(TimeseriesValues):
    """Fetch weather mosmix data (KML/MOSMIX_S dataset)."""

    def __post_init__(self) -> None:
        """Post-initialization of the DwdMosmixValues class."""
        from typing import cast  # noqa: PLC0415

        super().__post_init__()
        self.kml = KMLReader(
            station_ids=self.sr.station_id.to_list(),
            settings=cast("Settings", self.sr.stations.settings),
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

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect MOSMIX data for a given station and parameter or dataset."""
        from typing import cast  # noqa: PLC0415

        stations = cast("DwdMosmixRequest", self.sr.stations)
        # Shift issue date to 3, 9, 15, 21 hour format
        # After __post_init__, issue is always dt.datetime | DwdForecastDate (str is resolved)
        issue = cast("dt.datetime | DwdForecastDate", stations.issue)
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
            pl.col("date").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_zone="UTC"),
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
        from typing import cast  # noqa: PLC0415

        if cast("DwdMosmixRequest", self.sr.stations).station_group == DwdMosmixStationGroup.ALL_STATIONS:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_PATH)
        else:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_SINGLE_PATH).format(station_id=station_id)
        file_url = self.get_url_for_date(url, date)
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def get_url_for_date(self, url: str, date: dt.datetime | DwdForecastDate) -> str:
        """Get the URL for a given date."""
        from typing import cast  # noqa: PLC0415

        urls = list_remote_files_fsspec(url, cast("Settings", self.sr.stations.settings), CacheExpiry.NO_CACHE)
        if not urls:
            # answered before either branch reads the listing: an empty one fails differently in
            # each, and both in a way that names neither the directory nor what was looked for.
            #
            # And said with the doubt it deserves: `fs.find` walks with `on_error="omit"`, which
            # swallows `OSError` -- aiohttp's `ClientOSError` is one -- so a listing that could not
            # be read arrives looking exactly like a directory that holds nothing, as does the 404
            # of a station id that does not exist
            msg = f"Unable to find any file within {url}; a listing that failed looks the same as one that is empty"
            raise IndexError(msg)

        if date == DwdForecastDate.LATEST:
            # asked for a default rather than guarded against the exception `next` does not raise:
            # a `kml/` directory holding files but no `LATEST` among them is an ordinary outcome
            # held to the same rule as a dated run below, where a bare `"LATEST" in url` would
            # answer with a checksum published beside the alias -- and would do it on the default
            # path, the one a caller reaches without asking for anything. Today it is the listing's
            # sort order that keeps `.kmz` ahead of `.kmz.sha256`, which is luck rather than a rule
            # sorted rather than first-found: widening what counts as a forecast to `.kml` as
            # well as `.kmz` means a run can be published in both forms at once, which is what a
            # migration looks like while it is happening -- and answering with whichever the
            # listing happened to return first would make the answer depend on the listing's order
            aliases = sorted(url_ for url_ in urls if _LATEST_FILE.search(url_.rsplit("/", 1)[-1]))
            url_latest = aliases[0] if aliases else None
            if url_latest is None:
                msg = f"Unable to find LATEST file within {url}"
                raise IndexError(msg)
            return url_latest

        date = date.astimezone(dt.timezone.utc).replace(tzinfo=None)

        df = pl.DataFrame({"url": urls}, orient="col")

        df = df.with_columns(_run_stamp(pl.col("url")).alias("date"))

        df = df.filter(pl.col("date").is_not_null())

        df = df.with_columns(
            pl.concat_str(
                [
                    pl.col("date"),
                    pl.lit("00"),
                ]
            ).str.to_datetime("%Y%m%d%H%M"),
        )

        df = df.filter(pl.col("date").eq(date))

        if df.is_empty():
            msg = f"Unable to find {date} file within {url}"
            raise IndexError(msg)

        # `.item()` raises where a run matched twice, which the same widening allows: a forecast
        # published as `.kml` beside its `.kmz` carries one run stamp on two names. Sorted and
        # taken first, so two forms of one run answer with one of them, deterministically, rather
        # than with `can only call '.item()' if the Series is of length 1`
        return cast("str", df.get_column("url").sort().first())


@dataclass
class DwdMosmixRequest(TimeseriesRequest):
    """Request MOSMIX data from the DWD server."""

    metadata = DwdMosmixMetadata
    _values = DwdMosmixValues
    # parameters
    issue: str | dt.datetime | DwdForecastDate = DwdForecastDate.LATEST
    station_group: DwdMosmixStationGroup = DwdMosmixStationGroup.SINGLE_STATIONS

    _url = MOSMIX_STATION_CATALOGUE_URL

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

    @classmethod
    def available_issues(cls, station_id: str, settings: Settings) -> list[dt.datetime]:
        """Return datetimes for which MOSMIX L single-station files exist on DWD's server.

        The list is sorted in ascending order and contains only unique UTC datetimes.
        Only MOSMIX_L single-station files are considered; the LATEST symlink is excluded.
        """
        url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_SINGLE_PATH.format(station_id=station_id))
        urls = list_remote_files_fsspec(url, settings, CacheExpiry.NO_CACHE)
        if not urls:
            # a directory that exists and holds nothing has no issues to name, which is an answer
            # rather than the `invalid series dtype: expected String, got null` an empty frame used
            # to raise here. Reached by a station whose directory DWD has emptied or retired, and
            # by a path that no longer exists, which `fs.find` answers with no entries.
            #
            # Warned about rather than simply answered, because a listing that *failed* looks the
            # same from here: `fs.find` walks with `on_error="omit"`, which swallows `OSError`, and
            # aiohttp's `ClientOSError` is one -- so a connection reset mid-listing is swallowed
            # inside fsspec, never reaches the retry around this call, and arrives as an empty
            # directory would -- as does the 404 of a station id that does not exist. An
            # unremarked `[]` would make either a fact about the station.
            #
            # Telling them apart here, with an `fs.exists` probe before answering, has been
            # proposed three times in review and is written up against `on_error="raise"` on
            # GH-1947: the probe narrows the window rather than closing it, and can fail the same
            # way the listing did, while the listing reporting what it swallowed fixes every
            # provider at once
            log.warning(f"No MOSMIX run listed within {url}; a listing that failed looks the same as one that is empty")
            return []
        df = pl.DataFrame({"url": urls}, orient="col")
        df = df.with_columns(_run_stamp(pl.col("url")).alias("date"))
        df = df.filter(pl.col("date").is_not_null())
        if df.is_empty():
            # the directory named things and none of them is a dated run, answered with `[]` that
            # reads as "this station publishes no runs" exactly as the empty listing did.
            #
            # Counted rather than diagnosed. An alias is a forecast and only a dated run is what
            # this lists, so a directory pruned back to its alias is not the renaming this warning
            # otherwise means -- but "every entry is an alias" stops being true the moment a
            # checksum sits beside it, and naming the wrong cause is worse than naming none. The
            # counts say which shape it is without guessing why
            #
            # A warning and not an `info` because a directory holding sixteen dated runs today and
            # only its alias tomorrow is a retention change worth seeing -- not because `info`
            # would go unheard, which it would not: `setup_logging` runs `basicConfig(level=INFO)`
            # for both the CLI and the REST API, so `info` reaches exactly those two
            aliases = sum(1 for listed in urls if _LATEST_FILE.search(listed.rsplit("/", 1)[-1]))
            log.warning(
                f"No dated run listed within {url} ({len(urls)} entries, {aliases} of them the LATEST alias)",
            )
            return []
        df = df.with_columns(
            pl.concat_str([pl.col("date"), pl.lit("00")]).str.to_datetime("%Y%m%d%H%M").dt.replace_time_zone("UTC"),
        )
        return df.get_column("date").unique().sort().to_list()

    def __post_init__(self) -> None:
        """Post-initialization of the DwdMosmixRequest class."""
        super().__post_init__()
        self.station_group = (
            parse_enumeration_from_template(self.station_group, DwdMosmixStationGroup)
            or DwdMosmixStationGroup.SINGLE_STATIONS
        )
        issue = self.issue
        with contextlib.suppress(InvalidEnumerationError):
            issue = parse_enumeration_from_template(issue, DwdForecastDate)  # ty: ignore[no-matching-overload]
        if issue is not DwdForecastDate.LATEST:
            if isinstance(issue, str):
                issue = dt.datetime.fromisoformat(issue)
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour, tzinfo=issue.tzinfo)
        self.issue = issue

    def _all(self) -> pl.LazyFrame:
        """Read the MOSMIX station catalog from the DWD server and return a DataFrame."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        df_raw = read_mosmix_station_catalogue(settings, self._url)
        if df_raw.is_empty():
            return pl.LazyFrame()
        df_raw = df_raw.with_columns(
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("start_date"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("end_date"),
            pl.lit(None, pl.String).alias("state"),
        )
        # combinations of resolution and dataset
        from wetterdienst.model.metadata import ParameterModel  # noqa: PLC0415

        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
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
