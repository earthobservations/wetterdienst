# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Météo-France SYNOP API."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest


@pytest.mark.remote
def test_meteofrance_synop_api_stations() -> None:
    """Test that station metadata can be retrieved and is complete."""
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id("07005")
    df = request.df
    assert not df.is_empty()
    assert df.get_column("name").to_list() == ["ABBEVILLE"]


@pytest.mark.remote
def test_meteofrance_synop_api_values() -> None:
    """Test subdaily (3-hourly synop) values, including unit conversion from source Kelvin."""
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_mean_2m")],
        start_date=datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2024, 1, 2, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("07005")
    df = next(request.values.query()).df
    values = df.get_column("value")
    assert values.is_not_null().sum() > 0
    # temperature is converted from Kelvin to Celsius, so should be within a plausible range
    assert values.drop_nulls().is_between(-50, 50).all()


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [
        "wind_speed",
        "wind_direction",
        "humidity",
        "pressure_air_sea_level",
        "precipitation_height_last_3h",
        "cloud_cover_total",
    ],
)
def test_meteofrance_synop_api_parameters(parameter: str) -> None:
    """Test that core parameters can be requested and yield data for a well-covered station."""
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", parameter)],
        start_date=datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2024, 1, 3, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("07690")
    df = next(request.values.query()).df
    assert df.get_column("value").is_not_null().sum() > 0
