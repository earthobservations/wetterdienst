# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for geosphere observation API."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from dirty_equals import IsNumeric

from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest


@pytest.mark.remote
def test_geopshere_observation_api() -> None:
    """Test the correct parsing of data, especially the dates.

    Thanks, @mhuber89, for the discovery and fix!
    """
    stations_at = GeosphereObservationRequest(
        parameters=[("hourly", "data", "wind_speed")],
        start_date=datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2022, 6, 2, tzinfo=ZoneInfo("UTC")),
    )
    station_at = stations_at.filter_by_station_id("4821")
    df = station_at.values.all().df
    assert df.get_column("value").is_not_null().sum() == 25


@pytest.mark.remote
@pytest.mark.parametrize(
    ("resolution", "parameter", "expected"),
    [
        # cglo, served as irradiance in W / m² and passed through unconverted
        ("minute_10", "radiation_global_intensity", IsNumeric(ge=82770.0, le=82870.0)),
        ("hourly", "radiation_global_intensity", IsNumeric(ge=13790.0, le=13815.0)),
        # cglo_j, a distinct upstream parameter already accumulated over the day in J / cm²
        ("daily", "radiation_global", IsNumeric(ge=4966.2000, le=4972.0000)),
    ],
)
def test_geopshere_observation_api_radiation(resolution: str, parameter: str, expected: IsNumeric) -> None:
    """Test that radiation is reported in the unit the source publishes it in.

    Geosphere serves ``cglo`` as irradiance (W / m²) at 10 minutes and hourly, and ``cglo_j`` as
    irradiation accumulated over the interval (J / cm²) at daily and monthly. The sub-daily values used
    to be multiplied by the interval length in the parser to make them look like the daily ones; they
    now keep their own unit and canonical name instead. The expected sums are equivalent to the former
    J / cm² ones scaled by that interval: 82851 * 0.06 and 13795 * 0.36 both land in the daily range.
    """
    stations_at = GeosphereObservationRequest(
        parameters=[(resolution, "data", parameter)],
        start_date=datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2022, 6, 2, hour=23, minute=50, tzinfo=ZoneInfo("UTC")),
    )
    station_at = stations_at.filter_by_station_id("4821")
    df = station_at.values.all().df
    # the result is slightly different for each resolution
    assert df.get_column("value").sum() == expected
