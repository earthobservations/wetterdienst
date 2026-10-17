# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""AEMET OpenData observation data provider."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, cast

import polars as pl
import stamina

from wetterdienst.exceptions import CredentialMissingError, CredentialRejectedError, DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.quality_flags import join_quality_flags, raw_column, unpivot_with_raw
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.aemet.observation.metadata import AemetObservationMetadata
from wetterdienst.provider.aemet.observation.parser import (
    parse_decimal_comma,
    parse_dms_coordinate,
    parse_monthly_value,
    parse_wind_direction,
)
from wetterdienst.settings import Settings, reveal
from wetterdienst.util.network import (
    PROBE_TIMEOUT,
    _without_url_secrets,
    as_outage,
    credential_rejected,
    download_file,
    drop_cached_file,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

_BASE_URL = "https://opendata.aemet.es/opendata/api"
# AEMET rejects date ranges greater than 6 months; stay safely under that.
_MAX_REQUEST_DAYS = 179

# AEMET's own error message for a 429 is "Espere al siguiente minuto" (wait for the next
# minute), and it has also been observed, live, to fail in several other transient ways
# (TLS handshake failures, timeouts, and other failures on its second-stage "datos" URL) even
# after download_file()'s own short built-in retry is exhausted -- the exact status varies
# too much to enumerate as an allow-list, so everything is retried here EXCEPT the statuses
# that mean the request itself is invalid and retrying it can't help (bad auth, bad station,
# malformed request), and a failure download_file() reports as no network. That is aiohttp's
# ClientConnectorError -- refused, DNS, or a connection lost mid-handshake, but not a TLS error
# such as a failed certificate check or an alert (GH-2553) -- and it is returned without a
# retry here because offline, that only adds a wait. A timeout is not one and is retried, and
# so is a TLS error. Kept deliberately modest (a couple of short-backoff
# retries): AEMET's outages have been observed to regularly outlast even a much longer retry
# budget, so paying for one is mostly wasted time -- this is enough to smooth over brief blips
# without making a single failing call hang for minutes. A sustained outage is not waited out
# with a longer retry either.
_NON_RETRYABLE_STATUSES = {400, 401, 403, 404}
# the answers, as an HTTP status or an envelope's `estado`, that say AEMET refuses the API key
_KEY_REJECTED_STATUSES = frozenset({401, 403})
_RETRY_WAIT_INITIAL_SECONDS = 2
_RETRY_WAIT_MAX_SECONDS = 15
_RETRY_MAX_RETRIES = 2

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
}

_VALUE_COLUMNS = (
    "tmed",
    "tmax",
    "tmin",
    "prec",
    "dir",
    "velmedia",
    "racha",
    "presMax",
    "presMin",
    "hrMedia",
    "hrMax",
    "hrMin",
)

# AEMET rejects year ranges greater than 36 months (3 years) for monthly/annual values.
_MAX_REQUEST_YEARS = 3

# Monthly and annual values share the same response fields, distinguished by the "fecha"
# suffix (see _collect_monthly_or_annual).
_MONTHLY_ANNUAL_VALUE_COLUMNS = (
    "tm_mes",
    "tm_max",
    "tm_min",
    "ta_max",
    "ta_min",
    "p_mes",
    "p_max",
    "hr",
)

# The real-time (observación convencional) endpoint returns already-numeric JSON fields,
# unlike the climatological endpoints (no comma-decimals, no day-of-occurrence annotations).
_REALTIME_VALUE_COLUMNS = (
    "ta",
    "tamax",
    "tamin",
    "tpr",
    "prec",
    "dv",
    "dmax",
    "vv",
    "vmax",
    "pres",
    "pres_nmar",
    "hr",
)


class AemetKeyRejectedError(Exception):
    """AEMET refused the API key (HTTP or envelope status 401 or 403), as opposed to any other failure."""


class _AemetEnvelopeError(Exception):
    """AEMET answered with an envelope whose `estado` is no 200, and `status` is that `estado`."""

    def __init__(self, status: int | None, description: str) -> None:
        super().__init__(description)
        self.status = status


class _AemetRetryableError(Exception):
    """Internal signal used to trigger a stamina retry on a retryable AEMET failure."""


