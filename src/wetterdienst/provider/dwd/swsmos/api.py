# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD SWSMOS (Straßenwetter-MOS) road weather forecast provider.

DWD publishes one CSV file per model run under
https://opendata.dwd.de/weather/local_forecasts/swsmos/ (``swsmos_<YYYYMMDDHH0000>_opendata.csv.bz2``),
each holding an hourly forecast to +167 h for every road weather station. The station catalogue is
``swsKatalog.csv.bz2``. See ``metadata.py`` for the field/unit mapping.

Each run file is a small deviation from a plain CSV: line 1 is the header, line 2 is the run
timestamp, and the remaining lines are ``ID;Lat;Lon;YYYYMMDDHHmm;<values...>`` rows (one per station
per forecast hour). Values use ``.`` decimals; the catalogue uses ``,`` decimals.
"""

from __future__ import annotations

import bz2
import contextlib
import datetime as dt
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.swsmos.metadata import DwdSwsmosMetadata
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import download_file, list_remote_files_fsspec

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.model.result import ValuesResult
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_UTC = ZoneInfo("UTC")
_BASE_URL = "https://opendata.dwd.de/weather/local_forecasts/swsmos"
_CATALOG_URL = f"{_BASE_URL}/swsKatalog.csv.bz2"
_LATEST_FILE = "swsmos_LATEST_opendata.csv.bz2"

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}


class DwdForecastDate(Enum):
    """Sentinel selecting the latest available model run."""

    LATEST = "latest"


# what a run file is called, and nothing else. A bare ``swsmos_`` prefix also matches a checksum
# sidecar or a second product published beside the runs, and one of those sorts after the run it
# belongs to -- so the newest name would be a file that is not a run, handed straight to bz2
_RUN_FILE = re.compile(r"^swsmos_\d{14}_opendata\.csv\.bz2$")


def _run_url(issue: dt.datetime) -> str:
    return f"{_BASE_URL}/swsmos_{issue:%Y%m%d%H}0000_opendata.csv.bz2"


def _read_run_csv(content: bytes) -> pl.DataFrame:
    """Decompress and parse a run file, dropping the run-timestamp line between header and data."""
    lines = bz2.decompress(content).decode("latin-1").splitlines()
    if len(lines) < 3:
        return pl.DataFrame()
    csv = ("\n".join([lines[0], *lines[2:]])).encode()
    return pl.read_csv(csv, separator=";", infer_schema_length=0)


def _read_run(content: bytes, url: str) -> pl.DataFrame | None:
    """Parse a run file, or say it could not be read.

    A body that is not the bz2 a run file should be raises out of `bz2.decompress` -- `ValueError`
    where it stops early, `OSError` where it was never bz2 -- and nothing between here and the
    caller catches, so a truncated download used to end the request in a traceback where a failed
    download ends it in an empty frame. It also lands in the cache, so the traceback would have
    repeated for twelve hours. Reported and answered the way a failed fetch is instead.

    A body holding no readings is the same answer. `bz2.decompress(b"")` returns `b""` rather than
    raising, so a zero-byte 200 -- the first instant of the file the uncached listing has just
    named, or a mirror answering with nothing -- parses to a frame of no rows and no columns. Read
    as a run that simply holds nothing, that frame was the request's answer and the run before it
    was never tried: the window the fallback exists for, one byte-count away from the truncation it
    does catch. A run file holds every station at every forecast hour, so one holding nothing is
    one that was not read.
    """
    try:
        df = _read_run_csv(content)
    except (OSError, ValueError, EOFError, pl.exceptions.PolarsError) as ex:
        log.warning(f"Failed to read SWSMOS run {url}: {ex!r}")
        return None
    if df.is_empty():
        log.warning(f"SWSMOS run {url} holds no readings ({len(content)} bytes)")
        return None
    return df


class DwdSwsmosValues(TimeseriesValues):
    """Values class for DWD SWSMOS road weather forecast data."""

    def __post_init__(self) -> None:
        """Post-initialization of the DwdSwsmosValues class."""
        super().__post_init__()
        # the run this request answers for, resolved and parsed once. `None` is "not looked up
        # yet"; an empty frame is "looked up, and there is nothing there". See `_run_frame`
        self._run_frame_cache: pl.DataFrame | None = None

    def _run_candidates(self, settings: Settings) -> list[tuple[str, CacheExpiry]]:
        """List the runs to try, newest first, with how long each may be answered from the cache.

        How long a run may be cached is a property of the URL, not of the request. A run named by
        its timestamp is that run for good; ``swsmos_LATEST...`` is a name whose content DWD
        replaces every hour, so caching it by URL for twelve hours -- as this did -- answered "the
        latest run" with one up to twelve hours old, whose first twelve forecast hours had already
        happened. Measured: at 22:57 UTC the alias was answered from the 21:00 run while the server
        served 22:00.

        So `LATEST` resolves to the newest run the listing names rather than to the alias. The two
        are the same bytes -- the server returns one ETag for both (``6ab20a9e-1da802``, with one
        content-length and one Last-Modified), the alias being a link rather than a copy -- and
        asking for the run by name is the same answer from a URL that cannot change under its cache
        entry. `dwd/road` likewise indexes the timestamped files and skips the aliases duplicating
        them. The listing itself is never cached, so "newest" is current.

        Which is also why the run before it is offered as a fallback. An uncached listing names a
        run the moment it appears, and a run still being written cannot be read; a body that cannot
        be read is cached for twelve hours, so without somewhere else to go a single bad download
        would empty every request for half a day. An hour-old forecast is what `LATEST` should mean
        in that window, rather than nothing.
        """
        issue = cast("DwdSwsmosRequest", self.sr.stations).issue
        if issue is not DwdForecastDate.LATEST:
            return [(_run_url(cast("dt.datetime", issue)), CacheExpiry.TWELVE_HOURS)]
        files = list_remote_files_fsspec(f"{_BASE_URL}/", settings, CacheExpiry.NO_CACHE)
        names = {f.rsplit("/", 1)[-1]: f for f in files}
        # fixed-width digits, so lexical order is chronological order
        runs = sorted(n for n in names if _RUN_FILE.match(n))
        if runs:
            return [(names[n], CacheExpiry.TWELVE_HOURS) for n in reversed(runs[-2:])]
        if _LATEST_FILE in names:
            # nothing but the alias to go on. It is mutable, so it may only be held briefly: five
            # minutes is what `dwd/mosmix` holds its KML for, a bounded lag against an hourly cadence
            return [(names[_LATEST_FILE], CacheExpiry.FIVE_MINUTES)]
        # every other way a run can fail says so; this one used to answer every station with an
        # empty frame and no diagnostic at all. The listing is retried and re-raises, so an empty
        # one means the server genuinely named nothing -- a directory reorganised or the products
        # renamed, which is a provider restructure rather than a day with no data
        log.warning(f"No SWSMOS run listed within {_BASE_URL}/; the file names may have changed")
        return []

    def _run_content(self, url: str, ttl: CacheExpiry, settings: Settings) -> bytes | None:
        """Fetch one run, or say it could not be fetched."""
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=ttl,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if isinstance(file.content, Exception):
            if not file.is_no_internet_error:
                log.warning(f"Failed to fetch SWSMOS run {url}: {file.content}")
            return None
        return file.content.read()

    def _run_frame(self, settings: Settings) -> pl.DataFrame:
        """Resolve and parse the run once, for every station it answers for.

        One run file holds every road station's whole forecast, where the collection above this
        asks for one station at a time -- so the run was listed, fetched and parsed once per
        station, and all but one station's rows thrown away each time. Five stations decompressed
        and parsed the same 306,612 rows five times -- 2.5 s of a 2.7 s request -- and twenty-five
        took 14.1 s, where the whole network of 1,836 stations would have spent a quarter of an
        hour on 1,836 parses of one file. They now take 0.7 s and 0.8 s: one parse either way, the
        cost flat in the number of stations asked for. The file itself comes from the cache; what
        was repeated is the bz2 decompress and the CSV parse (~0.5 s), and -- for a `LATEST`
        request -- the uncached directory listing that resolves the alias, which is a remote round
        trip rather than local work.

        The whole run is kept, where road keeps only its last station group: a run is one file of
        some 20 MB no matter how wide the request or how long the window, so there is nothing here
        to bound. Nor is there a key. A group varies from station to station, while the run is a
        property of the request -- `issue` is resolved when the request is built and cannot change
        while it is answered -- so the frame parsed for one station is by construction the frame
        every other station wants.

        For `DwdForecastDate.LATEST` that also makes the answer consistent rather than merely
        quicker: resolving the run once pins every station to it. The listing that says which run
        is newest is never cached, so resolved per station a walk that DWD publishes a run into
        answers the stations after that point from the new one -- a frame quietly mixing two model
        runs, with no cache entry in the way to make it rare.

        A run that cannot be fetched is kept as an empty frame, where `ipma` deliberately leaves a
        failed fetch uncached to be retried: there, a feed that fails costs that feed's stations,
        while here one file is the whole request, so asking again per station cannot answer a
        different question. `download_file` has already asked twice by then -- `_worth_retrying_download`
        governs what a blip is -- and 1,836 stations asking 3,672 times is a herd against a server
        that has just failed, not a recovery. The warning naming the run says what happened.
        """
        if self._run_frame_cache is None:
            self._run_frame_cache = pl.DataFrame()
            for url, ttl in self._run_candidates(settings):
                content = self._run_content(url, ttl, settings)
                df = _read_run(content, url) if content is not None else None
                if content is not None and df is None:
                    # a body that cannot be read is held under its URL for as long as a good one
                    # would be, so what the cache hands back says nothing about what the server has
                    # now. Asked once more past it, a run DWD has since finished writing is read
                    # now.
                    #
                    # Whether to do this when a fallback exists was argued both ways in review, so
                    # the trade is written down rather than left to the next reader. Against: a
                    # `NO_CACHE` fetch is served by a plain `HTTPFileSystem`, so the good body is
                    # never written back over the bad one -- every later request pays for the file
                    # again, where falling back to the run before this one costs nothing and is
                    # already correct. For: that fallback is not free either, it is an hour of
                    # answering with yesterday's hour while the run the caller asked for sits
                    # complete on the server, and it is invisible where the re-ask's cost is not.
                    # `LATEST` means the newest run there is, not the newest one a stale cache
                    # entry will admit to, so the re-ask is made either way. The duplicate fetch
                    # this costs on a cache miss -- DWD listing a run mid-write, the body arriving
                    # half-written and being asked for again a moment later -- is one request's
                    # worth, against an hour of every request's.
                    #
                    # Only a body that arrived and could not be read: a fetch that failed has
                    # already been retried by `download_file`, and asking a server that just
                    # refused to serve the file is not a recovery.
                    #
                    # Not guarded on `cache_disable`, though a body fetched without a cache has
                    # nothing to ask past: `NetworkFilesystemManager` keys its filesystems by TTL
                    # and client kwargs alone, and registers one only where that key is new -- so
                    # a request made with caching disabled is served by whatever was registered
                    # first in that thread, cache and all. The flag therefore does not say whether
                    # a cache stood in the way, and a guard reading it as though it did would skip
                    # the re-ask in the one case that needs it. One duplicate fetch where caching
                    # really is off is the cheaper mistake (GH-1947)
                    content = self._run_content(url, CacheExpiry.NO_CACHE, settings)
                    df = _read_run(content, url) if content is not None else None
                if df is not None:
                    self._run_frame_cache = df
                    break
        return self._run_frame_cache

    def query(self) -> Iterator[ValuesResult]:
        """Answer each station of the request, from one run resolved for this query.

        The run is pinned for the length of a query and no longer -- cleared on the way in, so a
        caller keeping the values object and querying it again on a timer is answered with the run
        published since rather than the one it first resolved, and cleared on the way out, so the
        20 MB frame does not outlive the walk it was parsed for. `ValuesResult` holds the values
        object that produced it, so without that second clear a request for one station's forecast
        handed back a result pinning the whole network's parsed run for as long as the caller kept
        it. Neither clear makes this re-entrant: two interleaved walks over one values object would
        tread on each other's run, as they already do on `stations_counter`.
        """
        self._run_frame_cache = None
        try:
            yield from super().query()
        finally:
            self._run_frame_cache = None

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        elif isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        else:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        settings = cast("Settings", self.sr.stations.settings)
        df = self._run_frame(settings)
        if df.is_empty() or "ID" not in df.columns:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        df = df.filter(pl.col("ID") == station_id)
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        columns = [p.name_original for p in dataset.parameters if p.name_original in df.columns]
        df = df.select(
            pl.col("YYYYMMDDHHmm")
            .str.to_datetime("%Y%m%d%H%M", time_unit="us")
            .dt.replace_time_zone("UTC")
            .alias("date"),
            *[pl.col(c).cast(pl.Float64, strict=False) for c in columns],
        )
        df = df.unpivot(index=["date"], variable_name="parameter", value_name="value")
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("date"),
            pl.col("value"),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class DwdSwsmosRequest(TimeseriesRequest):
    """Request class for DWD SWSMOS road weather forecast data."""

    metadata = DwdSwsmosMetadata
    _values = DwdSwsmosValues

    issue: str | dt.datetime | DwdForecastDate = DwdForecastDate.LATEST

    def __post_init__(self) -> None:
        """Resolve the ``issue`` (model run) to LATEST or a UTC hour."""
        super().__post_init__()
        issue: str | dt.datetime | DwdForecastDate = self.issue
        with contextlib.suppress(InvalidEnumerationError):
            issue = parse_enumeration_from_template(issue, DwdForecastDate)  # ty: ignore[no-matching-overload]
        if issue is not DwdForecastDate.LATEST:
            if isinstance(issue, str):
                issue = dt.datetime.fromisoformat(issue)
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour, tzinfo=_UTC)
        self.issue = issue

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=_CATALOG_URL,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if isinstance(file.content, Exception):
            log.warning(f"Failed to fetch SWSMOS station catalogue: {file.content}")
            return pl.LazyFrame()
        # the catalogue is latin-1 encoded (German station names carry umlauts)
        catalogue = bz2.decompress(file.content.read()).decode("latin-1").encode("utf-8")
        df = pl.read_csv(catalogue, separator=";", infer_schema_length=0)
        if df.is_empty():
            return pl.LazyFrame()
        resolution = self.metadata[0]
        # catalogue columns: Kennung;Name;Streckentyp;Streckenbelag;Breite;Laenge;Hoehe;Flughafen;Inaktiv
        # (Breite/Laenge/Hoehe use a comma decimal separator, unlike the run files)
        # drop stations flagged inactive (the ``Inaktiv`` column is empty for active stations)
        if "Inaktiv" in df.columns:
            df = df.filter(pl.col("Inaktiv").is_null() | (pl.col("Inaktiv").str.strip_chars() == ""))
        return df.select(
            pl.col("Kennung").alias("station_id"),
            pl.col("Name").alias("name"),
            pl.col("Breite").str.replace(",", ".").cast(pl.Float64, strict=False).alias("latitude"),
            pl.col("Laenge").str.replace(",", ".").cast(pl.Float64, strict=False).alias("longitude"),
            pl.col("Hoehe").str.replace(",", ".").cast(pl.Float64, strict=False).alias("height"),
            pl.lit(resolution.name, pl.String).alias("resolution"),
            pl.lit(resolution.datasets[0].name, pl.String).alias("dataset"),
        ).lazy()
