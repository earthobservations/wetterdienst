# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import numpy as np
import polars as pl
from polars.testing import assert_series_equal

from wetterdienst.util.geo import Coordinates, convert_dm_to_dd, convert_dms_string_to_dd, derive_nearest_neighbours


def test_get_coordinates():
    coordinates = Coordinates(np.array([1, 2, 3, 4]), np.array([5, 6, 7, 8]))
    np.testing.assert_equal(coordinates.get_coordinates(), np.array([[1, 5], [2, 6], [3, 7], [4, 8]]))


def test_get_coordinates_in_radians():
    coordinates = Coordinates(np.array([1, 2, 3, 4]), np.array([5, 6, 7, 8]))
    np.testing.assert_almost_equal(
        coordinates.get_coordinates_in_radians(),
        np.array(
            [
                [0.0174533, 0.0872665],
                [0.0349066, 0.1047198],
                [0.0523599, 0.122173],
                [0.0698132, 0.1396263],
            ],
        ),
    )


def test_convert_dm_to_dd():
    """Test conversion from degree minute second to decimal degree"""
    data = pl.Series(values=[7.42, 52.08, -7.42, -52.08, 0])
    given = convert_dm_to_dd(data)
    expected = pl.Series(values=[7.7, 52.13, -7.7, -52.13, 0])
    assert_series_equal(given, expected)


def test_convert_dms_string_to_dd():
    """Test conversion from degree minute second to decimal degree"""
    data = pl.Series(values=["49 18 21"])
    given = convert_dms_string_to_dd(data)
    expected = pl.Series(values=[49.305833])
    assert_series_equal(given, expected)


def test_derive_nearest_neighbours():
    coords = Coordinates(np.array([50.0, 51.4]), np.array([8.9, 9.3]))
    metadata = pl.DataFrame(
        [
            {
                "station_id": 4371,
                "latitude": 52.1042,
                "longitude": 8.7521,
            },
            {
                "station_id": 4373,
                "latitude": 52.8568,
                "longitude": 11.1319,
            },
            {
                "station_id": 4411,
                "latitude": 49.9195,
                "longitude": 8.9671,
            },
            {
                "station_id": 13904,
                "latitude": 55.0,
                "longitude": 6.3333,
            },
            {
                "station_id": 13965,
                "latitude": 48.2639,
                "longitude": 8.8134,
            },
            {
                "station_id": 15207,
                "latitude": 51.2835,
                "longitude": 9.359,
            },
        ],
        orient="row",
    )
    distances, indices_nearest_neighbours = derive_nearest_neighbours(
        latitudes=metadata.get_column("latitude"),
        longitudes=metadata.get_column("longitude"),
        coordinates=coords,
        number_nearby=1,
    )
    np.testing.assert_array_almost_equal(distances, np.array([[0.001594], [0.002133]]))
    np.testing.assert_array_almost_equal(indices_nearest_neighbours, np.array([[2], [5]]))
