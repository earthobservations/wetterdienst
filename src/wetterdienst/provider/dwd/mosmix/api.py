# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API for DWD MOSMIX data."""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.exceptions import (
    InvalidEnumerationError,
    InvalidTimeIntervalError,
    IssueNotFoundError,
    NoInternetError,
    ProductOutOfSeasonError,
    ProviderRateLimitError,
)
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.model.quality_flags import join_quality_flags, unpivot_with_raw
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import UPDATED, TimeseriesValues
from wetterdienst.provider.dwd.catalogue import MOSMIX_STATION_CATALOGUE_URL, read_mosmix_station_catalogue
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import list_remote_files_fsspec

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

DWD_MOSMIX_S_PATH = "weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/"
DWD_MOSMIX_L_PATH = "weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/"
DWD_MOSMIX_L_SINGLE_PATH = "weather/local_forecasts/mos/MOSMIX_L/single_stations/{station_id}/kml/"
DWD_MOSMIX_SNOW_PATH = "weather/local_forecasts/mos/MOSMIX-SNOW_S/all_stations/kml/"

#: Where the runs of each dataset are listed (`DwdMosmixRequest.available_issues`): MOSMIX-L from the directory of
#: one station, MOSMIX-S and MOSMIX-SNOW from the directory of all stations, which is every station's.
_ISSUE_PATHS = {
    "large": DWD_MOSMIX_L_SINGLE_PATH,
    "small": DWD_MOSMIX_S_PATH,
    "snow": DWD_MOSMIX_SNOW_PATH,
}

#: The 15 stations of the MOSMIX-SNOW run of 2026-11-14 19 UTC (the offline fixture,
#: `tests/provider/dwd/mosmix/MOSMIX-SNOW_S_2026111419_48.kmz`), all in the Bavarian Alps. Not what the stations of the
#: dataset are: those are the stations the newest run names (`DwdMosmixRequest._snow_station_ids`), so that a station
#: DWD adds is reachable. This is the answer only where no run can be read, which is out of season (the directory is
#: empty from May to October) or when it could not be listed or read. The MOSMIX catalogue lists 37 `Z9xx` stations and
#: cannot say which are the run's. `test_dwd_mosmix_snow` holds this list to the live run, so a change is noticed.
MOSMIX_SNOW_STATION_IDS = (
    "Z901",
    "Z905",
    "Z908",
    "Z912",
    "Z914",
    "Z916",
    "Z917",
    "Z919",
    "Z928",
    "Z932",
    "Z934",
    "Z936",
    "Z943",
    "Z944",
    "Z946",
)


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
# the alias of any product, for what a listing is counted as: MOSMIX-SNOW's is `aktuell`, which no run is read from
_ALIAS_FILE = re.compile(r"(?:LATEST|aktuell).*" + _FORECAST_FILE, re.IGNORECASE)