def _download_with_rate_limit_retry(
    url: str,
    settings: Settings,
    ttl: CacheExpiry,
    *,
    client_kwargs: dict | None = None,
    wait_initial: float = _RETRY_WAIT_INITIAL_SECONDS,
    wait_max: float = _RETRY_WAIT_MAX_SECONDS,
    max_retries: int = _RETRY_MAX_RETRIES,
) -> File:
    """Download a URL, retrying on retryable AEMET failures.

    Retries both the per-minute rate limit (429) and transient network failures
    (timeouts, connection resets, etc.). A failure `download_file` classes as no network
    (`File.is_no_internet_error`) is not retried here.

    download_file() already retries transiently via stamina internally, but with a very
    short, generic backoff -- not enough to reliably clear either failure mode observed
    live. This runs its own, deliberately modest stamina retry loop on top (a couple of
    short-backoff retries): enough to smooth over brief blips without making a single
    failing call hang for minutes. It does NOT attempt to wait out a sustained outage or
    the full ~60s AEMET's own 429 policy technically calls for -- live AEMET outages have
    been observed to regularly outlast even a much longer retry budget, so that time would
    mostly be wasted.
    """
    last_file: File | None = None
    with contextlib.suppress(_AemetRetryableError):
        for attempt in stamina.retry_context(
            on=_AemetRetryableError,
            attempts=max_retries + 1,
            timeout=None,
            wait_initial=wait_initial,
            wait_max=wait_max,
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
                        f"Retryable AEMET failure (status={last_file.status}) for {url}: {last_file.content}; retrying",
                    )
                    raise _AemetRetryableError(url)
    if last_file is None:
        msg = "unreachable: stamina.retry_context always runs at least once"
        raise AssertionError(msg)
    return last_file


def _client_kwargs(settings: Settings) -> dict:
    """Build the client kwargs of AEMET's requests: the settings' own and the key as a request header.

    The api_key is sent as a request header (rather than a URL query parameter) so it
    never ends up embedded in a URL that gets logged. AEMET accepts the key either way;
    the "datos" URL from the envelope is a pre-signed link that doesn't need auth at all.
    """
    return {
        **settings.fsspec_client_kwargs,
        "headers": {**settings.fsspec_client_kwargs.get("headers", {}), "api_key": reveal(settings.auth.aemet)},
    }


def _read_envelope(file: File) -> dict | Exception:
    """Read the envelope AEMET answered a request with: the envelope if its `estado` is 200, else why not.

    A failure is returned, not raised. `AemetKeyRejectedError` is the one that says AEMET refuses the
    key: a 401 or 403 of the envelope request, or an `estado` of 401 or 403 in it.
    """
    if isinstance(file.content, Exception):
        if file.status in _KEY_REJECTED_STATUSES:
            return AemetKeyRejectedError(f"AEMET answered HTTP {file.status}: {file.content}")
        return file.content
    try:
        envelope = json.load(file.content)
        estado = envelope.get("estado")
    except (ValueError, AttributeError):
        # a 200 that is no envelope: a maintenance page, or JSON that is no object
        return Exception("AEMET answered with something other than its JSON envelope")
    if estado != 200:
        description = envelope.get("descripcion", "unknown AEMET error")
        if estado in _KEY_REJECTED_STATUSES:
            return AemetKeyRejectedError(description)
        return _AemetEnvelopeError(estado, description)
    return envelope


def _as_outage(failure: Exception, url: str) -> Exception:
    """Return a failure of a request as the `DownloadError` or `NoInternetError` it is, if AEMET did not answer.

    AEMET does not answer when the download timed out, was dropped or cut short, or came back as a
    5xx (`as_outage`), and when it says so in the envelope of an HTTP 200: an `estado` of 500 or
    more, which is how it reports its own faults (GH-2965). Any other failure is an answer and is
    returned as it was: a 404, whether of the request or as `estado` 404 ("no data for these
    criteria"), a refused key, a 429 that outlasted the retries, a body that is no envelope.
    """
    if (
        isinstance(failure, _AemetEnvelopeError)
        and isinstance(failure.status, int)
        and failure.status >= HTTPStatus.INTERNAL_SERVER_ERROR
    ):
        error = DownloadError(_without_url_secrets(url), f"AEMET answered estado {failure.status}: {failure}")
        error.__cause__ = failure
        return error
    return as_outage(failure, url)


def _key_rejected() -> CredentialRejectedError:
    """Say that AEMET refuses the API key (GH-3018)."""
    return credential_rejected("AEMET", "AEMET", "API key")


