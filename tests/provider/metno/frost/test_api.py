# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for MET Norway Frost API provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.metno.frost.api import MetnoFrostRequest

OSLO_BLINDERN = "SN18700"
UTC = ZoneInfo("UTC")

pytestmark = pytest.mark.skipif(
    not MetnoFrostRequest.is_configured(),
    reason="MET Norway Frost credentials not set — provide WD_AUTH__METNO_FROST=<client_id>",
)


@pytest.mark.remote
def test_metno_frost_stations() -> None:
    """Station metadata for Oslo/Blindern matches the Frost registry."""
    request = MetnoFrostRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
        end_date=dt.datetime(2020, 1, 2, tzinfo=UTC),
    ).filter_by_station_id(OSLO_BLINDERN)
    expected = pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "data",
                "station_id": OSLO_BLINDERN,
                "start_date": dt.datetime(1931, 1, 1, tzinfo=UTC),
                "end_date": None,
                "latitude": 59.9423,
                "longitude": 10.72,
                "height": 94.0,
                "name": "OSLO - BLINDERN",
                "state": "OSLO",
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
    assert_frame_equal(request.df, expected)


@pytest.mark.remote
def test_metno_frost_values_hourly() -> None:
    """Hourly air temperature at Oslo/Blindern returns 24 rows for a one-day window."""
    df = (
        MetnoFrostRequest(
            parameters=[("hourly", "data", "temperature_air_mean_2m")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 1, 2, tzinfo=UTC),
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values.all()
        .df
    )
    assert len(df) == 24
    assert df["station_id"].unique().to_list() == [OSLO_BLINDERN]
    assert df["resolution"].unique().to_list() == ["hourly"]
    assert df["parameter"].unique().to_list() == ["temperature_air_mean_2m"]
    first = df.row(0, named=True)
    assert first["date"] == dt.datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert first["value"] == pytest.approx(3.4)


@pytest.mark.remote
def test_metno_frost_values_daily() -> None:
    """Daily air temperature at Oslo/Blindern returns one row per day."""
    df = (
        MetnoFrostRequest(
            parameters=[("daily", "data", "temperature_air_mean_2m")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 1, 31, tzinfo=UTC),
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values.all()
        .df
    )
    assert len(df) == 30
    assert df["resolution"].unique().to_list() == ["daily"]
    first = df.row(0, named=True)
    assert first["date"] == dt.datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert first["value"] == pytest.approx(1.9)


@pytest.mark.remote
def test_metno_frost_values_monthly() -> None:
    """Monthly air temperature at Oslo/Blindern returns one row per month."""
    df = (
        MetnoFrostRequest(
            parameters=[("monthly", "data", "temperature_air_mean_2m")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 12, 31, tzinfo=UTC),
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values.all()
        .df
    )
    assert len(df) == 12
    assert df["resolution"].unique().to_list() == ["monthly"]
    first = df.row(0, named=True)
    assert first["date"] == dt.datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert first["value"] == pytest.approx(2.7)


@pytest.mark.remote
def test_metno_frost_values_hourly_multi_parameter_batched(caplog: pytest.LogCaptureFixture) -> None:
    """Requesting multiple hourly parameters issues a single batched request.

    Datasets are declared `grouped: True` so all parameters of a resolution are
    fetched via one comma-separated `elements=` query instead of one request per
    parameter. The response covers every element of the dataset; the requested
    subset is filtered out of it afterward.
    """
    with caplog.at_level("INFO", logger="wetterdienst.provider.metno.frost.api"):
        df = (
            MetnoFrostRequest(
                parameters=[
                    ("hourly", "data", "temperature_air_mean_2m"),
                    ("hourly", "data", "humidity"),
                    ("hourly", "data", "wind_speed"),
                ],
                start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
                end_date=dt.datetime(2020, 1, 2, tzinfo=UTC),
            )
            .filter_by_station_id(OSLO_BLINDERN)
            .values.all()
            .df
        )
    acquisitions = [r.message for r in caplog.records if r.message.startswith("Acquiring data from")]
    assert len(acquisitions) == 1
    # the single request's elements= list covers all three requested elements at once
    assert "air_temperature" in acquisitions[0]
    assert "relative_humidity" in acquisitions[0]
    assert "wind_speed" in acquisitions[0]
    assert sorted(df["parameter"].unique().to_list()) == ["humidity", "temperature_air_mean_2m", "wind_speed"]
    assert len(df.filter(pl.col("parameter") == "temperature_air_mean_2m")) == 24


@pytest.mark.remote
def test_metno_frost_values_6hour_fallback() -> None:
    """6-hourly synoptic precipitation uses time-series discovery fallback.

    The Frost API requires timeseriesids/performancecategories/exposurecategories for
    historical synoptic elements; without them the direct query returns 404. This test
    verifies the fallback path resolves that and returns the correct data.
    """
    df = (
        MetnoFrostRequest(
            parameters=[("6_hour", "data", "precipitation_height")],
            start_date=dt.datetime(2005, 9, 1, tzinfo=UTC),
            end_date=dt.datetime(2006, 1, 1, tzinfo=UTC),
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values.all()
        .df
    )
    # SN18700 has exactly 2 synoptic precipitation observations in this window
    assert len(df) == 2
    assert df["resolution"].unique().to_list() == ["6_hour"]
    assert df["parameter"].unique().to_list() == ["precipitation_height"]
    dates = df["date"].to_list()
    assert dt.datetime(2005, 9, 7, 0, 0, 0, tzinfo=UTC) in dates
    assert dt.datetime(2005, 10, 13, 12, 0, 0, tzinfo=UTC) in dates
