# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for ECCC API."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.provider.eccc.observation import EcccObservationRequest


@pytest.mark.remote
def test_eccc_api_stations(settings_convert_units_false: Settings) -> None:
    """Test fetching of ECCC stations."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start_date="1990-01-01",
        end_date="1990-01-02",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=(14,))
    given_df = request.df
    expected_df = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "14",
                "start_date": dt.datetime(1984, 1, 1, hour=8, tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime(1996, 11, 30, hour=8, tzinfo=ZoneInfo("UTC")),
                "latitude": 48.52,
                "longitude": -123.17,
                "height": 4.0,
                "name": "ACTIVE PASS",
                "state": "BC",
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_eccc_api_values(settings_convert_units_false: Settings) -> None:
    """Test fetching of ECCC data."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start_date="1979-11-02",
        end_date="1979-11-03",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("2",))
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "count_days_cooling_degree",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "count_days_heating_degree",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 11.7,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "precipitation_height",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "precipitation_height_liquid",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "snow_depth_new",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 9.5,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 6.3,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 3.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)
