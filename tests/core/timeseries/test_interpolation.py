# -*- coding: utf-8 -*-
# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.exceptions import StationNotFoundError
from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)
from wetterdienst.provider.eccc.observation.api import EcccObservationRequest

pytest.importorskip("shapely")

pytestmark = pytest.mark.slow


@pytest.fixture
def df_interpolated_empty():
    return pl.DataFrame(
        schema={
            Columns.DATE.value: pl.Datetime(time_zone="UTC"),
            Columns.PARAMETER.value: pl.Utf8,
            Columns.VALUE.value: pl.Float64,
            Columns.DISTANCE_MEAN.value: pl.Float64,
            Columns.STATION_IDS.value: pl.List(pl.Utf8),
        },
    )


@pytest.mark.remote
def test_interpolation_temperature_air_mean_200_hourly_by_coords(default_settings):
    request = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="hourly",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] == 18001
    assert result.df.drop_nulls().shape[0] == 17881
    given_df = result.filter_by_date("2022-01-02 00:00:00+00:00")
    expected_df = pl.DataFrame(
        {
            "date": [dt.datetime(2022, 1, 2, tzinfo=dt.timezone.utc)],
            "parameter": ["temperature_air_mean_200"],
            "value": [277.71],
            "distance_mean": [13.37],
            "station_ids": [["02480", "04411", "07341", "00917"]],
        }
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_temperature_air_mean_200_daily_by_station_id(default_settings):
    request = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="daily",
        start_date=dt.datetime(1986, 10, 31),
        end_date=dt.datetime(1986, 11, 1),
        settings=default_settings,
    )
    expected_df = pl.DataFrame(
        {
            "date": [
                dt.datetime(1986, 10, 31, tzinfo=dt.timezone.utc),
                dt.datetime(1986, 11, 1, tzinfo=dt.timezone.utc),
            ],
            "parameter": ["temperature_air_mean_200", "temperature_air_mean_200"],
            "value": [279.52, 281.85],
            "distance_mean": [16.99, 0.0],
            "station_ids": [["00072", "02074", "02638", "04703"], ["00071"]],
        }
    )
    for result in (
        request.interpolate(latlon=(48.2156, 8.9784)),
        request.interpolate_by_station_id(station_id="00071"),
    ):
        given_df = result.df
        assert given_df.shape[0] == 2
        assert given_df.drop_nulls().shape[0] == 2
        assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_precipitation_height_minute_10(default_settings):
    request = DwdObservationRequest(
        parameter="precipitation_height",
        resolution="minute_10",
        start_date=dt.datetime(2021, 10, 1),
        end_date=dt.datetime(2021, 10, 5),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] == 577
    assert result.df.drop_nulls().shape[0] == 577
    given_df = result.filter_by_date("2021-10-05 00:00:00+00:00")
    expected_df = pl.DataFrame(
        {
            "date": [dt.datetime(2021, 10, 5, tzinfo=dt.timezone.utc)],
            "parameter": ["precipitation_height"],
            "value": [0.03],
            "distance_mean": [9.38],
            "station_ids": [["04230", "02480", "04411", "07341"]],
        }
    )
    assert_frame_equal(given_df, expected_df)


def test_not_interpolatable_parameter(default_settings, df_interpolated_empty):
    request = DwdObservationRequest(
        parameter="wind_direction",
        resolution="hourly",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    assert_frame_equal(
        given_df,
        df_interpolated_empty,
    )


def test_not_interpolatable_dataset(default_settings, df_interpolated_empty):
    request = DwdObservationRequest(
        parameter="temperature_air",
        resolution="hourly",
        start_date=dt.datetime(2022, 1, 1),
        end_date=dt.datetime(2022, 1, 2),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    assert_frame_equal(
        given_df,
        df_interpolated_empty,
    )


def test_not_supported_provider_dwd_mosmix(default_settings, caplog):
    request = DwdMosmixRequest(
        parameter=["dd", "ww"],
        mosmix_type="small",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.is_empty()
    assert "Interpolation currently only works for DwdObservationRequest" in caplog.text


def test_not_supported_provider_ecc(default_settings, caplog):
    station = EcccObservationRequest(
        parameter=["temperature_air_mean_200"],
        resolution="daily",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=default_settings,
    )
    result = station.interpolate(latlon=(50.0, 8.9))
    assert result.df.is_empty()
    assert "Interpolation currently only works for DwdObservationRequest" in caplog.text


def test_interpolation_temperature_air_mean_200_daily_three_floats(default_settings):
    stations = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="daily",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=default_settings,
    )
    with pytest.raises(ValueError) as excinfo:
        stations.interpolate(latlon=(0, 1, 2))
    assert str(excinfo.value).startswith("too many values to unpack")


def test_interpolation_temperature_air_mean_200_daily_one_floats(default_settings):
    stations = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="daily",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=default_settings,
    )
    with pytest.raises(ValueError) as excinfo:
        stations.interpolate(latlon=(0,))
    assert str(excinfo.value).startswith("not enough values to unpack")


def test_interpolation_temperature_air_mean_200_daily_no_station_found(default_settings):
    stations = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="daily",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=default_settings,
    )
    with pytest.raises(StationNotFoundError) as excinfo:
        stations.interpolate_by_station_id(station_id="00")
    assert str(excinfo.value) == "no station found for 00000"