def _raise_if_unanswered(payload: bytes | Exception) -> None:
    """Raise what `_fetch_datos` returned if it is not an answer to the request, or a refusal of the key.

    A connection that could not be made (`NoInternetError`), an AEMET that did not answer
    (`DownloadError`, GH-2965) and an API key that AEMET refuses (`CredentialRejectedError`, GH-3018): a
    request that goes on past any of them reads as a station without data, or as a network without
    stations. What AEMET did answer is left to the caller, which skips the chunk.
    """
    if isinstance(payload, (NoInternetError, DownloadError)):
        raise payload
    if isinstance(payload, AemetKeyRejectedError):
        raise _key_rejected()


def _drop_cached_body(file: File, settings: Settings, ttl: CacheExpiry, client_kwargs: dict) -> None:
    """Drop what `download_file` cached for a download whose body is no good, so that the next request asks again.

    AEMET reports most of its errors in the body of an HTTP 200 (`estado` 429 for the rate limit, 500
    for its own faults), which `download_file` caches for the whole `ttl` like an answer. A failure
    that arrived as an HTTP error was never cached. Used for the envelope and for the "datos" body.
    """
    if isinstance(file.content, Exception):
        return
    drop_cached_file(
        file.url,
        settings.cache_dir,
        ttl,
        client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )


def _fetch_datos(url: str, settings: Settings, ttl: CacheExpiry) -> bytes | Exception:
    """Resolve AEMET's two-step response pattern (envelope + separate "datos" URL).

    A failure is returned, not raised (see `_read_envelope` for the one that says the key is refused).
    The "datos" URL is pre-signed and takes no key, so a refusal of it says nothing about the key.
    One that is no answer -- a timeout, a dropped connection, a body cut short, a 5xx, an `estado`
    of 500 or more -- is returned as the `DownloadError` that names the file, and a failed connection
    as the `NoInternetError` (`_as_outage`); the readers of values raise those (GH-2965). A refusal of
    the key is asked once more before it is returned, AEMET answering a 401 to a key that it accepts on
    the next request (GH-3022).

    Nothing that failed stays in the cache (see `_drop_cached_body`): not an envelope that is a
    failure, not a "datos" body that is no JSON array, and not the envelope of a "datos" link that
    could not be fetched. The link is pre-signed and may expire, and every request within the `ttl`
    would be handed the same one (12 hours for the station list) by the cached envelope.
    """
    client_kwargs = _client_kwargs(settings)
    file = _download_with_rate_limit_retry(url, settings, ttl, client_kwargs=client_kwargs)
    envelope = _read_envelope(file)
    if isinstance(envelope, AemetKeyRejectedError):
        # AEMET answers a 401 to a key it accepts on the next request, so the key is called refused
        # only when it refuses it twice (GH-3022). The first answer is dropped from the cache, so
        # that the second is a request and not the cached refusal
        _drop_cached_body(file, settings, ttl, client_kwargs)
        log.warning(f"AEMET refused the API key for {file.url}: {envelope}; asking once more")
        file = _download_with_rate_limit_retry(url, settings, ttl, client_kwargs=client_kwargs)
        envelope = _read_envelope(file)
    if isinstance(envelope, Exception):
        _drop_cached_body(file, settings, ttl, client_kwargs)
        return _as_outage(envelope, file.url)
    if not isinstance(envelope.get("datos"), str):
        _drop_cached_body(file, settings, ttl, client_kwargs)
        return Exception("AEMET answered with an envelope without a link to the data")
    datos_file = _download_with_rate_limit_retry(envelope["datos"], settings, ttl)
    if isinstance(datos_file.content, Exception):
        _drop_cached_body(file, settings, ttl, client_kwargs)
        return _as_outage(datos_file.content, datos_file.url)
    payload = datos_file.content.read()
    if not _is_json_array(payload):
        # a maintenance page or an error object answered with a 200: neither the body nor the link
        # that led to it is asked again from the cache
        _drop_cached_body(datos_file, settings, ttl, settings.fsspec_client_kwargs)
        _drop_cached_body(file, settings, ttl, client_kwargs)
        return Exception("AEMET answered with something other than a JSON array as the data")
    return payload


def _is_json_array(payload: bytes) -> bool:
    """Tell whether a "datos" body is a JSON array, which is what every endpoint used here serves.

    AEMET serves the "datos" payload as ISO-8859-1, not UTF-8, which latin-1 decodes whatever the bytes.
    """
    try:
        return isinstance(json.loads(payload.decode("latin-1")), list)
    except ValueError:
        return False


