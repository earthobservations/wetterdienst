# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geo utilities for the wetterdienst package."""

import math
from typing import Any, TypeVar

import polars as pl
import pyarrow as pa
import pyarrow.compute as _pc

from wetterdienst.exceptions import LocationOutOfRangeError

# pyarrow.compute lacks complete type stubs for compute functions
pc: Any = _pc

EARTH_RADIUS_IN_KM = 6371

#: the range of a point on the globe, in degrees; the poles and the antimeridian are in it. The fields of the REST
#: API, the command line and MCP and `summarize` of the Python API all hold a latitude and a longitude to it
LATITUDE_MIN = -90
LATITUDE_MAX = 90
LONGITUDE_MIN = -180
LONGITUDE_MAX = 180

# the conversions are plain arithmetic, so a column expression and a series run through the same body
_SeriesOrExpr = TypeVar("_SeriesOrExpr", pl.Series, pl.Expr)


def require_location_in_range(latitude: float, longitude: float) -> None:
    """Refuse a latitude outside -90..90 or a longitude outside -180..180, which names no point on the globe.

    Raises:
        LocationOutOfRangeError: where either is beyond, or is not a number, naming the range allowed

    """
    if not LATITUDE_MIN <= latitude <= LATITUDE_MAX:
        msg = f"latitude {latitude} is outside the range {LATITUDE_MIN} to {LATITUDE_MAX} degrees"
        raise LocationOutOfRangeError(msg)
    if not LONGITUDE_MIN <= longitude <= LONGITUDE_MAX:
        msg = f"longitude {longitude} is outside the range {LONGITUDE_MIN} to {LONGITUDE_MAX} degrees"
        raise LocationOutOfRangeError(msg)


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


def convert_dm_to_dd(dm: _SeriesOrExpr) -> _SeriesOrExpr:
    """Convert degree minutes (floats) to decimal degree.

    Args:
        dm: Series or expression with degree minutes as float

    Returns:
        Series or expression with decimal degree

    """
    value: Any = dm  # a series and an expression have the same arithmetic, which a type checker cannot follow
    degrees = value.cast(int)
    minutes = value - degrees
    decimals = (minutes / 60 * 100).round(2)
    return degrees + decimals


def convert_dms_string_to_dd(dms: _SeriesOrExpr) -> _SeriesOrExpr:
    """Convert degree minutes seconds (string) to decimal degree.

    Args:
        dms: Series or expression with degree minutes seconds as string

    Returns:
        Series or expression with decimal degree

    """
    value: Any = dms
    parts = value.str.split(" ")
    degrees = parts.list.get(0).cast(pl.Float64)
    minutes = parts.list.get(1).cast(pl.Float64)
    seconds = parts.list.get(2).cast(pl.Float64)
    return degrees + (minutes / 60) + (seconds / 3600)
