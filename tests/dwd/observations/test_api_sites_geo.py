from pathlib import Path

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock
import pandas as pd

from wetterdienst.dwd.metadata.column_map import METADATA_DTYPE_MAPPING
from wetterdienst.dwd.observations.api import DWDObservationSites
from wetterdienst.util.geo import derive_nearest_neighbours
from wetterdienst.util.geo import Coordinates
from wetterdienst import TimeResolution
from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst.exceptions import InvalidParameterCombination


HERE = Path(__file__).parent
METADATA_FILE = HERE / "FIXED_METADATA.JSON"
METADATA_DF = pd.read_json(METADATA_FILE)
METADATA_DF = METADATA_DF.astype(METADATA_DTYPE_MAPPING)


@patch(
    "wetterdienst.dwd.observations.stations.metadata_for_climate_observations",
    MagicMock(return_value=METADATA_DF),
)
def test_dwd_observation_sites_nearby_number_success():

    # Test for one nearest station
    sites = DWDObservationSites(
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
    )

    nearby_station = sites.nearby_number(
        50.0,
        8.9,
        1,
    )
    nearby_station = nearby_station.drop("TO_DATE", axis="columns")
    nearby_station.STATION_ID = nearby_station.STATION_ID.astype(np.int64)

    pd.testing.assert_frame_equal(
        nearby_station,
        pd.DataFrame(
            [
                [
                    np.int64(4411),
                    np.datetime64("2002-01-24"),
                    155.0,
                    49.9195,
                    8.9671,
                    "Schaafheim-Schlierbach",
                    "Hessen",
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
                "DISTANCE_TO_LOCATION",
            ],
        ),
    )

    nearby_station = DWDObservationSites(
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
    ).nearby_radius(
        50.0,
        8.9,
        20,
    )
    nearby_station = nearby_station.drop("TO_DATE", axis="columns")
    nearby_station.STATION_ID = nearby_station.STATION_ID.astype(np.int64)

    pd.testing.assert_frame_equal(
        nearby_station,
        pd.DataFrame(
            [
                [
                    np.int64(4411),
                    np.datetime64("2002-01-24 00:00:00"),
                    155.0,
                    49.9195,
                    8.9671,
                    "Schaafheim-Schlierbach",
                    "Hessen",
                    11.653026716750542,
                ],
                [
                    np.int64(2480),
                    np.datetime64("2004-09-01 00:00:00"),
                    108.0,
                    50.0643,
                    8.993,
                    "Kahl/Main",
                    "Bayern",
                    12.572153957087247,
                ],
                [
                    np.int64(7341),
                    np.datetime64("2005-07-16 00:00:00"),
                    119.0,
                    50.09,
                    8.7862,
                    "Offenbach-Wetterpark",
                    "Hessen",
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
                "DISTANCE_TO_LOCATION",
            ],
        ),
    )


@patch(
    "wetterdienst.dwd.observations.stations.metadata_for_climate_observations",
    MagicMock(return_value=METADATA_DF),
)
def test_dwd_observation_sites_nearby_number_fail_1():

    with pytest.raises(ValueError):
        DWDObservationSites(
            Parameter.TEMPERATURE_AIR,
            TimeResolution.HOURLY,
            PeriodType.RECENT,
            datetime(2020, 1, 1),
            datetime(2020, 1, 20),
        ).nearby_number(
            51.4,
            9.3,
            0,
        )


@patch(
    "wetterdienst.dwd.observations.stations.metadata_for_climate_observations",
    MagicMock(return_value=METADATA_DF),
)
def test_dwd_observation_sites_nearby_number_fail_2():

    with pytest.raises(InvalidParameterCombination):
        DWDObservationSites(
            Parameter.SOIL,
            TimeResolution.MINUTE_10,
            PeriodType.RECENT,
            datetime(2020, 1, 1),
            datetime(2020, 1, 20),
        ).nearby_number(
            51.4,
            9.3,
            1,
        )


@patch(
    "wetterdienst.dwd.observations.stations.metadata_for_climate_observations",
    MagicMock(return_value=METADATA_DF),
)
def test_dwd_observation_sites_nearby_distance():
    nearby_station = DWDObservationSites(
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
    ).nearby_radius(
        50.0,
        8.9,
        10,
    )
    assert nearby_station.empty is True


def test_derive_nearest_neighbours():
    coords = Coordinates(np.array([50.0, 51.4]), np.array([8.9, 9.3]))

    metadata = pd.read_json(METADATA_FILE)

    distances, indices_nearest_neighbours = derive_nearest_neighbours(
        metadata.LAT.values, metadata.LON.values, coords
    )

    np.testing.assert_array_almost_equal(distances, np.array([0.00182907, 0.00227919]))

    np.testing.assert_array_almost_equal(
        indices_nearest_neighbours, np.array([432, 655])
    )
