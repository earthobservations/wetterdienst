# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation summary."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)


def test_summary_temperature_air_mean_2m_daily(default_settings: Settings) -> None:
    """Test summarization of temperature_air_mean_2m."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(1965, 12, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    selected_dates = [
        dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1940, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1950, 1, 1, tzinfo=ZoneInfo("UTC")),
    ]
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "7ac6c582",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": selected_dates[0],
                "value": 0.5,
                "distance": 13.42,
                "taken_station_id": "01048",
            },
            {
                "station_id": "7ac6c582",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": selected_dates[1],
                "value": -5.5,
                "distance": 5.05,
                "taken_station_id": "01051",
            },
            {
                "station_id": "7ac6c582",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": selected_dates[2],
                "value": -2.7,
                "distance": 0.0,
                "taken_station_id": "01050",
            },
        ],
        orient="row",
    )
    for result in (request.summarize(latlon=(51.0221, 13.8470)), request.summarize_by_station_id(station_id="1050")):
        given_df = result.df
        given_df = given_df.filter(pl.col("date").is_in(selected_dates))
        assert_frame_equal(given_df, expected_df)


def test_not_summarizable_parameter(default_settings: Settings) -> None:
    """Test that a parameter that cannot be summarized is handled correctly."""
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "precipitation_form")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.summarize(latlon=(50.0, 8.9))
    given_df = result.df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    expected_df = pl.DataFrame(
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "distance": pl.Float64,
            "taken_station_id": pl.String,
        },
    )
    assert_frame_equal(
        given_df,
        expected_df,
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
    given_df = request.summarize(latlon=(50.0, 8.9)).df
    assert given_df.get_column("value").min() >= -40  # equals -40.0°C


def test_summary_error_no_start_date() -> None:
    """Test that an error is raised when start_date is missing."""
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
    )
    with pytest.raises(ValueError, match="start_date and end_date are required for summarization"):
        request.summarize(latlon=(52.8, 12.9))
