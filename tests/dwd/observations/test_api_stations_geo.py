from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from wetterdienst.dwd.observations import (
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
    DWDObservationStations,
)
from wetterdienst.exceptions import InvalidParameterCombination
from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

HERE = Path(__file__).parent
METADATA_FILE = HERE / "FIXED_METADATA.JSON"
METADATA_DF = pd.read_json(METADATA_FILE)
METADATA_DF = METADATA_DF.astype(DWDObservationStations._dtype_mapping)


@patch(
    "wetterdienst.dwd.observations.stations.metadata_for_climate_observations",
    MagicMock(return_value=METADATA_DF),
)
def test_dwd_observation_sites_nearby_number_success():

    # Test for one nearest station
    sites = DWDObservationStations(
        DWDObservationParameterSet.TEMPERATURE_AIR,
        DWDObservationResolution.HOURLY,
        DWDObservationPeriod.RECENT,
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
                    pd.to_datetime("2002-01-24").tz_localize("UTC"),
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

    nearby_station = DWDObservationStations(
        DWDObservationParameterSet.TEMPERATURE_AIR,
        DWDObservationResolution.HOURLY,
        DWDObservationPeriod.RECENT,
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
                    pd.to_datetime("2002-01-24 00:00:00").tz_localize("UTC"),
                    155.0,
                    49.9195,
                    8.9671,
                    "Schaafheim-Schlierbach",
                    "Hessen",
                    11.653026716750542,
                ],
                [
                    np.int64(2480),
                    pd.to_datetime("2004-09-01 00:00:00").tz_localize("UTC"),
                    108.0,
                    50.0643,
                    8.993,
                    "Kahl/Main",
                    "Bayern",
                    12.572153957087247,
                ],
                [
                    np.int64(7341),
                    pd.to_datetime("2005-07-16 00:00:00").tz_localize("UTC"),
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
        DWDObservationStations(
            DWDObservationParameterSet.TEMPERATURE_AIR,
            DWDObservationResolution.HOURLY,
            DWDObservationPeriod.RECENT,
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
        DWDObservationStations(
            DWDObservationParameterSet.SOIL,
            DWDObservationResolution.MINUTE_10,
            DWDObservationPeriod.RECENT,
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
    nearby_station = DWDObservationStations(
        DWDObservationParameterSet.TEMPERATURE_AIR,
        DWDObservationResolution.HOURLY,
        DWDObservationPeriod.RECENT,
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
