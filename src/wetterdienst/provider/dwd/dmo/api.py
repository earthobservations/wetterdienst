# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD DMO API."""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import logging
import re
from dataclasses import dataclass
from enum import Enum
from io import StringIO
from typing import TYPE_CHECKING, ClassVar, Literal
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import polars as pl
from lxml.etree import iterparse

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.dmo.metadata import DwdDmoMetadata
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import convert_dm_to_dd
from wetterdienst.util.network import download_file, list_remote_directory_fsspec, list_remote_files_fsspec
from wetterdienst.util.polars_util import read_fwf_from_df

if TYPE_CHECKING:
    from typing import BinaryIO

    from wetterdienst.settings import Settings

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


def _run_stamp(urls: pl.Expr, lead_time: DwdDmoLeadTime | None = None) -> pl.Expr:
    """Read the ``DDHHMM`` a DMO run is stamped with, or null where the name carries none.

    A run is published as ``ptp_gdmog_<station>_<lead>_<n>_<DDHHMM>.kmz``, and every part of that
    was read by position or by substring before, each wrongly:

    - the lead time was matched as a bare ``"78"`` or ``"168"`` anywhere in the URL, which the
      station id also satisfies. 187 of 5811 ids contain ``78``, so a request for the short lead
      time kept the long one's files too, two rows carried one run, and `.item()` raised.
    - the stamp was the last ``_``-separated part with four characters taken off the end, so a
      ``README`` reached the parse and raised `conversion from str to i64 failed`, and a
      ``..._210000.txt`` sidecar strips to a valid ``210000`` and could be answered with -- handing
      the reader a file that is not a forecast.

    Named as a whole, both stop being possible: the lead time is a field rather than a substring,
    and a name that is not a forecast carries no stamp. Asked without a lead time, as the listing
    of issues is, it reads either.
    """
    leads = f"{lead_time.value:03d}" if lead_time else "|".join(f"{lt.value:03d}" for lt in DwdDmoLeadTime)
    return urls.str.split("/").list.last().str.extract(rf"_(?:{leads})_\d+_(\d{{6}})\.kmz$", 1)


def add_date_from_filename(df: pl.DataFrame, current_date: dt.datetime) -> pl.DataFrame:
    """Add date from filename."""
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
    days_difference = int(df.get_column("day").cast(pl.Int8).max() or 0) - int(  # ty: ignore[invalid-argument-type]
        df.get_column("day").cast(pl.Int8).min() or 0  # ty: ignore[invalid-argument-type]
    )
    if days_difference > 20:
        df = df.with_columns(
            pl.when(pl.col("day") > 25).then(month - 1 if month > 1 else 12).otherwise(month).alias("month"),
        )
    else:
        df = df.with_columns(pl.lit(month).alias("month"))
    months_difference = int(df.get_column("month").max() or 0) - int(df.get_column("month").min() or 0)  # ty: ignore[invalid-argument-type]
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


# the station id in a single-station path, so one product's empty directory is reported once
# however many stations were asked for
_SINGLE_STATION_PATH = re.compile(r"/single_stations/[^/]+/")


# the spelling upstream publishes each product under, which is not the spelling the metadata names
# it by: `icon_eu` is served from `icon-eu`. Total rather than a pass-through with one special case,
# so a third product cannot inherit the metadata spelling by default and 404 far from the cause --
# `test_every_dmo_product_has_a_directory_upstream` fails the moment one is added without a decision
_DMO_PRODUCT_DIRS = {"icon": "icon", "icon_eu": "icon-eu"}


# distinguishes "not looked up yet" from a lookup that answered None
_UNREAD = object()


_PLACEMARK_COLUMNS = {
    "station_id": pl.String,
    "icao_id": pl.String,
    "name": pl.String,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "height": pl.String,
}


