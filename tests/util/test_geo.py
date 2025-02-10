# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for geo utilities."""

import polars as pl
from polars.testing import assert_series_equal

from wetterdienst.util.geo import convert_dm_to_dd, convert_dms_string_to_dd, derive_nearest_neighbours


def test_convert_dm_to_dd() -> None:
    """Test conversion from degree minute to decimal degree."""
    data = pl.Series(values=[7.42, 52.08, -7.42, -52.08, 0])
    given = convert_dm_to_dd(data)
    expected = pl.Series(values=[7.7, 52.13, -7.7, -52.13, 0])
    assert_series_equal(given, expected)


def test_convert_dms_string_to_dd() -> None:
    """Test conversion from degree minute second to decimal degree."""
    data = pl.Series(values=["49 18 21"])
    given = convert_dms_string_to_dd(data)
    expected = pl.Series(values=[49.305833])
    assert_series_equal(given, expected)


def test_derive_nearest_neighbours() -> None:
    """Test derivation of nearest neighbours."""
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
    distances = derive_nearest_neighbours(
        latitudes=metadata.get_column("latitude").to_arrow(),
        longitudes=metadata.get_column("longitude").to_arrow(),
        q_lat=50.0,
        q_lon=8.9,
    )
    # distance in km
    assert distances == [234.2045, 353.3014, 10.1569, 582.3868, 193.1483, 146.3421]
