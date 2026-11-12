# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KNMI's EDR API, the opt-in fast path for a long range of values of one station or a few (GH-3928).

The Open Data API serves one NetCDF file for every timestamp, so a station's series is one file for each of its
moments: a year of hourly values is 8,760 files, each one a request of the quota (`api`). The EDR API
(https://developer.dataplatform.knmi.nl/edr-api) answers a range of a few stations in one request, as CoverageJSON.
It needs a key of its own (`Settings.auth.knmi_edr`, `WD_AUTH__KNMI_EDR`) with a quota of its own (1,000 requests an
hour, whatever their size), which the key of the files is refused by, so it is used only where that key is set, and
only for a range that would take many files. Everything else, the list of the stations and the all-stations queries
included, is read from the files as it always was.

What was measured of it (2026-11-11, 6,864 cells of three stations at the three finest resolutions compared with the
files, none different):

- One request holds at most 300,000 points, times * parameters * stations; a request over that is a 413.
- `/collections/{collection}/locations/{wsi,wsi}` takes several stations; `datetime=start/end` holds both ends, and
  `parameter-name=A,B` the parameters. A 404 is "no data in the range", a 400 an unknown parameter or station.
- Every value is stamped with the END of its interval, as the time coordinate of the files is: the 10-minute and the
  hourly stamps are those of the provider, the daily, the monthly and the annual are one day, month or year later than
  the stamp of the provider, which is the start of the period (`to_edr_stamp`).
- A NaN is a null; a parameter that a station has no sensor for is left out of its coverage. The codes of the files
  (`-1` for a trace, 0 and 990 of the wind direction, 9 of the cloud cover) are passed through as they are.
- Neither the CoverageJSON nor the netCDF4 answer carries quality flags, which the files do not either.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation.grid import advance, ceil, floor
from wetterdienst.provider.knmi.observation.parser import ROW_SCHEMA, public_station_id
from wetterdienst.settings import reveal
from wetterdienst.util.network import CREDENTIAL_REJECTED_STATUSES, drop_cached_file

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from wetterdienst.metadata.cache import CacheExpiry
    from wetterdienst.settings import Settings
    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

EDR_BASE_URL = "https://api.dataplatform.knmi.nl/edr/v1"

#: The collections of the five resolutions: the datasets of the files (`api._DATASET_BY_RESOLUTION`). `GET /collections`
#: (read 2026-11-11) lists them with every variable the provider maps for them (16, 12, 13, 23 and 23), under the same
#: names and in the same units. The unvalidated hourly and daily collections beside them are not served by the files
#: either. The monthly and the annual ones, which the issue left open, exist and agree with the files (read 2026-11-12:
#: De Bilt for 2020-01 to 2020-03 and for 2017 to 2020; `test_edr_remote.py`).
COLLECTION_BY_RESOLUTION = {
    Resolution.MINUTE_10: "10-minute-in-situ-meteorological-observations",
    Resolution.HOURLY: "hourly-in-situ-meteorological-observations-validated",
    Resolution.DAILY: "daily-in-situ-meteorological-observations-validated",
    Resolution.MONTHLY: "monthly-in-situ-meteorological-observations-validated",
    Resolution.ANNUAL: "annual-in-situ-meteorological-observations-validated",
}

#: The most points (times * parameters * stations) of a request: the limit of the API, which answers 413 beyond it.
MAX_POINTS = 300_000

#: How many files a range must need before the EDR API is asked for it: more than this. The files cost one request of
#: the quota each (the resolve of the download link; the download is free), whatever the number of stations, since a
#: file holds them all and is kept for 12 hours once settled. 48 is two days of hourly values or 48 of daily ones: 48
#: requests are 5 % of the 1,000 an hour of a registered key and about 3 MB, which a person asking for a day or two does
#: not wait long for, and for which the files need no second key. Past it the files take longer and spend the quota in
#: earnest (a week of 10-minute values is 1,008 files, a year of hourly ones 8,760), where the EDR API answers the range
#: in one request or a few. "A few dozen", as the issue has it: lower, and the second route is taken for a range the
#: first serves in seconds; higher, a week of hourly values (168) would still be 168 requests.
MIN_FILES = 48

#: How many months a block of the calendar spans, the unit that a request is aligned to, so that queries of overlapping
#: ranges ask for, and are served from the cache with, the same chunks. The largest of a month, a year and a decade that
#: keeps the points of one station well under the limit: a month of 10-minute values (16 parameters: 71,424 points), a
#: year of hourly ones (12: 105,408) or of daily ones (13: 4,758), a decade of monthly ones (23: 2,760) or of annual
#: ones (23: 230). Several stations share a request as far as the limit allows (`stations_per_request`).
BLOCK_MONTHS = {
    Resolution.MINUTE_10: 1,
    Resolution.HOURLY: 12,
    Resolution.DAILY: 12,
    Resolution.MONTHLY: 120,
    Resolution.ANNUAL: 120,
}

#: The statuses that are not asked again: a retry cannot change what they say (`api._download_with_retry`). A 429 is the
#: quota used up, and asking again within the retries is how that gets worse.
NON_RETRYABLE_STATUSES = frozenset({400, 401, 403, 404, 413, 422, 429})

#: How a WIGOS station identifier reads (`0-20000-0-06260`, `0-528-0-06233`): what goes into the URL of a request
_WSI = re.compile(r"^[0-9]-[0-9]{1,5}-[0-9]-[0-9A-Za-z]{1,16}$")

_STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_UTC = dt.UTC


def is_wsi(text: object) -> bool:
    """Tell whether a text is a WIGOS station identifier, which may be put into the URL of a request."""
    return isinstance(text, str) and _WSI.match(text) is not None


def to_edr_stamp(stamp: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Give the stamp the API has for a value that the provider stamps with `stamp`: the end of its interval.

    The 10-minute and the hourly stamps of the provider are the end already; a day, a month and a year are stamped with
    their first moment, and the API with the next one.
    """
    if resolution in (Resolution.MINUTE_10, Resolution.HOURLY):
        return stamp
    return advance(stamp, resolution)


def to_stamp(edr_stamp: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Give the stamp of the provider of a value that the API stamps with `edr_stamp` (`to_edr_stamp` the other way)."""
    if resolution in (Resolution.MINUTE_10, Resolution.HOURLY):
        return edr_stamp
    return advance(edr_stamp, resolution, -1)


def stamp_of_moment(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Give the stamp of the values of the file named for `moment` (`api._stamp`): an hour is named for its start."""
    return advance(moment, resolution) if resolution == Resolution.HOURLY else moment


def stamp_bounds(
    start: dt.datetime, end: dt.datetime, resolution: Resolution, now: dt.datetime
) -> tuple[dt.datetime, dt.datetime] | None:
    """Give the first and the last stamp that the file route reads for a range (`api._moments`), None if it reads none.

    The stamps of the files whose names are in [start, end] by their stamps, and whose interval has ended: the end of an
    interval is what the API stamps it with, so that is a stamp that is at or before now (`to_edr_stamp`).
    A 10-minute range starts at the 10 minutes that hold its start, as the files do (the one before it is cut by the
    window); the others at the first stamp at or after it. A daily start is taken as it is: the caller leaves a start
    that is not on a midnight to the files.
    """
    if resolution == Resolution.MINUTE_10:
        first = floor(start, resolution)
    elif resolution == Resolution.DAILY:
        first = start
    else:
        first = ceil(start, resolution)
    last = min(floor(end, resolution), to_stamp(floor(now, resolution), resolution))
    return (first, last) if first <= last else None


def count_stamps(first: dt.datetime, last: dt.datetime, resolution: Resolution) -> int:
    """Count the stamps from `first` to `last`, both on the grid of the resolution and both counted."""
    if resolution == Resolution.MONTHLY:
        return (last.year - first.year) * 12 + last.month - first.month + 1
    if resolution == Resolution.ANNUAL:
        return last.year - first.year + 1
    return int((last - first) / (advance(first, resolution) - first)) + 1


@dataclass(frozen=True)
class Chunk:
    """The stamps (of the provider) from `first` to `last`, both read, that one request asks for."""

    first: dt.datetime
    last: dt.datetime

    def halves(self, resolution: Resolution) -> tuple[Chunk, Chunk] | None:
        """Cut the chunk in two at the middle of its stamps, None if it is a stamp."""
        count = count_stamps(self.first, self.last, resolution)
        if count < 2:
            return None
        middle = advance(self.first, resolution, count // 2)
        return Chunk(self.first, advance(middle, resolution, -1)), Chunk(middle, self.last)


def plan(
    first: dt.datetime, last: dt.datetime, resolution: Resolution, now: dt.datetime, available_from: dt.datetime
) -> list[Chunk]:
    """Cut the stamps from `first` to `last` into the chunks of requests, aligned to the calendar (`BLOCK_MONTHS`).

    A chunk is the whole block of the calendar that holds a stamp of the range, not the part of it that is asked for:
    the URL is the key of the cache, so a query that overlaps an earlier one asks for the same chunks and is served
    from them. Cut at the start of the data (`available_from`, the stamp of the first file) and at the last stamp that
    has ended (a period that has not ended is not asked for, GH-4008), which for the block that holds now moves with the
    grid of the resolution, as a copy of it is kept for minutes only.
    """
    span = BLOCK_MONTHS[resolution]
    ended = to_stamp(floor(now, resolution), resolution)
    chunks = []
    for index in range((first.year * 12 + first.month - 1) // span * span, (last.year * 12 + last.month - 1) + 1, span):
        block_start = dt.datetime(index // 12, index % 12 + 1, 1, tzinfo=_UTC)
        low = max(block_start, available_from)
        high = min(advance(advance(block_start, Resolution.MONTHLY, span), resolution, -1), ended)
        if low <= high:
            chunks.append(Chunk(low, high))
    return chunks


def stations_per_request(chunk: Chunk, resolution: Resolution, parameters: int) -> int:
    """Say how many stations a request for a chunk may name, by the points it holds: at least one."""
    return max(1, MAX_POINTS // (count_stamps(chunk.first, chunk.last, resolution) * max(parameters, 1)))


def request_url(
    collection: str, wsis: Sequence[str], parameters: Sequence[str], chunk: Chunk, resolution: Resolution
) -> str:
    """Name the request for a chunk of some stations: the key its answer is kept under, which holds no secret."""
    start = to_edr_stamp(chunk.first, resolution).strftime(_STAMP_FORMAT)
    end = to_edr_stamp(chunk.last, resolution).strftime(_STAMP_FORMAT)
    return (
        f"{EDR_BASE_URL}/collections/{collection}/locations/{','.join(wsis)}"
        f"?datetime={start}/{end}&parameter-name={','.join(parameters)}"
    )


class UnusableAnswerError(Exception):
    """An answer of the API that is no CoverageJSON of the stations asked for."""


def parse_coverage_json(payload: bytes, parameters: Sequence[str], resolution: Resolution) -> dict[str, pl.DataFrame]:
    """Read the CoverageJSON of a request into the readings of each station it holds, as KNMI wrote them.

    One frame of `timestamp` (the stamp of the provider), `parameter` and `value` for each station (by its number, the
    tail of its WIGOS identifier), with a row for each of the `parameters` at each time of the station: a parameter that
    the coverage leaves out (the station has no sensor for it) is a NaN, which is what the file holds for it, and a null
    is a NaN (the files' `_FillValue`), so that both go on through the same step as the files' values
    (`parser.knmi_readings`).

    Raises:
        UnusableAnswerError: the payload is no CoverageJSON of this shape.

    """
    try:
        return _read_coverages(json.loads(payload), parameters, resolution)
    except (ValueError, KeyError, TypeError, AttributeError, pl.exceptions.PolarsError) as error:
        raise UnusableAnswerError(type(error).__name__) from None


_SHIFT_BACK = {Resolution.DAILY: "-1d", Resolution.MONTHLY: "-1mo", Resolution.ANNUAL: "-1y"}


def _read_coverages(document: dict, parameters: Sequence[str], resolution: Resolution) -> dict[str, pl.DataFrame]:
    if document["type"] == "CoverageCollection":
        coverages = document["coverages"]
    elif document["type"] == "Coverage":
        coverages = [document]
    else:
        raise ValueError(document["type"])
    frames: dict[str, list[pl.DataFrame]] = {}
    for coverage in coverages:
        station = public_station_id(coverage["eumetnet:locationId"])
        times = coverage["domain"]["axes"]["t"]["values"]
        ranges = coverage["ranges"]
        stamps = pl.Series("timestamp", times, dtype=pl.String).str.to_datetime(
            _STAMP_FORMAT, time_unit="us", time_zone="UTC"
        )
        if resolution in _SHIFT_BACK:
            stamps = stamps.dt.offset_by(_SHIFT_BACK[resolution])
        rows = []
        for parameter in parameters:
            values = [float("nan")] * len(times) if parameter not in ranges else _numbers(ranges[parameter]["values"])
            if len(values) != len(times):
                raise ValueError(parameter)
            rows.append(pl.DataFrame({"timestamp": stamps, "parameter": parameter, "value": values}, schema=ROW_SCHEMA))
        if rows:
            frames.setdefault(station, []).extend(rows)
    return {station: pl.concat(rows) for station, rows in frames.items()}


def _numbers(values: list) -> list[float]:
    """Read the values of a range as the files hold them: a number, or NaN where the API has null."""
    out = []
    for value in values:
        if value is None:
            out.append(float("nan"))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out.append(float(value))
        else:
            raise ValueError(type(value).__name__)
    return out


#: The stations a request names, `(station_id, wsi)` each
Group = tuple[tuple[str, str], ...]


@dataclass
class Reading:
    """What was read of one station from the API (`frames`), and the stamps it was not (`left`), for the files."""

    frames: list[pl.DataFrame] = field(default_factory=list)
    left: list[Chunk] = field(default_factory=list)


@dataclass(frozen=True)
class _Answer:
    frames: dict[str, pl.DataFrame]


@dataclass(frozen=True)
class _NoData:
    """The API has no data for the chunk (a 404): not an error, the chunk is empty."""


@dataclass(frozen=True)
class _TooBig:
    """The API refuses the chunk as it is (a 413, a 400): it is asked for in smaller parts."""

    status: int


@dataclass(frozen=True)
class _Halt:
    """The API cannot be used for the rest of the request: the quota is used up, the key refused, no answer."""

    reason: str


class EdrReader:
    """Read the values of a range of some stations from the EDR API, as far as it answers, for one query.

    Holds what a query learns of the API: once the key is refused, the quota is used up or the API does not answer
    (`halted`), the rest of the query is not asked of it, and one warning is said for the query. What it did not read
    (`Reading.left`) the caller reads from the files, so that the rows come out as they would have from them.
    """

    def __init__(
        self,
        settings: Settings,
        download: Callable[..., File],
        expiry: Callable[[dt.datetime | None], CacheExpiry],
    ) -> None:
        """Hold the settings (the key of the API), the provider's download and its rule for how long a chunk is kept."""
        self._settings = settings
        self._download = download
        self._expiry = expiry
        self.halted = False
        self._warned = False

    def read(
        self,
        stations: Sequence[tuple[str, str]],
        resolution: Resolution,
        parameters: Sequence[str],
        chunks: Sequence[Chunk],
    ) -> dict[str, Reading]:
        """Read the chunks for stations, `(station_id, wsi)` each: what the API gave of each, and what it did not."""
        reads = {station_id: Reading() for station_id, _ in stations}
        queue: deque[tuple[Chunk, Group]] = deque()
        for chunk in chunks:
            size = stations_per_request(chunk, resolution, len(parameters))
            queue.extend((chunk, tuple(stations[i : i + size])) for i in range(0, len(stations), size))
        while queue:
            chunk, group = queue.popleft()
            outcome = None if self.halted else self._ask(chunk, group, resolution, parameters)
            if isinstance(outcome, _Answer):
                for station_id, _ in group:
                    if station_id in outcome.frames:
                        reads[station_id].frames.append(outcome.frames[station_id])
            elif isinstance(outcome, _TooBig) and (parts := self._smaller(chunk, group, resolution)):
                queue.extendleft(reversed(parts))
            elif outcome is None or isinstance(outcome, (_TooBig, _Halt)):
                # what the API cannot give, the files do: a chunk that is refused down to one station and one stamp, or
                # one that is met after the API has been given up on
                self._give_up(outcome)
                for station_id, _ in group:
                    reads[station_id].left.append(chunk)
        return reads

    def _give_up(self, outcome: _TooBig | _Halt | None) -> None:
        """Note that the API is no longer asked, if that is what the outcome says, and warn once."""
        if isinstance(outcome, _Halt):
            self.halted = True
            self._warn(outcome.reason)
        elif isinstance(outcome, _TooBig):
            self._warn(f"KNMI's EDR API refused a request with the status {outcome.status}")

    @staticmethod
    def _smaller(chunk: Chunk, group: Group, resolution: Resolution) -> list[tuple[Chunk, Group]] | None:
        """Cut a request that was refused as too big: its stations in two, or if it has one, its stamps."""
        if len(group) > 1:
            middle = len(group) // 2
            return [(chunk, group[:middle]), (chunk, group[middle:])]
        halves = chunk.halves(resolution)
        return None if halves is None else [(half, group) for half in halves]

    def _warn(self, reason: str) -> None:
        """Say once for the query that part of it is read from the files, and why. The key is never in it."""
        if not self._warned:
            self._warned = True
            log.warning(f"{reason}: the values left are read from the Open Data files, one request for each file")

    def _ask(
        self, chunk: Chunk, group: Group, resolution: Resolution, parameters: Sequence[str]
    ) -> _Answer | _NoData | _TooBig | _Halt:
        """Ask the API for a chunk of the stations of a group, or find the answer of it in the cache."""
        settings = self._settings
        wsis = [wsi for _, wsi in group]
        url = request_url(COLLECTION_BY_RESOLUTION[resolution], wsis, parameters, chunk, resolution)
        headers = settings.fsspec_client_kwargs.get("headers", {})
        # the key is sent in a header and nowhere else: the URL, which names the cached copy, holds none. Compression
        # (Accept-Encoding) shrinks the answer to a tenth
        client_kwargs = {
            **settings.fsspec_client_kwargs,
            "headers": {**headers, "Authorization": reveal(settings.auth.knmi_edr), "Accept-Encoding": "gzip"},
        }
        ttl = self._expiry(to_edr_stamp(chunk.last, resolution))
        # asked once: a 404 is the answer "no data", and every request is a unit of the quota
        file = self._download(
            url, settings, ttl, client_kwargs=client_kwargs, non_retryable=NON_RETRYABLE_STATUSES, attempts=1
        )
        if isinstance(file.content, Exception):
            return self._failed(file)
        try:
            return _Answer(parse_coverage_json(file.content.read(), parameters, resolution))
        except UnusableAnswerError as error:
            # a 200 that is no CoverageJSON would be served from the cache for as long as it is kept
            drop_cached_file(
                url,
                settings.cache_dir,
                ttl,
                client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            return _Halt(f"KNMI's EDR API answered something that is no CoverageJSON ({error})")

    @staticmethod
    def _failed(file: File) -> _NoData | _TooBig | _Halt:
        """Say what a download of the API that failed means for the request."""
        if isinstance(file.content, NoInternetError):
            file.raise_if_exception()
        status = file.status
        if status == 404:
            return _NoData()
        if status in (400, 413, 422):
            return _TooBig(status)
        if status in CREDENTIAL_REJECTED_STATUSES:
            return _Halt(f"KNMI's EDR API refused the key of WD_AUTH__KNMI_EDR (status {status})")
        if status == 429:
            return _Halt("KNMI's EDR API answered 429, its quota of 1,000 requests an hour is used up")
        return _Halt(f"KNMI's EDR API did not answer ({type(file.content).__name__}, status {status})")
