# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for MeteoSwiss observation API."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationRequest


@pytest.mark.remote
def test_meteoswiss_observation_api_stations() -> None:
    """Test that station metadata can be retrieved and is complete."""
    request = MeteoswissObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id("ABO")
    df = request.df
    assert not df.is_empty()
    assert df.get_column("name").to_list() == ["Adelboden"]
    assert df.get_column("state").to_list() == ["BE"]


@pytest.mark.remote
def test_meteoswiss_observation_api_daily() -> None:
    """Test daily values, spanning both the historical and recent data files."""
    request = MeteoswissObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2020, 1, 3, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("ABO")
    df = next(request.values.query()).df
    assert df.get_column("value").is_not_null().sum() == 3


@pytest.mark.remote
@pytest.mark.parametrize(
    "resolution",
    [
        "10_minutes",
        "hourly",
        "daily",
        "monthly",
        "annual",
    ],
)
def test_meteoswiss_observation_api_resolutions(resolution: str) -> None:
    """Test that all resolutions can be requested and yield tidy data.

    Monthly and annual values are dated to the first of the month/year, so a full-year
    window is used to reliably capture a value regardless of resolution.
    """
    request = MeteoswissObservationRequest(
        parameters=[(resolution, "data", "temperature_air_mean_2m")],
        start_date=datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2022, 12, 31, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("ABO")
    df = next(request.values.query()).df
    assert df.get_column("value").is_not_null().sum() > 0