def _probe_aemet_credentials(settings: Settings) -> bool | None:
    """Probe the AEMET API with the envelope of one request; an acceptance is cached on disk for ONE_MINUTE.

    Asked while a page waits for it, so it is bounded (GH-2564): one request, one attempt, for
    `PROBE_TIMEOUT_SECONDS`, and not through `_download_with_rate_limit_retry`, whose waits made a
    failing AEMET take over a minute to answer. Nor is the "datos" link followed: an `estado` of 200
    says the key is accepted, and what is behind the link is the whole station inventory.

    Returns False only when AEMET refuses the key (see `_read_envelope`), True when it answers, and
    None for any other failure -- no network, a failed TLS verification, a timeout, a 429 ("wait for
    the next minute"), a 5xx -- which says nothing about the key.

    Only an acceptance stays in the cache, and only for `ONE_MINUTE` (AEMET's own rate-limit window):
    a refusal or a failure is dropped (GH-2750), so a key that is activated or a limit that lifts is
    seen by the next probe, and a key that is revoked stops reading `True` within the minute.
    """
    if not settings.auth.aemet:
        return False
    ttl = CacheExpiry.ONE_MINUTE
    client_kwargs = {**_client_kwargs(settings), "timeout": PROBE_TIMEOUT}
    file = download_file(
        url=f"{_BASE_URL}/valores/climatologicos/inventarioestaciones/todasestaciones",
        cache_dir=settings.cache_dir,
        ttl=ttl,
        client_kwargs=client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
        attempts=1,
    )
    envelope = _read_envelope(file)
    if isinstance(envelope, Exception):
        _drop_cached_body(file, settings, ttl, client_kwargs)
        if isinstance(envelope, AemetKeyRejectedError):
            return False
        log.warning("Could not check the AEMET API key: %s", envelope)
        return None
    return True


