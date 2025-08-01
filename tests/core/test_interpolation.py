# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for interpolation."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.exceptions import StationNotFoundError
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

pytest.importorskip("shapely")

pytestmark = pytest.mark.slow


@pytest.fixture
def df_interpolated_empty() -> pl.DataFrame:
    """Provide empty DataFrame for interpolated values."""
    return pl.DataFrame(
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "distance_mean": pl.Float64,
            "taken_station_ids": pl.List(pl.String),
        },
    )


@pytest.mark.remote
def test_interpolation_temperature_air_mean_2m_hourly_by_coords(default_settings: Settings) -> None:
    """Test that the interpolation works with hourly data."""
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] == 18001
    assert result.df.drop_nulls().shape[0] == 17914
    given_df = result.filter_by_date("2022-01-02 00:00:00+00:00")
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "f674568e",
                "resolution": "hourly",
                "dataset": "temperature_air",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
                "value": 4.56,
                "distance_mean": 13.37,
                "taken_station_ids": ["02480", "04411", "07341", "00917"],
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_temperature_air_mean_2m_daily_by_station_id(default_settings: Settings) -> None:
    """Test that the interpolation works with daily data."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(1986, 10, 31, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(1986, 11, 1, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "6754d04d",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(1986, 10, 31, tzinfo=ZoneInfo("UTC")),
                "value": 6.37,
                "distance_mean": 16.99,
                "taken_station_ids": ["00072", "02074", "02638", "04703"],
            },
            {
                "station_id": "6754d04d",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(1986, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.7,
                "distance_mean": 0.0,
                "taken_station_ids": ["00071"],
            },
        ],
        orient="row",
    )
    for result in (
        request.interpolate(latlon=(48.2156, 8.9784)),
        request.interpolate_by_station_id(station_id="00071"),
    ):
        given_df = result.df
        assert given_df.shape[0] == 2
        assert given_df.drop_nulls().shape[0] == 2
        assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_precipitation_height_minute_10(default_settings: Settings) -> None:
    """Test that the interpolation works with precipitation."""
    request = DwdObservationRequest(
        parameters=[("minute_10", "precipitation", "precipitation_height")],
        start_date=dt.datetime(2021, 10, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 10, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] == 577
    assert result.df.drop_nulls().shape[0] == 577
    given_df = result.filter_by_date("2021-10-05 00:00:00+00:00")
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "f674568e",
                "resolution": "10_minutes",
                "dataset": "precipitation",
                "parameter": "precipitation_height",
                "date": dt.datetime(2021, 10, 5, tzinfo=ZoneInfo("UTC")),
                "value": 0.03,
                "distance_mean": 9.38,
                "taken_station_ids": ["04230", "02480", "04411", "07341"],
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


def test_not_interpolatable_parameter(default_settings: Settings, df_interpolated_empty: pl.DataFrame) -> None:
    """Test that a parameter that cannot be interpolated is handled correctly."""
    request = DwdObservationRequest(
        parameters=[("hourly", "wind", "wind_direction")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    assert_frame_equal(
        given_df,
        df_interpolated_empty,
    )


def test_not_interpolatable_dataset(default_settings: Settings, df_interpolated_empty: pl.DataFrame) -> None:
    """Test that a dataset that cannot be interpolated is handled correctly."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "precipitation_form")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    assert_frame_equal(
        given_df,
        df_interpolated_empty,
    )


@pytest.mark.remote
def test_provider_dwd_mosmix(default_settings: Settings) -> None:
    """Test a MOSMIX request with date filter."""
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "temperature_air_mean_2m")],
        start_date=dt.datetime.now(tz=ZoneInfo("UTC")) + dt.timedelta(days=1),
        end_date=dt.datetime.now(tz=ZoneInfo("UTC")) + dt.timedelta(days=8),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.get_column("value").min() >= -40  # equals -40.0°C


def test_interpolation_temperature_air_mean_2m_daily_three_floats(default_settings: Settings) -> None:
    """Test that the interpolation works with three floats."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="too many values to unpack"):
        stations.interpolate(latlon=(0, 1, 2))


def test_interpolation_temperature_air_mean_2m_daily_one_floats(default_settings: Settings) -> None:
    """Test that an error is raised when not enough values are provided."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="not enough values to unpack"):
        stations.interpolate(latlon=(0,))


def test_interpolation_temperature_air_mean_2m_daily_no_station_found(default_settings: Settings) -> None:
    """Test that an error is raised when no station is found."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(StationNotFoundError, match="no station found for 00000"):
        stations.interpolate_by_station_id(station_id="00")


def test_interpolation_increased_station_distance() -> None:
    """Test that the interpolation works with increased station distance."""
    settings = Settings(ts_interp_station_distance={"precipitation_height": 25})
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    )
    values = request.interpolate(latlon=(52.8, 12.9))
    assert values.df.get_column("value").sum() == 21.07


def test_interpolation_error_no_start_date() -> None:
    """Test that an error is raised when start_date is missing."""
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
    )
    with pytest.raises(ValueError, match="start_date and end_date are required for interpolation"):
        request.interpolate(latlon=(52.8, 12.9))
