# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import numpy as np

from wetterdienst.util.geo import Coordinates, convert_dm_to_dd


def test_get_coordinates():
    coordinates = Coordinates(np.array([1, 2, 3, 4]), np.array([5, 6, 7, 8]))
    np.testing.assert_equal(
        coordinates.get_coordinates(), np.array([[1, 5], [2, 6], [3, 7], [4, 8]])
    )


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
            ]
        ),
    )


def test_dms_to_dd():
    """ Test conversion from degree minute second to decimal degree """
    # test Mosmix station Muenster/Osnabrueck
    assert convert_dm_to_dd(7.42) == 7.7
    assert convert_dm_to_dd(52.08) == 52.13
