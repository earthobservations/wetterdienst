# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for AEMET OpenData observation provider."""

import datetime as dt
from io import BytesIO
from itertools import pairwise
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.aemet.observation.api import (
    AemetObservationRequest,
    AemetObservationValues,
    _download_with_rate_limit_retry,
)
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

MADRID_RETIRO = "3195"
UTC = ZoneInfo("UTC")

# Applied per-test (not as module-level pytestmark) so the local unit tests further down
# (chunking, retry behavior) still run without AEMET credentials.
requires_aemet_credentials = pytest.mark.skipif(
    not AemetObservationRequest.is_configured(),
    reason="AEMET credentials not set — provide WD_AUTH__AEMET=<api_key>",
)


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
                "start_date": None,
                "end_date": None,
                "latitude": 40.411389,
                "longitude": -3.677778,
                "height": 667.0,
                "name": "MADRID, RETIRO",
                "state": "MADRID",
            }
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
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
def test_aemet_observation_values_daily() -> None:
    """Daily climatological values at Madrid/Retiro match the AEMET reference values.

    2020-01-01 through 2020-01-05 is a fixed historical window unaffected by AEMET's
    real-time backfill/QC delay, so the expected values are stable.
    """
    df = (
        AemetObservationRequest(
            parameters=[("daily", "data")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 1, 5, tzinfo=UTC),
        )
        .filter_by_station_id(MADRID_RETIRO)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [MADRID_RETIRO]
    assert df["resolution"].unique().to_list() == ["daily"]

    def value_on(parameter: str, date: dt.datetime) -> float:
        row = df.filter(pl.col("parameter").eq(parameter), pl.col("date").eq(date))
        return row.get_column("value").item()

    day1 = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert value_on("temperature_air_mean_2m", day1) == pytest.approx(6.6)
    assert value_on("temperature_air_max_2m", day1) == pytest.approx(11.2)
    assert value_on("temperature_air_min_2m", day1) == pytest.approx(1.9)
    assert value_on("precipitation_height", day1) == pytest.approx(0.0)
    assert value_on("wind_speed", day1) == pytest.approx(0.3)
    assert value_on("wind_gust_max", day1) == pytest.approx(3.3)
    assert value_on("wind_direction", day1) == pytest.approx(50.0)
    assert value_on("pressure_air_site_max", day1) == pytest.approx(954.2)
    assert value_on("pressure_air_site_min", day1) == pytest.approx(952.0)
    # humidity is reported by AEMET as percent, wetterdienst stores it as fraction
    assert value_on("humidity", day1) == pytest.approx(0.65)
    assert value_on("humidity_max", day1) == pytest.approx(0.80)
    assert value_on("humidity_min", day1) == pytest.approx(0.48)

    # 2020-01-02 has dir=99 (calm/variable), which AEMET encodes with a sentinel value
    # rather than an actual direction. The parser must turn that into a null rather than
    # a bogus 990°; with the default ts_drop_nulls=True, a null value means no row at all.
    day2 = dt.datetime(2020, 1, 2, tzinfo=UTC)
    assert df.filter(pl.col("parameter").eq("wind_direction"), pl.col("date").eq(day2)).is_empty()


@pytest.mark.remote
@requires_aemet_credentials
def test_aemet_observation_values_monthly() -> None:
    """Monthly climatological values at Madrid/Retiro for January 2020 match the AEMET reference values."""
    df = (
        AemetObservationRequest(
            parameters=[("monthly", "data")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 1, 31, tzinfo=UTC),
        )
        .filter_by_station_id(MADRID_RETIRO)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [MADRID_RETIRO]
    assert df["resolution"].unique().to_list() == ["monthly"]
    assert df["date"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(7.0)
    assert value_of("temperature_air_max_2m_mean") == pytest.approx(10.4)
    assert value_of("temperature_air_min_2m_mean") == pytest.approx(3.6)
    # the multiday variants come from a value with a day-of-occurrence annotation, e.g.
    # "15.7(31)" — the parser must strip that and keep just the number.
    assert value_of("temperature_air_max_2m_multiday") == pytest.approx(15.7)
    assert value_of("temperature_air_min_2m_multiday") == pytest.approx(-0.7)
    assert value_of("precipitation_height") == pytest.approx(16.4)
    assert value_of("precipitation_height_max") == pytest.approx(5.4)
    # humidity is reported by AEMET as percent, wetterdienst stores it as fraction
    assert value_of("humidity") == pytest.approx(0.66)


@pytest.mark.remote
@requires_aemet_credentials
def test_aemet_observation_values_annual() -> None:
    """Annual climatological values at Madrid/Retiro for 2020 match the AEMET reference values.

    Also verifies that monthly and annual values are correctly split out of the same
    underlying AEMET response (distinguished by the "fecha" suffix), and that fields
    AEMET omits from the annual aggregate (like humidity) are simply absent rather than
    wrongly carried over from a monthly row.
    """
    df = (
        AemetObservationRequest(
            parameters=[("annual", "data")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 12, 31, tzinfo=UTC),
        )
        .filter_by_station_id(MADRID_RETIRO)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [MADRID_RETIRO]
    assert df["resolution"].unique().to_list() == ["annual"]
    assert df["date"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(16.0)
    assert value_of("temperature_air_max_2m_mean") == pytest.approx(20.9)
    assert value_of("temperature_air_min_2m_mean") == pytest.approx(11.1)
    # annotation is "(27/jul)" here (day/month, not just day, unlike the monthly endpoint)
    assert value_of("temperature_air_max_2m_multiday") == pytest.approx(39.4)
    assert value_of("temperature_air_min_2m_multiday") == pytest.approx(-1.3)
    assert value_of("precipitation_height") == pytest.approx(474.4)
    assert value_of("precipitation_height_max") == pytest.approx(37.8)
    # AEMET's annual aggregate doesn't include a humidity field at all
    assert df.filter(pl.col("parameter").eq("humidity")).is_empty()


@pytest.mark.remote
@requires_aemet_credentials
def test_aemet_observation_values_hourly_realtime() -> None:
    """Real-time (observación convencional) hourly values at Madrid/Retiro are structurally sane.

    This is live current-weather data with no fixed historical window (AEMET's endpoint
    doesn't accept a date range at all — it just returns whatever rolling window of recent
    hours it currently holds), so exact values can't be asserted like the other
    resolutions. This checks shape, recency, and physically plausible value ranges instead.
    """
    df = AemetObservationRequest(parameters=[("hourly", "data")]).filter_by_station_id(MADRID_RETIRO).values.all().df
    assert not df.is_empty()
    assert df["station_id"].unique().to_list() == [MADRID_RETIRO]
    assert df["resolution"].unique().to_list() == ["hourly"]

    # no date range was passed (date_required=False for this resolution) and AEMET only
    # ever returns a recent rolling window, so the latest timestamp should be recent.
    now = dt.datetime.now(tz=UTC)
    latest_date = df["date"].max()
    assert isinstance(latest_date, dt.datetime)
    assert latest_date >= now - dt.timedelta(hours=36)
    assert latest_date <= now + dt.timedelta(minutes=5)

    def latest(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).sort("date").get_column("value")[-1]

    assert -40 < latest("temperature_air_mean_2m") < 50
    assert 0.0 <= latest("humidity") <= 1.0
    # unlike the daily endpoint's coded 0-36 direction, real-time direction is already in
    # plain degrees — this would fail if the daily parser's *10 scaling was wrongly reused.
    assert 0 <= latest("wind_direction") <= 360
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
