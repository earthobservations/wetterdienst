from typing import Tuple, Union

import numpy as np
from scipy.spatial.ckdtree import cKDTree


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
        return np.array_equal(self.latitudes, other.latitudes) and np.array_equal(
            self.longitudes, other.longitudes
        )


def derive_nearest_neighbours(
    latitudes_stations: np.array,
    longitudes_stations: np.array,
    coordinates: Coordinates,
    num_stations_nearby: int = 1,
) -> Tuple[Union[float, np.ndarray], np.ndarray]:
    """
    A function that uses a k-d tree algorithm to obtain the nearest
    neighbours to coordinate pairs

    Args:
        latitudes_stations (np.array): latitude values of stations being compared to
        the coordinates
        longitudes_stations (np.array): longitude values of stations being compared to
        the coordinates
        coordinates (Coordinates): the coordinates for which the nearest neighbour
        is searched
        num_stations_nearby: Number of stations that should be nearby

    Returns:
        Tuple of distances and ranks of nearest to most distant stations
    """
    points = np.c_[np.radians(latitudes_stations), np.radians(longitudes_stations)]
    distance_tree = cKDTree(points)
    return distance_tree.query(
        coordinates.get_coordinates_in_radians(), k=num_stations_nearby
    )
