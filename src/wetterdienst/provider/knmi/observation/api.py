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
import io
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import polars as pl
import stamina

from wetterdienst.exceptions import CredentialMissingError, CredentialRejectedError, DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.knmi.observation.metadata import KnmiObservationMetadata
from wetterdienst.provider.knmi.observation.parser import decode_str, parse_knmi_netcdf, public_station_id
from wetterdienst.settings import reveal
from wetterdienst.util.extras import import_optional
from wetterdienst.util.network import (
    CREDENTIAL_REJECTED_STATUSES,
    _without_url_secrets,
    _without_url_secrets_in,
    as_outage,
    credential_rejected,
    download_file,
)

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
}

_STEP_BY_RESOLUTION = {
    Resolution.MINUTE_10: dt.timedelta(minutes=10),
    Resolution.HOURLY: dt.timedelta(hours=1),
    Resolution.DAILY: dt.timedelta(days=1),
}

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
    return f"daily-observations-validated-{moment:%Y%m%d}.nc"


def _floor(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Snap a moment down to its resolution's interval boundary (:X0 / :00 / midnight)."""
    if resolution == Resolution.MINUTE_10:
        return moment.replace(minute=moment.minute - moment.minute % 10, second=0, microsecond=0)
    if resolution == Resolution.HOURLY:
        return moment.replace(minute=0, second=0, microsecond=0)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _resolution_of(parameter_or_dataset: ParameterModel | DatasetModel) -> Resolution:
    """Return the Resolution enum for a parsed parameter or whole-dataset selection."""
    dataset = parameter_or_dataset.dataset if isinstance(parameter_or_dataset, ParameterModel) else parameter_or_dataset
    return dataset.resolution.value


def _ceil(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Snap a moment up to its resolution's interval boundary, the moment itself if it is on one."""
    floored = _floor(moment, resolution)
    return floored if floored == moment else floored + _STEP_BY_RESOLUTION[resolution]


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
    """
    return moment + dt.timedelta(hours=1) if resolution == Resolution.HOURLY else moment


def _moments(start_date: dt.datetime, end_date: dt.datetime, resolution: Resolution) -> Iterator[dt.datetime]:
    """Yield the moments that name the files whose values are stamped within [start_date, end_date]."""
    step = _STEP_BY_RESOLUTION[resolution]
    if resolution == Resolution.HOURLY:
        # the hour that ends at the first stamp at or after start_date (its file is named for the start of it)
        current = _ceil(start_date, resolution) - step
    elif resolution == Resolution.MINUTE_10:
        # 10-minute filenames encode the minute, so an unaligned start would not resolve -- floor it (the over-fetched
        # pre-start file is trimmed by the framework's [start, end] filter)
        current = _floor(start_date, resolution)
    else:
        # a daily file is stamped with its own date. When the whole request is daily, __post_init__ has already floored
        # start to the day so the moments are aligned; a mixed request keeps the (harmless) unaligned label
        current = start_date
    while _stamp(current, resolution) <= end_date:
        yield current
        current += step


def _download_with_retry(url: str, settings: Settings, ttl: CacheExpiry, *, client_kwargs: dict | None = None) -> File:
    """Download a URL, retrying on retryable failures (rate limiting, transient network errors).

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
                )
                # no network is not a blip two more retries clear: report it at once (the 503
                # `download_file` gives it would otherwise match)
                if (
                    isinstance(last_file.content, Exception)
                    and not last_file.is_no_internet_error
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


def _key_rejected(status: int) -> CredentialRejectedError:
    """Say that KNMI refuses the API key, which is sent to the request that asks for a file or a listing (GH-3018)."""
    return credential_rejected("KNMI", "KNMI", "API key", status)


def _latest_filename(dataset_name: str, version: str, settings: Settings) -> str | Exception:
    """Look up the most recently published file in a dataset.

    "Validated" datasets lag well behind real time (observed: ~1-2 days for hourly),
    so guessing a fixed offset from now() isn't reliable -- ask the API directly.
    """
    url = f"{_BASE_URL}/datasets/{dataset_name}/versions/{version}/files?maxKeys=1&orderBy=created&sorting=desc"
    client_kwargs = {
        **settings.fsspec_client_kwargs,
        "headers": {**settings.fsspec_client_kwargs.get("headers", {}), "Authorization": reveal(settings.auth.knmi)},
    }
    file = _download_with_retry(url, settings, CacheExpiry.ONE_HOUR, client_kwargs=client_kwargs)
    if isinstance(file.content, Exception):
        if file.status in CREDENTIAL_REJECTED_STATUSES:
            return _key_rejected(file.status)
        return as_outage(file.content, file.url)
    files = json.load(file.content).get("files", [])
    if not files:
        return Exception("no files found")
    return files[0]["filename"]


def _fetch_netcdf(dataset_name: str, version: str, filename: str, settings: Settings) -> bytes | Exception:
    """Resolve a temporary download URL for a dataset file, then download it.

    The resolve step needs the API key (in the Authorization header); the resulting
    temporary S3 URL is pre-signed and needs no auth of its own.

    A failure is returned, not raised. One that is no answer -- a timeout, a dropped connection, a
    body cut short, a 5xx -- is returned as the `DownloadError` naming the file (`as_outage`, GH-2965),
    a failed connection as the `NoInternetError`; the caller raises those. A 404 (a timestamp that is
    not published) and any other 4xx, a 429 among them, are returned as they came. A 401 or 403 of the
    request that carries the key is the `CredentialRejectedError` (GH-3018), returned like the others;
    the same status of the pre-signed link says nothing of the key and is returned as it came.

    Each KNMI file covers the whole network for one timestamp, but the framework collects
    values per station, so the same file would otherwise be downloaded once per station.
    Both the resolve response and the (potentially large) file bytes are cached for the same
    short window: within it, the resolve step returns the identical pre-signed URL for every
    station, so the content download is a cache hit -- one download per file per query run
    instead of one per station. The TTL is short because the pre-signed URL expires after an
    hour; files are immutable, so a cache hit is always valid.

    The pre-signed URL is a secret for the hour it lasts: it is in the local cache (the resolve response
    holds it, and the metadata file names the download by it), and in no log line and no error, which show
    it without its query (GH-3341). fsspec's own debug line of a request is not ours to change.
    """
    resolve_url = f"{_BASE_URL}/datasets/{dataset_name}/versions/{version}/files/{filename}/url"
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
        return Exception(f"KNMI resolve response for {filename} did not contain a temporaryDownloadUrl")
    content_file = _download_with_retry(download_url, settings, CacheExpiry.FIVE_MINUTES)
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
                log.warning(
                    f"Failed to acquire KNMI data for station {station_id}, file {filename}: "
                    f"{_without_url_secrets_in(str(payload))}"
                )
                continue
            df = parse_knmi_netcdf(payload, station_id, parameter_names, _stamp(moment, resolution))
            if not df.is_empty():
                frames.append(df)
        # every frame from parse_knmi_netcdf shares the same (timestamp, parameter, value, quality_flags) schema
        return pl.concat(frames) if frames else pl.DataFrame()


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
        if self.start and resolutions == {Resolution.DAILY}:
            self.start = _floor(cast("dt.datetime", self.start), Resolution.DAILY)

    def _all(self) -> pl.LazyFrame:
        """Enumerate stations per requested resolution.

        KNMI has no separate station registry -- each file lists the whole network for its
        own resolution, and those inventories differ (the 10-minute network is a superset of
        the hourly/daily one), so stations are read from the latest file of each requested
        resolution rather than a single shared one.
        """
        settings = cast("Settings", self.settings)
        requested = {
            (parameter.dataset.resolution.value, parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        station_frames: dict[Resolution, pl.DataFrame | None] = {}
        data = []
        for resolution, resolution_name, dataset in requested:
            if resolution not in station_frames:
                station_frames[resolution] = self._station_frame(resolution, settings)
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
        """Read the station inventory from the most recent file of the given resolution."""
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

        h5netcdf = import_optional("h5netcdf", "Reading KNMI NetCDF", extra="knmi")

        with h5netcdf.File(io.BytesIO(payload), "r") as file:
            variables = file.variables
            return pl.DataFrame(
                {
                    "station_id": [public_station_id(wsi) for wsi in variables["station"][:]],
                    "wigos_id": [decode_str(wsi) for wsi in variables["station"][:]],
                    "name": [decode_str(name) for name in variables["stationname"][:]],
                    "latitude": variables["lat"][:].tolist(),
                    "longitude": variables["lon"][:].tolist(),
                    "elevation": variables["height"][:].tolist(),
                },
            )
