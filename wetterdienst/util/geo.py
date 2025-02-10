# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geo utilities for the wetterdienst package."""

import math

import polars as pl
import pyarrow as pa
import pyarrow.compute as pc

EARTH_RADIUS_IN_KM = 6371


def derive_nearest_neighbours(
    latitudes: pa.Array,
    longitudes: pa.Array,
    q_lat: float,
    q_lon: float,
) -> list[float]:
    """Obtain the nearest neighbours using a simple distance computation.

    Args:
        latitudes: latitudes in degree
        longitudes: longitudes in degree
        q_lat: latitude of the query point
        q_lon: longitude of the query point

    Returns:
        Tuple of distances and ranks of nearest to most distant station

    """
    lat_radians = pc.multiply(latitudes, math.pi / 180)
    lon_radians = pc.multiply(longitudes, math.pi / 180)
    q_lat_radians = q_lat * math.pi / 180
    q_lon_radians = q_lon * math.pi / 180
    # Haversine formula approximation using PyArrow compute
    dlat = pc.subtract(lat_radians, q_lat_radians)
    dlon = pc.subtract(lon_radians, q_lon_radians)
    a = pc.add(
        pc.multiply(pc.sin(pc.divide(dlat, 2)), pc.sin(pc.divide(dlat, 2))),
        pc.multiply(
            pc.cos(q_lat_radians),
            pc.multiply(pc.cos(lat_radians), pc.multiply(pc.sin(pc.divide(dlon, 2)), pc.sin(pc.divide(dlon, 2)))),
        ),
    )
    c = pc.multiply(2, pc.atan2(pc.sqrt(a), pc.sqrt(pc.subtract(1, a))))
    distance = pc.multiply(EARTH_RADIUS_IN_KM, c)  # Earth radius in km
    return pc.round(distance, 4).to_pylist()


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