def _placemark_metadata(handle: BinaryIO) -> pl.DataFrame:
    """Read station id, name and position from the placemarks of one DMO run.

    The run is the only place some stations are described at all: 135 of the stations `icon`
    forecasts for are absent from `dmo_stationsliste_txt.asc`, 72 of them with ids the catalogue
    never carries (`Y0330`, `G431`, `O015`). A placemark gives an id, a name and a position in
    decimal degrees -- better formed than the catalogue, which needs `_dm_degrees` -- but no ICAO id,
    which is why this fills the catalogue's gaps rather than replacing it (GH-1966).
    """
    rows = []
    for _, element in iterparse(handle, events=("end",), resolve_entities=False):
        if not element.tag.endswith("}Placemark"):
            continue
        station_id = name = coordinates = None
        for child in element:
            if child.tag.endswith("}name"):
                station_id = child.text
            elif child.tag.endswith("}description"):
                name = child.text
            elif child.tag.endswith("}Point"):
                point = next((c for c in child if c.tag.endswith("}coordinates")), None)
                coordinates = point.text if point is not None else None
        element.clear()
        if not station_id or not coordinates:
            continue
        longitude, latitude, height = ([*coordinates.strip().split(","), "", ""])[:3]
        rows.append(
            {
                "station_id": station_id,
                "icao_id": None,
                "name": (name or "").strip() or None,
                "latitude": float(latitude),
                "longitude": float(longitude),
                # left a string, as the catalogue's is: the base request casts it
                "height": height or None,
            },
        )
    return pl.DataFrame(rows, schema=_PLACEMARK_COLUMNS, orient="row")


def _dm_degrees(column: str) -> pl.Expr:
    """Read one `dmo_stationsliste_txt.asc` position column, which is degrees and minutes.

    `70.56` is 70 degrees 56 minutes. The whole file is one format, `{degrees}.{minutes:2d}`, and it
    is the degrees rendering empty at zero that makes the rest look irregular -- the minutes are
    right-aligned in two columns, so a lone digit arrives behind a space and a negative one arrives
    behind its own minus sign:

    ===============  ==============  ====================
    as written       means           DWD's own KMZ says
    ===============  ==============  ====================
    ``70.56``        70 deg 56'      70.9333
    ``. 5`` (sic)    0 deg 05'       0.0800
    ``.19``          0 deg 19'       0.3167
    ``.-6``          -0 deg 06'      -0.1000
    ===============  ==============  ====================

    The space is why the spaces come out before the rules below are applied, and it is real: all 14
    one-digit rows are written `. 5` rather than `.5`.

    Read as plain decimals these go wrong two ways. `.5` is 0 deg 50' -- 0.83 rather than 0.08, a
    station put 84 km from where DWD says it is, with nothing raised. `.-6` does raise, with
    `conversion from str to f64 failed` naming neither the column nor the station. Of the file's
    11 622 position fields, 77 carry no degrees and 21 of those need repairing: 14 written with one
    minute digit, 11 of which land 50 to 150 km out while 3 are a harmless zero, and 7 carrying the
    sign on the minutes, which is what the hardcoded station patches were for.

    Normalised to `[-]0.MM` first, so both shapes reach the cast as the decimal the file meant. The
    MOSMIX catalogue is the same format read by the same conversion and has no such row -- every one
    of its 11 298 fields carries its degrees -- so this belongs here rather than in the shared reader.

    What this cannot reach: a degreeless field whose sign is missing rather than misplaced. The file
    writes one, `P0563` (London Luton), as `.22` where DWD's own placemark says -0.37, and nothing in
    the field distinguishes that from the 39 degreeless fields that really are positive. It is read
    as written, 82 km east of Luton, exactly as it was before this function existed.
    """
    return (
        pl.col(column)
        .str.replace_all(" ", "")
        # the sign belongs to the value, not to its minutes: `.-6` -> `-.6`
        .str.replace(r"^\.-(\d{1,2})$", "-.${1}")
        # and the minutes are two digits, so a lone one is a leading zero away from being read as ten
        # times itself: `-.6` -> `-0.06`, while `.19` -> `0.19` is the same number written out
        .str.replace(r"^(-?)\.(\d)$", "${1}0.0${2}")
        .str.replace(r"^(-?)\.(\d\d)$", "${1}0.${2}")
        .cast(float)
        .map_batches(convert_dm_to_dd, return_dtype=pl.Float64)
    )


