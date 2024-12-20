# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt

import polars as pl
import pytest

from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.dmo.api import add_date_from_filename


@pytest.fixture
def df_files_january():
    return pl.DataFrame(
        {
            "date_str": [
                "310000",
                "311200",
            ],
        },
        orient="col",
    )


@pytest.fixture
def df_files_two_month():
    return pl.DataFrame(
        {
            "date_str": [
                "311200",
                "010000",
                "011200",
                "020000",
            ],
        },
        orient="col",
    )


@pytest.fixture
def df_files_end_of_month():
    return pl.DataFrame(
        {
            "date_str": [
                "310000",
                "311200",
            ],
        },
        orient="col",
    )


@pytest.mark.remote
def test_dwd_dmo_stations(default_settings):
    # Acquire data.
    stations = DwdDmoRequest(parameters=[("hourly", "icon")], settings=default_settings)
    given_df = stations.all().df
    assert not given_df.is_empty()
    assert given_df.select(pl.all().max()).to_dicts()[0] == {
        "station_id": "Z949",
        "icao_id": "ZYTX",
        "start_date": None,
        "end_date": None,
        "latitude": 79.59,
        "longitude": 179.2,
        "height": 4670.0,
        "name": "ZWOENITZ",
        "state": None,
    }
    assert given_df.select(pl.all().min()).to_dicts()[0] == {
        "station_id": "01001",
        "icao_id": "AFDU",
        "start_date": None,
        "end_date": None,
        "latitude": -78.27,
        "longitude": -176.1,
        "height": -350.0,
        "name": "16N55W",
        "state": None,
    }
    station_names_sorted = given_df.sort(pl.col("name").str.len_chars()).get_column("name").to_list()
    assert station_names_sorted[:5] == ["ELM", "PAU", "SAL", "AUE", "HOF"]
    assert station_names_sorted[-5:] == [
        "MÜNSINGEN-APFELSTETT",
        "VILLINGEN-SCHWENNING",
        "WEINGARTEN BEI RAVEN",
        "LONDON WEATHER CENT.",
        "QUITO/MARISCAL SUCRE",
    ]


def test_add_date_from_filename(df_files_two_month):
    df = add_date_from_filename(df_files_two_month, dt.datetime(2021, 11, 15))
    assert df.get_column("date").to_list() == [
        dt.datetime(2021, 10, 31, 12, 0),
        dt.datetime(2021, 11, 1, 0, 0),
        dt.datetime(2021, 11, 1, 12, 0),
        dt.datetime(2021, 11, 2, 0, 0),
    ]


def test_add_date_from_filename_early_in_month(df_files_end_of_month):
    df = add_date_from_filename(df_files_end_of_month, dt.datetime(2021, 11, 1, 2))
    assert df.get_column("date").to_list() == [
        dt.datetime(2021, 10, 31, 0, 0, 0),
        dt.datetime(2021, 10, 31, 12, 0, 0),
    ]


def test_add_date_from_filename_early_in_year(df_files_january):
    df = add_date_from_filename(df_files_january, dt.datetime(2021, 1, 1, 1, 1, 1))
    assert df.get_column("date").to_list() == [
        dt.datetime(2020, 12, 31, 0, 0, 0),
        dt.datetime(2020, 12, 31, 12, 0, 0),
    ]


def test_add_date_from_filename_too_few_dates():
    df = pl.DataFrame(
        {
            "date_str": [
                "311200",
            ],
        },
        orient="col",
    )
    with pytest.raises(ValueError):
        add_date_from_filename(df, dt.datetime(2021, 1, 1, 1, 1, 1))
