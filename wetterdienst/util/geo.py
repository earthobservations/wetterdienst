# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import Tuple, Union

import numpy as np
from sklearn.neighbors import BallTree


class Coordinates:
    """Class for storing and retrieving coordinates"""

    def __init__(self, latitudes: np.array, longitudes: np.array):
        """
        Args:
            latitudes: latitudes in degree
            longitudes: longitudes in degree

        """

        self.latitudes = latitudes
        self.longitudes = longitudes

    def get_coordinates(self) -> np.array:
        """
        Returns: coordinates in degree where the first column is the latitudes
         and the second column the longitudes

        """
        return np.array([self.latitudes, self.longitudes]).T

    def get_coordinates_in_radians(self):
        """
        Returns: coordinates in radians where the first column is the latitudes
         and the second column the longitudes

        """
        return np.radians(self.get_coordinates())

    def __eq__(self, other):
        return np.array_equal(self.latitudes, other.latitudes) and np.array_equal(self.longitudes, other.longitudes)


def derive_nearest_neighbours(
    latitudes: np.array,
    longitudes: np.array,
    coordinates: Coordinates,
    number_nearby: int = 1,
) -> Tuple[Union[float, np.ndarray], np.ndarray]:
    """
    A function that uses a k-d tree algorithm to obtain the nearest
    neighbours to coordinate pairs

    Args:
        latitudes (np.array): latitude values of stations_result being compared to
        the coordinates
        longitudes (np.array): longitude values of stations_result being compared to
        the coordinates
        coordinates (Coordinates): the coordinates for which the nearest neighbour
        is searched
        number_nearby: Number of stations_result that should be nearby

    Returns:
        Tuple of distances and ranks of nearest to most distant stations_result
    """
    points = np.c_[np.radians(latitudes), np.radians(longitudes)]

    distance_tree = BallTree(points, metric="haversine")

    return distance_tree.query(coordinates.get_coordinates_in_radians().reshape(-1, 2), k=number_nearby)


def convert_dm_to_dd(dms: float) -> float:
    """Convert degree minutes to decimal degree"""
    degrees, minutes = divmod(dms, 1)

    decimals = round(minutes / 60 * 100, 2)

    return degrees + decimals
