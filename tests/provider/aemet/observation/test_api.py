# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for AEMET OpenData observation provider."""

import contextlib
import datetime as dt
import json
import logging
from collections.abc import Callable
from http import HTTPStatus
from io import BytesIO
from itertools import pairwise
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from aiohttp import ClientPayloadError, ClientResponseError, ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

from tests.conftest import skip_if_upstream_unavailable
from wetterdienst.exceptions import CredentialRejectedError, DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.aemet.observation import api as aemet_api
from wetterdienst.provider.aemet.observation.api import (
    AemetKeyRejectedError,
    AemetObservationRequest,
    AemetObservationValues,
    _AemetEnvelopeError,
    _download_with_rate_limit_retry,
)
from wetterdienst.provider.aemet.observation.parser import (
    parse_decimal_comma,
    parse_monthly_value,
    parse_wind_direction,
)
from wetterdienst.settings import Settings
from wetterdienst.ui.core import failure_status
from wetterdienst.util.network import PROBE_TIMEOUT_SECONDS, File

MADRID_RETIRO = "3195"
BARCELONA = "0076"
UTC = ZoneInfo("UTC")

# Applied per-test (not as module-level pytestmark) so the local unit tests further down
# (chunking, retry behavior) still run without AEMET credentials.
requires_aemet_credentials = pytest.mark.skipif(
    not AemetObservationRequest.is_configured(),
    reason="AEMET credentials not set — provide WD_AUTH__AEMET=<api_key>",
)


def _is_rate_limit(failure: DownloadError) -> bool:
    """Tell whether a `DownloadError` is AEMET refusing the rate: an HTTP 429 or an `estado` 429 (GH-2989).

    A refused key is raised as the `CredentialRejectedError` by the reader (GH-3018), which `_values_or_skip` skips on.

    A timeout, a dropped connection and a 5xx are no refusal: the reader raises them as a `DownloadError` too, and
    `skip_if_upstream_unavailable` skips on them (GH-2965).

    A 400, a 404 or an envelope that says there is no data is AEMET answering, and what it most likely says is
    that the request was built wrong, which is what these tests are there to catch (see `tests/conftest.py`).
    """
    cause = failure.__cause__
    status = cause.status if isinstance(cause, (ClientResponseError, _AemetEnvelopeError)) else None
    return status == HTTPStatus.TOO_MANY_REQUESTS


def _values_or_skip(
    make_request: Callable[[], AemetObservationRequest],
    monkeypatch: pytest.MonkeyPatch,
) -> pl.DataFrame:
    """Build a request and read its values, and skip the test if AEMET refused the key or the rate (GH-2965).

    A timeout, a dropped connection or a 5xx is raised as a `DownloadError` that `skip_if_upstream_unavailable`
    skips on. A refused key is raised as the `CredentialRejectedError` (GH-3018), by the chunk and by the station
    list alike, and skips here, and so does a rate limit, a `DownloadError` whose cause is a 429 (GH-2989). CI runs
    every job of both workflows on one key, and AEMET answers that with a 401 or a 429 for part of the calls; the
    test asserts what AEMET publishes, which a refusal says nothing about. The request is built here, because
    filtering by station id already reads the station list.

    Only a refusal skips: a key refused (a revoked key skips the same way, and the reason names it) and a rate
    limit. Any other failure, such as a 404, and an empty frame without one fail.
    """
    failures: list[Exception] = []
    fetch = aemet_api._fetch_datos  # noqa: SLF001

    def recording_fetch(*args: Any, **kwargs: Any) -> bytes | Exception:  # noqa: ANN401
        payload = fetch(*args, **kwargs)
        if isinstance(payload, Exception):
            failures.append(payload)
        return payload

    monkeypatch.setattr(aemet_api, "_fetch_datos", recording_fetch)
    try:
        return make_request().values().all().df
    except CredentialRejectedError as refused:
        # the reason names what AEMET answered, which the error raised for the caller does not
        pytest.skip(f"AEMET did not hand out the data: {(failures or [refused])[0]!r}")
    except DownloadError as failed:
        if not _is_rate_limit(failed):
            raise
        pytest.skip(f"AEMET did not hand out the data: {failed!r}")


@pytest.mark.remote
@requires_aemet_credentials
def test_aemet_observation_stations() -> None:
    """Station metadata for Madrid/Retiro matches the AEMET station inventory."""
    request = AemetObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id(MADRID_RETIRO)
    expected = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": MADRID_RETIRO,
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 40.411389,
                "longitude": -3.677778,
                "elevation": 667.0,
                "name": "MADRID, RETIRO",
                "region": "MADRID",
            }
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
        },
        orient="row",
    )
    df = request.df
    assert (
        df.select(pl.exclude("latitude", "longitude")).to_dicts()
        == expected.select(
            pl.exclude("latitude", "longitude"),
        ).to_dicts()
    )
    assert df["latitude"].item() == pytest.approx(40.411389)
    assert df["longitude"].item() == pytest.approx(-3.677778)


@pytest.mark.remote
@requires_aemet_credentials
def test_aemet_observation_values_daily(monkeypatch: pytest.MonkeyPatch) -> None:
    """Daily climatological values at Madrid/Retiro match the AEMET reference values.

    2020-01-01 through 2020-01-05 is a fixed historical window unaffected by AEMET's
    real-time backfill/QC delay, so the expected values are stable.
    """
    df = _values_or_skip(
        lambda: AemetObservationRequest(
            parameters=[("daily", "data")],
            start=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end=dt.datetime(2020, 1, 5, tzinfo=UTC),
        ).filter_by_station_id(MADRID_RETIRO),
        monkeypatch,
    )
    assert df["station_id"].unique().to_list() == [MADRID_RETIRO]
    assert df["resolution"].unique().to_list() == ["daily"]

    def value_on(parameter: str, date: dt.datetime) -> float:
        row = df.filter(pl.col("parameter").eq(parameter), pl.col("timestamp").eq(date))
        return row.get_column("value").item()

    day1 = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert value_on("temperature_air_mean_2m", day1) == pytest.approx(6.6)
    assert value_on("temperature_air_max_2m", day1) == pytest.approx(11.2)
    assert value_on("temperature_air_min_2m", day1) == pytest.approx(1.9)
    assert value_on("precipitation_amount", day1) == pytest.approx(0.0)
    assert value_on("wind_speed_mean", day1) == pytest.approx(0.3)
    assert value_on("wind_gust_max", day1) == pytest.approx(3.3)
    assert value_on("wind_direction_gust_max", day1) == pytest.approx(50.0)
    assert value_on("pressure_air_site_max", day1) == pytest.approx(954.2)
    assert value_on("pressure_air_site_min", day1) == pytest.approx(952.0)
    # humidity is reported by AEMET as percent, wetterdienst stores it as fraction
    assert value_on("humidity_relative", day1) == pytest.approx(0.65)
    assert value_on("humidity_relative_max", day1) == pytest.approx(0.80)
    assert value_on("humidity_relative_min", day1) == pytest.approx(0.48)

    # 2020-01-02 has dir=99 (calm/variable), which AEMET encodes with a sentinel value
    # rather than an actual direction. The parser must turn that into a null rather than
    # a bogus 990°; with the default drop_nulls=True, a null value means no row at all.
    day2 = dt.datetime(2020, 1, 2, tzinfo=UTC)
    assert df.filter(pl.col("parameter").eq("wind_direction_gust_max"), pl.col("timestamp").eq(day2)).is_empty()


