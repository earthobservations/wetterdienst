# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Verify acquisition of DWD MOSMIX station list.

Please note that in the original data, the values in the `LAT` and `LON`
columns are in "Degrees Minutes" format (`<degrees>.<degrees minutes>`.),
and not in "Decimal Degrees".

Source: https://www.dwd.de/EN/ourservices/met_application_mosmix/mosmix_stations.cfg?view=nasPublication&nn=495490
"""
import polars as pl
import pytest
from dirty_equals import IsInt, IsTuple
from polars.testing import assert_frame_equal

from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest


@pytest.fixture
def mosmix_stations_schema():
    return {
        "station_id": str,
        "icao_id": str,
        "from_date": pl.Datetime(time_zone="UTC"),
        "to_date": pl.Datetime(time_zone="UTC"),
        "height": float,
        "latitude": float,
        "longitude": float,
        "name": str,
        "state": str,
    }


@pytest.mark.remote
def test_dwd_mosmix_stations_success(default_settings, mosmix_stations_schema):
    """
    Verify full MOSMIX station list.
    """
    # Acquire data.
    given_df = DwdMosmixRequest(parameter="large", mosmix_type="large", settings=default_settings).all().df
    assert not given_df.is_empty()
    # Verify size of dataframe with all records.
    assert given_df.shape == IsTuple(IsInt(ge=5500), 9)
    # Verify content of dataframe. For reference purposes,
    # we use the first and the last record of the list.
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01001",
                "icao_id": "ENJA",
                "from_date": None,
                "to_date": None,
                "height": 10.0,
                "latitude": 70.93,
                "longitude": -8.67,
                "name": "JAN MAYEN",
                "state": None,
            },
            {
                "station_id": "Z949",
                "icao_id": None,
                "from_date": None,
                "to_date": None,
                "height": 1200.0,
                "latitude": 47.58,
                "longitude": 13.02,
                "name": "JENNER",
                "state": None,
            },
        ],
        schema=mosmix_stations_schema,
    )
    assert_frame_equal(given_df[[0, -1], :], expected_df)


@pytest.mark.remote
def test_dwd_mosmix_stations_filtered(default_settings, mosmix_stations_schema):
    """
    Verify MOSMIX station list filtering by station identifier.
    """
    # Acquire data.
    stations = DwdMosmixRequest(parameter="large", mosmix_type="large", settings=default_settings)
    given_df = stations.all().df
    assert not given_df.is_empty()
    # Filter dataframe.
    given_df = given_df.filter(pl.col(Columns.STATION_ID.value).is_in(["01001", "72306", "83891", "94767"])).sort(
        by="station_id"
    )
    # Verify content of filtered dataframe.
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01001",
                "icao_id": "ENJA",
                "from_date": None,
                "to_date": None,
                "height": 10.0,
                "latitude": 70.93,
                "longitude": -8.67,
                "name": "JAN MAYEN",
                "state": None,
            },
            {
                "station_id": "72306",
                "icao_id": "KRDU",
                "from_date": None,
                "to_date": None,
                "height": 132.0,
                "latitude": 35.87,
                "longitude": -78.78,
                "name": "RALEIGH/DURHAM NC.",
                "state": None,
            },
            {
                "station_id": "83891",
                "icao_id": "SBLJ",
                "from_date": None,
                "to_date": None,
                "height": 937.0,
                "latitude": -27.8,
                "longitude": -50.33,
                "name": "LAGES",
                "state": None,
            },
            {
                "station_id": "94767",
                "icao_id": "YSSY",
                "from_date": None,
                "to_date": None,
                "height": 6.0,
                "latitude": -33.95,
                "longitude": 151.18,
                "name": "SYDNEY AIRPORT",
                "state": None,
            },
        ],
        schema=mosmix_stations_schema,
    )
    assert_frame_equal(given_df, expected_df)
