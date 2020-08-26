import os

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
import pandas as pd

from wetterdienst.additionals.geo_location import (
    get_nearby_stations,
    _derive_nearest_neighbours,
)
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.data_models.coordinates import Coordinates


fixtures_dir = f"{os.path.dirname(__file__)}/../fixtures/"


@patch(
    "wetterdienst.parse_metadata.metadata_for_climate_observations",
    MagicMock(return_value=pd.read_json(f"{fixtures_dir}FIXED_METADATA.JSON")),
)
def test_get_nearby_stations():
    # Test for one nearest station
    nearest_station, distances = get_nearby_stations(
        [50.0, 51.4],
        [8.9, 9.3],
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        num_stations_nearby=1,
    )

    assert nearest_station == [4411]

    np.testing.assert_array_almost_equal(
        np.array(distances), np.array([[11.653026716750542, 14.520733407578632]])
    )

    # Test for maximum distance (take same station
    nearest_station, distances = get_nearby_stations(
        [50.0, 51.4],
        [8.9, 9.3],
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        max_distance_in_km=20,
    )

    assert nearest_station == [4411, 2480]

    np.testing.assert_array_almost_equal(
        np.array(distances),
        np.array(
            [
                [11.653026716750542, 14.520733407578632],
                [12.572153957087247, 19.587815617354487],
            ]
        ),
    )

    with pytest.raises(ValueError):
        get_nearby_stations(
            [50.0, 51.4],
            [8.9, 9.3],
            Parameter.TEMPERATURE_AIR,
            TimeResolution.HOURLY,
            PeriodType.RECENT,
            num_stations_nearby=1,
            max_distance_in_km=1,
        )

    with pytest.raises(ValueError):
        get_nearby_stations(
            [50.0, 51.4],
            [8.9, 9.3],
            Parameter.TEMPERATURE_AIR,
            TimeResolution.HOURLY,
            PeriodType.RECENT,
            num_stations_nearby=0,
        )


def test_derive_nearest_neighbours():
    coords = Coordinates(np.array([50.0, 51.4]), np.array([8.9, 9.3]))

    metadata = pd.read_json(f"{fixtures_dir}FIXED_METADATA.JSON")

    distances, indices_nearest_neighbours = _derive_nearest_neighbours(
        metadata.LAT.values, metadata.LON.values, coords
    )

    np.testing.assert_array_almost_equal(distances, np.array([0.00182907, 0.00227919]))

    np.testing.assert_array_almost_equal(
        indices_nearest_neighbours, np.array([432, 655])
    )
