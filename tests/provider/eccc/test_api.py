# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import numpy as np
import pandas as pd
import pytest
import pytz
from pandas._testing import assert_frame_equal

from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.settings import Settings


@pytest.mark.remote
def test_eccc_api_stations():
    Settings.tidy = True
    Settings.humanize = True
    Settings.si_units = False

    request = EcccObservationRequest(
        parameter="DAILY",
        resolution="DAILY",
        start_date="1990-01-01",
        end_date="1990-01-02",
    ).filter_by_station_id(station_id=(14,))

    expected = pd.DataFrame(
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

    assert_frame_equal(request.df, expected)


@pytest.mark.remote
def test_eccc_api_values():
    Settings.tidy = True
    Settings.humanize = True
    Settings.si_units = False

    request = EcccObservationRequest(
        parameter="DAILY",
        resolution="DAILY",
        start_date="1980-01-01",
        end_date="1980-01-02",
    ).filter_by_station_id(station_id=(1652,))

    values = request.values.all().df

    expected_df = pd.DataFrame(
        {
            "station_id": pd.Categorical(["1652"] * 22),
            "dataset": pd.Categorical(["daily"] * 22),
            "parameter": pd.Categorical(
                [
                    "temperature_air_max_200",
                    "temperature_air_max_200",
                    "temperature_air_min_200",
                    "temperature_air_min_200",
                    "temperature_air_mean_200",
                    "temperature_air_mean_200",
                    "count_days_heating_degree",
                    "count_days_heating_degree",
                    "count_days_cooling_degree",
                    "count_days_cooling_degree",
                    "precipitation_height_liquid",
                    "precipitation_height_liquid",
                    "snow_depth_new",
                    "snow_depth_new",
                    "precipitation_height",
                    "precipitation_height",
                    "snow_depth",
                    "snow_depth",
                    "wind_direction_gust_max",
                    "wind_direction_gust_max",
                    "wind_gust_max",
                    "wind_gust_max",
                ]
            ),
            "date": [
                pd.Timestamp("1980-01-01", tz=pytz.UTC),
                pd.Timestamp("1980-01-02", tz=pytz.UTC),
            ]
            * 11,
            "value": [
                -16.3,
                -16.4,
                -29.1,
                -28.3,
                -22.7,
                -22.4,
                40.7,
                40.4,
                0.0,
                0.0,
                0.0,
                0.0,
                1.8,
                0.0,
                0.8,
                0.0,
                19.0,
                20.0,
                np.NaN,
                np.NaN,
                np.NaN,
                np.NaN,
            ],
            "quality": pd.Series([np.NaN] * 22, dtype=float),
        }
    )

    assert_frame_equal(values.reset_index(drop=True), expected_df, check_categorical=False)
