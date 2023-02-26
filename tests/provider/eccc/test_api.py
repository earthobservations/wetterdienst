# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import numpy as np
import pandas as pd
import pytest
import pytz
from pandas._testing import assert_frame_equal

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
    expected_df = pd.DataFrame(
        {
            "station_id": pd.Series(["14"], dtype=str),
            "from_date": [pd.Timestamp("1984-01-01", tz=pytz.UTC)],
            "to_date": [pd.Timestamp("1996-12-31", tz=pytz.UTC)],
            "height": pd.Series([4.0], dtype=float),
            "latitude": pd.Series([48.87], dtype=float),
            "longitude": pd.Series([-123.28], dtype=float),
            "name": pd.Series(["ACTIVE PASS"], dtype=str),
            "state": pd.Series(["BRITISH COLUMBIA"], dtype=str),
        }
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_eccc_api_values(settings_si_false):
    request = EcccObservationRequest(
        parameter="DAILY",
        resolution="DAILY",
        start_date="1980-01-01",
        end_date="1980-01-02",
        settings=settings_si_false,
    ).filter_by_station_id(station_id=(1652,))
    given_df = request.values.all().df
    expected_df = pd.DataFrame.from_records(
        [
            ["1652", "daily", "temperature_air_max_200", "1980-01-01", -16.3, np.NaN],
            ["1652", "daily", "temperature_air_max_200", "1980-01-02", -16.4, np.NaN],
            ["1652", "daily", "temperature_air_min_200", "1980-01-01", -29.1, np.NaN],
            ["1652", "daily", "temperature_air_min_200", "1980-01-02", -28.3, np.NaN],
            ["1652", "daily", "temperature_air_mean_200", "1980-01-01", -22.7, np.NaN],
            ["1652", "daily", "temperature_air_mean_200", "1980-01-02", -22.4, np.NaN],
            ["1652", "daily", "count_days_heating_degree", "1980-01-01", 40.7, np.NaN],
            ["1652", "daily", "count_days_heating_degree", "1980-01-02", 40.4, np.NaN],
            ["1652", "daily", "count_days_cooling_degree", "1980-01-01", 0.0, np.NaN],
            ["1652", "daily", "count_days_cooling_degree", "1980-01-02", 0.0, np.NaN],
            ["1652", "daily", "precipitation_height_liquid", "1980-01-01", 0.0, np.NaN],
            ["1652", "daily", "precipitation_height_liquid", "1980-01-02", 0.0, np.NaN],
            ["1652", "daily", "snow_depth_new", "1980-01-01", 1.8, np.NaN],
            ["1652", "daily", "snow_depth_new", "1980-01-02", 0.0, np.NaN],
            ["1652", "daily", "precipitation_height", "1980-01-01", 0.8, np.NaN],
            ["1652", "daily", "precipitation_height", "1980-01-02", 0.0, np.NaN],
            ["1652", "daily", "snow_depth", "1980-01-01", 19.0, np.NaN],
            ["1652", "daily", "snow_depth", "1980-01-02", 20.0, np.NaN],
            ["1652", "daily", "wind_direction_gust_max", "1980-01-01", np.NaN, np.NaN],
            ["1652", "daily", "wind_direction_gust_max", "1980-01-02", np.NaN, np.NaN],
            ["1652", "daily", "wind_gust_max", "1980-01-01", np.NaN, np.NaN],
            ["1652", "daily", "wind_gust_max", "1980-01-02", np.NaN, np.NaN],
        ],
        columns=["station_id", "dataset", "parameter", "date", "value", "quality"],
    )
    expected_df = expected_df.astype({"station_id": "category", "dataset": "category", "parameter": "category"})
    expected_df.date = pd.to_datetime(expected_df.date, utc=True)
    assert_frame_equal(given_df.reset_index(drop=True), expected_df, check_categorical=False)