class AemetObservationValues(TimeseriesValues):
    """Values class for AEMET OpenData observation data."""

    _endpoint_daily = (
        _BASE_URL + "/valores/climatologicos/diarios/datos/"
        "fechaini/{start_date}/fechafin/{end_date}/estacion/{station_id}"
    )
    _endpoint_monthly = (
        _BASE_URL
        + "/valores/climatologicos/mensualesanuales/datos/anioini/{start_year}/aniofin/{end_year}/estacion/{station_id}"
    )
    _endpoint_realtime = _BASE_URL + "/observacion/convencional/datos/estacion/{station_id}"

    @staticmethod
    def _date_chunks(start_date: dt.datetime, end_date: dt.datetime) -> Iterator[tuple[dt.datetime, dt.datetime]]:
        """Split a date range into chunks of at most _MAX_REQUEST_DAYS, as required by the AEMET API."""
        step = dt.timedelta(days=_MAX_REQUEST_DAYS)
        chunk_start = start_date
        while chunk_start <= end_date:
            chunk_end = min(chunk_start + step, end_date)
            yield chunk_start, chunk_end
            chunk_start = chunk_end + dt.timedelta(seconds=1)

    @staticmethod
    def _year_chunks(start_year: int, end_year: int) -> Iterator[tuple[int, int]]:
        """Split a year range into chunks of at most _MAX_REQUEST_YEARS, as required by the AEMET API."""
        step = _MAX_REQUEST_YEARS - 1
        chunk_start = start_year
        while chunk_start <= end_year:
            chunk_end = min(chunk_start + step, end_year)
            yield chunk_start, chunk_end
            chunk_start = chunk_end + 1

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        elif isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        else:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        if dataset.resolution.value == Resolution.HOURLY:
            return self._collect_realtime(station_id, dataset)
        if dataset.resolution.value == Resolution.DAILY:
            return self._collect_daily(station_id, dataset)
        return self._collect_monthly_or_annual(station_id, dataset)

    def _collect_realtime(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        """Collect real-time (observación convencional) values.

        Unlike the climatological endpoints, this one takes no date range at all — AEMET
        always returns whatever rolling window of recent hourly observations (typically
        the last ~24h) it currently holds for the station. Filtering to a user-requested
        start/end (if any) happens generically afterward in TimeseriesValues.query().
        """
        settings = cast("Settings", self.sr.request.settings)
        api_key = settings.auth.aemet
        if not api_key:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        url = self._endpoint_realtime.format(station_id=station_id)
        payload = _fetch_datos(url, settings, CacheExpiry.FIVE_MINUTES)
        _raise_if_unanswered(payload)
        if isinstance(payload, Exception):
            log.warning(f"Failed to acquire AEMET data for station {station_id}, chunk {url}: {payload}")
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        records = json.loads(payload.decode("latin-1"))
        if not records:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.DataFrame(records, infer_schema_length=None)
        if "fint" not in df.columns:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        for column in _REALTIME_VALUE_COLUMNS:
            if column not in df.columns:
                df = df.with_columns(pl.lit(None, pl.Float64).alias(column))
        df = df.with_columns(pl.col(column).cast(pl.Float64, strict=False) for column in _REALTIME_VALUE_COLUMNS)
        df = df.unpivot(index="fint", on=list(_REALTIME_VALUE_COLUMNS), variable_name="parameter", value_name="value")
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("fint").str.to_datetime("%Y-%m-%dT%H:%M:%S%z").dt.convert_time_zone("UTC").alias("timestamp"),
            pl.col("value"),
        )

    def _collect_daily(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        settings = cast("Settings", self.sr.request.settings)
        api_key = settings.auth.aemet
        start_date = self.sr.start
        end_date = self.sr.end
        if not start_date or not end_date or not api_key:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        records = []
        for chunk_start, chunk_end in self._date_chunks(start_date, end_date):
            url = self._endpoint_daily.format(
                station_id=station_id,
                start_date=chunk_start.strftime("%Y-%m-%dT%H:%M:%SUTC"),
                end_date=chunk_end.strftime("%Y-%m-%dT%H:%M:%SUTC"),
            )
            payload = _fetch_datos(url, settings, CacheExpiry.FIVE_MINUTES)
            # offline, every remaining chunk (and station) would fail the same way: the request
            # ends here, with the error, rather than with the chunks read (GH-2620, GH-2640).
            # The same for an AEMET that did not answer -- a timeout, a dropped connection, a
            # 5xx: a range read in part is not an answer, and an empty one would read as a
            # station without data (GH-2965). And for a key it refuses, which every chunk and
            # station would meet again (GH-3018)
            _raise_if_unanswered(payload)
            if isinstance(payload, Exception):
                # AEMET answered, and the answer is no data for this chunk (a 404) or a rate limit
                # that outlasted the retries: this chunk is missing from the result.
                log.warning(f"Failed to acquire AEMET data for station {station_id}, chunk {url}: {payload}")
                continue
            records.extend(json.loads(payload.decode("latin-1")))
        if not records:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.DataFrame(records, infer_schema_length=None)
        for column in ("fecha", *_VALUE_COLUMNS):
            if column not in df.columns:
                df = df.with_columns(pl.lit(None, pl.String).alias(column))
        # a value that is no number is null and keeps its text beside it as `raw:` (GH-2759)
        parsed = {
            "tmed": parse_decimal_comma("tmed"),
            "tmax": parse_decimal_comma("tmax"),
            "tmin": parse_decimal_comma("tmin"),
            "prec": parse_decimal_comma("prec"),
            "dir": parse_wind_direction("dir"),
            "velmedia": parse_decimal_comma("velmedia"),
            "racha": parse_decimal_comma("racha"),
            "presMax": parse_decimal_comma("presMax"),
            "presMin": parse_decimal_comma("presMin"),
            "hrMedia": parse_decimal_comma("hrMedia"),
            "hrMax": parse_decimal_comma("hrMax"),
            "hrMin": parse_decimal_comma("hrMin"),
        }
        df = df.with_columns(
            *[value.alias(name) for name, (value, _) in parsed.items()],
            *[raw.alias(raw_column(name)) for name, (_, raw) in parsed.items()],
        )
        df = unpivot_with_raw(df, index=["fecha"], on=list(_VALUE_COLUMNS))
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("fecha").str.to_datetime("%Y-%m-%d").dt.replace_time_zone("UTC").alias("timestamp"),
            pl.col("value"),
            join_quality_flags(None, raw=pl.col("raw")),
        )

    def _collect_monthly_or_annual(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        """Collect monthly or annual values.

        Both resolutions come from the same AEMET endpoint (mensualesanuales) in one
        combined response: a "fecha" of "YYYY-01".."YYYY-12" is a month, "YYYY-13" is
        that year's annual total/summary. Which one this call returns is decided by
        dataset.resolution — the other rows are simply filtered out.
        """
        settings = cast("Settings", self.sr.request.settings)
        api_key = settings.auth.aemet
        start_date = self.sr.start
        end_date = self.sr.end
        if not start_date or not end_date or not api_key:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        records = []
        for start_year, end_year in self._year_chunks(start_date.year, end_date.year):
            url = self._endpoint_monthly.format(
                station_id=station_id,
                start_year=start_year,
                end_year=end_year,
            )
            payload = _fetch_datos(url, settings, CacheExpiry.FIVE_MINUTES)
            _raise_if_unanswered(payload)
            if isinstance(payload, Exception):
                log.warning(f"Failed to acquire AEMET data for station {station_id}, chunk {url}: {payload}")
                continue
            records.extend(json.loads(payload.decode("latin-1")))
        if not records:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.DataFrame(records, infer_schema_length=None)
        for column in ("fecha", *_MONTHLY_ANNUAL_VALUE_COLUMNS):
            if column not in df.columns:
                df = df.with_columns(pl.lit(None, pl.String).alias(column))
        df = df.with_columns(
            pl.col("fecha").str.extract(r"^(\d{4})-(\d{1,2})$", 1).cast(pl.Int32).alias("_year"),
            pl.col("fecha").str.extract(r"^(\d{4})-(\d{1,2})$", 2).cast(pl.Int32).alias("_period"),
        )
        is_annual = dataset.resolution.value == Resolution.ANNUAL
        df = df.filter(pl.col("_period").eq(13)) if is_annual else df.filter(pl.col("_period").ne(13))
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        date_expr = pl.date(pl.col("_year"), 1, 1) if is_annual else pl.date(pl.col("_year"), pl.col("_period"), 1)
        df = df.with_columns(date_expr.alias("_date"))
        parsed = {
            "tm_mes": parse_monthly_value("tm_mes"),
            "tm_max": parse_monthly_value("tm_max"),
            "tm_min": parse_monthly_value("tm_min"),
            "ta_max": parse_monthly_value("ta_max"),
            "ta_min": parse_monthly_value("ta_min"),
            "p_mes": parse_monthly_value("p_mes"),
            "p_max": parse_monthly_value("p_max"),
            "hr": parse_decimal_comma("hr"),
        }
        df = df.with_columns(
            *[value.alias(name) for name, (value, _) in parsed.items()],
            *[raw.alias(raw_column(name)) for name, (_, raw) in parsed.items()],
        )
        df = unpivot_with_raw(df, index=["_date"], on=list(_MONTHLY_ANNUAL_VALUE_COLUMNS))
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("_date").cast(pl.Datetime(time_zone="UTC")).alias("timestamp"),
            pl.col("value"),
            join_quality_flags(None, raw=pl.col("raw")),
        )


