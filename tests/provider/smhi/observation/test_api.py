# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for SMHI observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.smhi.observation import SmhiObservationRequest

ABISKO = "188790"
UTC = ZoneInfo("UTC")

# SMHI's live service has not been observed to be chronically flaky the way AEMET/Frost
# have been, but it's a live third-party API like any other -- xfail rather than a hard
# failure keeps a transient blip from blocking CI/merges, matching the AEMET/ECCC precedent.
xfail_if_smhi_unavailable = pytest.mark.xfail(strict=False, reason="SMHI server intermittently unavailable")


@pytest.mark.remote
@xfail_if_smhi_unavailable
def test_smhi_observation_stations() -> None:
    """Station metadata for Abisko Aut matches the SMHI station registry."""
    request = SmhiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id(ABISKO)
    df = request.df
    assert df.select(pl.exclude("latitude", "longitude", "start_date", "end_date")).to_dicts() == [
        {
            "resolution": "hourly",
            "dataset": "data",
            "station_id": ABISKO,
            "height": 392.235,
            "name": "Abisko Aut",
            "state": None,
        },
    ]
    assert df["latitude"].item() == pytest.approx(68.3538)
    assert df["longitude"].item() == pytest.approx(18.8164)


@pytest.mark.remote
@xfail_if_smhi_unavailable
def test_smhi_observation_values_daily() -> None:
    """Daily values at Abisko Aut for 2020-01-01 match the SMHI reference values."""
    df = (
        SmhiObservationRequest(
            parameters=[("daily", "data")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
        )
        .filter_by_station_id(ABISKO)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [ABISKO]
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["date"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(-5.0)
    assert value_of("temperature_air_max_2m") == pytest.approx(-1.7)
    assert value_of("temperature_air_min_2m") == pytest.approx(-6.1)
    assert value_of("precipitation_height") == pytest.approx(10.5)


@pytest.mark.remote
@xfail_if_smhi_unavailable
def test_smhi_observation_values_hourly() -> None:
    """Hourly values at Abisko Aut for 2020-01-01 00:00 match the SMHI reference values."""
    df = (
        SmhiObservationRequest(
            parameters=[("hourly", "data")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
        )
        .filter_by_station_id(ABISKO)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [ABISKO]
    assert df["resolution"].unique().to_list() == ["hourly"]

    def value_at(parameter: str, hour: int) -> float:
        date = dt.datetime(2020, 1, 1, hour, tzinfo=UTC)
        return df.filter(pl.col("parameter").eq(parameter), pl.col("date").eq(date)).get_column("value").item()

    assert value_at("temperature_air_mean_2m", 0) == pytest.approx(-3.3)
    assert value_at("temperature_dew_point_mean_2m", 0) == pytest.approx(-5.3)
    assert value_at("wind_speed", 0) == pytest.approx(2.8)
    assert value_at("wind_direction", 0) == pytest.approx(273.0)
    assert value_at("wind_gust_max", 0) == pytest.approx(6.9)
    assert value_at("precipitation_height", 0) == pytest.approx(0.0)
    # humidity is reported by SMHI as percent, wetterdienst stores it as fraction
    assert value_at("humidity", 0) == pytest.approx(0.86)
    assert value_at("pressure_air_sea_level", 0) == pytest.approx(997.1)
    assert value_at("visibility_range", 0) == pytest.approx(13244.0)


@pytest.mark.remote
@xfail_if_smhi_unavailable
def test_smhi_observation_values_monthly() -> None:
    """Monthly values at Abisko Aut for January 2020 match the SMHI reference values."""
    df = (
        SmhiObservationRequest(
            parameters=[("monthly", "data")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 1, 31, tzinfo=UTC),
        )
        .filter_by_station_id(ABISKO)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [ABISKO]
    assert df["resolution"].unique().to_list() == ["monthly"]
    assert df["date"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(-5.6)
    assert value_of("precipitation_height") == pytest.approx(40.9)


@pytest.mark.remote
@xfail_if_smhi_unavailable
def test_smhi_observation_values_minute_1() -> None:
    """1-minute values at Abisko Aut are live/rolling data with no fixed historical window.

    SMHI only exposes a short rolling window for minute-resolution data (via the
    "latest-day" period, no historical archive at all) -- structural/range checks only,
    like AEMET's real-time hourly endpoint.
    """
    df = SmhiObservationRequest(parameters=[("minute_1", "data")]).filter_by_station_id(ABISKO).values.all().df
    assert not df.is_empty()
    assert df["station_id"].unique().to_list() == [ABISKO]
    assert df["resolution"].unique().to_list() == ["1_minute"]

    latest_date = df["date"].max()
    assert isinstance(latest_date, dt.datetime)
    now = dt.datetime.now(tz=UTC)
    assert now - dt.timedelta(hours=2) <= latest_date <= now

    def latest(parameter: str) -> float:
        sub = df.filter(pl.col("parameter").eq(parameter)).sort("date")
        return sub.get_column("value").tail(1).item()

    assert -60.0 <= latest("temperature_air_mean_2m") <= 60.0
    assert 0.0 <= latest("humidity") <= 1.0
    assert 0 <= latest("wind_direction") <= 360
    assert 0.0 <= latest("wind_speed") <= 100.0
    assert 800 < latest("pressure_air_sea_level") < 1100