def _run_stamp_of(url: str) -> str | None:
    """Read the run a single URL is named for, or None -- `_run_stamp`'s rule, one name at a time."""
    match = re.search(rf"(?i)_(\d{{10}})(?:_[^.]*)?{_FORECAST_FILE}", url.rsplit("/", 1)[-1])
    return match.group(1) if match else None


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
    would match one run: a second lead time in one directory, `..._120.kmz` beside `..._240.kmz`.
    The callers sort and take the last, all of them, rather than the
    `IndexError` written for a run with no file. DWD publishes no such sidecar today, which is what
    makes this the kind of thing to settle while the rule is being written rather than after.
    """
    return urls.str.split("/").list.last().str.extract(rf"(?i)_(\d{{10}})(?:_[^.]*)?{_FORECAST_FILE}", 1)


def out_of_season_message(url: str, month: int) -> str:
    """Say why no MOSMIX-SNOW run is listed within `url`, in the month it is asked in.

    DWD publishes it from November to April only, and while there is snow: from May to October the season is the
    reason and says when to come back, from November to April the season is no reason and the message only says that
    no run is listed (and that DWD publishes it only while there is snow).
    """
    if 5 <= month <= 10:
        return (
            f"No MOSMIX-SNOW run is listed within {url}: DWD publishes it from November to April only, so there is "
            "no snow forecast to read until the winter."
        )
    return f"No MOSMIX-SNOW run is listed within {url}: DWD publishes it only while there is snow."


def _newest_run(urls: list[str]) -> str | None:
    """Give the newest run of a listing by the stamp its name carries, or None where it names no run."""
    runs = sorted((stamp, url) for url, stamp in ((u, _run_stamp_of(u)) for u in urls) if stamp is not None)
    return runs[-1][1] if runs else None


class DwdMosmixValues(TimeseriesValues[DatasetModel]):
    """Fetch weather mosmix data (KML/MOSMIX_S dataset)."""

    def __post_init__(self) -> None:
        """Post-initialization of the DwdMosmixValues class."""
        from typing import cast  # noqa: PLC0415

        super().__post_init__()
        # one parsed file per dataset of the request, so that small + large (+ snow) parse each file once and not
        # the other dataset's again at every station (GH-4093)
        self.kml = KMLReader(
            station_ids=self.sr.station_id.to_list(),
            settings=cast("Settings", self.sr.request.settings),
            keep_parsed=len(self.sr.request._requested_datasets),  # noqa: SLF001
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
        from typing import cast  # noqa: PLC0415

        stations = cast("DwdMosmixRequest", self.sr.request)
        # Shift issue date to 3, 9, 15, 21 hour format
        # After __post_init__, issue is always dt.datetime | DwdForecastDate (str is resolved)
        issue = cast("dt.datetime | DwdForecastDate", stations.issue)
        if issue is not DwdForecastDate.LATEST and parameter_or_dataset == DwdMosmixMetadata.hourly.large:
            issue = self.adjust_datetime(issue)
        df = self.read_mosmix(station_id=station_id, dataset=parameter_or_dataset, date=issue)
        if df is None or df.is_empty():
            return pl.DataFrame()
        df = unpivot_with_raw(df, index=["timestamp"])
        # the station, resolution and dataset are the core's to write (`shape_provider_frame`); the stamp is a text,
        # which the core rejects, so it is read here, as the UTC its `Z` says
        df = df.select(
            "parameter",
            pl.col("timestamp").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_zone="UTC"),
            "value",
            # the "-" the file writes for a missing value (GH-2759)
            join_quality_flags(None, raw=pl.col("raw")),
        )
        # a forecast is dated by its model run and not by the file it was published in: the `IssueTime` of the run read
        # (GH-2567 asks for the date of the update), for a run that has steps the answer keeps
        issued = self.kml.metadata.get("issue_time")
        return self._note_files_with_rows(
            df.with_columns(pl.lit(issued, dtype=pl.Datetime("us", "UTC")).alias(UPDATED)), parameter_or_dataset
        )

    def read_mosmix(self, station_id: str, dataset: DatasetModel, date: dt.datetime | DwdForecastDate) -> pl.DataFrame:
        """Read MOSMIX data from the DWD server."""
        if dataset == DwdMosmixMetadata.hourly.small:
            return self.read_mosmix_small(station_id, date)
        if dataset == DwdMosmixMetadata.hourly.large:
            return self.read_mosmix_large(station_id, date)
        if dataset == DwdMosmixMetadata.hourly.snow:
            return self.read_mosmix_snow(station_id, date)
        msg = f"Dataset {dataset} not supported"
        raise KeyError(msg)

    def read_mosmix_small(self, station_id: str, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Read single MOSMIX-S file for all stations or multiple files for single stations."""
        from typing import cast  # noqa: PLC0415

        url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_S_PATH)
        # MOSMIX-S publishes every station in one file, so an empty listing is never one station's
        # -- and `one_station_only=False` raises rather than answering `None`, which is why there
        # is no empty-frame branch here where `read_mosmix_large` has one
        file_url = cast("str", self.get_url_for_date(url, date, one_station_only=False))
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def read_mosmix_large(
        self,
        station_id: str,
        date: DwdForecastDate | dt.datetime,
    ) -> pl.DataFrame:
        """Read single MOSMIX-L file for all stations or multiple files for single stations."""
        from typing import cast  # noqa: PLC0415

        all_stations = cast("DwdMosmixRequest", self.sr.request).station_group == DwdMosmixStationGroup.ALL_STATIONS
        if all_stations:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_PATH)
        else:
            url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_L_SINGLE_PATH).format(station_id=station_id)
        file_url = self.get_url_for_date(url, date, one_station_only=not all_stations)
        if not file_url:
            return pl.DataFrame()
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def read_mosmix_snow(self, station_id: str, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Read single MOSMIX-SNOW-S file for all stations.

        The product is published in the cadence and the KML layout of MOSMIX-S, an hour's run of 15 stations being
        10 KB. DWD publishes it from November to April only, and the directory is empty in the other months.
        """
        from typing import cast  # noqa: PLC0415

        url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_SNOW_PATH)
        file_url = cast("str", self.get_url_for_date(url, date, one_station_only=False, seasonal=True))
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def get_url_for_date(
        self,
        url: str,
        date: dt.datetime | DwdForecastDate,
        *,
        one_station_only: bool,
        seasonal: bool = False,
    ) -> str | None:
        """Get the URL for a given date, or None where one station's directory names nothing.

        `None` rather than a raise, and only for a directory that names nothing, and only where
        that directory belongs to one station: DWD empties or retires a station's directory without
        warning, and a single one of those used to end a request for fifty stations, since nothing
        between here and `values.all()` catches. The other forty-nine have forecasts and are the
        answer the caller asked for. `dwd/dmo` has always made this split; mosmix raised because its
        return type said it must (GH-1949).

        The all-stations products have no such reading. One empty listing there is every station at
        once, so it cannot mean a station retired -- it means the listing failed or DWD moved the
        product, and `fs.find` swallowing an `OSError` makes those look identical to an empty
        directory. Answering `None` would turn a connection reset into an empty result for the
        whole request, exit 0 and HTTP 200. Those still raise.

        A directory that names files but no forecast still raises, being a statement about the
        product rather than about one station: it means what is published there is not what this
        knows how to read, which is worth a request ending over.

        A `seasonal` product (MOSMIX-SNOW, published from November to April) is empty for half the year,
        and an empty listing there is what the season says rather than a product that moved, so it is
        answered as what it is: an `IssueNotFoundError`, a 404 that names the season and the directory.
        It is no `StopIteration` and no cryptic `IndexError`, and an `IndexError` still, as before.
        """
        from typing import cast  # noqa: PLC0415

        urls = list_remote_files_fsspec(url, cast("Settings", self.sr.request.settings), CacheExpiry.NO_CACHE)
        if not urls:
            # answered before either branch reads the listing: an empty one fails differently in
            # each, and both in a way that names neither the directory nor what was looked for.
            #
            # A listing that failed raises -- a connection that could not be made as `NoInternetError`
            # (GH-2640) -- so what is empty here is a directory that holds nothing or that does not
            # exist, as the 404 of a station id that does not exist
            if seasonal:
                raise ProductOutOfSeasonError(out_of_season_message(url, dt.datetime.now(dt.UTC).month))
            message = f"No file listed within {url}; a missing directory lists as empty"
            if not one_station_only:
                raise IndexError(message)
            log.warning(message)
            return None

        if date == DwdForecastDate.LATEST:
            # the newest run the listing names, rather than the `LATEST` alias beside it. The two
            # are the same bytes -- the server answers one ETag, one content-length and one
            # Last-Modified for both, which is also what says the newest name is safe to read: one
            # inode under two names is a link made when the upload finished, not a name that
            # appears while 36 MB is still arriving. `dwd/road` and `dwd/dmo` have indexed the
            # named files on that basis for as long as they have existed -- but a run named
            # by its timestamp is that run for good, where the alias is a name whose content DWD
            # replaces every hour. Only the named one can be held, and `MOSMIX_S` is 36 MB
            # (GH-1945). `dwd/road` and `dwd/dmo` both index the named files and skip the alias.
            #
            # Newest by stamp, and by name after it -- `sorted` falls through to the URL where two
            # names carry one stamp, and `[-1]` takes the last of them. Every path here takes that
            # same end: the dated branch below, and the alias fallback, so asking for a run by name
            # and asking for the newest run cannot answer with different files. Only one file per
            # run exists today, `_run_stamp` matching `.kmz` alone, so either end is that file --
            # but a second lead time in one directory would make it matter
            runs = sorted((stamp, url_) for url_, stamp in ((u, _run_stamp_of(u)) for u in urls) if stamp is not None)
            if runs:
                return runs[-1][1]
            aliases = sorted(url_ for url_ in urls if _LATEST_FILE.search(url_.rsplit("/", 1)[-1]))
            if aliases:
                # the same end as every other path, so two alias forms -- a second lead time, which
                # `dwd/dmo` already publishes -- cannot answer differently from the run paths
                return aliases[-1]
            msg = f"Unable to find LATEST file within {url}"
            raise IndexError(msg)

        if date.tzinfo is not None:
            # converted only when it carries a zone, as in `dwd/dmo`: a naive date is UTC already,
            # which the run stamps compared below are, and `astimezone` would read it as the
            # host's local time (GH-2275)
            date = date.astimezone(dt.UTC).replace(tzinfo=None)

        df = pl.DataFrame({"url": urls}, orient="col")

        df = df.with_columns(_run_stamp(pl.col("url")).alias("timestamp"))

        df = df.filter(pl.col("timestamp").is_not_null())

        df = df.with_columns(
            pl.concat_str(
                [
                    pl.col("timestamp"),
                    pl.lit("00"),
                ]
            ).str.to_datetime("%Y%m%d%H%M"),
        )

        # the caller's only where the listing held forecasts, none of them of this issue: one holding
        # no forecast at all is the product's state, whichever issue was asked for
        listed = not df.is_empty()
        df = df.filter(pl.col("timestamp").eq(date))

        if df.is_empty():
            msg = f"Unable to find {date} file within {url}"
            if not listed:
                raise IndexError(msg)
            raise IssueNotFoundError(msg)

        # `.item()` raises on two rows rather than answering, and two rows are possible: a second
        # lead time in one directory (`..._120.kmz` beside `..._240.kmz`) carries one run stamp on
        # two names. Not `.kml` beside `.kmz`, which `_FORECAST_FILE` excludes a line above -- the
        # comment used to say that, and it was wrong.
        #
        # Last of the sort, which is what the `LATEST` branch takes, so asking for a run by name
        # and asking for the newest run answer with the same file rather than with different ones
        return cast("str", df.get_column("url").sort().last())


@dataclass
class DwdMosmixRequest(TimeseriesRequest):
    """Request MOSMIX data from the DWD server."""

    metadata = DwdMosmixMetadata
    _values = DwdMosmixValues
    # parameters
    issue: str | dt.datetime | DwdForecastDate = DwdForecastDate.LATEST
    station_group: DwdMosmixStationGroup = DwdMosmixStationGroup.SINGLE_STATIONS

    _url = MOSMIX_STATION_CATALOGUE_URL
    # per request, not per class: the stations of the newest MOSMIX-SNOW run, read once (`_snow_station_ids`)
    _snow_stations: set[str] | None = dataclasses.field(default=None, repr=False, compare=False)

    @classmethod
    def available_issues(cls, station_id: str, settings: Settings, dataset: str = "large") -> list[dt.datetime]:
        """Return datetimes for which the files of a MOSMIX product exist on DWD's server.

        `dataset` names the product, as the datasets of the network do: `large` (MOSMIX-L, the default), `small`
        (MOSMIX-S) or `snow` (MOSMIX-SNOW). MOSMIX-L is listed from the directory of the one station, which is what a
        request reads by default (`DwdMosmixStationGroup.SINGLE_STATIONS`). MOSMIX-S and MOSMIX-SNOW are published as
        one file of all stations per run, so their runs are the same whatever `station_id` is, as for SWSMOS.

        The list is sorted in ascending order and contains only unique UTC datetimes.
        The LATEST symlink is excluded.

        Raises:
            InvalidEnumerationError: `dataset` is none of the three.

        """
        if dataset not in _ISSUE_PATHS:
            msg = f"dataset must be one of {', '.join(_ISSUE_PATHS)} for DWD MOSMIX issues (got {dataset!r})"
            raise InvalidEnumerationError(msg)
        url = urljoin("https://opendata.dwd.de", _ISSUE_PATHS[dataset].format(station_id=station_id))
        urls = list_remote_files_fsspec(url, settings, CacheExpiry.NO_CACHE)
        if not urls:
            if dataset == "snow":
                # empty from May to October, which is the season and no product that moved
                log.warning(out_of_season_message(url, dt.datetime.now(dt.UTC).month))
                return []
            # a directory that exists and holds nothing has no issues to name, which is an answer
            # rather than the `invalid series dtype: expected String, got null` an empty frame used
            # to raise here. Reached by a station whose directory DWD has emptied or retired, and
            # by a path that no longer exists, which `fs.find` answers with no entries.
            #
            # Warned about rather than simply answered, because a path that no longer exists lists as
            # empty too, as does the 404 of a station id that does not exist. A listing that failed
            # is not that: it raises, and offline it raises `NoInternetError` (GH-2640).
            log.warning(f"No MOSMIX run listed within {url}; a missing directory lists as empty")
            return []
        df = pl.DataFrame({"url": urls}, orient="col")
        df = df.with_columns(_run_stamp(pl.col("url")).alias("timestamp"))
        df = df.filter(pl.col("timestamp").is_not_null())
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
            # MOSMIX-SNOW names its alias `..._aktuell_48.kmz`, MOSMIX-S and -L `..._LATEST_...`
            aliases = sum(1 for listed in urls if _ALIAS_FILE.search(listed.rsplit("/", 1)[-1]))
            log.warning(
                f"No dated run listed within {url} ({len(urls)} entries, {aliases} of them the LATEST alias)",
            )
            return []
        df = df.with_columns(
            pl.concat_str([pl.col("timestamp"), pl.lit("00")])
            .str.to_datetime("%Y%m%d%H%M")
            .dt.replace_time_zone("UTC"),
        )
        return df.get_column("timestamp").unique().sort().to_list()

    def __post_init__(self) -> None:
        """Post-initialization of the DwdMosmixRequest class."""
        super().__post_init__()
        self.station_group = (
            parse_enumeration_from_template(self.station_group, DwdMosmixStationGroup)
            or DwdMosmixStationGroup.SINGLE_STATIONS
        )
        issue = self.issue
        # a datetime names no member of the enumeration, so only a string or a member is looked up
        if not isinstance(issue, dt.datetime):
            with contextlib.suppress(InvalidEnumerationError):
                issue = parse_enumeration_from_template(issue, DwdForecastDate)
        if issue is not DwdForecastDate.LATEST:
            if isinstance(issue, str):
                try:
                    issue = dt.datetime.fromisoformat(issue)
                except ValueError as e:
                    raise InvalidTimeIntervalError(str(e)) from e
            # in UTC before it is floored, as `dwd/dmo` does: DWD stamps its runs in UTC. A naive
            # issue kept naive was read as the server's local time by `get_url_for_date`'s
            # `astimezone`, and one with an offset was floored in its own wall-clock hours -- to
            # 08:30 UTC for 14:30+05:30, and for MOSMIX-L to 07:00 UTC for 11:00+02:00 -- each a run
            # DWD never published (GH-2275)
            issue = issue.astimezone(ZoneInfo("UTC")) if issue.tzinfo else issue.replace(tzinfo=ZoneInfo("UTC"))
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour, tzinfo=ZoneInfo("UTC"))
        self.issue = issue

    def _narrowed_by(self, dataset: DatasetModel) -> list[tuple[str, str | None]]:
        """Add what the request asks of the run to what it is held to (`parameter-without-rows`)."""
        narrowed = super()._narrowed_by(dataset)
        if isinstance(self.issue, dt.datetime):
            narrowed.append((f"the run issued {self.issue:%Y-%m-%d %H} UTC", None))
        return narrowed

    def _snow_station_ids(self, catalogue_ids: list[str]) -> set[str]:
        """Give the stations MOSMIX-SNOW forecasts for: those the newest run names that the catalogue lists.

        The run is 10 KB, read once per request (the listing for five minutes, a named run for twelve hours, as every
        MOSMIX run is held). Where no run is listed, as from May to October, or it could not be listed or read, the 15
        stations of `MOSMIX_SNOW_STATION_IDS` are the answer, with a warning for a failure: the dataset has stations
        out of season, and a request for values then says why it has no run. A station the run names that the
        catalogue does not list has no position and is none of the stations.
        """
        from typing import cast  # noqa: PLC0415

        if self._snow_stations is not None:
            return self._snow_stations
        settings = cast("Settings", self.settings)
        url = urljoin("https://opendata.dwd.de", DWD_MOSMIX_SNOW_PATH)
        named: set[str] = set()
        try:
            newest = _newest_run(list_remote_files_fsspec(url, settings, CacheExpiry.FILEINDEX))
            if newest is not None:
                reader = KMLReader(station_ids=catalogue_ids, settings=settings)
                reader.read(newest)
                named = set(reader.data)
        except (NoInternetError, ProviderRateLimitError):
            raise
        except Exception as ex:  # noqa: BLE001
            log.warning(
                f"Unable to read the stations the newest MOSMIX-SNOW run names within {url} ({ex!r}); "
                "listing the 15 stations known from the run of 2026-11-14"
            )
        self._snow_stations = named or set(MOSMIX_SNOW_STATION_IDS)
        return self._snow_stations

    def _all(self) -> pl.LazyFrame:
        """Read the MOSMIX station catalog from the DWD server and return a DataFrame."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        catalogue = read_mosmix_station_catalogue(settings, self._url)
        if catalogue.is_empty() or DwdMosmixMetadata.hourly.snow.name not in {
            name for _, name in self._requested_datasets
        }:
            # one catalogue for every dataset: the core copies it over the request's datasets
            return catalogue.lazy()
        # MOSMIX-SNOW forecasts for a few of the stations, which the catalogue does not say (`_snow_station_ids`), so
        # its stations are those and not the 5,000 of the catalogue that can only answer with no rows. A frame per
        # dataset, as a provider whose stations differ per dataset hands them (`TimeseriesRequest._all`)
        snow_stations = self._snow_station_ids(catalogue.get_column("station_id").to_list())
        frames = [
            (catalogue.filter(pl.col("station_id").is_in(snow_stations)) if name == "snow" else catalogue).with_columns(
                pl.lit(resolution, pl.String).alias("resolution"), pl.lit(name, pl.String).alias("dataset")
            )
            for resolution, name in self._requested_datasets
        ]
        return pl.concat(frames).lazy()
