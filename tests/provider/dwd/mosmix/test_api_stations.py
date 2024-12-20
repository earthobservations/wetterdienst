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
        "start_date": pl.Datetime(time_zone="UTC"),
        "end_date": pl.Datetime(time_zone="UTC"),
        "latitude": float,
        "longitude": float,
        "height": float,
        "name": str,
        "state": str,
    }


@pytest.mark.remote
def test_dwd_mosmix_stations_success(default_settings, mosmix_stations_schema):
    """
    Verify full MOSMIX station list.
    """
    # Acquire data.
    given_df = DwdMosmixRequest(parameters=[("hourly", "large")], settings=default_settings).all().df
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
                "start_date": None,
                "end_date": None,
                "latitude": 70.93,
                "longitude": -8.67,
                "height": 10.0,
                "name": "JAN MAYEN",
                "state": None,
            },
            {
                "station_id": "Z949",
                "icao_id": None,
                "start_date": None,
                "end_date": None,
                "latitude": 47.58,
                "longitude": 13.02,
                "height": 1200.0,
                "name": "JENNER",
                "state": None,
            },
        ],
        schema=mosmix_stations_schema,
        orient="row",
    )
    assert_frame_equal(given_df[[0, -1], :], expected_df)


@pytest.mark.xfail(reason="polars min currently not working as expected with strings")
@pytest.mark.remote
def test_dwd_mosmix_stations_filtered(default_settings, mosmix_stations_schema):
    """
    Verify MOSMIX station list filtering by station identifier.
    """
    # Acquire data.
    stations = DwdMosmixRequest(parameters=[("hourly", "large")], settings=default_settings)
    given_df = stations.all().df
    assert not given_df.is_empty()
    assert given_df.select(pl.all().max()).to_dicts()[0] == {
        "station_id": "Z949",
        "icao_id": "ZYTX",
        "start_date": None,
        "end_date": None,
        "latitude": 79.98,
        "longitude": 179.33,
        "height": 4670.0,
        "name": "ZWOENITZ",
        "state": None,
    }
    assert given_df.select(pl.all().min()).to_dicts()[0] == {
        "station_id": "01001",
        "icao_id": "AFDU",
        "start_date": None,
        "end_date": None,
        "latitude": -75.45,
        "longitude": -176.17,
        "height": -350.0,
        "name": "16N55W",
        "state": None,
    }
    station_names_sorted = given_df.sort(pl.col("name").str.len_chars()).get_column("name").to_list()
    assert station_names_sorted[:5] == ["ELM", "PAU", "SAL", "AUE", "HOF"]
    assert station_names_sorted[-5:] == [
        "KARLSRUHE/BADEN-BADE",
        "FELDBERG/MECKLENBURG",
        "HINTERHORNBACH/OESTE",
        "UNTERGSCHWEND/OESTER",
        "ACHENKIRCH/OESTERREI",
    ]
    # Filter dataframe.
    given_df = given_df.filter(pl.col(Columns.STATION_ID.value).is_in(["01001", "72306", "83891", "94767"]))
    # Verify content of filtered dataframe.
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01001",
                "icao_id": "ENJA",
                "start_date": None,
                "end_date": None,
                "latitude": 70.93,
                "longitude": -8.67,
                "height": 10.0,
                "name": "JAN MAYEN",
                "state": None,
            },
            {
                "station_id": "72306",
                "icao_id": "KRDU",
                "start_date": None,
                "end_date": None,
                "latitude": 35.87,
                "longitude": -78.78,
                "height": 132.0,
                "name": "RALEIGH/DURHAM NC.",
                "state": None,
            },
            {
                "station_id": "83891",
                "icao_id": "SBLJ",
                "start_date": None,
                "end_date": None,
                "latitude": -27.8,
                "longitude": -50.33,
                "height": 937.0,
                "name": "LAGES",
                "state": None,
            },
            {
                "station_id": "94767",
                "icao_id": "YSSY",
                "start_date": None,
                "end_date": None,
                "latitude": -33.95,
                "longitude": 151.18,
                "height": 6.0,
                "name": "SYDNEY AIRPORT",
                "state": None,
            },
        ],
        schema=mosmix_stations_schema,
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)
