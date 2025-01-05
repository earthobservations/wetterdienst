from datetime import datetime

import pytest
from dirty_equals import IsNumeric

from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest


@pytest.mark.remote
def test_geopshere_observation_api():
    """Test the correct parsing of data, especially the dates -> thanks @mhuber89 for the discovery and fix"""
    stations_at = GeosphereObservationRequest(
        parameters=[("hourly", "data", "wind_speed")],
        start_date=datetime(2022, 6, 1),
        end_date=datetime(2022, 6, 2),
    )
    station_at = stations_at.filter_by_station_id("4821")
    df = station_at.values.all().df
    assert df.get_column("value").is_not_null().sum() == 25


@pytest.mark.remote
@pytest.mark.parametrize(
    "resolution",
    [
        "minute_10",
        "hourly",
        "daily",
    ],
)
def test_geopshere_observation_api_radiation(resolution):
    """Test correct radiation conversion (W / m² -> J / cm²), factor should be 0.06"""
    stations_at = GeosphereObservationRequest(
        parameters=[(resolution, "data", "radiation_global")],
        start_date=datetime(2022, 6, 1),
        end_date=datetime(2022, 6, 2, hour=23, minute=50),
    )
    station_at = stations_at.filter_by_station_id("4821")
    df = station_at.values.all().df
    # the result is slightly different for each resolution
    assert df.get_column("value").sum() == IsNumeric(ge=4966.2000, le=4972.0000)
