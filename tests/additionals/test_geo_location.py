import os

import pytest
import numpy as np
from datetime import datetime
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
from wetterdienst.exceptions import InvalidParameterCombination


fixtures_dir = f"{os.path.dirname(__file__)}/../fixtures/"


@patch(
    "wetterdienst.parse_metadata.metadata_for_climate_observations",
    MagicMock(return_value=pd.read_json(f"{fixtures_dir}FIXED_METADATA.JSON")),
)
def test_get_nearby_stations():
    # Test for one nearest station
    nearest_station = get_nearby_stations(
        50.0,
        8.9,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        num_stations_nearby=1,
    )
    nearest_station = nearest_station.drop("TO_DATE", axis="columns")

    pd.testing.assert_frame_equal(
        nearest_station,
        pd.DataFrame(
            [
                [
                    4411,
                    np.datetime64("2002-01-24", dtype="np.datetime64[ns]"),
                    155.0,
                    49.9195,
                    8.9671,
                    "Schaafheim-Schlierbach",
                    "Hessen",
                    True,
                    11.65302672,
                ]
            ],
            columns=[
                "STATION_ID",
                "FROM_DATE",
                "STATION_HEIGHT",
                "LAT",
                "LON",
                "STATION_NAME",
                "STATE",
                "HAS_FILE",
                "DISTANCE_TO_LOCATION",
            ],
            index=[321],
        ),
    )

    nearest_station = get_nearby_stations(
        50.0,
        8.9,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        max_distance_in_km=20,
    )
    nearest_station = nearest_station.drop("TO_DATE", axis="columns")
    pd.testing.assert_frame_equal(
        nearest_station,
        pd.DataFrame(
            [
                [
                    4411,
                    np.datetime64("2002-01-24 00:00:00", dtype="datetime64[ns]"),
                    155.0,
                    49.9195,
                    8.9671,
                    "Schaafheim-Schlierbach",
                    "Hessen",
                    True,
                    11.653026716750542,
                ],
                [
                    2480,
                    np.datetime64("2004-09-01 00:00:00", dtype="datetime64[ns]"),
                    108.0,
                    50.0643,
                    8.993,
                    "Kahl/Main",
                    "Bayern",
                    True,
                    12.572153957087247,
                ],
                [
                    7341,
                    np.datetime64("2005-07-16 00:00:00", dtype="datetime64[ns]"),
                    119.0,
                    50.09,
                    8.7862,
                    "Offenbach-Wetterpark",
                    "Hessen",
                    True,
                    16.13301589362613,
                ],
            ],
            columns=[
                "STATION_ID",
                "FROM_DATE",
                "STATION_HEIGHT",
                "LAT",
                "LON",
                "STATION_NAME",
                "STATE",
                "HAS_FILE",
                "DISTANCE_TO_LOCATION",
            ],
            index=[321, 170, 465],
        ),
    )

    with pytest.raises(ValueError):
        get_nearby_stations(
            50.0,
            8.9,
            datetime(2020, 1, 1),
            datetime(2020, 1, 20),
            Parameter.TEMPERATURE_AIR,
            TimeResolution.HOURLY,
            PeriodType.RECENT,
            num_stations_nearby=1,
            max_distance_in_km=1,
        )

    with pytest.raises(ValueError):
        get_nearby_stations(
            51.4,
            9.3,
            datetime(2020, 1, 1),
            datetime(2020, 1, 20),
            Parameter.TEMPERATURE_AIR,
            TimeResolution.HOURLY,
            PeriodType.RECENT,
            num_stations_nearby=0,
        )

    with pytest.raises(InvalidParameterCombination):
        get_nearby_stations(
            51.4,
            9.3,
            datetime(2020, 1, 1),
            datetime(2020, 1, 20),
            Parameter.SOIL,
            TimeResolution.MINUTE_10,
            PeriodType.RECENT,
            num_stations_nearby=1,
        )


def test_get_nearby_stations_out_of_distance():
    nearest_station = get_nearby_stations(
        [50.0],
        [8.9],
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        max_distance_in_km=10,
    )
    assert nearest_station[0].empty is True


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
