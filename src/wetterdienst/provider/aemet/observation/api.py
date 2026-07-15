# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""AEMET OpenData observation data provider."""

from __future__ import annotations

import contextlib
import datetime as dt
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
from wetterdienst.provider.aemet.observation.metadata import AemetObservationMetadata
from wetterdienst.provider.aemet.observation.parser import (
    parse_decimal_comma,
    parse_dms_coordinate,
    parse_monthly_value,
    parse_wind_direction,
)
from wetterdienst.settings import Settings
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

_BASE_URL = "https://opendata.aemet.es/opendata/api"
# AEMET rejects date ranges greater than 6 months; stay safely under that.
_MAX_REQUEST_DAYS = 179

# AEMET's own error message for a 429 is "Espere al siguiente minuto" (wait for the next
# minute) — the short retry/backoff baked into download_file() is nowhere near enough to
# clear that, so a 429 gets its own, much longer wait here instead of being treated as a
# regular failure (which would otherwise silently drop that chunk's data).
_RATE_LIMIT_STATUS = 429
_RATE_LIMIT_RETRY_WAIT_SECONDS = 60
_RATE_LIMIT_MAX_RETRIES = 2

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
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


class _AemetRateLimitedError(Exception):
    """Internal signal used to trigger a stamina retry when AEMET returns HTTP 429."""


def _download_with_rate_limit_retry(
    url: str,
    settings: Settings,
    ttl: CacheExpiry,
    *,
    wait_seconds: float = _RATE_LIMIT_RETRY_WAIT_SECONDS,
    max_retries: int = _RATE_LIMIT_MAX_RETRIES,
) -> File:
    """Download a URL, waiting out AEMET's per-minute rate limit (HTTP 429) if hit.

    download_file() already retries transiently via stamina internally, but with a short,
    generic backoff that's nowhere near AEMET's actual "wait for the next minute" 429
    policy. This runs its own stamina retry loop on top, scoped specifically to 429s, with
    a fixed wait long enough to actually clear the rate limit.
    """
    last_file: File | None = None
    with contextlib.suppress(_AemetRateLimitedError):
        for attempt in stamina.retry_context(
            on=_AemetRateLimitedError,
            attempts=max_retries + 1,
            timeout=None,
            wait_initial=wait_seconds,
            wait_max=wait_seconds,
            wait_jitter=0,
        ):
            with attempt:
                last_file = download_file(
                    url=url,
                    cache_dir=settings.cache_dir,
                    ttl=ttl,
                    client_kwargs=settings.fsspec_client_kwargs,
                    cache_disable=settings.cache_disable,
                    use_certifi=settings.use_certifi,
                )
                if isinstance(last_file.content, Exception) and last_file.status == _RATE_LIMIT_STATUS:
                    log.warning(f"AEMET rate limit hit for {url}, retrying in {wait_seconds:.0f}s")
                    raise _AemetRateLimitedError(url)
    if last_file is None:
        msg = "unreachable: stamina.retry_context always runs at least once"
        raise AssertionError(msg)
    return last_file


def _fetch_datos(url: str, settings: Settings, ttl: CacheExpiry) -> bytes | Exception:
    """Resolve AEMET's two-step response pattern (envelope + separate "datos" URL)."""
    file = _download_with_rate_limit_retry(url, settings, ttl)
    if isinstance(file.content, Exception):
        return file.content
    envelope = json.load(file.content)
    if envelope.get("estado") != 200:
        return Exception(envelope.get("descripcion", "unknown AEMET error"))
    datos_file = _download_with_rate_limit_retry(envelope["datos"], settings, ttl)
    if isinstance(datos_file.content, Exception):
        return datos_file.content
    # AEMET serves the "datos" payload as ISO-8859-1, not UTF-8.
    return datos_file.content.read()


def _probe_aemet_credentials(settings: Settings) -> bool:
    """Probe the AEMET API; result is cached on disk for ONE_HOUR via download_file."""
    if not settings.auth.aemet:
        return False
    url = f"{_BASE_URL}/valores/climatologicos/inventarioestaciones/todasestaciones?api_key={settings.auth.aemet}"
    payload = _fetch_datos(url, settings, CacheExpiry.ONE_HOUR)
    return not isinstance(payload, Exception)


