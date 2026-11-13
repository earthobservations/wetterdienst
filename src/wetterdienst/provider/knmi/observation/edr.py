# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KNMI's EDR API, the only source of the values of `knmi/observation` since GH-3928.

KNMI's Open Data API serves one NetCDF file for every timestamp, so a station's series was one file for each of its
moments: a year of hourly values was 8,760 files, each a request of the quota. The EDR API
(https://developer.dataplatform.knmi.nl/edr-api) answers a range of several stations in one request, as CoverageJSON. It
needs a key of its own (`Settings.auth.knmi_edr`, `WD_AUTH__KNMI_EDR`) with a quota of 1,000 requests an hour, whatever
their size, which the key of the Open Data API is refused by, so the files are no longer read.

What was measured of it (2026-11-11 and 2026-11-12, against the files, cell by cell: none different):

- One request holds at most 300,000 points, times * parameters * stations; a request over that is a 413.
- `/collections/{collection}/locations/{wsi,wsi}` takes several stations; `datetime=start/end` holds both ends, and
  `parameter-name=A,B` the parameters. A 404 is "no data in the range", a 400 an unknown parameter or station.
- `/collections/{collection}/cube?bbox=...` answers the same stations with the same values for the same request, so a
  query of many stations costs no fewer requests that way: the limit counts the same points. `/locations/{ids}` is used.
- Every value is stamped with the END of its interval, as the time coordinate of the files is: the 10-minute and the
  hourly stamps are those of the provider, the daily, the monthly and the annual are one day, month or year later than
  the stamp of the provider, which is the start of the period (`to_edr_stamp`).
- A NaN is a null; a parameter that a station has no sensor for is left out of its coverage. The codes of the files
  (`-1` for a trace, 0 and 990 of the wind direction, 9 of the cloud cover) are passed through as they are.
- A refused key is a 401 (no key, `Authorization field missing`) or a 403 (another key, such as the one of the Open Data
  API: `Access to this API has been disallowed`) of the gateway, which cost no quota. A key whose quota of the hour is
  used up is a 403 too (2026-11-13: `{"error": "Quota exceeded"}`), the same status for a key that is fine. The status
  alone cannot tell them apart, so a 403 is read by its body (`read_quota_exceeded`) and the quota is the
  `ProviderRateLimitError`, which says that and not that the key is wrong (GH-4046).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from http import HTTPStatus
from math import ceil as _ceil_div
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import CredentialRejectedError, DownloadError, ProviderRateLimitError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation.download import download_with_retry
from wetterdienst.provider.knmi.observation.grid import advance, ceil, floor
from wetterdienst.provider.knmi.observation.parser import ROW_SCHEMA, public_station_id
from wetterdienst.settings import reveal
from wetterdienst.util.network import (
    CREDENTIAL_REJECTED_STATUSES,
    RATE_LIMIT_RETRY_AFTER_SECONDS,
    _without_url_secrets,
    _without_url_secrets_in,
    drop_cached_file,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from wetterdienst.metadata.cache import CacheExpiry
    from wetterdienst.settings import Settings
    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

EDR_BASE_URL = "https://api.dataplatform.knmi.nl/edr/v1"

#: Where a key of the EDR API is requested
EDR_KEY_URL = "https://developer.dataplatform.knmi.nl/edr-api"

#: The collections of the five resolutions. `GET /collections` (read 2026-11-11) lists them with every variable the
#: provider maps for them (16, 12, 13, 23 and 23), under the names and in the units of the old files. The unvalidated
#: hourly and daily collections beside them are not served. The monthly and the annual ones agree with the files
#: (De Bilt, 2026-11-12; `test_edr_remote.py`).
COLLECTION_BY_RESOLUTION = {
    Resolution.MINUTE_10: "10-minute-in-situ-meteorological-observations",
    Resolution.HOURLY: "hourly-in-situ-meteorological-observations-validated",
    Resolution.DAILY: "daily-in-situ-meteorological-observations-validated",
    Resolution.MONTHLY: "monthly-in-situ-meteorological-observations-validated",
    Resolution.ANNUAL: "annual-in-situ-meteorological-observations-validated",
}


def _utc(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=dt.UTC)


#: The first stamp (of the provider) of each collection, from the start of its temporal extent in `GET /collections`
#: (read 2026-11-11: 2012-01-01T00:00, 1951-01-01T01:00, 1901-01-02, 1901-02-01 and 1902-01-01; the API stamps the
#: end of
#: the interval, so a day, a month and a year are one earlier): nothing before it is asked for.
FIRST_STAMP = {
    Resolution.MINUTE_10: _utc(2012, 1, 1),
    Resolution.HOURLY: _utc(1951, 1, 1, 1),
    Resolution.DAILY: _utc(1901, 1, 1),
    Resolution.MONTHLY: _utc(1901, 1, 1),
    Resolution.ANNUAL: _utc(1901, 1, 1),
}

#: The most points (times * parameters * stations) of a request: the limit of the API, which answers 413 beyond it.
MAX_POINTS = 300_000

#: How many months a block of the calendar spans, the unit that a request of one station is aligned to, so that queries
#: of overlapping ranges ask for, and are served from the cache with, the same chunks. The largest of a month, a year
#: and a decade that keeps the points of one station well under the limit: a month of 10-minute values (16 parameters:
#: 71,424 points), a year of hourly ones (12: 105,408) or of daily ones (13: 4,758), a decade of monthly ones (23:
#: 2,760)
#: or of annual ones (23: 230).
BLOCK_MONTHS = {
    Resolution.MINUTE_10: 1,
    Resolution.HOURLY: 12,
    Resolution.DAILY: 12,
    Resolution.MONTHLY: 120,
    Resolution.ANNUAL: 120,
}

#: How many stations at most are read for one request of a query: the station in hand and those that follow it.
STATIONS_AT_MOST = 100

#: How many points at most the readings of the stations that are read ahead hold at once, before the first of them is
#: handed over: about 100 MB of frames. A long range of one station is a point each of 3 million and more, which is a
#: station at a time, as the files were read; a day of every station is a few thousand and is read in one request.
MEMORY_POINTS = 3_000_000

#: How many stations the API may refuse alone in a query before that is no longer a station it does not know (`_refuse`)
MAX_REFUSED_STATIONS = 2

#: The requests a query may take at most: the quota of a registered key for an hour (`api` refuses a query above it)
MAX_REQUESTS = 1000

#: How a WIGOS station identifier reads (`0-20000-0-06260`, `0-528-0-06233`): what goes into the URL of a request
_WSI = re.compile(r"^[0-9]-[0-9]{1,5}-[0-9]-[0-9A-Za-z]{1,16}$")

_STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def is_wsi(text: object) -> bool:
    """Tell whether a text is a WIGOS station identifier, which may be put into the URL of a request."""
    return isinstance(text, str) and _WSI.match(text) is not None


def key_rejected(status: int | None) -> CredentialRejectedError:
    """Say that KNMI refuses the key, and that it is a key of the EDR API that is needed (GH-3928).

    The message names the setting and where the key is requested, never the key. The key of the Open Data API, which
    `WD_AUTH__KNMI` held until then, is refused by the EDR API with a 403.
    """
    answer = f"rejected the request with HTTP {status}" if status else "rejected the request"
    return CredentialRejectedError(
        f"KNMI {answer}. It now reads from its EDR API only, which needs a key of that API in WD_AUTH__KNMI_EDR: a key "
        f"of the Open Data API, as WD_AUTH__KNMI held until now, is refused. Request one in the API Catalog at "
        f"{EDR_KEY_URL}."
    )


def client_kwargs(settings: Settings) -> dict:
    """Give the client arguments of a request to the API: the key in a header and the answer asked for compressed.

    The key is sent in this header and nowhere else: the URL, which names the cached copy, holds none. Compression
    (`Accept-Encoding`) shrinks the answer to a tenth.
    """
    headers = settings.fsspec_client_kwargs.get("headers", {})
    return {
        **settings.fsspec_client_kwargs,
        "headers": {**headers, "Authorization": reveal(settings.auth.knmi_edr), "Accept-Encoding": "gzip"},
    }


def fetch(url: str, settings: Settings, ttl: CacheExpiry) -> File:
    """Ask the API for a URL, once (a 404 is "no data", and every request is a unit of the quota), as the key goes."""
    return download_with_retry(url, settings, ttl, client_kwargs=client_kwargs(settings), attempts=1)


#: What the gateway answers a 403 with when the quota of the key is used up (read 2026-11-13:
#: `{"error": "Quota exceeded"}`)
_QUOTA_EXCEEDED = "quota exceeded"


def quota_exceeded(url: str, *, status: int, retry_after: int | None = None) -> ProviderRateLimitError:
    """Say that KNMI's quota of the key is used up, and that the key is fine: retry later (GH-4046).

    The sentence names no URL and no key, so the REST API shows it as it is. `retry_after` is the wait KNMI sent, in
    seconds, if it sent one.
    """
    again = f" KNMI says it resets in about {_minutes(retry_after)}." if retry_after else ""
    return ProviderRateLimitError(
        _without_url_secrets(url),
        f"KNMI's EDR API answered {status}: the quota of {MAX_REQUESTS:,} requests an hour of the key of this "
        f"installation is used up, which is no fault of the key. Try again later, once the hour has passed.{again}",
        retry_after,
    )


def rate_limited(url: str, retry_after: int | None = None) -> ProviderRateLimitError:
    """Say that KNMI limits how fast the key may ask (a 429), without saying that the hour's quota is what ran out.

    The API limits the rate per second (200) as well as the requests of the hour, and a 429 does not say which, so no
    reset time is promised: the wait is the one KNMI sent (`retry_after`) or, where it sent none, a short one
    (`RATE_LIMIT_RETRY_AFTER_SECONDS`, the default of every provider's 429).
    """
    again = f" KNMI says to wait about {_minutes(retry_after)}." if retry_after else ""
    return ProviderRateLimitError(
        _without_url_secrets(url),
        "KNMI's EDR API answered 429: it limits how fast the key of this installation may ask (a rate per second, "
        f"and a quota of {MAX_REQUESTS:,} requests an hour), which is no fault of the key. Try again later.{again}",
        retry_after or RATE_LIMIT_RETRY_AFTER_SECONDS,
    )


def _minutes(seconds: int) -> str:
    return f"{seconds} seconds" if seconds < 2 * 60 else f"{_ceil_div(seconds / 60)} minutes"


def read_quota_exceeded(file: File) -> ProviderRateLimitError | None:
    """Tell whether a 403 is the quota of the key used up, from the body of that answer: the error if it is, else None.

    The gateway answers 403 for a key it refuses and for a key whose quota is used up, saying which only in the body
    (`Access to this API has been disallowed`, `Quota exceeded`). The download keeps that body (`File.refusal`, at most
    `REFUSAL_BODY_CHARS` characters, read from the first answer): no second request is made. Nothing of it is logged or
    put into the message. A 403 that has no body to read (a timeout, a body too long) is None: the status alone then
    says the key is refused, as it always did.
    """
    refusal = file.refusal
    if (
        refusal is None
        or refusal.status != HTTPStatus.FORBIDDEN
        or _QUOTA_EXCEEDED not in _error_text(refusal.body).lower()
    ):
        return None
    return quota_exceeded(file.url, status=file.status, retry_after=file.retry_after)


def _error_text(body: str) -> str:
    """Give the `error` of a gateway's JSON body, the body itself where it is no such JSON."""
    try:
        document = json.loads(body)
    except ValueError:
        return body
    error = document.get("error") if isinstance(document, dict) else None
    return error if isinstance(error, str) else body


def raise_if_unanswered(file: File) -> None:
    """Raise what a download of the API that failed means for the caller: nothing for a 404 and a 400, which answer.

    A quota that is used up (a 429, or a 403 whose body says `Quota exceeded`) is the `ProviderRateLimitError`: the key
    is fine and asking again now makes it worse, so the query ends here and is never asked again. A refused key (any
    other 401 or 403) is the `CredentialRejectedError` (`key_rejected`), no connection the `NoInternetError`, and any
    other failure (a 5xx that the retries did not clear) a `DownloadError`: a range read in part is not an answer, and
    an empty one would read as a station without data.
    """
    if not isinstance(file.content, Exception) or file.status in {400, 404, 413, 422}:
        return
    if file.status == HTTPStatus.FORBIDDEN:
        if (exhausted := read_quota_exceeded(file)) is not None:
            raise exhausted
        raise key_rejected(file.status)
    if file.status in CREDENTIAL_REJECTED_STATUSES:
        raise key_rejected(file.status)
    if file.status == HTTPStatus.TOO_MANY_REQUESTS:
        raise rate_limited(file.url, file.retry_after)
    file.raise_if_exception()


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


def stamp_bounds(
    start: dt.datetime, end: dt.datetime, resolution: Resolution, now: dt.datetime
) -> tuple[dt.datetime, dt.datetime] | None:
    """Give the first and the last stamp of a range, None if it holds none.

    The stamps in [start, end] whose interval has ended: the end of an interval is what the API stamps it with, so that
    is a stamp that is at or before now (`to_edr_stamp`; a period that has not ended is not asked for, GH-4008). A range
    starts at the stamp that holds its start (the 10 minutes, the day), which the window of the request cuts down to
    what it asks for, and for an hour, a month and a year at the first stamp at or after it.
    """
    first = (
        ceil(start, resolution)
        if resolution in (Resolution.HOURLY, Resolution.MONTHLY, Resolution.ANNUAL)
        else floor(start, resolution)
    )
    last = min(floor(end, resolution), to_stamp(floor(now, resolution), resolution))
    first = max(first, FIRST_STAMP[resolution])
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


def stations_per_request(chunk: Chunk, resolution: Resolution, parameters: int) -> int:
    """Say how many stations a request for a chunk may name, by the points it holds: at least one."""
    return max(1, MAX_POINTS // (count_stamps(chunk.first, chunk.last, resolution) * max(parameters, 1)))


#: The resolutions whose stamp is the END of its interval and is the stamp of the API too: a block of the calendar holds
#: the stamps after its first moment, up to and with the first moment of the next block (a day, a month and a year are
#: stamped with their start, and a block holds the stamps from its first moment up to the last before the next)
_END_STAMPED = (Resolution.MINUTE_10, Resolution.HOURLY)


def _aligned(first: dt.datetime, last: dt.datetime, resolution: Resolution, now: dt.datetime) -> list[Chunk]:
    """Cut the stamps from `first` to `last` into the blocks of the calendar that hold them (`BLOCK_MONTHS`).

    A chunk is the whole block, not the part of it that is asked for: the URL is the key of the cache, so a query that
    overlaps an earlier one asks for the same chunks and is served from them. The hourly and the 10-minute stamps mark
    the end of their interval, so a block of them is (its first moment, the first moment of the next block]: a calendar
    year of hourly values, 2020-01-01 01:00 to 2021-01-01 00:00, is one block and one request, where the blocks of the
    stamps from 00:00 would be two. Cut at the start of the data and at the last stamp that has ended, which for the
    block that holds now moves with the grid of the resolution, as a copy of it is kept for minutes only.
    """
    span = BLOCK_MONTHS[resolution]
    ended = to_stamp(floor(now, resolution), resolution)
    end_stamped = resolution in _END_STAMPED
    step = advance(first, resolution) - first
    # the block that holds a stamp is that of the start of its interval
    start_of = (lambda stamp: stamp - step) if end_stamped else (lambda stamp: stamp)
    chunks = []
    for index in range(
        (start_of(first).year * 12 + start_of(first).month - 1) // span * span,
        start_of(last).year * 12 + start_of(last).month - 1 + 1,
        span,
    ):
        block_start = dt.datetime(index // 12, index % 12 + 1, 1, tzinfo=dt.UTC)
        block_end = advance(block_start, Resolution.MONTHLY, span)
        low = max(advance(block_start, resolution) if end_stamped else block_start, FIRST_STAMP[resolution])
        high = min(block_end if end_stamped else advance(block_end, resolution, -1), ended)
        if low <= high:
            chunks.append(Chunk(low, high))
    return chunks


def _exact(
    first: dt.datetime, last: dt.datetime, resolution: Resolution, stations: int, parameters: int
) -> list[tuple[Chunk, int]]:
    """Cut the stamps from `first` to `last` into as few requests as the limit allows, for some stations.

    As many stations go in a request as fit, and as many stamps as fit beside them.
    """
    group = min(stations, max(1, MAX_POINTS // max(parameters, 1)))
    stamps = max(1, MAX_POINTS // (group * max(parameters, 1)))
    chunks = []
    current = first
    while current <= last:
        end = min(advance(current, resolution, stamps - 1), last)
        chunks.append((Chunk(current, end), group))
        current = advance(end, resolution)
    return chunks


def _requests(plan: Sequence[tuple[Chunk, int]], stations: int) -> int:
    return sum(_ceil_div(stations / size) for _, size in plan)


def plan_requests(
    stations: int, first: dt.datetime, last: dt.datetime, resolution: Resolution, now: dt.datetime, parameters: int
) -> list[tuple[Chunk, int]]:
    """Plan the requests for a range of some stations: the chunks, and how many stations go in a request for each.

    One station gets the blocks of the calendar (`_aligned`), whose copies in the cache serve any query that overlaps
    them. Several stations get whichever of the blocks and of the exact range costs fewer requests, the blocks where the
    two cost the same: a day of every station at 10 minutes or hourly is one request of the stamps that were asked for,
    where it is a request for each pair of stations of a whole year in the blocks (`/locations/{ids}` and `/cube` cost
    the same, the limit counts the same points).
    """
    blocks = [
        (chunk, stations_per_request(chunk, resolution, parameters)) for chunk in _aligned(first, last, resolution, now)
    ]
    if stations == 1 or not blocks:
        return blocks
    ended = to_stamp(floor(now, resolution), resolution)
    exact = _exact(max(first, FIRST_STAMP[resolution]), min(last, ended), resolution, stations, parameters)
    return exact if _requests(exact, stations) < _requests(blocks, stations) else blocks


def room(stamps: int, parameters: int) -> int:
    """Say how many stations are read ahead with the one in hand for a range of `stamps`, by the memory they hold.

    No more than `STATIONS_AT_MOST` and `MEMORY_POINTS` allow: a long range is a station at a time, a day all of them.
    """
    return min(STATIONS_AT_MOST, max(1, MEMORY_POINTS // (max(stamps, 1) * max(parameters, 1))))


def estimate_requests(
    stations: int,
    first: dt.datetime,
    last: dt.datetime,
    resolution: Resolution,
    now: dt.datetime,
    parameters: int,
    *,
    batch: int | None = None,
) -> int:
    """Count the requests that reading `stations` for the stamps from `first` to `last` takes, as the walk makes them.

    The stations are read in batches (`room`, or `batch` where the caller reads fewer), each planned on its own
    (`plan_requests`), which is why 77 stations of 10 years of hourly values take more requests than the blocks of one
    station times the stations that fit a request.
    """
    size = batch or room(count_stamps(first, last, resolution), parameters)
    total = 0
    for start in range(0, stations, size):
        group = min(size, stations - start)
        total += _requests(plan_requests(group, first, last, resolution, now, parameters), group)
    return total


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
    the coverage leaves out (the station has no sensor for it) is a NaN, which is what the files held for it, and a null
    is a NaN (the files' `_FillValue`), so that both go on through the same step (`parser.knmi_readings`).

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
    """Read the values of a range as the files held them: a number, or NaN where the API has null."""
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
    """What was read of one station from the API."""

    frames: list[pl.DataFrame] = field(default_factory=list)


@dataclass(frozen=True)
class _Answer:
    frames: dict[str, pl.DataFrame]


@dataclass(frozen=True)
class _NoData:
    """The API has no data for the chunk (a 404): not an error, the chunk is empty."""


@dataclass(frozen=True)
class _TooBig:
    """The API refuses the chunk as it is (a 413): it is asked for in smaller parts."""


@dataclass(frozen=True)
class _Refused:
    """The API refuses the request (a 400 or a 422, an unknown station among those named): not by its size."""

    status: int
    detail: str = ""


class EdrReader:
    """Read the values of a range of some stations from the EDR API, for one query.

    A 413 is asked for again in smaller parts and a 404 is no data. A 400 or a 422 is a request the API refuses for a
    station that it does not know, as it names no station: the stations of the request are cut in two, until the one
    that
    is refused is alone, which is then left out for the rest of the query (`skipped`), with a warning, and never asked
    for again. Anything else that is no answer ends the query with an error (`raise_if_unanswered`): there is nowhere
    else
    to read it from.
    """

    def __init__(
        self,
        settings: Settings,
        expiry: Callable[[dt.datetime | None], CacheExpiry],
    ) -> None:
        """Hold the settings (the key of the API) and the rule for how long a chunk is kept."""
        self._settings = settings
        self._expiry = expiry
        #: the stations that the API refused, which are not asked for again
        self.skipped: set[str] = set()
        self._warned: set[str] = set()
        #: whether the API has answered a request of the query (data, or no data: a 404 is an answer to a request that
        #: was asked right), which a request that is refused for every station is not
        self._answered = False
        #: the stations refused alone before anything was answered, which wait to be told from a refusal that is no
        #: station's
        self._aside: dict[str, _Refused] = {}

    def read(  # noqa: C901
        self,
        stations: Sequence[tuple[str, str]],
        resolution: Resolution,
        parameters: Sequence[str],
        plan: Sequence[tuple[Chunk, int]],
    ) -> dict[str, Reading]:
        """Read the planned chunks for the stations, `(station_id, wsi)` each: what the API gave of each."""
        reads = {station_id: Reading() for station_id, _ in stations}
        queue: deque[tuple[Chunk, Group]] = deque()
        for chunk, size in plan:
            queue.extend((chunk, tuple(stations[i : i + size])) for i in range(0, len(stations), size))
        while queue:
            chunk, wanted = queue.popleft()
            group = tuple(
                station for station in wanted if station[0] not in self.skipped and station[0] not in self._aside
            )
            if not group:
                continue
            outcome = self._ask(chunk, group, resolution, parameters)
            if isinstance(outcome, (_Answer, _NoData)):
                self._answered = True
                self._skip_those_set_aside()
            if isinstance(outcome, _Answer):
                for station_id, _ in group:
                    if station_id in outcome.frames:
                        reads[station_id].frames.append(outcome.frames[station_id])
            elif isinstance(outcome, _TooBig):
                parts = self._smaller(chunk, group, resolution)
                if parts is None:
                    # one station and one stamp is the least a request can be: nothing else to try
                    raise DownloadError(
                        _without_url_secrets(EDR_BASE_URL),
                        "KNMI's EDR API refuses a request of one station and one stamp",
                    )
                queue.extendleft(reversed(parts))
            elif isinstance(outcome, _Refused):
                if len(group) > 1:
                    if self._aside and not self._answered:
                        # a second refusal of several stations with nothing answered: not about a station
                        raise self._not_a_station(next(iter(self._aside)), outcome)
                    middle = len(group) // 2
                    queue.extendleft(reversed([(chunk, group[:middle]), (chunk, group[middle:])]))
                elif self._answered:
                    self._skip(group[0][0], outcome)
                else:
                    # nothing is answered yet, so whether it is the station is not known: it waits, and the others go on
                    self._aside[group[0][0]] = outcome
        if self._aside:
            # the queue is drained and nothing was answered: the stations were not the cause
            raise self._not_a_station(next(iter(self._aside)), next(iter(self._aside.values())))
        return reads

    def _skip_those_set_aside(self) -> None:
        """Leave out the stations that were refused alone before anything was answered: it was them, after all."""
        aside, self._aside = self._aside, {}
        for station_id, outcome in aside.items():
            self._skip(station_id, outcome)

    def _skip(self, station_id: str, outcome: _Refused) -> None:
        """Leave a station out that the API refused alone, with a warning, unless that is a third one.

        KNMI answers 400 for an unknown parameter or datetime as well as for an unknown station, and names none of them
        where the client can read it. Once the API has answered a request of the query, a station refused alone is a
        station it does not know; a third one is more than that, and ends the query with the error.
        """
        if len(self.skipped) >= MAX_REFUSED_STATIONS:
            raise self._not_a_station(station_id, outcome)
        self.skipped.add(station_id)
        self._warn(
            f"KNMI's EDR API refused the request for the station {station_id} (status {outcome.status}), "
            "which is left out"
        )

    def _not_a_station(self, station_id: str, outcome: _Refused) -> DownloadError:
        """Give the error of a 400 that is no unknown station: what the client knows of it, and where to look."""
        return DownloadError(
            _without_url_secrets(EDR_BASE_URL),
            f"KNMI's EDR API answered {outcome.status} for the station {station_id}"
            + (f" ({outcome.detail})" if outcome.detail else "")
            + (
                ", and answered no request of the query"
                if not self._answered
                else f" after {len(self.skipped)} stations that it refused"
            )
            + ", which is more than a station it does not know: check the parameters and the dates asked for",
        )

    @staticmethod
    def _smaller(chunk: Chunk, group: Group, resolution: Resolution) -> list[tuple[Chunk, Group]] | None:
        """Cut a request that was refused as too big: its stations in two, or if it has one, its stamps."""
        if len(group) > 1:
            middle = len(group) // 2
            return [(chunk, group[:middle]), (chunk, group[middle:])]
        halves = chunk.halves(resolution)
        return None if halves is None else [(half, group) for half in halves]

    def _warn(self, reason: str) -> None:
        """Say a reason once for the query, each distinct one. The key is never in it."""
        if reason not in self._warned:
            self._warned.add(reason)
            log.warning(reason)

    def _ask(
        self, chunk: Chunk, group: Group, resolution: Resolution, parameters: Sequence[str]
    ) -> _Answer | _NoData | _TooBig | _Refused:
        """Ask the API for a chunk of the stations of a group, or find the answer of it in the cache."""
        settings = self._settings
        wsis = [wsi for _, wsi in group]
        url = request_url(COLLECTION_BY_RESOLUTION[resolution], wsis, parameters, chunk, resolution)
        ttl = self._expiry(to_edr_stamp(chunk.last, resolution))
        file = fetch(url, settings, ttl)
        if isinstance(file.content, Exception):
            raise_if_unanswered(file)
            if file.status == 404:
                return _NoData()
            if file.status == 413:
                return _TooBig()
            return _Refused(file.status, _without_url_secrets_in(str(file.content))[:200])
        try:
            return _Answer(parse_coverage_json(file.content.read(), parameters, resolution))
        except UnusableAnswerError as error:
            # a 200 that is no CoverageJSON would be served from the cache for as long as it is kept
            drop_cached_file(
                url,
                settings.cache_dir,
                ttl,
                client_kwargs(settings),
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            raise DownloadError(
                _without_url_secrets(url), f"KNMI's EDR API answered something that is no CoverageJSON ({error})"
            ) from None
