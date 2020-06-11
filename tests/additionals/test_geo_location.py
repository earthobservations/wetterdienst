from python_dwd.additionals.geo_location import get_nearest_station,\
    _derive_nearest_neighbours
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.data_models.coordinates import Coordinates
import numpy as np
from unittest.mock import patch, MagicMock
import pandas as pd
import os

fixtures_dir = f"{os.path.dirname(__file__)}/../fixtures/"


@patch(
    'python_dwd.metadata_dwd.metadata_for_dwd_data',
    MagicMock(return_value=pd.read_json(f"{fixtures_dir}FIXED_METADATA.JSON"))
)
def test_get_nearest_station():
    nearest_indices, distances = get_nearest_station(
        [50., 51.4], [8.9, 9.3],
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT)

    assert nearest_indices == [4411, 15207]

    np.testing.assert_array_almost_equal(
        np.array(distances),
        np.array([11.653026716750542, 14.520733407578632]))


def test_derive_nearest_neighbours():
    coords = Coordinates(np.array([50., 51.4]), np.array([8.9, 9.3]))

    metadata = pd.read_json(f"{fixtures_dir}FIXED_METADATA.JSON")

    distances, indices_nearest_neighbours = _derive_nearest_neighbours(
        metadata.LAT.values,
        metadata.LON.values,
        coords)
    np.testing.assert_array_almost_equal(distances,
                                         np.array([0.00182907, 0.00227919]))

    np.testing.assert_array_almost_equal(indices_nearest_neighbours,
                                         np.array([432, 655]))