def _dmo_product_dir(dataset_name_original: str) -> str:
    """Name the directory one DMO product publishes under, in the spelling upstream uses for it."""
    try:
        dataset_name = _DMO_PRODUCT_DIRS[dataset_name_original]
    except KeyError:
        msg = (
            f"No DMO product directory is known for {dataset_name_original!r}; "
            f"known products are {sorted(_DMO_PRODUCT_DIRS)}"
        )
        raise ValueError(msg) from None
    return f"weather/local_forecasts/dmo/{dataset_name}"


def _dmo_station_dir(dataset_name_original: str) -> str:
    """Name the directory holding one subdirectory per station a DMO product forecasts for.

    Upstream publishes no station list per product -- `dmo_stationsliste_txt.asc` is one list for
    both -- but it publishes this, and for both products the names in here are exactly the
    placemarks that product's `all_stations` run carries (measured 2026-09-24: 5757 for `icon`,
    3688 for `icon_eu`, both sets identical to the placemarks). So it answers which stations a
    product covers for the cost of one directory listing rather than a 20 MB parse.
    """
    return f"{_dmo_product_dir(dataset_name_original)}/{DwdDmoStationGroup.SINGLE_STATIONS.value}"


def _dmo_kmz_path(dataset_name_original: str, station_group: DwdDmoStationGroup, station_id: str | None) -> str:
    """Name the directory one product publishes its runs in.

    One function, because `available_issues` and `get_url_for_date` have to read the *same*
    directory: they were built separately, so the command that says which issues exist listed
    `icon/single_stations/<id>/kmz/` whatever the request would go on to read, and named issues the
    values path then rejected (GH-1956).
    """
    path = f"{_dmo_product_dir(dataset_name_original)}/{station_group.value}"
    if station_group is DwdDmoStationGroup.ALL_STATIONS:
        return f"{path}/kmz"
    return f"{path}/{station_id}/kmz/"


