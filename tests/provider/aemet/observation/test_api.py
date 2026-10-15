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
from aiohttp import ClientResponseError
from fsspec.exceptions import FSTimeoutError

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.aemet.observation import api as aemet_api
from wetterdienst.provider.aemet.observation.api import (
    AemetKeyRejectedError,
    AemetObservationRequest,
    AemetObservationValues,
    _download_with_rate_limit_retry,
)
from wetterdienst.provider.aemet.observation.parser import (
    parse_decimal_comma,
    parse_monthly_value,
    parse_wind_direction,
)
from wetterdienst.settings import Settings
from wetterdienst.util.network import PROBE_TIMEOUT_SECONDS, File, _worth_retrying

MADRID_RETIRO = "3195"
BARCELONA = "0076"
UTC = ZoneInfo("UTC")

# Applied per-test (not as module-level pytestmark) so the local unit tests further down
# (chunking, retry behavior) still run without AEMET credentials.
requires_aemet_credentials = pytest.mark.skipif(
    not AemetObservationRequest.is_configured(),
    reason="AEMET credentials not set — provide WD_AUTH__AEMET=<api_key>",
)


def _is_refusal_or_outage(failure: Exception) -> bool:
    """Tell whether AEMET did not answer the request: a refused key, an HTTP 429, a timeout or an HTTP 5xx.

    A rate limit or a fault that AEMET reports in the envelope of an HTTP 200 (`estado` 429 or 5xx) reaches
    here as a plain `Exception` that is not told from a 404 of the envelope, so it still fails the test.

    A 400, a 404 or an envelope that says there is no data is AEMET answering, and what it most likely says is
    that the request was built wrong, which is what these tests are there to catch (see `tests/conftest.py`).
    """
    if isinstance(failure, AemetKeyRejectedError):
        return True
    if isinstance(failure, ClientResponseError) and failure.status == HTTPStatus.TOO_MANY_REQUESTS:
        return True
    return _worth_retrying(failure)


def _values_or_skip(
    make_request: Callable[[], AemetObservationRequest],
    monkeypatch: pytest.MonkeyPatch,
) -> pl.DataFrame:
    """Build a request and read its values, and skip the test if AEMET refused or did not answer (GH-2965).

    The reader logs the failure of a station list or a chunk and goes on with an empty frame, so a 401, a 429
    or a 5xx never reaches the test as the exception that `skip_if_upstream_unavailable` skips on. CI runs
    every job of both workflows on one key, and AEMET answers that with a 401 or a 429 for part of the calls;
    the test asserts what AEMET publishes, which a refusal says nothing about. The request is built here,
    because filtering by station id already reads the station list.

    Only an empty frame after failures that all are a refusal or an outage skips (a revoked key skips the
    same way, and the reason names it). Any other failure, such as a 404, and an empty frame without one fail.
    """
    failures: list[Exception] = []
    fetch = aemet_api._fetch_datos  # noqa: SLF001

    def recording_fetch(*args: Any, **kwargs: Any) -> bytes | Exception:  # noqa: ANN401
        payload = fetch(*args, **kwargs)
        if isinstance(payload, Exception):
            failures.append(payload)
        return payload

    monkeypatch.setattr(aemet_api, "_fetch_datos", recording_fetch)
    df = make_request().values.all().df
    if df.is_empty() and failures and all(_is_refusal_or_outage(failure) for failure in failures):
        pytest.skip(f"AEMET did not hand out the data: {failures[0]!r}")
    return df


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
    assert value_on("wind_speed", day1) == pytest.approx(0.3)
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
    assert 0 <= latest("wind_direction_last_10min") <= 360
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
        ).filter_by_station_id(MADRID_RETIRO).values.all()

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
        .values.all()
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
        pytest.param(_response_error(429), id="rate-limit"),
        pytest.param(_response_error(503), id="5xx"),
        pytest.param(FSTimeoutError(), id="timeout"),
    ],
)
def test_values_or_skip_skips_when_aemet_refused_the_data(monkeypatch: pytest.MonkeyPatch, refusal: Exception) -> None:
    """A chunk AEMET refused or did not answer (a 401 or a 429 of a key shared by CI) skips, naming the answer."""
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