@pytest.mark.remote
@requires_aemet_credentials
def test_aemet_observation_values_monthly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monthly climatological values at Madrid/Retiro for January 2020 match the AEMET reference values."""
    df = _values_or_skip(
        lambda: AemetObservationRequest(
            parameters=[("monthly", "data")],
            start=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end=dt.datetime(2020, 1, 31, tzinfo=UTC),
        ).filter_by_station_id(MADRID_RETIRO),
        monkeypatch,
    )
    assert df["station_id"].unique().to_list() == [MADRID_RETIRO]
    assert df["resolution"].unique().to_list() == ["monthly"]
    assert df["timestamp"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(7.0)
    assert value_of("temperature_air_max_2m_mean") == pytest.approx(10.4)
    assert value_of("temperature_air_min_2m_mean") == pytest.approx(3.6)
    # the absolute extremes of the month come from a value with a day-of-occurrence annotation, e.g.
    # "15.7(31)" — the parser must strip that and keep just the number.
    assert value_of("temperature_air_max_2m") == pytest.approx(15.7)
    assert value_of("temperature_air_min_2m") == pytest.approx(-0.7)
    assert value_of("precipitation_amount") == pytest.approx(16.4)
    assert value_of("precipitation_amount_max") == pytest.approx(5.4)
    # humidity is reported by AEMET as percent, wetterdienst stores it as fraction
    assert value_of("humidity_relative") == pytest.approx(0.66)


@pytest.mark.remote
@requires_aemet_credentials
def test_aemet_observation_values_annual(monkeypatch: pytest.MonkeyPatch) -> None:
    """Annual climatological values at Madrid/Retiro for 2020 match the AEMET reference values.

    Also verifies that monthly and annual values are correctly split out of the same
    underlying AEMET response (distinguished by the "fecha" suffix), and that fields
    AEMET omits from the annual aggregate (like humidity) are simply absent rather than
    wrongly carried over from a monthly row.
    """
    df = _values_or_skip(
        lambda: AemetObservationRequest(
            parameters=[("annual", "data")],
            start=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end=dt.datetime(2020, 12, 31, tzinfo=UTC),
        ).filter_by_station_id(MADRID_RETIRO),
        monkeypatch,
    )
    assert df["station_id"].unique().to_list() == [MADRID_RETIRO]
    assert df["resolution"].unique().to_list() == ["annual"]
    assert df["timestamp"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(16.0)
    assert value_of("temperature_air_max_2m_mean") == pytest.approx(20.9)
    assert value_of("temperature_air_min_2m_mean") == pytest.approx(11.1)
    # annotation is "(27/jul)" here (day/month, not just day, unlike the monthly endpoint)
    assert value_of("temperature_air_max_2m") == pytest.approx(39.4)
    assert value_of("temperature_air_min_2m") == pytest.approx(-1.3)
    assert value_of("precipitation_amount") == pytest.approx(474.4)
    assert value_of("precipitation_amount_max") == pytest.approx(37.8)
    # AEMET's annual aggregate doesn't include a humidity field at all
    assert df.filter(pl.col("parameter").eq("humidity_relative")).is_empty()


@pytest.mark.remote
@requires_aemet_credentials
def test_aemet_observation_values_hourly_realtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real-time (observación convencional) hourly values at Madrid/Retiro are structurally sane.

    This is live current-weather data with no fixed historical window (AEMET's endpoint
    doesn't accept a date range at all — it just returns whatever rolling window of recent
    hours it currently holds), so exact values can't be asserted like the other
    resolutions. This checks shape, recency, and physically plausible value ranges instead.
    """
    df = _values_or_skip(
        lambda: AemetObservationRequest(parameters=[("hourly", "data")]).filter_by_station_id(MADRID_RETIRO),
        monkeypatch,
    )
    assert not df.is_empty()
    assert df["station_id"].unique().to_list() == [MADRID_RETIRO]
    assert df["resolution"].unique().to_list() == ["hourly"]

    # no date range was passed (date_required=False for this resolution) and AEMET only
    # ever returns a recent rolling window, so the latest timestamp should be recent.
    now = dt.datetime.now(tz=UTC)
    latest_date = df["timestamp"].max()
    assert isinstance(latest_date, dt.datetime)
    assert latest_date >= now - dt.timedelta(hours=36)
    assert latest_date <= now + dt.timedelta(minutes=5)

    def latest(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).sort("timestamp").get_column("value")[-1]

    assert -40 < latest("temperature_air_2m") < 50
    assert 0.0 <= latest("humidity_relative") <= 1.0
    # unlike the daily endpoint's coded 0-36 direction, real-time direction is already in
    # plain degrees — this would fail if the daily parser's *10 scaling was wrongly reused.
    assert 0 <= latest("wind_direction_mean_last_10min") <= 360
    assert 800 < latest("pressure_air_site") < 1100


def test_aemet_observation_date_chunks_within_limit() -> None:
    """A date range within the 6-month limit is not split at all."""
    start_date = dt.datetime(2020, 1, 1, tzinfo=UTC)
    end_date = dt.datetime(2020, 1, 5, tzinfo=UTC)
    chunks = list(AemetObservationValues._date_chunks(start_date, end_date))  # noqa: SLF001
    assert chunks == [(start_date, end_date)]