class DwdDmoValues(TimeseriesValues):
    """Fetch DWD DMO data."""

    def __post_init__(self) -> None:
        """Post-initialize the DwdDmoValues class."""
        from typing import cast  # noqa: PLC0415

        super().__post_init__()
        self.kml = KMLReader(
            station_ids=self.sr.station_id.to_list(),
            settings=cast("Settings", self.sr.stations.settings),
        )
        # directories already reported as naming nothing, so one empty listing is one line rather
        # than one per station of an `all_stations` request
        self._listings_warned_about: set[str] = set()

    def get_dwd_dmo_path(self, dataset: DatasetModel, station_id: str | None = None) -> str:
        """Get DWD DMO path."""
        from typing import cast  # noqa: PLC0415

        stations = cast("DwdDmoRequest", self.sr.stations)
        return _dmo_kmz_path(
            dataset.name_original,
            cast("DwdDmoStationGroup", stations.station_group),
            station_id,
        )

    @property
    def metadata(self) -> pl.DataFrame:
        """Get metadata DataFrame for DMO."""
        return self.sr.df

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        from typing import cast  # noqa: PLC0415

        issue = cast("dt.datetime | DwdForecastDate", cast("DwdDmoRequest", self.sr.stations).issue)
        df = self.read_dmo(station_id=station_id, dataset=parameter_or_dataset, date=issue)
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
        from typing import cast  # noqa: PLC0415

        if cast("DwdDmoRequest", self.sr.stations).station_group == DwdDmoStationGroup.ALL_STATIONS:
            dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon_eu)
        else:
            dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon_eu, station_id=station_id)
        url = urljoin("https://opendata.dwd.de", dmo_path)
        file_url = self.get_url_for_date(url, date)
        if not file_url:
            return pl.DataFrame()
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def read_icon(self, station_id: str, date: DwdForecastDate | dt.datetime) -> pl.DataFrame:
        """Read either large icon file with all stations or small single station file."""
        from typing import cast  # noqa: PLC0415

        if cast("DwdDmoRequest", self.sr.stations).station_group == DwdDmoStationGroup.ALL_STATIONS:
            dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon)
        else:
            dmo_path = self.get_dwd_dmo_path(DwdDmoMetadata.hourly.icon, station_id=station_id)
        url = urljoin("https://opendata.dwd.de", dmo_path)
        file_url = self.get_url_for_date(url, date)
        if not file_url:
            return pl.DataFrame()
        self.kml.read(file_url)
        return self.kml.get_station_forecast(station_id)

    def get_url_for_date(self, url: str, date: dt.datetime | DwdForecastDate) -> str | None:
        """Get URL for a specific date."""
        from typing import cast  # noqa: PLC0415

        stations = cast("DwdDmoRequest", self.sr.stations)
        lead_time = cast("DwdDmoLeadTime", stations.lead_time)
        urls = list_remote_files_fsspec(url, cast("Settings", stations.settings), CacheExpiry.NO_CACHE)
        if not urls:
            # said here as well as in `available_issues`, and it matters more here: `read_icon` and
            # `read_icon_eu` turn this `None` into an empty frame, which merges into the result as
            # "this station has no forecast" with no warning, no error and no exit code. The same
            # swallowed walk and the same 404 reach both
            # once per product, not once per station. `all_stations` asks this for every station
            # in the request against one URL, and `single_stations` -- the default -- asks against
            # a URL carrying the station id, so keying on the URL itself deduplicated only half of
            # it. A request for `icon_eu` used to print one line per station of the catalogue,
            # because the catalogue was the one shared by both products and 2255 of its stations
            # have no `icon_eu` directory to list; narrowing it to the product (GH-1964) leaves
            # this for the stations a product drops between two listings
            key = _SINGLE_STATION_PATH.sub("/single_stations/<station>/", url)
            if key not in self._listings_warned_about:
                self._listings_warned_about.add(key)
                log.warning(
                    f"No DMO run listed within {url}; a listing that failed looks the same as one that is empty",
                )
            return None
        df = pl.DataFrame({"url": urls}, orient="col")
        df = df.with_columns(_run_stamp(pl.col("url"), lead_time).alias("date_str"))
        df = df.filter(pl.col("date_str").is_not_null())
        if df.is_empty():
            # the directory named things, none of them a forecast for this lead time. Reported as
            # itself rather than as `Unable to find None file within ...`, which is what the
            # `LATEST` branch below produced once its filter had emptied the frame
            msg = f"Unable to find a {lead_time.value} h forecast within {url}"
            raise IndexError(msg)
        df = add_date_from_filename(df, dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None))
        if date == DwdForecastDate.LATEST:
            date = cast("dt.datetime", df.get_column("date").max())
        elif date.tzinfo is not None:
            # `available_issues` hands these out tz-aware, and the column built above is naive, so
            # comparing them raised `could not evaluate comparison between series 'date' of dtype:
            # Datetime('us') and ... Datetime('us', 'UTC')` -- the command that says which issues
            # exist printing them in a form the next command could not accept. Converted only when
            # it carries a zone: a naive datetime is already what this compares in, and
            # `astimezone` would read it as local time
            date = date.astimezone(dt.timezone.utc).replace(tzinfo=None)
        df = df.filter(pl.col("date").eq(date))
        if df.is_empty():
            msg = f"Unable to find {date} file within {url}"
            raise IndexError(msg)
        # sorted rather than `.item()`, which raises on two rows instead of answering. Under the
        # lead-anchored rule above, the only field left varying is `n` -- fixed per lead time,
        # `078` with `1` and `168` with `3` -- so two names cannot carry one stamp today and this
        # is a deterministic tiebreak for a case that cannot currently arise, not a policy about
        # which of two files to prefer
        return cast("str", df.get_column("url").sort().first())


