# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.eccc.observation import EcccObservationRequest


@pytest.mark.remote
def test_eccc_api_stations(settings_si_false):
    request = EcccObservationRequest(
        parameter="DAILY",
        resolution="DAILY",
        start_date="1990-01-01",
        end_date="1990-01-02",
        settings=settings_si_false,
    ).filter_by_station_id(station_id=(14,))
    given_df = request.df
    expected_df = pl.DataFrame(
        {
            "station_id": ["14"],
            "from_date": [dt.datetime(1984, 1, 1, tzinfo=dt.timezone.utc)],
            "to_date": [dt.datetime(1996, 12, 31, tzinfo=dt.timezone.utc)],
            "height": [4.0],
            "latitude": [48.87],
            "longitude": [-123.28],
            "name": ["ACTIVE PASS"],
            "state": ["BRITISH COLUMBIA"],
        }
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_eccc_api_values(settings_si_false):
    request = EcccObservationRequest(
        parameter="daily",
        resolution="daily",
        start_date="1980-01-01",
        end_date="1980-01-02",
        settings=settings_si_false,
    ).filter_by_station_id(station_id=(1652,))
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "temperature_air_max_200",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": -16.3,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "temperature_air_max_200",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": -16.4,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "temperature_air_min_200",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": -29.1,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "temperature_air_min_200",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": -28.3,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "temperature_air_mean_200",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": -22.7,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "temperature_air_mean_200",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": -22.4,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "count_days_heating_degree",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": 40.7,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "count_days_heating_degree",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": 40.4,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "count_days_cooling_degree",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "count_days_cooling_degree",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "precipitation_height_liquid",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "precipitation_height_liquid",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "snow_depth_new",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": 1.8,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "snow_depth_new",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "precipitation_height",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": 0.8,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "precipitation_height",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "snow_depth",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": 19.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "snow_depth",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": 20.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "wind_direction_gust_max",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "wind_direction_gust_max",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "wind_gust_max",
                "date": dt.datetime(1980, 1, 1, tzinfo=dt.timezone.utc),
                "value": 31.0,
                "quality": None,
            },
            {
                "station_id": "1652",
                "dataset": "daily",
                "parameter": "wind_gust_max",
                "date": dt.datetime(1980, 1, 2, tzinfo=dt.timezone.utc),
                "value": 31.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": str,
            "dataset": str,
            "parameter": str,
            "date": pl.Datetime(time_zone="UTC"),
            "value": float,
            "quality": float,
        },
    )
    assert_frame_equal(given_df, expected_df)