def test_aemet_observation_date_chunks_split_and_cover_full_range() -> None:
    """A date range spanning more than 6 months is split into multiple chunks.

    AEMET rejects any single request spanning more than 6 months (discovered against the
    live API — this limit isn't documented). The chunks must together cover the whole
    requested range exactly once, with no gaps or overlaps, and none may itself exceed
    the 6-month limit.
    """
    start_date = dt.datetime(2020, 1, 1, tzinfo=UTC)
    end_date = dt.datetime(2021, 6, 30, tzinfo=UTC)
    chunks = list(AemetObservationValues._date_chunks(start_date, end_date))  # noqa: SLF001

    assert len(chunks) > 1
    assert chunks[0][0] == start_date
    assert chunks[-1][1] == end_date
    for chunk_start, chunk_end in chunks:
        assert (chunk_end - chunk_start).days <= 180

    # chunks must be contiguous: each one starts exactly one second after the previous ends
    for (_, prev_end), (next_start, _) in pairwise(chunks):
        assert next_start == prev_end + dt.timedelta(seconds=1)


def test_aemet_observation_daily_normalizes_non_utc_start_end_date_to_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tz-aware non-UTC start/end date is normalized to UTC before being sent to AEMET.

    TimeseriesRequest.convert_timestamps() only tags naive datetimes as UTC; it never
    converts an already-tz-aware non-UTC datetime. Madrid is UTC+1 in January, so
    2020-01-01 00:30 Madrid time is 2019-12-31 23:30 UTC -- if _collect_daily formatted
    the raw (non-UTC) wall-clock values with a hardcoded "UTC" suffix, AEMET would
    silently be asked for the wrong day entirely.
    """
    captured_urls = []
    station_payload = json.dumps(
        [
            {
                "indicativo": MADRID_RETIRO,
                "nombre": "MADRID, RETIRO",
                "provincia": "MADRID",
                "altitud": "667",
                "latitud": "402941N",
                "longitud": "34041W",
            },
        ],
    ).encode("latin-1")

    def fake_fetch_datos(url: str, *_args: object, **_kwargs: object) -> bytes | Exception:
        if "todasestaciones" in url:
            return station_payload
        captured_urls.append(url)
        return Exception("stop after capturing the request URL")

    monkeypatch.setattr("wetterdienst.provider.aemet.observation.api._fetch_datos", fake_fetch_datos)

    madrid = ZoneInfo("Europe/Madrid")
    with contextlib.suppress(ValueError):
        # ValueError("cannot concat empty list"): expected, since the daily fetch above
        # deliberately fails after capturing the URL -- only the URL matters here.
        AemetObservationRequest(
            parameters=[("daily", "data")],
            start=dt.datetime(2020, 1, 1, 0, 30, tzinfo=madrid),
            end=dt.datetime(2020, 1, 1, 0, 30, tzinfo=madrid),
            settings=Settings(auth={"aemet": "dummy-key-for-test"}),
        ).filter_by_station_id(MADRID_RETIRO).values().all()

    assert len(captured_urls) == 1
    assert "fechaini/2019-12-31T23:30:00UTC" in captured_urls[0]
    assert "fechafin/2019-12-31T23:30:00UTC" in captured_urls[0]


def test_aemet_observation_year_chunks_within_limit() -> None:
    """A year range within the 3-year (36-month) limit is not split at all."""
    chunks = list(AemetObservationValues._year_chunks(2018, 2020))  # noqa: SLF001
    assert chunks == [(2018, 2020)]


def test_aemet_observation_year_chunks_split_and_cover_full_range() -> None:
    """A year range spanning more than 3 years is split into multiple chunks.

    AEMET rejects any single request spanning more than 36 months (discovered against the
    live API — this limit isn't documented). The chunks must together cover the whole
    requested range exactly once, with no gaps or overlaps, and none may itself exceed
    the 3-year limit.
    """
    chunks = list(AemetObservationValues._year_chunks(2000, 2020))  # noqa: SLF001

    assert len(chunks) > 1
    assert chunks[0][0] == 2000
    assert chunks[-1][1] == 2020
    for chunk_start, chunk_end in chunks:
        assert chunk_end - chunk_start <= 2  # at most 3 years inclusive

    # chunks must be contiguous: each one starts exactly one year after the previous ends
    for (_, prev_end), (next_start, _) in pairwise(chunks):
        assert next_start == prev_end + 1


def test_aemet_observation_rate_limit_retry_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 response is retried with a backoff instead of being treated as a normal failure.

    AEMET's own error message for a 429 is "wait for the next minute" — the short
    retry/backoff baked into download_file() is nowhere near enough for that, so this
    provider runs its own stamina retry loop on top. download_file is mocked so the test
    needs no real credentials or network access; the retry wait is set to a fraction of a
    second (rather than the real up-to-60s) so the test stays fast.
    """
    responses = iter(
        [
            File(url="url", content=Exception("rate limited"), status=429),
            File(url="url", content=Exception("rate limited"), status=429),
            File(url="url", content=BytesIO(b"ok"), status=200),
        ],
    )
    calls = []
    monkeypatch.setattr(
        "wetterdienst.provider.aemet.observation.api.download_file",
        lambda **_kwargs: (calls.append(1), next(responses))[1],
    )
    result = _download_with_rate_limit_retry(
        "https://example.org",
        Settings(),
        CacheExpiry.NO_CACHE,
        wait_initial=0.01,
        wait_max=0.01,
        max_retries=2,
    )
    assert result.status == 200
    assert len(calls) == 3


def test_aemet_observation_transient_failure_retry_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient failure (e.g. a dropped connection) is retried like a 429.

    AEMET has been observed, live, to intermittently drop connections outright even
    after download_file()'s own short built-in retry is exhausted — those chunk-losing
    failures are retried the same way as a 429, just with a shorter backoff.
    """
    responses = iter(
        [
            File(url="url", content=Exception("connection reset"), status=503),
            File(url="url", content=BytesIO(b"ok"), status=200),
        ],
    )
    calls = []
    monkeypatch.setattr(
        "wetterdienst.provider.aemet.observation.api.download_file",
        lambda **_kwargs: (calls.append(1), next(responses))[1],
    )
    result = _download_with_rate_limit_retry(
        "https://example.org",
        Settings(),
        CacheExpiry.NO_CACHE,
        wait_initial=0.01,
        wait_max=0.01,
        max_retries=2,
    )
    assert result.status == 200
    assert len(calls) == 2


def test_aemet_observation_rate_limit_retry_gives_up_eventually(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent 429s are not retried forever — the caller gets back the failed File."""
    calls = []

    def always_429(**_kwargs: object) -> File:
        calls.append(1)
        return File(url="url", content=Exception("rate limited"), status=429)

    monkeypatch.setattr("wetterdienst.provider.aemet.observation.api.download_file", always_429)
    result = _download_with_rate_limit_retry(
        "https://example.org",
        Settings(),
        CacheExpiry.NO_CACHE,
        wait_initial=0.01,
        wait_max=0.01,
        max_retries=2,
    )
    assert result.status == 429
    assert isinstance(result.content, Exception)
    assert len(calls) == 3  # 1 initial attempt + 2 retries, then gives up


def test_aemet_observation_permanent_failure_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-retryable failure (e.g. a plain 404) is returned immediately, without retrying."""
    calls = []

    def always_404(**_kwargs: object) -> File:
        calls.append(1)
        return File(url="url", content=Exception("not found"), status=404)

    monkeypatch.setattr("wetterdienst.provider.aemet.observation.api.download_file", always_404)
    result = _download_with_rate_limit_retry(
        "https://example.org",
        Settings(),
        CacheExpiry.NO_CACHE,
        wait_initial=0.01,
        wait_max=0.01,
        max_retries=2,
    )
    assert result.status == 404
    assert len(calls) == 1


def test_aemet_observation_no_internet_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download that failed for want of a network is returned at once, not retried."""
    calls = []

    def offline(**_kwargs: object) -> File:
        calls.append(1)
        return File(url="url", content=NoInternetError("no route to host"), status=503)

    monkeypatch.setattr("wetterdienst.provider.aemet.observation.api.download_file", offline)
    result = _download_with_rate_limit_retry(
        "https://example.org",
        Settings(),
        CacheExpiry.NO_CACHE,
        wait_initial=0.01,
        wait_max=0.01,
        max_retries=2,
    )
    assert result.is_no_internet_error
    assert len(calls) == 1


def test_aemet_observation_plain_503_still_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 503 that is not a missing network (an overloaded server) keeps its retries."""
    calls = []

    def overloaded(**_kwargs: object) -> File:
        calls.append(1)
        return File(url="url", content=Exception("service unavailable"), status=503)

    monkeypatch.setattr("wetterdienst.provider.aemet.observation.api.download_file", overloaded)
    result = _download_with_rate_limit_retry(
        "https://example.org",
        Settings(),
        CacheExpiry.NO_CACHE,
        wait_initial=0.01,
        wait_max=0.01,
        max_retries=2,
    )
    assert not result.is_no_internet_error
    assert len(calls) == 3


def _fake_fetch_datos(monkeypatch: pytest.MonkeyPatch, *answers: bytes | Exception) -> list[str]:
    """Serve the station list, answer the values requests with `answers` in order, the last for all after.

    Returns the values URLs requested.
    """
    attempted: list[str] = []
    station_payload = json.dumps(
        [
            {
                "indicativo": MADRID_RETIRO,
                "nombre": "MADRID, RETIRO",
                "provincia": "MADRID",
                "altitud": "667",
                "latitud": "402941N",
                "longitud": "34041W",
            },
            {
                "indicativo": BARCELONA,
                "nombre": "BARCELONA AEROPUERTO",
                "provincia": "BARCELONA",
                "altitud": "4",
                "latitud": "412258N",
                "longitud": "020412E",
            },
        ],
    ).encode("latin-1")

    def fake_fetch_datos(url: str, *_args: object, **_kwargs: object) -> bytes | Exception:
        if "todasestaciones" in url:
            return station_payload
        attempted.append(url)
        return answers[min(len(attempted), len(answers)) - 1]

    monkeypatch.setattr("wetterdienst.provider.aemet.observation.api._fetch_datos", fake_fetch_datos)
    return attempted


def _values(resolution: str, years: int, station_ids: tuple[str, ...] = (MADRID_RETIRO,)) -> pl.DataFrame:
    start = dt.datetime(2010, 1, 1, tzinfo=UTC)
    return (
        AemetObservationRequest(
            parameters=[(resolution, "data")],
            start=start,
            end=start.replace(year=start.year + years),
            settings=Settings(auth={"aemet": "dummy-key-for-test"}),
        )
        .filter_by_station_id(station_ids)
        .values()
        .all()
        .df
    )


@pytest.mark.parametrize("resolution", ["daily", "monthly", "annual", "hourly"])
def test_aemet_observation_values_offline_raise_at_the_first_chunk(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    resolution: str,
) -> None:
    """Offline, the per-chunk loops raise `NoInternetError` after one request, logging no warning (GH-2640)."""
    attempted = _fake_fetch_datos(monkeypatch, NoInternetError("no route to host"))
    with caplog.at_level(logging.DEBUG, logger="wetterdienst.provider.aemet"), pytest.raises(NoInternetError):
        _values(resolution, years=10)
    assert len(attempted) == 1
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


@pytest.mark.parametrize("resolution", ["daily", "monthly", "annual", "hourly"])
def test_aemet_observation_values_offline_raise_at_the_first_station(
    monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    """Offline, the request ends at the first download: the second station is not tried (GH-2620)."""
    attempted = _fake_fetch_datos(monkeypatch, NoInternetError("no route to host"))
    with pytest.raises(NoInternetError):
        _values(resolution, years=10, station_ids=(MADRID_RETIRO, BARCELONA))
    assert len(attempted) == 1


def test_aemet_observation_values_going_offline_midway_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A network lost after the first chunk raises, rather than answering with the chunk read (GH-2640)."""
    records = json.dumps([{"fecha": "2010-01-01", "tmed": "5,5"}]).encode("latin-1")
    attempted = _fake_fetch_datos(monkeypatch, records, NoInternetError("no route to host"))
    with pytest.raises(NoInternetError):
        _values("daily", years=10)
    assert len(attempted) == 2


def test_aemet_observation_stations_offline_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreachable AEMET is no network without stations (GH-2640)."""
    monkeypatch.setattr(
        "wetterdienst.provider.aemet.observation.api._fetch_datos",
        lambda *_args, **_kwargs: NoInternetError("no route to host"),
    )
    request = AemetObservationRequest(
        parameters=[("daily", "data")], settings=Settings(auth={"aemet": "dummy-key-for-test"})
    )
    with pytest.raises(NoInternetError):
        request.all()


@pytest.mark.parametrize(("resolution", "chunks"), [("daily", 21), ("monthly", 4), ("annual", 4)])
def test_aemet_observation_values_failed_chunk_is_skipped_and_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    resolution: str,
    chunks: int,
) -> None:
    """A failure that is not a missing network still skips only its own chunk, with a warning."""
    attempted = _fake_fetch_datos(monkeypatch, Exception("server error"))
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.aemet"):
        df = _values(resolution, years=10)
    assert df.is_empty()
    assert len(attempted) == chunks
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == chunks


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status)


def _rate_limited(cause: Exception) -> DownloadError:
    """Make the `DownloadError` `_fetch_datos` returns for a rate limit, with its `cause`."""
    error = DownloadError("https://opendata.aemet.es/opendata/api/x", "AEMET answered 429, the rate limit")
    error.__cause__ = cause
    return error


def _daily_request() -> AemetObservationRequest:
    return AemetObservationRequest(
        parameters=[("daily", "data")],
        start=dt.datetime(2020, 1, 1, tzinfo=UTC),
        end=dt.datetime(2020, 1, 5, tzinfo=UTC),
        settings=Settings(auth={"aemet": "dummy-key-for-test"}),
    ).filter_by_station_id(MADRID_RETIRO)


def _not_skipped(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    """Run the helper on a daily request, and turn a skip into a failure so that a wrong skip cannot pass as one."""
    try:
        return _values_or_skip(_daily_request, monkeypatch)
    except pytest.skip.Exception as skipped:
        return pytest.fail(f"skipped: {skipped}")


@pytest.mark.parametrize(
    "refusal",
    [
        pytest.param(AemetKeyRejectedError("AEMET answered HTTP 401: Unauthorized"), id="key-rejected"),
        pytest.param(_rate_limited(_response_error(429)), id="rate-limit"),
        pytest.param(_rate_limited(_AemetEnvelopeError(429, "wait for the next minute")), id="rate-limit-estado"),
    ],
)
def test_values_or_skip_skips_when_aemet_refused_the_data(monkeypatch: pytest.MonkeyPatch, refusal: Exception) -> None:
    """A chunk AEMET refused (a 401 or a 429 of a key shared by CI) skips, naming the answer."""
    _fake_fetch_datos(monkeypatch, refusal)
    with pytest.raises(pytest.skip.Exception, match="AEMET did not hand out the data"):
        _values_or_skip(_daily_request, monkeypatch)


def test_values_or_skip_skips_when_the_station_list_was_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The station list is read by the request, under the helper, and its refusal skips too."""
    refusal = AemetKeyRejectedError("AEMET answered HTTP 401: Unauthorized")
    monkeypatch.setattr(aemet_api, "_fetch_datos", lambda *_args, **_kwargs: refusal)
    with pytest.raises(pytest.skip.Exception, match="HTTP 401"):
        _values_or_skip(_daily_request, monkeypatch)


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(Exception("No hay datos que satisfagan esos criterios de busqueda"), id="envelope-no-data"),
        pytest.param(_response_error(404), id="404"),
        pytest.param(_response_error(400), id="400"),
    ],
)
def test_values_or_skip_does_not_skip_an_answer_that_is_no_refusal(
    monkeypatch: pytest.MonkeyPatch, answer: Exception
) -> None:
    """AEMET answering that it has no data, or that the request is wrong, goes back as the empty frame it is."""
    _fake_fetch_datos(monkeypatch, answer)
    assert _not_skipped(monkeypatch).is_empty()


