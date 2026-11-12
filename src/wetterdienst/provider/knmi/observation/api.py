# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KNMI (Netherlands) observation data provider.

Unlike every other provider in this package, KNMI's modern Data Platform has no
per-station history endpoint at all: each dataset file covers a single timestamp for
every station in the network at once. There's no OPeNDAP/THREDDS/Zarr access either
(confirmed against KNMI's own API docs) -- the only way to get a station's time series
is to download one whole file per timestamp needed and extract that station's row. A
30-day hourly query is 720 individual file downloads (each needing its own
list-then-resolve-then-download round trip); a multi-year range is impractical. This
is a real, documented characteristic of KNMI's API, not a shortcut taken here.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import re
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, ClassVar, cast

import polars as pl
import stamina

from wetterdienst.exceptions import (
    CredentialMissingError,
    CredentialRejectedError,
    DownloadError,
    NoInternetError,
    UpstreamError,
)
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.knmi.observation.metadata import KnmiObservationMetadata
from wetterdienst.provider.knmi.observation.parser import (
    decode_str,
    open_netcdf,
    parse_knmi_netcdf,
    public_station_id,
    station_wsis,
)
from wetterdienst.settings import reveal
from wetterdienst.util.network import (
    CREDENTIAL_REJECTED_STATUSES,
    RedirectRefusedError,
    _without_url_secrets,
    _without_url_secrets_in,
    as_outage,
    credential_rejected,
    download_file,
    drop_cached_file,
    fetchable_link,
    read_cached_copy,
    skip_cause_of_failure,
)
from wetterdienst.util.response_warnings import note_skipped_download

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.settings import Settings
    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

_BASE_URL = "https://api.dataplatform.knmi.nl/open-data/v1"

_DATASET_BY_RESOLUTION = {
    Resolution.MINUTE_10: ("10-minute-in-situ-meteorological-observations", "1.0"),
    Resolution.HOURLY: ("hourly-in-situ-meteorological-observations-validated", "1.0"),
    Resolution.DAILY: ("daily-in-situ-meteorological-observations-validated", "1.0"),
    Resolution.MONTHLY: ("monthly-in-situ-meteorological-observations-validated", "1.0"),
    Resolution.ANNUAL: ("annual-in-situ-meteorological-observations-validated", "1.0"),
}

#: The catalogue of the stations of KNMI's network ("Meteo data - information on stations in the KNMI observations
#: network", https://dataplatform.knmi.nl/dataset/waarneemstations-csv-1-0): one small CSV file (7.7 kB, 77 stations)
#: for every date a station was opened, closed or moved, named `csv_knmi_nl_YYYYMMDD.csv`. It is served by the same API
#: and with the same key as the observations (read 2026-11-11), so the list of the stations needs no second key.
_STATIONS_DATASET = ("waarneemstations_csv", "1.0")

#: How long the file of the catalogue of the stations is kept. A file is made only when a station is opened, closed or
#: moved (four in the 20 months to 2026-07: made 2024-11-22, 2025-11-28, 2026-03-09 and 2026-07-07, the last for 15
#: June), and KNMI replaces one in place now and then (the file of 2024-10-31 was made on 2024-11-12 and replaced on
#: 2024-11-22), so the copy of a name is kept a week, which costs nothing: the download is free and the one list
#: serves every resolution.
_CATALOGUE_EXPIRY = CacheExpiry.ONE_WEEK

#: How long the listing that names the newest file of the catalogue is kept: a request of the quota each time. KNMI
#: publishes the catalogue weeks after the date in its name (the file of 2026-06-15 was made on 2026-07-07), so a
#: station it has just added must not stay out of the list for a week more: half a day, as the other listings of the
#: provider that name a file that may be there since.
_CATALOGUE_LISTING_EXPIRY = CacheExpiry.TWELVE_HOURS

#: How long after the stop date of a closed station of the catalogue its record may run, which is added to it to give
#: `end_timestamp`: Soesterberg's data is in the monthly file of 2008-12 and not in that of 2009-01, 46 days after its
#: stop date of 2008-11-15, and the listings cut a window with a buffer of their own (`limit_to_window`) on top of it.
_CLOSED_MARGIN = dt.timedelta(days=62)

#: The first day of the data of each dataset (the name of its oldest file, read 2026-11-11): a station that was
#: closed before it has none in it. The 10-minute files start in 2012, the stations before the 1990s are in the others.
_DATASET_START = {
    Resolution.MINUTE_10: dt.date(2012, 1, 1),
    Resolution.HOURLY: dt.date(1951, 1, 1),
    Resolution.DAILY: dt.date(1901, 1, 1),
    Resolution.MONTHLY: dt.date(1901, 1, 1),
    Resolution.ANNUAL: dt.date(1901, 1, 1),
}

#: The types of station of the catalogue (compared stripped and in lower case) that only the 10-minute files hold: the
#: four fog stations (Assendelft 06233, Muiden 06236, Nieuw-Vennep 06237 and Nieuwkoop 06238) are in the 10-minute
#: files of 2014 to 2024 and in none of the 37 hourly, daily, monthly and annual files of 1901 to 2026 that were read
#: (2026-11-11). "Fog station/Meteo site" (Voorschoten 06215) is in them all and is not this type.
_TEN_MINUTE_ONLY_TYPES = frozenset({"fog station"})

#: The WMO blocks of the stations a dataset does not hold although the catalogue lists them: block 78, the Caribbean
#: Netherlands (Saba 78871, Sint Eustatius 78873, Bonaire 78990), is in the hourly, daily and monthly files of 2026 and
#: in none of the annual files of 2010, 2015, 2017, 2020, 2022, 2024 and 2025 (read 2026-11-11), which a listing near
#: Bonaire then answered with three stations that have no data.
_BLOCKS_NOT_IN_DATASET = {Resolution.ANNUAL: ("78",)}

#: The datasets whose files are named for a period (a month, a year) or a date and not for the moment they were made:
#: the latest file is the last period, which is not always the one made last (the annual file of 2023 was made after
#: those of 2024 and 2025, and the catalogue file of 2012-01-01 after those of 2023, read 2026-11-11)
_LATEST_BY_FILENAME = frozenset(
    (
        *(_DATASET_BY_RESOLUTION[resolution][0] for resolution in (Resolution.MONTHLY, Resolution.ANNUAL)),
        _STATIONS_DATASET[0],
    )
)

_STEP_BY_RESOLUTION = {
    Resolution.MINUTE_10: dt.timedelta(minutes=10),
    Resolution.HOURLY: dt.timedelta(hours=1),
    Resolution.DAILY: dt.timedelta(days=1),
}

#: The periods of a month and of a year, which are no fixed length
_CALENDAR_RESOLUTIONS = (Resolution.MONTHLY, Resolution.ANNUAL)

#: What a download of KNMI returns when it is not an answer to the request, and must be raised: no connection,
#: no answer, a refused key.
_UNANSWERED = (NoInternetError, DownloadError, CredentialRejectedError)

_NON_RETRYABLE_STATUSES = {400, 401, 403, 404}
_RETRY_WAIT_INITIAL_SECONDS = 2
_RETRY_WAIT_MAX_SECONDS = 15
_RETRY_MAX_RETRIES = 2


class _KnmiRetryableError(Exception):
    """Internal signal used to trigger a stamina retry on a retryable KNMI failure."""


def _filename_for(resolution: Resolution, moment: dt.datetime) -> str:
    if resolution == Resolution.MINUTE_10:
        return f"KMDS__OPER_P___10M_OBS_L2_{moment:%Y%m%d%H%M}.nc"
    if resolution == Resolution.HOURLY:
        return f"hourly-observations-validated-{moment:%Y%m%d}-{moment:%H}.nc"
    if resolution == Resolution.DAILY:
        return f"daily-observations-validated-{moment:%Y%m%d}.nc"
    if resolution == Resolution.MONTHLY:
        return f"monthly-observations-validated-{moment:%Y%m}.nc"
    return f"annual-observations-validated-{moment:%Y}.nc"


def _floor(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Snap a moment down to its resolution's interval boundary (:X0 / :00 / midnight / the 1st / 1 January)."""
    if resolution == Resolution.MINUTE_10:
        return moment.replace(minute=moment.minute - moment.minute % 10, second=0, microsecond=0)
    if resolution == Resolution.HOURLY:
        return moment.replace(minute=0, second=0, microsecond=0)
    if resolution == Resolution.MONTHLY:
        return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if resolution == Resolution.ANNUAL:
        return moment.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _advance(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Move a moment on its boundary to the next one: the next 10 minutes, hour, day, month or year."""
    if resolution == Resolution.MONTHLY:
        return moment.replace(year=moment.year + moment.month // 12, month=moment.month % 12 + 1)
    if resolution == Resolution.ANNUAL:
        return moment.replace(year=moment.year + 1)
    return moment + _STEP_BY_RESOLUTION[resolution]


def _resolution_of(parameter_or_dataset: ParameterModel | DatasetModel) -> Resolution:
    """Return the Resolution enum for a parsed parameter or whole-dataset selection."""
    dataset = parameter_or_dataset.dataset if isinstance(parameter_or_dataset, ParameterModel) else parameter_or_dataset
    return dataset.resolution.value


def _ceil(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Snap a moment up to its resolution's interval boundary, the moment itself if it is on one."""
    floored = _floor(moment, resolution)
    return floored if floored == moment else _advance(floored, resolution)


def _stamp(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Return the `timestamp` of the values in the file that is named for `moment`.

    KNMI stamps the values of a file with the END of the interval they cover ("The timestamp in the files indicates the
    end of the measuring interval preceding that timestamp"), and the three datasets name their files differently
    (GH-2824). Read from real files on 2026-10-18 (De Bilt, 2026-10-14):

    - 10 minutes: the name is the end. `KMDS__OPER_P___10M_OBS_L2_202610140900.nc` has the time coordinate 09:00
      ("the end of the 10-minute measurement interval") and `ta` 14.7 degC, NOAA GHCNh De Bilt at 09:00 UTC; the
      files named 08:50 and 09:10 hold 14.6 and 15.2. So the name is the stamp (the dataset page's example table
      has a file named 2350 with the timestamp 00:00; the real files do not).
    - hourly: the name is the START of the hour. `hourly-observations-validated-20261014-08.nc` has the time
      coordinate 09:00 and `T` 14.7 degC, the same as the 10-minute file named 09:00 and GHCNh at 09:00, so its
      stamp is the name plus one hour (over the five hours read, 08 to 12: 0.0 K against GHCNh at the coordinate,
      1.2 K at the name).
    - daily: the name is the date, the time coordinate is the end of that UTC day (the next 00:00); the value is
      stamped with the date, as for every provider (`TG` 11.5 of `daily-observations-validated-20261014.nc` is the
      value of 20261014 in the legacy export).
    - monthly and annual: the name is the period, the time coordinate is the end of it (the 1st of the next month,
      1 January of the next year, 00:00 UTC; long_name 'Time (in UTC) indicating the end of the monthly measurement
      interval'). Read from real files on 2026-11-11: `monthly-observations-validated-202609.nc` has the time
      2026-10-01, `-190101.nc` 1901-02-01, `annual-observations-validated-2024.nc` 2025-01-01 and `-1901.nc` 1902-01-01.
      The value is stamped with the first day of the period, as for the daily file, and as every provider labels a
      month and a year.
    """
    return moment + dt.timedelta(hours=1) if resolution == Resolution.HOURLY else moment


def _moments(start_date: dt.datetime, end_date: dt.datetime, resolution: Resolution) -> Iterator[dt.datetime]:
    """Yield the moments that name the files whose values are stamped within [start_date, end_date].

    Only a file whose interval has ended can exist: the hour, the day, the month or the year that is still running has
    no file yet (the annual file of the year that is running is made in the next one), so the moments stop at the first
    one whose interval ends after now (`_end_of`), with no request and so no 404 that would be reported as a file
    skipped, a partial answer to try again later (GH-4008). The running 10 minutes or hour of a range that reaches
    now are asked for as soon as they have ended, which is when their file is made.
    """
    if resolution == Resolution.HOURLY:
        # the hour that ends at the first stamp at or after start_date (its file is named for the start of it)
        current = _ceil(start_date, resolution) - _STEP_BY_RESOLUTION[resolution]
    elif resolution in _CALENDAR_RESOLUTIONS:
        # a month or a year is stamped with its first day: the first one at or after start_date (the request has
        # floored a start that is alone in its resolution, as for a day; a start of a mixed request that is mid-month
        # leaves that month out, whose stamp is before it, as the framework's filter would)
        current = _ceil(start_date, resolution)
    elif resolution == Resolution.MINUTE_10:
        # 10-minute filenames encode the minute, so an unaligned start would not resolve -- floor it (the over-fetched
        # pre-start file is trimmed by the framework's [start, end] filter)
        current = _floor(start_date, resolution)
    else:
        # a daily file is stamped with its own date. When the whole request is daily, __post_init__ has already floored
        # start to the day so the moments are aligned; a mixed request keeps the (harmless) unaligned label
        current = start_date
    now = _now()
    while _stamp(current, resolution) <= end_date:
        interval_end = _end_of(_filename_for(resolution, current))
        if interval_end is not None and interval_end > now:
            return
        yield current
        current = _advance(current, resolution)


#: How old the end of the interval a file covers must be for its content to be kept long. Before it a file is kept for
#: five minutes, as it always was (GH-3927): the line was drawn at six hours, and it is no measured moment of settling.
#: What was measured (2026-11-11) is that the hourly files are made 5.5 to 78 hours after their hour, at a median of
#: 25, so most do not exist yet at six hours
_SETTLED_AFTER = dt.timedelta(hours=6)


def _now() -> dt.datetime:
    """Give the time the age of a file is taken against (a seam for a test, which pins it)."""
    return dt.datetime.now(dt.UTC)


def _file_expiry(end: dt.datetime | None) -> CacheExpiry:
    """Say how long the content of a file is kept, by the end of the interval it covers (`_end_of`, GH-3927).

    A file whose end is younger than `_SETTLED_AFTER` is kept for `CacheExpiry.FIVE_MINUTES`, as it was before:
    it is fetched again for what KNMI has added since. An older one is kept for `CacheExpiry.TWELVE_HOURS`. That is
    no claim that it is final, for no age makes a file so (GH-4008, read 2026-11-11 from the `lastModified` of the
    newest 1,000 hourly and daily files, all monthly and all annual ones):

    - KNMI validates the hourly and the daily files one to four weeks after their period and replaces them then, in
      batches: 408 hourly files of 15 to 31 October on 10 and 11 November, 21 daily files of 15 October to 4 November
      on 10 November, 15 of 1 to 15 September on 24 September, 15 of 11 to 26 August on 31 August.
    - It corrects older files now and then: 349 daily files were replaced more than a week after their day, 251 of
      them on 18 September 2025, nine days after the archive was loaded, and the rest on 18 other days, a few at a
      time. Of the 1,510 monthly files 4 were replaced after they were made (1976-06 on 24 September, 2026-01 on 29
      September, 2026-09 six hours later, 2026-10 eight days later), of the 125 annual ones 1.

    So the twelve hours are no longer than a replaced file takes to be read again: the cap, not the age, limits how
    stale a copy is, and a shorter one would only repeat requests (one each) for files that change once, weeks away.
    A file whose end is not known counts as young.
    """
    if end is None:
        return CacheExpiry.FIVE_MINUTES
    if end.tzinfo is None:
        end = end.replace(tzinfo=dt.UTC)
    if _now() - end < _SETTLED_AFTER:
        return CacheExpiry.FIVE_MINUTES
    return CacheExpiry.TWELVE_HOURS


#: The moment a filename is named for, as `_filename_for` writes it: the 10-minute, the hourly, the daily, the monthly
#: and the annual layout
_FILENAME_MOMENT = re.compile(r"(?:_(\d{12})|-(\d{8}-\d{2})|-(\d{8})|-(\d{6})|-(\d{4}))\.nc$")

#: What a file's name says of the interval it covers, by layout: how the name reads, and the resolution whose step is
#: the interval after the moment of the name (`_stamp`: the 10-minute name is the end, the hourly name the start of its
#: hour, the daily name the date of a day that ends 24 hours later, the monthly and the annual name the first day of
#: a month and of a year, which end at the next 1st and the next 1 January)
_INTERVAL_OF_NAME = (
    ("%Y%m%d%H%M", None),
    ("%Y%m%d-%H", Resolution.HOURLY),
    ("%Y%m%d", Resolution.DAILY),
    ("%Y%m", Resolution.MONTHLY),
    ("%Y", Resolution.ANNUAL),
)


def _end_of(filename: str) -> dt.datetime | None:
    """Read from its name where the interval a file covers ends, in UTC; None for a name that has no moment.

    The end, because KNMI fills a file in until its interval is over: the stamp of an hourly value is the end of
    its hour (`_stamp`), so a file named for the start of an hour ends an hour after the name, a daily file
    ends at the next midnight, a monthly one at the start of the next month and an annual one at the next 1 January.
    This is what the age of a file is taken from, whichever label the reader asked it
    by (a mixed request keeps an unaligned daily label), and for a file only known by name (the latest of a listing).
    """
    found = _FILENAME_MOMENT.search(filename)
    if found is None:
        return None
    for text, (layout, resolution) in zip(found.groups(), _INTERVAL_OF_NAME, strict=True):
        if text is not None:
            start = dt.datetime.strptime(text, layout).replace(tzinfo=dt.UTC)
            return start if resolution is None else _advance(start, resolution)
    return None


def _forget_file(dataset_name: str, version: str, filename: str, settings: Settings) -> None:
    """Drop the copy kept for a file, so that the next read asks KNMI again. Never raises.

    For a body that arrived (a 200) and is no file the reader can open: it would be served until it expires, up to 12
    hours (a week for the catalogue). Dropped from the directory of every expiry, since the age that chose one moves.
    """
    for expiry in (CacheExpiry.FIVE_MINUTES, CacheExpiry.TWELVE_HOURS, _CATALOGUE_EXPIRY):
        drop_cached_file(
            _file_key(dataset_name, version, filename),
            settings.cache_dir,
            expiry,
            settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )


@contextlib.contextmanager
def _forgotten_if_unreadable(dataset_name: str, version: str, filename: str, settings: Settings) -> Iterator[None]:
    """Run the read of a file's bytes, and drop the copy (`_forget_file`) if the reader fails on them, then raise."""
    try:
        yield
    except Exception:
        _forget_file(dataset_name, version, filename, settings)
        raise


def _file_key(dataset_name: str, version: str, filename: str) -> str:
    """Name a file by its dataset, version and filename: the KNMI API's address of the file, which is never asked for.

    The name its content is kept under, which no resolve changes and which holds no secret (`_fetch_netcdf`). The
    resolve of its download link is this and `/url`.
    """
    return f"{_BASE_URL}/datasets/{dataset_name}/versions/{version}/files/{filename}"


def _download_with_retry(
    url: str,
    settings: Settings,
    ttl: CacheExpiry,
    *,
    client_kwargs: dict | None = None,
    fetch_url: str | None = None,
) -> File:
    """Download a URL, retrying on retryable failures (rate limiting, transient network errors).

    `fetch_url` is where a copy that is not held is fetched from, where `url` is the name it is kept under.

    Mirrors AEMET's retry design: a deliberately modest couple of short-backoff
    retries, not an attempt to wait out a sustained outage. A failure `download_file`
    classes as no network (`File.is_no_internet_error`) is not retried here.
    """
    last_file: File | None = None
    with contextlib.suppress(_KnmiRetryableError):
        for attempt in stamina.retry_context(
            on=_KnmiRetryableError,
            attempts=_RETRY_MAX_RETRIES + 1,
            timeout=None,
            wait_initial=_RETRY_WAIT_INITIAL_SECONDS,
            wait_max=_RETRY_WAIT_MAX_SECONDS,
        ):
            with attempt:
                last_file = download_file(
                    url=url,
                    cache_dir=settings.cache_dir,
                    ttl=ttl,
                    client_kwargs=client_kwargs if client_kwargs is not None else settings.fsspec_client_kwargs,
                    cache_disable=settings.cache_disable,
                    use_certifi=settings.use_certifi,
                    fetch_url=fetch_url,
                )
                # no network is not a blip two more retries clear: report it at once (the 503
                # `download_file` gives it would otherwise match)
                if (
                    isinstance(last_file.content, Exception)
                    and not last_file.is_no_internet_error
                    and not isinstance(last_file.content, RedirectRefusedError)
                    and last_file.status not in _NON_RETRYABLE_STATUSES
                ):
                    log.warning(
                        f"Retryable KNMI failure (status={last_file.status}) for {_without_url_secrets(url)}: "
                        f"{_without_url_secrets_in(str(last_file.content))}; retrying",
                    )
                    raise _KnmiRetryableError(_without_url_secrets(url))
    if last_file is None:
        msg = "unreachable: stamina.retry_context always runs at least once"
        raise AssertionError(msg)
    return last_file


class _UnusableError(Exception):
    """An answer of KNMI that is no answer to the request: a listing that lists no file or is no listing at all."""


def _key_rejected(status: int) -> CredentialRejectedError:
    """Say that KNMI refuses the API key, which is sent to the request that asks for a file or a listing (GH-3018)."""
    return credential_rejected("KNMI", "KNMI", "API key", status)


def _latest_filename(
    dataset_name: str, version: str, settings: Settings, ttl: CacheExpiry = CacheExpiry.ONE_HOUR
) -> str | Exception:
    """Look up the most recently published file in a dataset, the listing being kept for `ttl`.

    "Validated" datasets lag well behind real time (observed: ~1-2 days for hourly),
    so guessing a fixed offset from now() isn't reliable -- ask the API directly.
    """
    order_by = "filename" if dataset_name in _LATEST_BY_FILENAME else "created"
    url = f"{_BASE_URL}/datasets/{dataset_name}/versions/{version}/files?maxKeys=1&orderBy={order_by}&sorting=desc"
    client_kwargs = {
        **settings.fsspec_client_kwargs,
        "headers": {**settings.fsspec_client_kwargs.get("headers", {}), "Authorization": reveal(settings.auth.knmi)},
    }
    file = _download_with_retry(url, settings, ttl, client_kwargs=client_kwargs)
    if isinstance(file.content, Exception):
        if file.status in CREDENTIAL_REJECTED_STATUSES:
            return _key_rejected(file.status)
        return as_outage(file.content, file.url)
    # a 200 that is no listing (an HTML page, a changed API) is kept as the listing for the whole `ttl`, and would be
    # read back as often as it is asked for: it is dropped, and answered as what it is
    try:
        files = json.load(file.content).get("files", [])
        filename = files[0]["filename"] if files else None
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        drop_cached_file(
            url,
            settings.cache_dir,
            ttl,
            client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        return _UnusableError(f"the listing of {dataset_name} is no list of files ({type(error).__name__})")
    if filename is None:
        return _UnusableError("no files found")
    if not isinstance(filename, str):
        return _UnusableError(f"the listing of {dataset_name} names a file that is no name")
    return filename


def _fetch_netcdf(
    dataset_name: str, version: str, filename: str, settings: Settings, expiry: CacheExpiry | None = None
) -> bytes | Exception:
    """Read a dataset file from the cache, or resolve a temporary download URL for it and download it.

    A file of an observation dataset is kept as `_file_expiry` says, by the interval its name gives. `expiry` is for a
    file that has none (the CSV of the catalogue of the stations, `_station_catalogue`), which is kept for that long.

    The resolve step needs the API key (in the Authorization header); the resulting
    temporary S3 URL is pre-signed and needs no auth of its own.

    A failure is returned, not raised. One that is no answer -- a timeout, a dropped connection, a
    body cut short, a 5xx -- is returned as the `DownloadError` naming the file (`as_outage`, GH-2965),
    a failed connection as the `NoInternetError`; the caller raises those. A 404 (a timestamp that is
    not published) and any other 4xx, a 429 among them, are returned as they came. A 401 or 403 of the
    request that carries the key is the `CredentialRejectedError` (GH-3018), returned like the others;
    the same status of the pre-signed link says nothing of the key and is returned as it came.

    Each KNMI file covers the whole network for one timestamp, but the framework collects
    values per station, so the same file would otherwise be downloaded once per station, and
    again by every later query. Its content is kept under a name made of its dataset, version and
    filename (`_file_key`), not under the pre-signed URL, which is made anew by every resolve and is
    gone within the hour (GH-3927): for 12 hours if the interval the file covers ended more than six hours ago,
    for 5 minutes if it ended later, as KNMI may still fill it in (`_end_of` reads the end from the name,
    `_file_expiry` says how long). A body the reader cannot open is dropped by the caller (`_forget_file`).
    A copy that is held is returned without a request to KNMI, resolve included. Only a miss resolves a
    link, which is cached for minutes (within them every station of a query is handed the same one) and
    is fetched once for the copy. With `cache_disable` no copy is held, as for every download.

    The pre-signed URL is a secret for the hour it lasts: it is in the local cache (the resolve response
    holds it), and in no log line and no error, which show it without its query (GH-3341). The copy
    is named by the key, so the metadata file of the cache does not hold it. fsspec's own debug line of
    a request is not ours to change.
    """
    key = _file_key(dataset_name, version, filename)
    if expiry is None:
        expiry = _file_expiry(_end_of(filename))
    kept = read_cached_copy(
        key,
        settings.cache_dir,
        expiry,
        settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    if kept is not None:
        return kept
    resolve_url = f"{key}/url"
    client_kwargs = {
        **settings.fsspec_client_kwargs,
        "headers": {**settings.fsspec_client_kwargs.get("headers", {}), "Authorization": reveal(settings.auth.knmi)},
    }
    resolve_file = _download_with_retry(resolve_url, settings, CacheExpiry.FIVE_MINUTES, client_kwargs=client_kwargs)
    if isinstance(resolve_file.content, Exception):
        # only the request that carries the key says anything about it: a refusal of the pre-signed link
        # below (an expired signature) is a file that is not served
        if resolve_file.status in CREDENTIAL_REJECTED_STATUSES:
            return _key_rejected(resolve_file.status)
        return as_outage(resolve_file.content, resolve_file.url)
    # a 200 with an unexpected body (throttling notice, API change) must not KeyError out of
    # the per-moment loop and abort the whole query -- surface it as a skippable failure.
    download_url = json.load(resolve_file.content).get("temporaryDownloadUrl")
    if not download_url:
        return _UnusableError(f"KNMI resolve response for {filename} did not contain a temporaryDownloadUrl")
    try:
        # the link is the resolve answer's to name: fetched at the hosts of KNMI, its API and the store that signs
        # the link (`PROVIDER_HOSTS`, GH-3339)
        download_url = fetchable_link(download_url, _BASE_URL)
    except DownloadError as refused:
        # the resolve answer is cached for minutes, and would hand out the same link again
        drop_cached_file(
            resolve_file.url,
            settings.cache_dir,
            CacheExpiry.FIVE_MINUTES,
            client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        return refused
    content_file = _download_with_retry(key, settings, expiry, fetch_url=download_url)
    if isinstance(content_file.content, Exception):
        return as_outage(content_file.content, content_file.url)
    return content_file.content.read()


class KnmiObservationValues(TimeseriesValues):
    """Values class for KNMI observation data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
            parameter_names = [parameter.name_original for parameter in dataset.parameters]
        elif isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
            parameter_names = [parameter_or_dataset.name_original]
        else:
            return pl.DataFrame()

        settings = cast("Settings", self.sr.request.settings)
        start_date = self.sr.start
        end_date = self.sr.end
        if not start_date or not end_date or not settings.auth.knmi:
            return pl.DataFrame()

        resolution = dataset.resolution.value
        dataset_name, version = _DATASET_BY_RESOLUTION[resolution]

        frames = []
        for moment in _moments(start_date, end_date, resolution):
            filename = _filename_for(resolution, moment)
            payload = _fetch_netcdf(dataset_name, version, filename, settings)
            if isinstance(payload, _UNANSWERED):
                # offline, every remaining moment would fail the same way (and an hourly month
                # is 720 of them), nor would the next station's: the request ends here, with the
                # error, rather than with the moments read (GH-2620, GH-2640). The same for a
                # KNMI that does not answer -- a timeout, a dropped connection, a body cut short
                # or a 5xx that the retries above did not clear: a range read in part is not an
                # answer, and an empty one would read as a station without data (GH-2965). And for a
                # key KNMI refuses, which every moment and station would meet again (GH-3018)
                raise payload
            if isinstance(payload, Exception):
                # a single missing timestamp (a 404) or one that KNMI refused (a 429, an answer)
                # shouldn't sink the whole range
                note_skipped_download(skip_cause_of_failure(payload))
                log.warning(
                    f"Failed to acquire KNMI data for station {station_id}, file {filename}: "
                    f"{_without_url_secrets_in(str(payload))}"
                )
                continue
            with _forgotten_if_unreadable(dataset_name, version, filename, settings):
                df = parse_knmi_netcdf(
                    payload,
                    station_id,
                    parameter_names,
                    _stamp(moment, resolution),
                    trace_codes=resolution not in _CALENDAR_RESOLUTIONS,
                )
            if not df.is_empty():
                frames.append(df)
        # every frame from parse_knmi_netcdf shares the same (timestamp, parameter, value, quality_flags) schema
        return pl.concat(frames) if frames else pl.DataFrame()


def _read_station_catalogue(payload: bytes) -> pl.DataFrame:
    """Read the CSV of the catalogue into one row for each station, with the columns of the station list.

    The columns of the file (read 2026-11-11, 77 rows)::

        STN,WSI,STARTT,STOPT,LOCATIE,TYPE,HOOGTE,POS_X,POS_Y,POS_NB,POS_OL
        260,0-20000-0-06260,1896-04-01,9999-12-31,De Bilt,Meteo site,1.9,140.78,456.76,52.0989,5.1797

    `STN` is the number without its zeros (260), the WSI at its tail has them (06260): `station_id` is the tail of the
    WSI, as it is in the files. `POS_NB` and `POS_OL` are the latitude and the longitude (`POS_X` and `POS_Y` the
    Dutch grid), `HOOGTE` the height in metres, `STOPT` the day the station was closed (9999-12-31 for one that is
    open).

    `STARTT` is not read: it is the start of the station as it is now, not of the data of its predecessors (Schiphol's
    data begins in 1951 and its `STARTT` is 1990-07-01, De Kooy's before 1955-12-25 and Eelde's before 1948-08-01: 15
    of the 77 in the 37 files read), so a `start_timestamp` made of it would hide data from a window before it.

    `STOPT` is no exact end either (Soesterberg's data runs to the end of 2008 past its 2008-11-15, F16-A's ends before
    its 2020-09-01), so a closed station's `end_timestamp` is its `STOPT` and `_CLOSED_MARGIN` more, and an open one has
    none. A listing for a window (`limit_to_window`) then leaves out a station closed long before it (Soesterberg
    from a window in 2026), which with no end it kept, and no window the data is in is cut.

    Raises:
        UpstreamError: the file lacks a column, or a row.

    """
    df = pl.read_csv(BytesIO(payload), infer_schema=False, encoding="utf8-lossy")
    needed = {"WSI", "STOPT", "LOCATIE", "TYPE", "HOOGTE", "POS_NB", "POS_OL"}
    if not needed <= set(df.columns) or df.is_empty():
        msg = "The KNMI catalogue of the stations lacks a column or has no station."
        raise UpstreamError(msg)
    return df.select(
        pl.col("WSI").str.split("-").list.last().alias("station_id"),
        pl.col("WSI").alias("wigos_id"),
        pl.col("LOCATIE").str.strip_chars().alias("name"),
        pl.col("POS_NB").cast(pl.Float64, strict=False).alias("latitude"),
        pl.col("POS_OL").cast(pl.Float64, strict=False).alias("longitude"),
        pl.col("HOOGTE").cast(pl.Float64, strict=False).alias("elevation"),
        pl.col("TYPE").alias("type"),
        # 9999-12-31 is "not closed"
        pl.col("STOPT")
        .str.to_date("%Y-%m-%d", strict=False)
        .pipe(lambda day: pl.when(day.dt.year() < 9999).then(day))
        .alias("closed"),
    ).with_columns(
        (pl.col("closed").cast(pl.Datetime("us")) + pl.lit(_CLOSED_MARGIN))
        .dt.replace_time_zone("UTC")
        .alias("end_timestamp"),
    )


def _station_catalogue(settings: Settings) -> pl.DataFrame | None:
    """Read the newest catalogue of the stations of KNMI, None where there is none to be read (GH-4008).

    The stations were the ones of the latest file of a resolution, which is no list of the stations that have data: a
    file holds the stations that reported in its interval, so the latest 10-minute file held 57 stations where those of
    2024 held 69 and the 12 years of them 76 of the 77, and a station that was closed has no file in which it is
    found at all (Valkenburg 06210 until 2016, Soesterberg 06265 until 2008, whose data is there). The catalogue lists
    every station there was, with the name and the position that it has now, which is the newest one: a station that
    was moved or renamed is listed as it is in the newest catalogue, which the files since agree with (De Bilt was
    "DE BILT AWS" in the files until late 2024; Eindhoven 06370 moved from 51.4497, 5.3769 to 51.4631, 5.3856 and
    Deelen 06275 from 52.0547, 5.8722 to 52.0589, 5.8731, which the files carry as it was until June 2026 and the
    newest of 10 November carries as it is). It costs the same two requests whatever the resolutions asked for.

    A KNMI that does not answer, no network or a key it refuses is raised as everywhere else. A catalogue that is gone
    (a 404, no file listed) or is no file this reads (a listing or a CSV that is none) is None, and the stations are
    read from the latest files as they were (`KnmiObservationRequest._station_frame`). One that KNMI refuses to serve
    (a 429, another 4xx) is the empty frame, warned about once, as it was for the latest file: the files would be asked
    of an API that has just refused, two requests of the quota for each resolution.
    """
    dataset_name, version = _STATIONS_DATASET
    filename = _latest_filename(dataset_name, version, settings, _CATALOGUE_LISTING_EXPIRY)
    if isinstance(filename, _UNANSWERED):
        raise filename
    if isinstance(filename, Exception):
        return _without_catalogue(filename, "Failed to look up the latest KNMI catalogue of the stations")
    payload = _fetch_netcdf(dataset_name, version, filename, settings, _CATALOGUE_EXPIRY)
    if isinstance(payload, _UNANSWERED):
        raise payload
    if isinstance(payload, Exception):
        return _without_catalogue(payload, "Failed to fetch the KNMI catalogue of the stations")
    try:
        return _read_station_catalogue(payload)
    except (pl.exceptions.PolarsError, UpstreamError) as error:
        _forget_file(dataset_name, version, filename, settings)
        log.warning(f"The KNMI catalogue of the stations {filename} could not be read: {error}")
        return None


def _without_catalogue(failure: Exception, message: str) -> pl.DataFrame | None:
    """Warn that there is no catalogue to read, and say what the stations are then (`_station_catalogue`)."""
    log.warning(f"{message}: {_without_url_secrets_in(str(failure))}")
    gone = isinstance(failure, (FileNotFoundError, _UnusableError)) or getattr(failure, "status", None) == 404
    return None if gone else pl.DataFrame()


def _catalogue_stations(catalogue: pl.DataFrame, resolution: Resolution) -> pl.DataFrame:
    """Give the stations of the catalogue that have data at a resolution: without those that cannot."""
    df = catalogue.filter(pl.col("closed").is_null() | (pl.col("closed") >= _DATASET_START[resolution]))
    if resolution != Resolution.MINUTE_10:
        kind = pl.col("type").str.strip_chars().str.to_lowercase()
        df = df.filter(~kind.is_in(_TEN_MINUTE_ONLY_TYPES))
    for block in _BLOCKS_NOT_IN_DATASET.get(resolution, ()):
        df = df.filter(~pl.col("station_id").str.starts_with(block))
    return df.drop("type", "closed")


@dataclass
class KnmiObservationRequest(TimeseriesRequest):
    """Request class for KNMI observation data."""

    metadata = KnmiObservationMetadata
    _values = KnmiObservationValues

    # extend base columns of core class with the station's full WIGOS station identifier, of which
    # `station_id` is the trailing WMO number
    _base_columns: ClassVar = (
        *TimeseriesRequest._base_columns,  # noqa: SLF001
        "wigos_id",
    )

    @classmethod
    def is_configured(cls) -> bool:  # noqa: D102
        from wetterdienst.settings import Settings  # noqa: PLC0415

        return bool(Settings().auth.knmi)

    def __post_init__(self) -> None:  # noqa: D105
        super().__post_init__()
        settings = cast("Settings", self.settings)
        if not settings.auth.knmi:
            msg = (
                "KNMI Data Platform requires authentication. "
                "Request a free API key at https://developer.dataplatform.knmi.nl/ "
                "and set WD_AUTH__KNMI=<api_key> (env var) "
                "or Settings(auth={'knmi': '<api_key>'}) (Python)."
            )
            raise CredentialMissingError(msg)
        # When the whole request targets the daily resolution, snap start down to the day: a daily value is stamped
        # with its date, so a query beginning mid-day should include that day, and flooring start here (the one
        # filter the framework shares across resolutions) keeps the stamp on the date AND the day in range. The
        # 10-minute and the hourly values are stamped with the END of their interval (`_stamp`), so an unaligned
        # start correctly excludes the interval that ends before it (the framework's [start, end] filter does
        # that; `_moments` starts at the first stamp at or after it). A mixed-resolution request has no single
        # boundary and is left as-is.
        resolutions = {
            _resolution_of(parameter_or_dataset)
            for parameter_or_dataset in self.parameters
            if isinstance(parameter_or_dataset, (ParameterModel, DatasetModel))
        }
        # the same for a month and a year, which are stamped with their first day (`_stamp`)
        for resolution in (Resolution.DAILY, *_CALENDAR_RESOLUTIONS):
            if self.start and resolutions == {resolution}:
                self.start = _floor(cast("dt.datetime", self.start), resolution)

    def _all(self) -> pl.LazyFrame:
        """Enumerate stations per requested resolution, from the catalogue of the stations of KNMI.

        The catalogue is one list for every resolution (`_station_catalogue`), of which a resolution lists the stations
        that have data in its dataset (`_catalogue_stations`): the 10-minute network holds the fog stations that the
        other four do not, and no station of the 10-minute files closed before them. Where there is no catalogue to
        read, each file of KNMI lists the whole network for its own resolution and those inventories differ, so the
        stations are read from the latest file of each requested resolution.
        """
        settings = cast("Settings", self.settings)
        # in the order the request names them (a set would give the stations in the order of the hash seed of the
        # process, GH-3551)
        requested = dict.fromkeys(
            (parameter.dataset.resolution.value, parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        )
        catalogue = _station_catalogue(settings) if requested else None
        if catalogue is not None and catalogue.is_empty():
            # KNMI refused the catalogue: no stations, as for any other answer of it that is no list
            return pl.LazyFrame()
        station_frames: dict[Resolution, pl.DataFrame | None] = {}
        data = []
        for resolution, resolution_name, dataset in requested:
            if resolution not in station_frames:
                station_frames[resolution] = (
                    self._station_frame(resolution, settings)
                    if catalogue is None
                    else _catalogue_stations(catalogue, resolution)
                )
            df = station_frames[resolution]
            if df is None:
                continue
            data.append(
                df.with_columns(
                    pl.lit(resolution_name, dtype=pl.String).alias("resolution"),
                    pl.lit(dataset, dtype=pl.String).alias("dataset"),
                ),
            )
        if not data:
            return pl.LazyFrame()
        return pl.concat(data, how="diagonal").lazy()

    @staticmethod
    def _station_frame(resolution: Resolution, settings: Settings) -> pl.DataFrame | None:
        """Read the station inventory from the most recent file of the given resolution.

        What lists the stations where the catalogue cannot be read. It holds the stations that reported in that one
        file, which is not every station that has data (`_station_catalogue`).
        """
        dataset_name, version = _DATASET_BY_RESOLUTION[resolution]
        filename = _latest_filename(dataset_name, version, settings)
        # an unreachable KNMI is no network without stations (GH-2640), nor is one that does not answer
        # (GH-3022) or refuses the key (GH-3018)
        if isinstance(filename, _UNANSWERED):
            raise filename
        if isinstance(filename, Exception):
            log.warning(f"Failed to look up latest KNMI {resolution.value} file: {filename}")
            return None
        payload = _fetch_netcdf(dataset_name, version, filename, settings)
        if isinstance(payload, _UNANSWERED):
            raise payload
        if isinstance(payload, Exception):
            log.warning(f"Failed to fetch KNMI {resolution.value} stations: {_without_url_secrets_in(str(payload))}")
            return None

        with _forgotten_if_unreadable(dataset_name, version, filename, settings), open_netcdf(payload) as file:
            variables = file.variables
            return pl.DataFrame(
                {
                    "station_id": [public_station_id(wsi) for wsi in variables["station"][:]],
                    # the 10-minute files key a station by its bare number, and carry the WSI in a variable of its own
                    "wigos_id": station_wsis(variables),
                    "name": [decode_str(name) for name in variables["stationname"][:]],
                    "latitude": variables["lat"][:].tolist(),
                    "longitude": variables["lon"][:].tolist(),
                    "elevation": variables["height"][:].tolist(),
                },
            )
