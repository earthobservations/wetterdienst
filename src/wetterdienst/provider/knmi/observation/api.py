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
from typing import TYPE_CHECKING, cast

import polars as pl
import stamina

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.knmi.observation.metadata import KnmiObservationMetadata
from wetterdienst.provider.knmi.observation.parser import decode_str, parse_knmi_netcdf, public_station_id
from wetterdienst.util.network import download_file

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

_NON_RETRYABLE_STATUSES = {400, 401, 403, 404}
_RETRY_WAIT_INITIAL_SECONDS = 2
_RETRY_WAIT_MAX_SECONDS = 15
_RETRY_MAX_RETRIES = 2


class _KnmiRetryableError(Exception):
    """Internal signal used to trigger a stamina retry on a retryable KNMI failure."""


def _redact(url: str) -> str:
    """Drop the query string so a pre-signed S3 download URL's signature never lands in logs."""
    return url.split("?", 1)[0]


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


def _moments(start_date: dt.datetime, end_date: dt.datetime, resolution: Resolution) -> Iterator[dt.datetime]:
    step = _STEP_BY_RESOLUTION[resolution]
    # 10-minute filenames encode the minute, so an unaligned start would not resolve -- floor
    # it (the over-fetched pre-start file is trimmed by the framework's [start, end] filter).
    # Hourly/daily filenames truncate to the hour/day and are left unfloored here: flooring
    # them would date the value before an unaligned start_date and drop the first period. When
    # the whole request is a single resolution, __post_init__ has already floored start_date so
    # the moments are aligned; a mixed request keeps the (harmless) unaligned label.
    current = _floor(start_date, resolution) if resolution == Resolution.MINUTE_10 else start_date
    while current <= end_date:
        yield current
        current += step


