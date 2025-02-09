# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geo utilities for the wetterdienst package."""

from __future__ import annotations

import numpy as np
import polars as pl
from sklearn.neighbors import BallTree


class Coordinates:
    """Coordinates class to store latitudes and longitudes."""

    def __init__(self, latitudes: np.array, longitudes: np.array) -> None:
        """Initialize the coordinates.

        Args:
        latitudes: latitudes in degree
        longitudes: longitudes in degree

        """
        self.latitudes = latitudes
        self.longitudes = longitudes

    def get_coordinates(self) -> np.array:
        """Return coordinates in degree.

        The first column is the latitudes and the second column the longitudes

        """
        return np.array([self.latitudes, self.longitudes]).T

    def get_coordinates_in_radians(self) -> np.array:
        """Return coordinates in radians.

        The first column is the latitudes and the second column the longitudes.
        """
        return np.radians(self.get_coordinates())

    def __eq__(self, other: object) -> bool:
        """Check if two coordinates are equal."""
        return np.array_equal(self.latitudes, other.latitudes) and np.array_equal(self.longitudes, other.longitudes)


def derive_nearest_neighbours(
    latitudes: np.array,
    longitudes: np.array,
    coordinates: Coordinates,
    number_nearby: int = 1,
) -> tuple[float | np.ndarray, np.ndarray]:
    """Obtain the nearest neighbours to coordinate using a k-d tree algorithm.

    Args:
        latitudes: latitudes in degree
        longitudes: longitudes in degree
        coordinates: coordinates to find nearest neighbours to
        number_nearby: number of nearest neighbours to find


    Returns:
        Tuple of distances and ranks of nearest to most distant station

    """
    points = np.c_[np.radians(latitudes), np.radians(longitudes)]
    distance_tree = BallTree(points, metric="haversine")
    return distance_tree.query(coordinates.get_coordinates_in_radians().reshape(-1, 2), k=number_nearby)


def convert_dm_to_dd(dm: pl.Series) -> pl.Series:
    """Convert degree minutes (floats) to decimal degree.

    Args:
        dm: Series with degree minutes as float

    Returns:
        Series with decimal degree

    """
    degrees = dm.cast(int)
    minutes = dm - degrees
    decimals = (minutes / 60 * 100).round(2)
    return degrees + decimals


def convert_dms_string_to_dd(dms: pl.Series) -> pl.Series:
    """Convert degree minutes seconds (string) to decimal degree.

    Args:
        dms: Series with degree minutes seconds as string

    Returns:
        Series with decimal degree

    """
    dms = dms.str.split(" ").to_frame("dms")
    dms = dms.select(
        pl.col("dms").list.get(0).cast(pl.Float64).alias("degrees"),
        pl.col("dms").list.get(1).cast(pl.Float64).alias("minutes"),
        pl.col("dms").list.get(2).cast(pl.Float64).alias("seconds"),
    )
    return dms.get_column("degrees").rename("") + (dms.get_column("minutes") / 60) + (dms.get_column("seconds") / 3600)
