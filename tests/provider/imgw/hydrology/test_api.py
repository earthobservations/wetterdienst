import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyRequest


@pytest.fixture
def df_expected_station():
    return pl.DataFrame(
        [
            {
                "station_id": "150190130",
                "start_date": None,
                "end_date": None,
                "latitude": 50.350278,
                "longitude": 19.185556,
                "height": None,
                "name": "£AGISZA",
                "state": None,
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


@pytest.mark.xfail
def test_imgw_hydrology_api_daily(df_expected_station):
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
                "dataset": "hydrology",
                "parameter": "discharge",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.62,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "stage",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.64,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "temperature_water",
                "date": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
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
    assert_frame_equal(values.df, df_expected)


@pytest.mark.xfail
def test_imgw_hydrology_api_monthly(df_expected_station):
    request = ImgwHydrologyRequest(
        parameters=[("monthly", "hydrology")],
        start_date="2010-06-01",
    ).filter_by_station_id("150190130")
    assert_frame_equal(request.df, df_expected_station)
    values = request.values.all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "discharge_max",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 18.3,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "discharge_mean",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.36,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "discharge_min",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 2.75,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "stage_max",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 2.64,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "stage_mean",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.99,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "stage_min",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.49,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "temperature_water_max",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "temperature_water_mean",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "150190130",
                "dataset": "hydrology",
                "parameter": "temperature_water_min",
                "date": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
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