@dataclass
class AemetObservationRequest(TimeseriesRequest):
    """Request class for AEMET OpenData observation data."""

    metadata = AemetObservationMetadata
    _values = AemetObservationValues

    _endpoint = _BASE_URL + "/valores/climatologicos/inventarioestaciones/todasestaciones"

    @classmethod
    def is_configured(cls) -> bool:  # noqa: D102
        return bool(Settings().auth.aemet)

    @classmethod
    def is_valid(cls, settings: Settings | None = None) -> bool | None:  # noqa: D102
        return _probe_aemet_credentials(settings or Settings())

    def __post_init__(self) -> None:  # noqa: D105
        super().__post_init__()
        settings = cast("Settings", self.settings)
        if not settings.auth.aemet:
            msg = (
                "AEMET OpenData requires authentication. "
                "Request a free API key at https://opendata.aemet.es/centrodedescargas/altaUsuario "
                "and set WD_AUTH__AEMET=<api_key> (env var) "
                "or Settings(auth={'aemet': '<api_key>'}) (Python)."
            )
            raise CredentialMissingError(msg)

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        payload = _fetch_datos(self._endpoint, settings, CacheExpiry.METAINDEX)
        # an unreachable AEMET is no network without stations (GH-2640), nor is one that does not answer
        # (GH-3022) or refuses the key (GH-3018)
        _raise_if_unanswered(payload)
        if isinstance(payload, Exception):
            log.warning(f"Failed to fetch AEMET stations: {payload}")
            return pl.LazyFrame()

        df = pl.DataFrame(json.loads(payload.decode("latin-1")))
        df = df.rename({"indicativo": "station_id", "nombre": "name", "provincia": "region"})
        df = df.with_columns(
            # the inventory pads some names with blanks (`PORTOCOLOM  `), which a comparison of the name misses
            pl.col("name").str.strip_chars(),
            pl.col("altitud").cast(pl.Float64, strict=False).alias("elevation"),
            parse_dms_coordinate("latitud").alias("latitude"),
            parse_dms_coordinate("longitud").alias("longitude"),
        )
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        data = []
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        if not data:
            return pl.LazyFrame()
        df = pl.concat(data)
        return df.select(
            pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in self._base_columns
        ).lazy()
