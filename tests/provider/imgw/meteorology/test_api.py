# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.imgw.meteorology.api import ImgwMeteorologyRequest


@pytest.mark.xfail
def test_imgw_meteorology_api_daily():
    request = ImgwMeteorologyRequest(
        parameters=[("daily", "klimat")],
        start_date="2010-08-01",
    ).filter_by_station_id("253160090")
    df_expected_station = pl.DataFrame(
        [
            {
                "station_id": "253160090",
                "start_date": None,
                "end_date": None,
                "latitude": 53.46,
                "longitude": 16.104444,
                "height": 137.0,
                "name": "WIERZCHOWO",
                "state": "Drawa",
            }
        ],
        schema={
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(request.df, df_expected_station)
    values = request.values.all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "cloud_cover_total",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 28.75,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "humidity",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "precipitation_height",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "snow_depth",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 301.35,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "temperature_air_mean_0_05m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 278.75,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 293.75,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 282.35,
                "quality": None,
            },
            {
                "station_id": "253160090",
                "dataset": "climate",
                "parameter": "wind_speed",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.7,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)


@pytest.mark.xfail
def test_imgw_meteorology_api_monthly():
    request = ImgwMeteorologyRequest(
        parameters=[("monthly", "synop")],
        start_date="2010-08-01",
    ).filter_by_station_id("349190600")
    df_expected_station = pl.DataFrame(
        [
            {
                "station_id": "349190600",
                "start_date": None,
                "end_date": None,
                "latitude": 49.806666666666665,
                "longitude": 19.002222222222223,
                "height": 396.0,
                "name": "BIELSKO-BIA£A",
                "state": "Bia³a",
            }
        ],
        schema={
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(request.df, df_expected_station)
    values = request.values.all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "cloud_cover_total",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 60.0,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "humidity",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 75.3,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "precipitation_height",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 204.1,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "precipitation_height_day",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 136.4,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "precipitation_height_max",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 92.3,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "precipitation_height_night",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 67.7,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "pressure_air_sea_level",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 101380.0,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "pressure_air_site",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 96740.0,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "pressure_vapor",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1560.0,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "snow_depth_max",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 302.65,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "temperature_air_max_2m_mean",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 296.34999999999997,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 291.34999999999997,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "temperature_air_min_0_05m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 280.84999999999997,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 281.65,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "temperature_air_min_2m_mean",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 287.15,
                "quality": None,
            },
            {
                "station_id": "349190600",
                "dataset": "synop",
                "parameter": "wind_speed",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.1,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)