@dataclass
class DwdDmoRequest(TimeseriesRequest):
    """Implementation of sites for dmo sites."""

    metadata = DwdDmoMetadata
    _values = DwdDmoValues
    # required parameters
    issue: str | dt.datetime | DwdForecastDate = DwdForecastDate.LATEST
    station_group: Literal["single_stations", "all_stations"] | DwdDmoStationGroup | None = None
    lead_time: Literal["short", "long"] | DwdDmoLeadTime | None = None
    # per request, not per class: a listing read once should not outlive the settings it was read with
    _coverage_cache: dict[str, set[str] | None] = dataclasses.field(default_factory=dict, repr=False)
    _placemark_cache: dict[str, pl.DataFrame | None] = dataclasses.field(default_factory=dict, repr=False)

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
        """Adjust datetime to DMO's release hours, which are 00 and 12 UTC.

        Datetime is floored to closest release time e.g. if hour is 14, it will be rounded to 12

        """
        # floored, as the line above says and as this did not do: `hour % 12` is non-zero for 1
        # through 11 as well as for 13 through 23, and sending both to 12 rounds the morning *up*.
        # Asking for the 03:00 run returned the 12:00 one, issued nine hours later, or raised where
        # 12:00 was not published yet while 00:00 sat there unasked for.
        #
        # Unreachable until now, which is why it stood: every non-`LATEST` issue is stamped
        # tz-aware and was compared against a naive column, so it raised `SchemaError` before any
        # of this decided anything. Fixing that comparison is what made this live
        adjusted_date = datetime_.replace(minute=0, second=0, microsecond=0)
        return adjusted_date.replace(hour=adjusted_date.hour // 12 * 12)

    @classmethod
    def available_issues(
        cls,
        station_id: str,
        settings: Settings,
        *,
        dataset: DatasetModel | str = "icon",
        station_group: DwdDmoStationGroup | str | None = None,
        lead_time: DwdDmoLeadTime | str | None = None,
    ) -> list[dt.datetime]:
        """Return the run start times DWD publishes for one product, in ascending UTC order.

        Answers for a particular product, because the values path reads a particular product: this
        listed `icon/single_stations/<id>/kmz/` whatever the request was for, and named issues that
        the request would then reject (GH-1956). Two ways, both measured against the live server:
        `icon_eu`'s `all_stations` publishes only the `078` lead time, so an issue advertised from a
        `168` file met `IndexError: Unable to find a 168 h forecast within ...`; and a station the
        shared catalogue listed for `icon_eu` without `icon_eu` covering it has no single-station
        directory, so every issue this advertised for it resolved to an empty frame -- GH-1964, which
        narrowed the catalogue to the product. The directory comes from `_dmo_kmz_path` now, which is
        the one the values path reads.

        The defaults are `DwdDmoRequest`'s own, so what this answers with no arguments is what a
        request built with no arguments accepts. Pass `lead_time=None` for the old behaviour of
        listing the runs of every lead time together, which is a question about the directory rather
        than about anything that can be asked for.

        Args:
            station_id: The station to answer for, where the product is published per station.
            settings: The settings to list with.
            dataset: The DMO product -- `icon` or `icon_eu`, or the `DatasetModel` itself.
            station_group: `single_stations` (the default) or `all_stations`.
            lead_time: `short` (078, the default) or `long` (168); `None` lists every lead time.

        Returns:
            The run start times, tz-aware UTC, deduplicated and ascending.

        """
        group = parse_enumeration_from_template(station_group, DwdDmoStationGroup) or DwdDmoStationGroup.SINGLE_STATIONS
        lead = parse_enumeration_from_template(lead_time, DwdDmoLeadTime) if lead_time is not None else None
        name_original = dataset.name_original if isinstance(dataset, DatasetModel) else str(dataset)
        url = urljoin("https://opendata.dwd.de", _dmo_kmz_path(name_original, group, station_id))
        urls = list_remote_files_fsspec(url, settings, CacheExpiry.NO_CACHE)
        if not urls:
            # a directory that exists and holds nothing has no issues to name. Built into a frame
            # it is a `url` column of dtype Null, and the split below raises `invalid series dtype:
            # expected String, got null` out of `wetterdienst issues` -- the same fault fixed for
            # `dwd/mosmix`, which GH-1946 fixes there -- though in that provider
            # `get_url_for_date` raises where the one above returns `None`, which is its contract
            # rather than a disagreement.
            #
            # Warned about rather than simply answered, because a listing that *failed* looks the
            # same from here: `fs.find` walks with `on_error="omit"`, which swallows `OSError`, and
            # aiohttp's `ClientOSError` is one -- so a connection reset mid-listing arrives as an
            # empty directory would, and an unremarked `[]` would make that blip a fact about the
            # station
            log.warning(f"No DMO run listed within {url}; a listing that failed looks the same as one that is empty")
            return []
        df = pl.DataFrame({"url": urls}, orient="col")
        # the same rule `get_url_for_date` reads by, and for the same lead time, so what is
        # advertised is what it will accept. A name that is not a forecast carries no stamp and is
        # dropped
        df = df.with_columns(_run_stamp(pl.col("url"), lead).alias("date_str"))
        df = df.filter(pl.col("date_str").is_not_null())
        if df.is_empty():
            what = "a forecast file" if lead is None else f"a {lead.value} h forecast"
            log.warning(f"None of the {len(urls)} entries listed within {url} is {what}")
            return []
        now_utc = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
        df = add_date_from_filename(df, now_utc)
        return df.get_column("date").dt.replace_time_zone("UTC").unique().sort().to_list()

    def __post_init__(self) -> None:
        """Post-initialize the DwdDmoRequest class."""
        super().__post_init__()
        self.station_group = (
            parse_enumeration_from_template(self.station_group, DwdDmoStationGroup)
            or DwdDmoStationGroup.SINGLE_STATIONS
        )
        self.lead_time = parse_enumeration_from_template(self.lead_time, DwdDmoLeadTime) or DwdDmoLeadTime.SHORT
        issue: str | dt.datetime | DwdForecastDate = self.issue
        with contextlib.suppress(InvalidEnumerationError):
            issue = parse_enumeration_from_template(issue, DwdForecastDate)  # ty: ignore[no-matching-overload]
        if issue is not DwdForecastDate.LATEST:
            if isinstance(issue, str):
                issue = dt.datetime.fromisoformat(issue)
            # converted, not relabelled: taking the wall-clock hour and stamping UTC on it read
            # `13:00+02:00` as 13:00 UTC, so an issue given in any other zone floored to the wrong
            # release -- 11:00 UTC asked for, 12:00 UTC answered, which at 11:00 is a run not yet
            # published and so an `IndexError` where the 00:00 run was sitting there. A naive issue
            # is taken as UTC, which is what it has always meant here
            issue = issue.astimezone(ZoneInfo("UTC")) if issue.tzinfo else issue.replace(tzinfo=ZoneInfo("UTC"))
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour, tzinfo=ZoneInfo("UTC"))
            # Shift issue date to 0, 12 hour format
            issue = self.adjust_datetime(issue)
        self.issue = issue

    def _with_stations_the_catalogue_omits(
        self,
        df_dataset: pl.DataFrame,
        covered: set[str],
        dataset_name_original: str,
    ) -> pl.DataFrame:
        """Add the stations a product forecasts for that `dmo_stationsliste_txt.asc` does not list.

        135 of them for `icon`, 132 for `icon_eu` (measured 2026-09-24), and they could not be asked
        for at all: absent from the catalogue, they were filtered out of every request even though
        their forecasts are published and fetch with HTTP 200. The catalogue is the only source of an
        ICAO id, so it stays the source for the stations it does list, and these are described from
        the run instead -- with no ICAO id, which is already a value the catalogue produces for the
        stations it writes as `----` (GH-1966).
        """
        missing = covered - set(df_dataset.get_column("station_id"))
        if not missing:
            return df_dataset
        described = self._station_metadata_from_placemarks(dataset_name_original)
        if described is None:
            return df_dataset
        extra = described.filter(pl.col("station_id").is_in(missing))
        if extra.is_empty():
            return df_dataset
        log.debug(
            f"{len(extra)} stations {dataset_name_original} forecasts for are not in the shared DMO catalogue; "
            f"describing them from its newest run instead",
        )
        extra = extra.with_columns(
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("start_date"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("end_date"),
            pl.lit(None, pl.String).alias("state"),
        )
        return pl.concat([df_dataset, extra.select(df_dataset.columns)])

    @staticmethod
    def _narrows_rather_than_empties(covered: set[str], df_raw: pl.DataFrame, dataset_name_original: str) -> bool:
        """Say whether a coverage listing names stations this catalogue has, so filtering by it narrows.

        `_covered_station_ids` reads directory names, and a directory tree that stops being one
        directory per station still yields names: were `single_stations/` reorganised into a
        subdirectory per lead time, the listing would come back as `{"078", "168"}`, pass the
        emptiness check, and filter every station in the catalogue out. The result is an empty
        stations frame with nothing raised and nothing logged -- the same indistinguishable silence
        GH-1964 and GH-1947 are about, arriving through the very change that was meant to end it.

        One station in common is enough: the products genuinely cover different subsets, so anything
        stricter would fire on the real disagreement this exists to represent.
        """
        if not covered.isdisjoint(df_raw.get_column("station_id")):
            return True
        log.warning(
            f"None of the {len(covered)} entries listed for {dataset_name_original} names a station in the "
            f"catalogue, so they are not a station listing; keeping the catalogue shared by both DMO products",
        )
        return False

    def _station_metadata_from_placemarks(self, dataset_name_original: str) -> pl.DataFrame | None:
        """Describe the stations a product forecasts for, from its newest `all_stations` run.

        Read only when the catalogue is missing a station the product covers, so that a catalogue
        DWD completes stops costing anything, and cached per request for the same reason
        `_covered_station_ids` is.
        """
        from typing import cast  # noqa: PLC0415

        cached = self._placemark_cache.get(dataset_name_original, _UNREAD)
        if cached is not _UNREAD:
            return cast("pl.DataFrame | None", cached)
        frame = self._read_station_metadata_from_placemarks(dataset_name_original)
        self._placemark_cache[dataset_name_original] = frame
        return frame

    def _read_station_metadata_from_placemarks(self, dataset_name_original: str) -> pl.DataFrame | None:
        """Do the fetch `_station_metadata_from_placemarks` caches, or None if it could not be done."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        url = urljoin(
            "https://opendata.dwd.de",
            _dmo_kmz_path(dataset_name_original, DwdDmoStationGroup.ALL_STATIONS, station_id=None),
        )
        try:
            urls = list_remote_files_fsspec(url, settings, CacheExpiry.FILEINDEX)
            runs = pl.DataFrame({"url": urls}, orient="col").with_columns(
                # the same rule the values path reads runs by, asked without a lead time: for
                # station metadata either lead time will do, both carrying the same placemarks
                _run_stamp(pl.col("url")).alias("stamp"),
            )
            runs = runs.filter(pl.col("stamp").is_not_null()).sort("stamp")
            if runs.is_empty():
                log.warning(f"No DMO run listed within {url}, so the stations it describes cannot be read")
                return None
            newest = cast("str", runs.get_column("url").last())
            reader = KMLReader(station_ids=[], settings=settings)
            # the reader owns the open archive; parsing finishes before it goes out of scope
            return _placemark_metadata(reader.fetch(newest))
        except Exception as ex:  # noqa: BLE001
            log.warning(
                f"Unable to read the stations {dataset_name_original} describes within {url} ({ex!r}); "
                f"the ones its catalogue omits stay unreachable",
            )
            return None

    def _covered_station_ids(self, dataset_name_original: str) -> set[str] | None:
        """Read which stations one DMO product forecasts for, or None if that could not be read.

        The catalogue at `_url` is one list for both products and matches neither. Of its 5811
        stations `icon` covers 5622 and `icon_eu` 3556 (measured 2026-09-24), so a request for
        `icon_eu` advertised 2255 stations that can only ever answer with an empty frame -- which
        from the caller's side is indistinguishable from a station whose forecast is merely missing
        right now, and from the swallowed listing GH-1947 was about (GH-1964).

        None rather than an empty set when the listing cannot be read, because the two mean opposite
        things: the caller keeps the whole catalogue for a listing it could not read, rather than
        answering that a product has no stations at all.
        """
        from typing import cast  # noqa: PLC0415

        # once per product per request, not once per `all()`. `TimeseriesRequest.all()` is not
        # memoized and the filters call it repeatedly -- `filter_by_rank` twice, `filter_by_distance`
        # four times -- so with `cache_disable` set, which turns fsspec's listings cache off too,
        # a single `filter_by_distance` would fetch this 640 KB index four times per product
        cached = self._coverage_cache.get(dataset_name_original, _UNREAD)
        if cached is not _UNREAD:
            return cast("set[str] | None", cached)
        covered = self._read_covered_station_ids(dataset_name_original)
        self._coverage_cache[dataset_name_original] = covered
        return covered

    def _read_covered_station_ids(self, dataset_name_original: str) -> set[str] | None:
        """Do the listing `_covered_station_ids` caches."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        url = urljoin("https://opendata.dwd.de", _dmo_station_dir(dataset_name_original))
        try:
            entries = list_remote_directory_fsspec(url, settings, CacheExpiry.METAINDEX)
        except Exception as ex:  # noqa: BLE001
            # degraded audibly rather than silently: falling back to the shared catalogue is the
            # behaviour this method exists to correct, so a caller getting it back has to hear why
            log.warning(
                f"Unable to list the stations {dataset_name_original} covers within {url} ({ex!r}); "
                f"falling back to the catalogue shared by both DMO products, which is wider than "
                f"either of them",
            )
            return None
        station_ids = {entry["name"].rstrip("/").rsplit("/", 1)[-1] for entry in entries}
        station_ids.discard("")
        if not station_ids:
            log.warning(
                f"No station listed within {url}; falling back to the catalogue shared by both DMO products",
            )
            return None
        return station_ids

    def _all(self) -> pl.LazyFrame:
        """Get all stations from DMO."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
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
        df_raw = df_raw.with_columns(
            pl.col("icao_id").replace("----", None),
            _dm_degrees("latitude").alias("latitude"),
            _dm_degrees("longitude").alias("longitude"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("start_date"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("end_date"),
            pl.lit(None, pl.String).alias("state"),
        )
        # combinations of resolution and dataset
        from wetterdienst.model.metadata import ParameterModel  # noqa: PLC0415

        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name, parameter.dataset.name_original)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        data = []
        # for each combination of resolution and dataset create a new DataFrame with the columns,
        # narrowed to the stations that combination's product actually forecasts for
        for resolution, dataset, dataset_original in resolutions_and_datasets:
            df_dataset = df_raw
            covered = self._covered_station_ids(dataset_original)
            if covered is not None and self._narrows_rather_than_empties(covered, df_dataset, dataset_original):
                df_dataset = df_dataset.filter(pl.col("station_id").is_in(covered))
                df_dataset = self._with_stations_the_catalogue_omits(df_dataset, covered, dataset_original)
            data.append(
                df_dataset.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        df = pl.concat(data)
        df = df.select(self._base_columns)
        return df.lazy()