class AemetObservationValues(TimeseriesValues):
    """Values class for AEMET OpenData observation data."""

    _endpoint_daily = (
        _BASE_URL + "/valores/climatologicos/diarios/datos/"
        "fechaini/{start_date}/fechafin/{end_date}/estacion/{station_id}"
        "?api_key={api_key}"
    )
    _endpoint_monthly = (
        _BASE_URL + "/valores/climatologicos/mensualesanuales/datos/"
        "anioini/{start_year}/aniofin/{end_year}/estacion/{station_id}"
        "?api_key={api_key}"
    )
    _endpoint_realtime = _BASE_URL + "/observacion/convencional/datos/estacion/{station_id}?api_key={api_key}"

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
        start_date/end_date (if any) happens generically afterward in TimeseriesValues.query().
        """
        settings = cast("Settings", self.sr.stations.settings)
        api_key = settings.auth.aemet
        if not api_key:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        url = self._endpoint_realtime.format(station_id=station_id, api_key=api_key)
        payload = _fetch_datos(url, settings, CacheExpiry.FIVE_MINUTES)
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
            pl.col("fint").str.to_datetime("%Y-%m-%dT%H:%M:%S%z").dt.convert_time_zone("UTC").alias("date"),
            pl.col("value"),
            pl.lit(None, pl.Float64).alias("quality"),
        )

    def _collect_daily(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        settings = cast("Settings", self.sr.stations.settings)
        api_key = settings.auth.aemet
        start_date = self.sr.start_date
        end_date = self.sr.end_date
        if not start_date or not end_date or not api_key:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        records = []
        for chunk_start, chunk_end in self._date_chunks(start_date, end_date):
            url = self._endpoint_daily.format(
                station_id=station_id,
                start_date=chunk_start.strftime("%Y-%m-%dT%H:%M:%SUTC"),
                end_date=chunk_end.strftime("%Y-%m-%dT%H:%M:%SUTC"),
                api_key=api_key,
            )
            payload = _fetch_datos(url, settings, CacheExpiry.FIVE_MINUTES)
            if isinstance(payload, Exception):
                # rate-limit retries (if applicable) are already exhausted at this point,
                # so this chunk's data is genuinely missing from the result.
                log.warning(f"Failed to acquire AEMET data for station {station_id}, chunk {url}: {payload}")
                continue
            records.extend(json.loads(payload.decode("latin-1")))
        if not records:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.DataFrame(records, infer_schema_length=None)
        for column in ("fecha", *_VALUE_COLUMNS):
            if column not in df.columns:
                df = df.with_columns(pl.lit(None, pl.String).alias(column))
        df = df.with_columns(
            parse_decimal_comma("tmed").alias("tmed"),
            parse_decimal_comma("tmax").alias("tmax"),
            parse_decimal_comma("tmin").alias("tmin"),
            parse_decimal_comma("prec").alias("prec"),
            parse_wind_direction("dir").alias("dir"),
            parse_decimal_comma("velmedia").alias("velmedia"),
            parse_decimal_comma("racha").alias("racha"),
            parse_decimal_comma("presMax").alias("presMax"),
            parse_decimal_comma("presMin").alias("presMin"),
            pl.col("hrMedia").cast(pl.Float64, strict=False).alias("hrMedia"),
            pl.col("hrMax").cast(pl.Float64, strict=False).alias("hrMax"),
            pl.col("hrMin").cast(pl.Float64, strict=False).alias("hrMin"),
        )
        df = df.unpivot(index="fecha", on=list(_VALUE_COLUMNS), variable_name="parameter", value_name="value")
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("fecha").str.to_datetime("%Y-%m-%d").dt.replace_time_zone("UTC").alias("date"),
            pl.col("value"),
            pl.lit(None, pl.Float64).alias("quality"),
        )

    def _collect_monthly_or_annual(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        """Collect monthly or annual values.

        Both resolutions come from the same AEMET endpoint (mensualesanuales) in one
        combined response: a "fecha" of "YYYY-01".."YYYY-12" is a month, "YYYY-13" is
        that year's annual total/summary. Which one this call returns is decided by
        dataset.resolution — the other rows are simply filtered out.
        """
        settings = cast("Settings", self.sr.stations.settings)
        api_key = settings.auth.aemet
        start_date = self.sr.start_date
        end_date = self.sr.end_date
        if not start_date or not end_date or not api_key:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        records = []
        for start_year, end_year in self._year_chunks(start_date.year, end_date.year):
            url = self._endpoint_monthly.format(
                station_id=station_id,
                start_year=start_year,
                end_year=end_year,
                api_key=api_key,
            )
            payload = _fetch_datos(url, settings, CacheExpiry.FIVE_MINUTES)
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
        df = df.with_columns(
            parse_monthly_value("tm_mes").alias("tm_mes"),
            parse_monthly_value("tm_max").alias("tm_max"),
            parse_monthly_value("tm_min").alias("tm_min"),
            parse_monthly_value("ta_max").alias("ta_max"),
            parse_monthly_value("ta_min").alias("ta_min"),
            parse_monthly_value("p_mes").alias("p_mes"),
            parse_monthly_value("p_max").alias("p_max"),
            pl.col("hr").cast(pl.Float64, strict=False).alias("hr"),
        )
        df = df.unpivot(
            index="_date",
            on=list(_MONTHLY_ANNUAL_VALUE_COLUMNS),
            variable_name="parameter",
            value_name="value",
        )
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("_date").cast(pl.Datetime(time_zone="UTC")).alias("date"),
            pl.col("value"),
            pl.lit(None, pl.Float64).alias("quality"),
        )


@dataclass
class AemetObservationRequest(TimeseriesRequest):
    """Request class for AEMET OpenData observation data."""

    metadata = AemetObservationMetadata
    _values = AemetObservationValues

    _endpoint = _BASE_URL + "/valores/climatologicos/inventarioestaciones/todasestaciones?api_key={api_key}"

    @classmethod
    def is_configured(cls) -> bool:  # noqa: D102
        return bool(Settings().auth.aemet)

    @classmethod
    def is_valid(cls, settings: Settings | None = None) -> bool:  # noqa: D102
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
            raise ValueError(msg)

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        url = self._endpoint.format(api_key=settings.auth.aemet)
        payload = _fetch_datos(url, settings, CacheExpiry.METAINDEX)
        if isinstance(payload, Exception):
            log.warning(f"Failed to fetch AEMET stations: {payload}")
            return pl.LazyFrame()

        df = pl.DataFrame(json.loads(payload.decode("latin-1")))
        df = df.rename({"indicativo": "station_id", "nombre": "name", "provincia": "state"})
        df = df.with_columns(
            pl.col("altitud").cast(pl.Float64, strict=False).alias("height"),
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