def _download_with_retry(url: str, settings: Settings, ttl: CacheExpiry, *, client_kwargs: dict | None = None) -> File:
    """Download a URL, retrying on retryable failures (rate limiting, transient network errors).

    Mirrors AEMET's retry design: a deliberately modest couple of short-backoff
    retries, not an attempt to wait out a sustained outage.
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
                if isinstance(last_file.content, Exception) and last_file.status not in _NON_RETRYABLE_STATUSES:
                    log.warning(
                        f"Retryable KNMI failure (status={last_file.status}) for {_redact(url)}: "
                        f"{last_file.content}; retrying",
                    )
                    raise _KnmiRetryableError(_redact(url))
    if last_file is None:
        msg = "unreachable: stamina.retry_context always runs at least once"
        raise AssertionError(msg)
    return last_file


def _latest_filename(dataset_name: str, version: str, settings: Settings) -> str | Exception:
    """Look up the most recently published file in a dataset.

    "Validated" datasets lag well behind real time (observed: ~1-2 days for hourly),
    so guessing a fixed offset from now() isn't reliable -- ask the API directly.
    """
    url = f"{_BASE_URL}/datasets/{dataset_name}/versions/{version}/files?maxKeys=1&orderBy=created&sorting=desc"
    client_kwargs = {
        **settings.fsspec_client_kwargs,
        "headers": {**settings.fsspec_client_kwargs.get("headers", {}), "Authorization": settings.auth.knmi},
    }
    file = _download_with_retry(url, settings, CacheExpiry.ONE_HOUR, client_kwargs=client_kwargs)
    if isinstance(file.content, Exception):
        return file.content
    files = json.load(file.content).get("files", [])
    if not files:
        return Exception("no files found")
    return files[0]["filename"]


def _fetch_netcdf(dataset_name: str, version: str, filename: str, settings: Settings) -> bytes | Exception:
    """Resolve a temporary download URL for a dataset file, then download it.

    The resolve step needs the API key (in the Authorization header); the resulting
    temporary S3 URL is pre-signed and needs no auth of its own.

    Each KNMI file covers the whole network for one timestamp, but the framework collects
    values per station, so the same file would otherwise be downloaded once per station.
    Both the resolve response and the (potentially large) file bytes are cached for the same
    short window: within it, the resolve step returns the identical pre-signed URL for every
    station, so the content download is a cache hit -- one download per file per query run
    instead of one per station. The TTL is short because the pre-signed URL expires after an
    hour; files are immutable, so a cache hit is always valid.
    """
    resolve_url = f"{_BASE_URL}/datasets/{dataset_name}/versions/{version}/files/{filename}/url"
    client_kwargs = {
        **settings.fsspec_client_kwargs,
        "headers": {**settings.fsspec_client_kwargs.get("headers", {}), "Authorization": settings.auth.knmi},
    }
    resolve_file = _download_with_retry(resolve_url, settings, CacheExpiry.FIVE_MINUTES, client_kwargs=client_kwargs)
    if isinstance(resolve_file.content, Exception):
        return resolve_file.content
    # a 200 with an unexpected body (throttling notice, API change) must not KeyError out of
    # the per-moment loop and abort the whole query -- surface it as a skippable failure.
    download_url = json.load(resolve_file.content).get("temporaryDownloadUrl")
    if not download_url:
        return Exception(f"KNMI resolve response for {filename} did not contain a temporaryDownloadUrl")
    content_file = _download_with_retry(download_url, settings, CacheExpiry.FIVE_MINUTES)
    if isinstance(content_file.content, Exception):
        return content_file.content
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
            return self._empty_df()

        settings = cast("Settings", self.sr.stations.settings)
        start_date = self.sr.start_date
        end_date = self.sr.end_date
        if not start_date or not end_date or not settings.auth.knmi:
            return self._empty_df()

        resolution = dataset.resolution.value
        dataset_name, version = _DATASET_BY_RESOLUTION[resolution]

        frames = []
        for moment in _moments(start_date, end_date, resolution):
            filename = _filename_for(resolution, moment)
            payload = _fetch_netcdf(dataset_name, version, filename, settings)
            if isinstance(payload, Exception):
                # a single missing/failed timestamp shouldn't sink the whole range --
                # rate-limit/transient retries (if applicable) are already exhausted here.
                log.warning(f"Failed to acquire KNMI data for station {station_id}, file {filename}: {payload}")
                continue
            df = parse_knmi_netcdf(payload, station_id, parameter_names, moment)
            if not df.is_empty():
                frames.append(df)
        if not frames:
            return self._empty_df()

        # every frame from parse_knmi_netcdf shares the same (date, parameter, value) schema
        df = pl.concat(frames)
        return df.select(
            pl.lit(resolution.value, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("date"),
            pl.col("value"),
            pl.lit(None, pl.Float64).alias("quality"),
        )

    @staticmethod
    def _empty_df() -> pl.DataFrame:
        return pl.DataFrame(
            schema={
                "resolution": pl.String,
                "dataset": pl.String,
                "parameter": pl.String,
                "station_id": pl.String,
                "date": pl.Datetime(time_unit="us", time_zone="UTC"),
                "value": pl.Float64,
                "quality": pl.Float64,
            },
        )


@dataclass
class KnmiObservationRequest(TimeseriesRequest):
    """Request class for KNMI observation data."""

    metadata = KnmiObservationMetadata
    _values = KnmiObservationValues

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
            raise ValueError(msg)
        # KNMI's files are keyed by UTC (filenames encode the UTC date/hour/minute). The base
        # convert_timestamps only tags *naive* inputs as UTC -- a tz-aware non-UTC datetime is
        # kept as-is -- so normalize to UTC here before any flooring or filename formatting,
        # otherwise a start_date like 10:00 Europe/Amsterdam (08:00 UTC) would fetch the 10:00
        # UTC file. Mirrors AEMET's UTC normalization.
        if self.start_date:
            self.start_date = cast("dt.datetime", self.start_date).astimezone(dt.timezone.utc)
        if self.end_date:
            self.end_date = cast("dt.datetime", self.end_date).astimezone(dt.timezone.utc)
        # When the whole request targets a single hourly/daily resolution, snap start_date down
        # to that resolution's interval boundary. Those are period aggregates labelled at the
        # period start, so a query beginning mid-period should include that period; flooring
        # start_date here (the one filter the framework shares across resolutions) keeps value
        # dates on the true boundary AND keeps the start-containing period in range -- correct
        # timestamps with no dropped period. 10-minute is excluded: its values are end-labelled
        # sub-hour intervals, so an unaligned start correctly excludes the pre-start interval
        # (the framework's [start, end] filter handles that, with _moments flooring only to
        # resolve filenames). A mixed-resolution request has no single boundary and is left as-is.
        resolutions = {
            _resolution_of(parameter_or_dataset)
            for parameter_or_dataset in self.parameters
            if isinstance(parameter_or_dataset, (ParameterModel, DatasetModel))
        }
        if self.start_date and resolutions in ({Resolution.HOURLY}, {Resolution.DAILY}):
            self.start_date = _floor(cast("dt.datetime", self.start_date), next(iter(resolutions)))

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
        if isinstance(filename, Exception):
            log.warning(f"Failed to look up latest KNMI {resolution.value} file: {filename}")
            return None
        payload = _fetch_netcdf(dataset_name, version, filename, settings)
        if isinstance(payload, Exception):
            log.warning(f"Failed to fetch KNMI {resolution.value} stations: {payload}")
            return None

        import h5netcdf  # noqa: PLC0415

        with h5netcdf.File(io.BytesIO(payload), "r") as file:
            variables = file.variables
            return pl.DataFrame(
                {
                    "station_id": [public_station_id(wsi) for wsi in variables["station"][:]],
                    "name": [decode_str(name) for name in variables["stationname"][:]],
                    "latitude": variables["lat"][:].tolist(),
                    "longitude": variables["lon"][:].tolist(),
                    "height": variables["height"][:].tolist(),
                },
            )
