# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the IMGW hydrology API."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyRequest


@pytest.fixture
def df_expected_station() -> pl.DataFrame:
    """Provide expected DataFrame for station."""
    return pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "hydrology",
                "station_id": "150190130",
                "start_date": None,
                "end_date": None,
                "latitude": 50.35027777777778,
                "longitude": 19.185555555555556,
                "height": None,
                "name": "ŁAGISZA",
                "state": None,
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
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


def test_imgw_hydrology_api_daily(df_expected_station: pl.DataFrame) -> None:
    """Test fetching of daily hydrology data."""
    request = ImgwHydrologyRequest(
        parameters=[("daily", "hydrology")],
        start_date="2010-08-01",
    ).filter_by_station_id("150190130")
    assert_frame_equal(request.df, df_expected_station)
    values = request.values.all()
    df_expected = pl.DataFrame(
        [
            {
                "station_id": "150190130",
                "resolution": "daily",
                "dataset": "hydrology",
                "parameter": "discharge",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.62,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "resolution": "daily",
                "dataset": "hydrology",
                "parameter": "stage",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 164.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected)


def test_imgw_hydrology_api_monthly() -> None:
    """Test fetching of monthly hydrology data."""
    request = ImgwHydrologyRequest(
        parameters=[("monthly", "hydrology")],
        start_date="2010-06-01",
    ).filter_by_station_id("150190130")
    df_expected_station = pl.DataFrame(
        [
            {
                "resolution": "monthly",
                "dataset": "hydrology",
                "station_id": "150190130",
                "start_date": None,
                "end_date": None,
                "latitude": 50.35027777777778,
                "longitude": 19.185555555555556,
                "height": None,
                "name": "ŁAGISZA",
                "state": None,
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
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
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "discharge_max",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 18.3,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "discharge_mean",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.36,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "discharge_min",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 2.75,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "stage_max",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 264.0,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "stage_mean",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 199.0,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "stage_min",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 149.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)
