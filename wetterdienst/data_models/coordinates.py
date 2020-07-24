"""Class for storing and retrieving coordinates"""
import numpy as np


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