def test_values_or_skip_does_not_skip_an_empty_array(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty array is AEMET answering with no data: the frame goes back, empty, to fail the test."""
    _fake_fetch_datos(monkeypatch, b"[]")
    assert _not_skipped(monkeypatch).is_empty()


def test_values_or_skip_hands_out_what_aemet_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Values that arrived are returned for the test to assert on."""
    records = json.dumps([{"fecha": "2020-01-01", "tmed": "6,6", "dir": "05"}]).encode("latin-1")
    _fake_fetch_datos(monkeypatch, records)
    df = _not_skipped(monkeypatch)
    assert df.filter(pl.col("parameter").eq("wind_direction_gust_max")).get_column("value").to_list() == [50.0]


_OUTAGES = [
    pytest.param(FSTimeoutError(), id="timeout"),
    pytest.param(ServerDisconnectedError(), id="dropped connection"),
    pytest.param(ClientPayloadError("body cut short"), id="cut body"),
    pytest.param(_response_error(500), id="500"),
    pytest.param(_response_error(503), id="503"),
]


def _download_error(cause: Exception) -> DownloadError:
    error = DownloadError("https://opendata.aemet.es/opendata/api/x", "outage")
    error.__cause__ = cause
    return error


@pytest.mark.parametrize("resolution", ["daily", "monthly", "annual", "hourly"])
def test_aemet_observation_values_raise_a_download_error_at_the_first_chunk(
    monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    """An AEMET that did not answer ends the request with the `DownloadError`, after one request (GH-2965)."""
    failure = _download_error(FSTimeoutError())
    attempted = _fake_fetch_datos(monkeypatch, failure)
    with pytest.raises(DownloadError) as raised:
        _values(resolution, years=10, station_ids=(MADRID_RETIRO, BARCELONA))
    assert raised.value is failure
    assert len(attempted) == 1


def test_aemet_observation_values_going_down_midway_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An AEMET that stops answering after the first chunk raises, rather than answering with the chunk read."""
    records = json.dumps([{"fecha": "2010-01-01", "tmed": "5,5"}]).encode("latin-1")
    attempted = _fake_fetch_datos(monkeypatch, records, _download_error(_response_error(503)))
    with pytest.raises(DownloadError):
        _values("daily", years=10)
    assert len(attempted) == 2


@pytest.mark.parametrize("resolution", ["daily", "monthly", "annual", "hourly"])
def test_aemet_observation_values_raise_credential_rejected_error_at_the_first_chunk(
    monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    """A key AEMET refuses ends the request after one request, naming the setting and not the key (GH-3018)."""
    attempted = _fake_fetch_datos(monkeypatch, AemetKeyRejectedError("AEMET answered HTTP 401: Unauthorized"))
    with pytest.raises(CredentialRejectedError) as raised:
        _values(resolution, years=10, station_ids=(MADRID_RETIRO, BARCELONA))
    assert "WD_AUTH__AEMET" in str(raised.value)
    assert "dummy-key-for-test" not in f"{raised.value!s}{raised.value!r}"
    assert len(attempted) == 1


def test_aemet_observation_values_raise_when_the_key_is_refused_midway(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key refused after the first chunk raises, rather than answering with the chunk read (GH-3018)."""
    records = json.dumps([{"fecha": "2010-01-01", "tmed": "5,5"}]).encode("latin-1")
    attempted = _fake_fetch_datos(monkeypatch, records, AemetKeyRejectedError("AEMET answered HTTP 401: Unauthorized"))
    with pytest.raises(CredentialRejectedError):
        _values("daily", years=10)
    assert len(attempted) == 2


def _stations(monkeypatch: pytest.MonkeyPatch, answer: bytes | Exception) -> AemetObservationRequest:
    """Serve the station list as `answer`, and give the request that reads it."""
    monkeypatch.setattr(aemet_api, "_fetch_datos", lambda *_args, **_kwargs: answer)
    return AemetObservationRequest(
        parameters=[("daily", "data")], settings=Settings(auth={"aemet": "dummy-key-for-test"})
    )


@pytest.mark.parametrize("failure", _OUTAGES)
def test_aemet_observation_stations_raise_a_download_error_for_a_list_that_did_not_answer(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    """An AEMET that does not answer the station list is no network without stations (GH-3022)."""
    error = _download_error(failure)
    with pytest.raises(DownloadError) as raised:
        _stations(monkeypatch, error).all()
    assert raised.value is error


def test_aemet_observation_stations_raise_credential_rejected_error_for_a_refused_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A key AEMET refuses for the station list is raised, not read as a network without stations (GH-3018)."""
    request = _stations(monkeypatch, AemetKeyRejectedError("AEMET answered HTTP 403: Forbidden"))
    with pytest.raises(CredentialRejectedError, match="WD_AUTH__AEMET"):
        request.all()


def test_aemet_observation_stations_keep_the_empty_result_for_an_answer(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An `estado` of 404 for the station list is AEMET answering: no stations, warned about, as before."""
    request = _stations(monkeypatch, _AemetEnvelopeError(404, "No hay datos"))
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.aemet"):
        assert request.all().df.is_empty()
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING] == [
        "Failed to fetch AEMET stations: No hay datos",
    ]


def _serve_envelope_and_datos(monkeypatch: pytest.MonkeyPatch, envelope: File, datos: File | None = None) -> list[str]:
    """Answer the envelope request with `envelope` and the request of its "datos" link with `datos`.

    Returns the urls asked.
    """
    asked: list[str] = []

    def download(url: str, *_args: object, **_kwargs: object) -> File:
        asked.append(url)
        if len(asked) == 1:
            return envelope
        assert datos is not None
        return datos

    monkeypatch.setattr(aemet_api, "_download_with_rate_limit_retry", download)
    return asked


def _serve_in_turn(monkeypatch: pytest.MonkeyPatch, *answers: File) -> list[str]:
    """Answer the requests of `_fetch_datos` with `answers` in turn, the last one for good. Returns the urls asked."""
    asked: list[str] = []

    def download(url: str, *_args: object, **_kwargs: object) -> File:
        asked.append(url)
        return answers[min(len(asked), len(answers)) - 1]

    monkeypatch.setattr(aemet_api, "_download_with_rate_limit_retry", download)
    return asked


_ENDPOINT = "https://opendata.aemet.es/opendata/api/valores/climatologicos/diarios/datos/x"
_DATOS = "https://opendata.aemet.es/opendata/sh/0123abc?X-Amz-Signature=secret"


def _fetch() -> bytes | Exception:
    return aemet_api._fetch_datos(  # noqa: SLF001
        _ENDPOINT, Settings(auth={"aemet": "dummy-key-for-test"}, cache_disable=True), CacheExpiry.NO_CACHE
    )


@pytest.mark.parametrize("failure", _OUTAGES)
def test_aemet_fetch_datos_returns_an_envelope_that_did_not_answer_as_a_download_error(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    """The envelope request that timed out, was dropped or cut short, or met a 5xx, is a `DownloadError` naming it."""
    _serve_envelope_and_datos(monkeypatch, File(url=_ENDPOINT, content=failure, status=500))
    result = _fetch()
    assert isinstance(result, DownloadError)
    assert result.url == _ENDPOINT
    assert result.__cause__ is failure


@pytest.mark.parametrize("failure", _OUTAGES)
def test_aemet_fetch_datos_returns_a_datos_link_that_did_not_answer_as_a_download_error(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    """The "datos" request that did not answer is a `DownloadError` naming the link, without its signature."""
    _serve_envelope_and_datos(monkeypatch, _envelope(200, datos=_DATOS), File(url=_DATOS, content=failure, status=500))
    result = _fetch()
    assert isinstance(result, DownloadError)
    assert result.url == "https://opendata.aemet.es/opendata/sh/0123abc"
    assert "secret" not in str(result)
    assert result.__cause__ is failure


@pytest.mark.parametrize("estado", [500, 502, 503])
def test_aemet_fetch_datos_returns_a_fault_of_the_envelope_as_a_download_error(
    monkeypatch: pytest.MonkeyPatch, estado: int
) -> None:
    """AEMET reports its own faults as the `estado` of an HTTP 200, which is a 5xx like any other."""
    _serve_envelope_and_datos(monkeypatch, _envelope(estado))
    result = _fetch()
    assert isinstance(result, DownloadError)
    assert result.url == "envelope"
    assert str(estado) in str(result)


@pytest.mark.parametrize(
    ("as_envelope", "reason"),
    [
        pytest.param(False, "HTTP 429, the rate limit", id="http-429"),
        pytest.param(True, "estado 429, the rate limit: the answer", id="estado-429"),
    ],
)
def test_aemet_fetch_datos_returns_a_rate_limit_as_a_download_error(
    monkeypatch: pytest.MonkeyPatch,
    as_envelope: bool,  # noqa: FBT001
    reason: str,
) -> None:
    """A rate limit that outlasted the retries is no answer: a `DownloadError` naming the file, caused by the 429."""
    file = _envelope(429) if as_envelope else File(url=_ENDPOINT, content=_response_error(429), status=429)
    _serve_envelope_and_datos(monkeypatch, file)
    result = _fetch()
    assert isinstance(result, DownloadError)
    assert result.url == file.url
    assert reason in str(result)
    assert result.__cause__ is not None
    assert getattr(result.__cause__, "status", None) == HTTPStatus.TOO_MANY_REQUESTS
    # a 429 is a failure of the provider's, answered as the table of `failure_status` has it
    assert failure_status(result) == HTTPStatus.BAD_GATEWAY


def test_aemet_fetch_datos_returns_a_rate_limit_of_the_datos_link_as_a_download_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The "datos" request met by the rate limit is a `DownloadError` naming the link, without its signature."""
    refusal = _response_error(429)
    _serve_envelope_and_datos(monkeypatch, _envelope(200, datos=_DATOS), File(url=_DATOS, content=refusal, status=429))
    result = _fetch()
    assert isinstance(result, DownloadError)
    assert result.url == "https://opendata.aemet.es/opendata/sh/0123abc"
    assert "secret" not in str(result)
    assert result.__cause__ is refusal


@pytest.mark.parametrize("resolution", ["daily", "monthly", "annual", "hourly"])
def test_aemet_observation_values_raise_a_rate_limit_rather_than_skip_the_chunk(
    monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    """A chunk the rate limit refused is not "no data": the request ends with the error, not with a partial result."""
    attempted = _fake_fetch_datos(monkeypatch, _rate_limited(_response_error(429)))
    with pytest.raises(DownloadError, match="the rate limit"):
        _values(resolution, years=10)
    assert len(attempted) == 1


def test_aemet_fetch_datos_returns_an_estado_that_is_no_number_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """An `estado` the JSON gives as text is no status to compare: it stays a plain failure, which is logged."""
    body = json.dumps({"estado": "500", "descripcion": "the answer"}).encode()
    _serve_envelope_and_datos(monkeypatch, File(url=_ENDPOINT, content=BytesIO(body), status=200))
    result = _fetch()
    assert isinstance(result, Exception)
    assert not isinstance(result, DownloadError)


def test_aemet_fetch_datos_returns_what_is_an_answer_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404, an `estado` of 404, a refused key and a body that is no envelope stay what they were."""
    for file in (
        File(url=_ENDPOINT, content=FileNotFoundError(_ENDPOINT), status=404),
        File(url=_ENDPOINT, content=_response_error(400), status=400),
        _envelope(404),
        File(url=_ENDPOINT, content=BytesIO(b"<html>maintenance</html>"), status=200),
    ):
        _serve_envelope_and_datos(monkeypatch, file)
        result = _fetch()
        assert isinstance(result, Exception)
        assert not isinstance(result, DownloadError), file
    for refusal in (lambda: File(url=_ENDPOINT, content=_response_error(401), status=401), lambda: _envelope(403)):
        # a refusal is asked for once more (GH-3022), so it is the answer to both requests
        _serve_in_turn(monkeypatch, refusal(), refusal())
        assert isinstance(_fetch(), AemetKeyRejectedError)
    _serve_envelope_and_datos(
        monkeypatch, _envelope(200, datos=_DATOS), File(url=_DATOS, content=FileNotFoundError(_DATOS), status=404)
    )
    assert isinstance(_fetch(), FileNotFoundError)


def test_aemet_fetch_datos_does_not_take_a_refused_datos_link_for_a_refused_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The "datos" link is pre-signed and takes no key: its 403 says nothing of the key (GH-3018)."""
    refusal = _response_error(403)
    _serve_envelope_and_datos(monkeypatch, _envelope(200, datos=_DATOS), File(url=_DATOS, content=refusal, status=403))
    result = _fetch()
    assert result is refusal
    assert not isinstance(result, AemetKeyRejectedError)


def test_aemet_fetch_datos_returns_no_internet_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed connection stays the `NoInternetError` it is (GH-2640)."""
    offline = NoInternetError("no route to host")
    _serve_envelope_and_datos(monkeypatch, File(url=_ENDPOINT, content=offline, status=503))
    assert _fetch() is offline


def test_aemet_observation_values_keep_the_empty_result_for_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404 and an `estado` of 404 are AEMET answering that it has no data: the empty frame, as before."""
    _serve_envelope_and_datos(monkeypatch, File(url=_ENDPOINT, content=FileNotFoundError(_ENDPOINT), status=404))
    assert _values("daily", years=1).is_empty()
    _serve_envelope_and_datos(monkeypatch, _envelope(404))
    assert _values("hourly", years=1).is_empty()


@pytest.mark.parametrize(
    ("failure", "skipped"),
    [
        pytest.param(FSTimeoutError(), True, id="timeout"),
        pytest.param(_response_error(503), True, id="503"),
        pytest.param(_AemetEnvelopeError(500, "AEMET fault"), True, id="estado-500"),
        pytest.param(FileNotFoundError("not found"), False, id="404 is an answer"),
    ],
)
def test_aemet_outage_met_by_the_values_reader_skips_the_remote_test(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    skipped: bool,  # noqa: FBT001
) -> None:
    """A remote AEMET test is skipped on an outage of the values, which used to reach it as an empty frame."""
    stations = json.dumps(
        [
            {
                "indicativo": MADRID_RETIRO,
                "nombre": "MADRID, RETIRO",
                "provincia": "MADRID",
                "altitud": "667",
                "latitud": "402941N",
                "longitud": "34041W",
            }
        ]
    ).encode("latin-1")

    def download(url: str, *_args: object, **_kwargs: object) -> File:
        if "todasestaciones" in url:
            return _envelope(200, datos="https://opendata.aemet.es/opendata/sh/stations")
        if url.endswith("/sh/stations"):
            return File(url=url, content=BytesIO(stations), status=200)
        if isinstance(failure, _AemetEnvelopeError):
            return _envelope(failure.status)
        return File(url=url, content=failure, status=500)

    monkeypatch.setattr(aemet_api, "_download_with_rate_limit_retry", download)

    @skip_if_upstream_unavailable()
    def _remote_test() -> None:
        assert not _daily_request().values().all().df.is_empty()

    with pytest.raises(pytest.skip.Exception if skipped else AssertionError):
        _remote_test()


def _probe_answering(monkeypatch: pytest.MonkeyPatch, *files: File) -> list[dict]:
    """Have the probe's download answer with `files` in order, and fail a probe that goes through the retry loop.

    Returns what the download was called with.
    """
    calls: list[dict] = []
    answers = iter(files)

    def download(**kwargs: object) -> File:
        calls.append(kwargs)
        return next(answers)

    def retried(*_args: object, **_kwargs: object) -> File:
        msg = "a probe is not retried (GH-2564)"
        raise AssertionError(msg)

    monkeypatch.setattr("wetterdienst.provider.aemet.observation.api.download_file", download)
    monkeypatch.setattr("wetterdienst.provider.aemet.observation.api._download_with_rate_limit_retry", retried)
    return calls


def _envelope(estado: int, **extra: str) -> File:
    body = json.dumps({"estado": estado, "descripcion": "the answer", **extra}).encode()
    return File(url="envelope", content=BytesIO(body), status=200)


@pytest.fixture
def _aemet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WD_AUTH__AEMET", "dummy-key-for-test")


@pytest.mark.usefixtures("_aemet_key")
@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(File(url="u", content=Exception("401, message='Unauthorized'"), status=401), id="http-401"),
        pytest.param(File(url="u", content=Exception("403, message='Forbidden'"), status=403), id="http-403"),
        pytest.param(_envelope(401), id="estado-401"),
        pytest.param(_envelope(403), id="estado-403"),
    ],
)
def test_aemet_observation_is_valid_is_false_for_a_rejected_key(monkeypatch: pytest.MonkeyPatch, answer: File) -> None:
    """AEMET refuses a key with an HTTP 401/403 or an envelope `estado` of 401/403 (GH-2562)."""
    calls = _probe_answering(monkeypatch, answer)
    assert AemetObservationRequest.is_valid() is False
    assert len(calls) == 1


@pytest.mark.usefixtures("_aemet_key")
@pytest.mark.parametrize("datos", [{"datos": "https://opendata.aemet.es/datos"}, {}], ids=["datos-link", "no-link"])
def test_aemet_observation_is_valid_is_true_for_an_accepted_key(
    monkeypatch: pytest.MonkeyPatch, datos: dict[str, str]
) -> None:
    """An envelope `estado` of 200 is the key accepted; what its link leads to is not fetched (GH-2564)."""
    calls = _probe_answering(monkeypatch, _envelope(200, **datos))
    assert AemetObservationRequest.is_valid() is True
    assert [call["url"] for call in calls] == [
        "https://opendata.aemet.es/opendata/api/valores/climatologicos/inventarioestaciones/todasestaciones"
    ]


@pytest.mark.usefixtures("_aemet_key")
def test_aemet_observation_is_valid_is_one_short_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe asks once and gives up after `PROBE_TIMEOUT_SECONDS`, not as long as a values request (GH-2564).

    Asked through the retry loop it took 73 s on a cold cache with AEMET answering 408 and 503, and
    a page waited for it.
    """
    calls = _probe_answering(monkeypatch, _envelope(200))
    assert AemetObservationRequest.is_valid() is True
    assert len(calls) == 1
    assert calls[0]["attempts"] == 1
    assert calls[0]["client_kwargs"]["timeout"].total == PROBE_TIMEOUT_SECONDS
    assert Settings().fsspec_client_kwargs["timeout"] > PROBE_TIMEOUT_SECONDS
    # an acceptance is cached for a minute, not an hour: a revoked key must not read True for an hour (GH-2750)
    assert calls[0]["ttl"] is CacheExpiry.ONE_MINUTE


@pytest.mark.usefixtures("_aemet_key")
@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(File(url="u", content=OSError("certificate verify failed"), status=500), id="ssl"),
        pytest.param(File(url="u", content=NoInternetError("no route to host"), status=503), id="no-network"),
        pytest.param(File(url="u", content=TimeoutError("timed out"), status=408), id="timeout"),
        pytest.param(File(url="u", content=Exception("503"), status=503), id="http-503"),
        pytest.param(_envelope(429), id="estado-429"),
        pytest.param(_envelope(500), id="estado-500"),
        pytest.param(File(url="u", content=BytesIO(b"<html>maintenance</html>"), status=200), id="html-200"),
        pytest.param(File(url="u", content=BytesIO(b"[]"), status=200), id="json-no-object"),
    ],
)
def test_aemet_observation_is_valid_is_unknown_when_the_probe_could_not_tell(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, answer: File
) -> None:
    """Any failure but a refused key says nothing about the key, so it is None, not False, and logged (GH-2562)."""
    calls = _probe_answering(monkeypatch, answer)
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.aemet"):
        assert AemetObservationRequest.is_valid() is None
    assert len(calls) == 1
    assert any(record.getMessage().startswith("Could not check the AEMET API key") for record in caplog.records)


def test_aemet_observation_monthly_value_keeps_the_text_of_what_is_no_number() -> None:
    """Test that `24.2(20)` is 24.2 and a text with no number in front is null with its text as `raw` (GH-2759)."""
    value, raw = parse_monthly_value("v")
    df = pl.DataFrame({"v": ["24.2(20)", "39.4(27/jul)", "-3.0", "Ip", "", None]}).select(
        value.alias("value"), raw.alias("raw")
    )
    assert df.get_column("value").to_list() == [24.2, 39.4, -3.0, None, None, None]
    assert df.get_column("raw").to_list() == [None, None, None, "Ip", None, None]


def test_aemet_observation_daily_values_keep_the_text_of_what_is_no_number() -> None:
    """Test the decimal comma, the wind direction in tens of degrees with its 99, and a text that is no number."""
    value, raw = parse_decimal_comma("v")
    direction, direction_raw = parse_wind_direction("v")
    df = pl.DataFrame({"v": ["28,0", "Ip", "99", "23", None]}).select(
        value.alias("value"), raw.alias("raw"), direction.alias("direction"), direction_raw.alias("direction_raw")
    )
    assert df.get_column("value").to_list() == [28.0, None, 99.0, 23.0, None]
    assert df.get_column("raw").to_list() == [None, "Ip", None, None, None]
    assert df.get_column("direction").to_list() == [280.0, None, None, 230.0, None]
    assert df.get_column("direction_raw").to_list() == [None, "Ip", "99", None, None]


@pytest.mark.parametrize(
    "refusal",
    [
        pytest.param(File(url=_ENDPOINT, content=_response_error(401), status=401), id="http-401"),
        pytest.param(_envelope(401), id="estado-401"),
    ],
)
def test_aemet_fetch_datos_asks_again_after_a_401_and_takes_the_second_answer(
    monkeypatch: pytest.MonkeyPatch, refusal: File
) -> None:
    """AEMET answers a 401 to a key it accepts on the next request: one refusal is not a refused key (GH-3022)."""
    asked = _serve_in_turn(
        monkeypatch,
        refusal,
        _envelope(200, datos=_DATOS),
        File(url=_DATOS, content=BytesIO(b'[{"indicativo": "3195"}]'), status=200),
    )
    assert _fetch() == b'[{"indicativo": "3195"}]'
    assert asked == [_ENDPOINT, _ENDPOINT, _DATOS]


def test_aemet_fetch_datos_returns_the_refusal_of_a_second_401_and_does_not_ask_a_third_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A key refused twice is refused: the refusal that the readers raise as `CredentialRejectedError`."""
    refusal = File(url=_ENDPOINT, content=_response_error(401), status=401)
    asked = _serve_in_turn(monkeypatch, refusal, refusal, _envelope(200, datos=_DATOS))
    assert isinstance(_fetch(), AemetKeyRejectedError)
    assert asked == [_ENDPOINT, _ENDPOINT]


def test_aemet_fetch_datos_does_not_ask_again_for_anything_but_a_refused_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404, a 429 and an outage are met once, as before: only the 401 and 403 of the key are asked again."""
    for file in (File(url=_ENDPOINT, content=FileNotFoundError(_ENDPOINT), status=404), _envelope(404), _envelope(429)):
        asked = _serve_in_turn(monkeypatch, file)
        assert isinstance(_fetch(), Exception)
        assert asked == [_ENDPOINT], file
