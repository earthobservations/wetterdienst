# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from freezegun import freeze_time
from polars.testing import assert_frame_equal

from wetterdienst import Resolution, Settings
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest
from wetterdienst.provider.dwd.observation.metadata import (
    DwdObservationMetadata,
)


@pytest.fixture
def dwd_climate_summary_wide_columns():
    return [
        "station_id",
        "dataset",
        "date",
        "fx",
        "qn_fx",
        "fm",
        "qn_fm",
        "rsk",
        "qn_rsk",
        "rskf",
        "qn_rskf",
        "sdk",
        "qn_sdk",
        "shk_tag",
        "qn_shk_tag",
        "nm",
        "qn_nm",
        "vpm",
        "qn_vpm",
        "pm",
        "qn_pm",
        "tmk",
        "qn_tmk",
        "upm",
        "qn_upm",
        "txk",
        "qn_txk",
        "tnk",
        "qn_tnk",
        "tgk",
        "qn_tgk",
    ]


@pytest.mark.remote
def test_dwd_observation_data_empty(default_settings):
    request = DwdObservationRequest(
        parameters=[
            ("minute_10", "temperature_air"),
            ("minute_10", "wind"),
            ("minute_10", "precipitation"),
        ],
        periods="now",
        settings=default_settings,
    ).filter_by_rank(latlon=(52.384630, 9.733908), rank=1)
    given_df = request.values.all().df
    assert given_df.select(pl.col("station_id")).to_series().unique().to_list() == ["02011"]
    assert (
        given_df.filter(pl.col("dataset").is_in(["wind", "temperature_air"]))
        .select(pl.col("value"))
        .drop_nulls()
        .is_empty()
    )


def test_request_period_historical(default_settings):
    # Historical period expected
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1971-01-01",
        settings=default_settings,
    )
    assert request.periods == [
        Period.HISTORICAL,
    ]


def test_request_period_historical_recent(default_settings):
    # Historical and recent period expected
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1971-01-01",
        end_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=400),
        settings=default_settings,
    )
    assert request.periods == [
        Period.HISTORICAL,
        Period.RECENT,
    ]


def test_request_period_historical_recent_now(default_settings):
    # Historical, recent and now period expected
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1971-01-01",
        end_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None),
        settings=default_settings,
    )
    assert request.periods == [
        Period.HISTORICAL,
        Period.RECENT,
        Period.NOW,
    ]


@freeze_time(dt.datetime(2022, 1, 29, 1, 30, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_recent_now(default_settings):
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert request.periods == [Period.RECENT, Period.NOW]


@freeze_time(dt.datetime(2022, 1, 29, 2, 30, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_now(default_settings):
    # Now period
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert request.periods == [Period.NOW]


@freeze_time(dt.datetime(2021, 3, 28, 18, 38, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_now_fixed_date(default_settings):
    # Now period
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert Period.NOW in request.periods


def test_request_period_now_previous_hour(default_settings):
    # Now period
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=1),
        settings=default_settings,
    )
    assert Period.NOW in request.periods


def test_request_period_empty(default_settings):
    # No period (for example in future)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) + dt.timedelta(days=720),
        settings=default_settings,
    )
    assert request.periods == []


@pytest.mark.remote
def test_dwd_observation_data_count_null_values(settings_drop_nulls_false_complete_true):
    """Test for DataFrame having empty values for dates where the station should not
    have values"""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1933-12-27",  # few days before official start
        end_date="1934-01-04",  # few days after official start,
        settings=settings_drop_nulls_false_complete_true,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert given_df.get_column("value").is_null().sum() == 86


@pytest.mark.remote
def test_dwd_observation_data_result_missing_data(settings_drop_nulls_false_complete_true):
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_mean_2m")],
        start_date="2020-06-09 12:00:00",  # no data at this time (reason unknown)
        end_date="2020-06-09 12:00:00",
        settings=settings_drop_nulls_false_complete_true,
    ).filter_by_station_id(
        station_id=["03348"],
    )
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "03348",
                "dataset": "temperature_air",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2020, 6, 9, 12, 0, 0, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            }
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
    assert_frame_equal(
        given_df,
        expected_df,
    )


@pytest.mark.remote
def test_dwd_observation_data_result_all_missing_data(default_settings):
    request = DwdObservationRequest(
        parameters=[DwdObservationMetadata.minute_10.precipitation.precipitation_height],
        start_date=dt.datetime(2021, 10, 4),
        end_date=dt.datetime(2021, 10, 5),
        settings=default_settings,
    ).filter_by_station_id(["05435"])
    given_df = request.values.all().df
    assert given_df.is_empty()


@pytest.mark.remote
def test_dwd_observation_data_result_wide_single_dataset(
    settings_humanize_si_false_wide_shape_drop_nulls_complete,
    dwd_climate_summary_wide_columns,
):
    """Test for actual values (wide)"""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_si_false_wide_shape_drop_nulls_complete,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert given_df.columns == dwd_climate_summary_wide_columns
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"] * 2,
            "dataset": ["climate_summary"] * 2,
            "date": [
                dt.datetime(1933, 12, 31, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "fx": [None, None],
            "qn_fx": [None, None],
            "fm": [None, None],
            "qn_fm": [None, None],
            "rsk": [None, 0.2],
            "qn_rsk": [None, 1.0],
            "rskf": [None, 8.0],
            "qn_rskf": [None, 1.0],
            "sdk": [None, None],
            "qn_sdk": [None, None],
            "shk_tag": [None, 0.0],
            "qn_shk_tag": [None, 1.0],
            "nm": [None, 8.0],
            "qn_nm": [None, 1.0],
            "vpm": [None, 6.4],
            "qn_vpm": [None, 1.0],
            "pm": [None, 1008.60],
            "qn_pm": [None, 1.0],
            "tmk": [None, 0.5],
            "qn_tmk": [None, 1.0],
            "upm": [None, 97.00],
            "qn_upm": [None, 1.0],
            "txk": [None, 0.7],
            "qn_txk": [None, 1.0],
            "tnk": [None, 0.2],
            "qn_tnk": [None, 1.0],
            "tgk": [None, None],
            "qn_tgk": [None, None],
        },
        schema={
            "station_id": pl.String,
            "dataset": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "fx": pl.Float64,
            "qn_fx": pl.Float64,
            "fm": pl.Float64,
            "qn_fm": pl.Float64,
            "rsk": pl.Float64,
            "qn_rsk": pl.Float64,
            "rskf": pl.Float64,
            "qn_rskf": pl.Float64,
            "sdk": pl.Float64,
            "qn_sdk": pl.Float64,
            "shk_tag": pl.Float64,
            "qn_shk_tag": pl.Float64,
            "nm": pl.Float64,
            "qn_nm": pl.Float64,
            "vpm": pl.Float64,
            "qn_vpm": pl.Float64,
            "pm": pl.Float64,
            "qn_pm": pl.Float64,
            "tmk": pl.Float64,
            "qn_tmk": pl.Float64,
            "upm": pl.Float64,
            "qn_upm": pl.Float64,
            "txk": pl.Float64,
            "qn_txk": pl.Float64,
            "tnk": pl.Float64,
            "qn_tnk": pl.Float64,
            "tgk": pl.Float64,
            "qn_tgk": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(
        given_df,
        expected_df,
    )


@pytest.mark.remote
def test_dwd_observation_data_result_wide_single_parameter(
    settings_humanize_si_false_wide_shape_drop_nulls_complete,
):
    """Test for actual values (wide)"""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "precipitation_height")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_si_false_wide_shape_drop_nulls_complete,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert given_df.columns == [
        "station_id",
        "dataset",
        "date",
        "rsk",
        "qn_rsk",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"] * 2,
            "dataset": ["climate_summary"] * 2,
            "date": [
                dt.datetime(1933, 12, 31, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "rsk": [None, 0.2],
            "qn_rsk": [None, 1.0],
        },
        schema={
            "station_id": pl.String,
            "dataset": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "rsk": pl.Float64,
            "qn_rsk": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_result_wide_convert_units(
    settings_humanize_false_wide_shape_drop_nulls_complete,
    dwd_climate_summary_wide_columns,
):
    """Test for actual values (wide) in metric units"""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_false_wide_shape_drop_nulls_complete,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert given_df.columns == dwd_climate_summary_wide_columns
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"] * 2,
            "dataset": ["climate_summary"] * 2,
            "date": [
                dt.datetime(1933, 12, 31, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "fx": [None, None],
            "qn_fx": [None, None],
            "fm": [None, None],
            "qn_fm": [None, None],
            "rsk": [None, 0.2],
            "qn_rsk": [None, 1.0],
            "rskf": [None, 8.0],
            "qn_rskf": [None, 1.0],
            "sdk": [None, None],
            "qn_sdk": [None, None],
            "shk_tag": [None, 0.0],
            "qn_shk_tag": [None, 1.0],
            "nm": [None, 1.0],
            "qn_nm": [None, 1.0],
            "vpm": [None, 6.400],
            "qn_vpm": [None, 1.0],
            "pm": [None, 1008.600],
            "qn_pm": [None, 1.0],
            "tmk": [None, 0.5],
            "qn_tmk": [None, 1.0],
            "upm": [None, 0.9700],
            "qn_upm": [None, 1.0],
            "txk": [None, 0.7],
            "qn_txk": [None, 1.0],
            "tnk": [None, 0.2],
            "qn_tnk": [None, 1.0],
            "tgk": [None, None],
            "qn_tgk": [None, None],
        },
        schema={
            "station_id": pl.String,
            "dataset": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "fx": pl.Float64,
            "qn_fx": pl.Float64,
            "fm": pl.Float64,
            "qn_fm": pl.Float64,
            "rsk": pl.Float64,
            "qn_rsk": pl.Float64,
            "rskf": pl.Float64,
            "qn_rskf": pl.Float64,
            "sdk": pl.Float64,
            "qn_sdk": pl.Float64,
            "shk_tag": pl.Float64,
            "qn_shk_tag": pl.Float64,
            "nm": pl.Float64,
            "qn_nm": pl.Float64,
            "vpm": pl.Float64,
            "qn_vpm": pl.Float64,
            "pm": pl.Float64,
            "qn_pm": pl.Float64,
            "tmk": pl.Float64,
            "qn_tmk": pl.Float64,
            "upm": pl.Float64,
            "qn_upm": pl.Float64,
            "txk": pl.Float64,
            "qn_txk": pl.Float64,
            "tnk": pl.Float64,
            "qn_tnk": pl.Float64,
            "tgk": pl.Float64,
            "qn_tgk": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_result_wide_two_datasets(
    settings_humanize_si_false_wide_shape_drop_nulls_complete,
):
    """Test for actual values (wide)"""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary"), ("daily", "precipitation_more")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_si_false_wide_shape_drop_nulls_complete,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"] * 4,
            "dataset": ["climate_summary"] * 2 + ["precipitation_more"] * 2,
            "date": [
                dt.datetime(1933, 12, 31, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1933, 12, 31, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "climate_summary_fx": [None, None, None, None],
            "qn_climate_summary_fx": [None, None, None, None],
            "climate_summary_fm": [None, None, None, None],
            "qn_climate_summary_fm": [None, None, None, None],
            "climate_summary_rsk": [None, 0.2, None, 0.2],
            "qn_climate_summary_rsk": [None, 1.0, None, 1.0],
            "climate_summary_rskf": [None, 8.0, None, 8.0],
            "qn_climate_summary_rskf": [None, 1.0, None, 1.0],
            "climate_summary_sdk": [None, None, None, None],
            "qn_climate_summary_sdk": [None, None, None, None],
            "climate_summary_shk_tag": [None, 0.0, None, 0.0],
            "qn_climate_summary_shk_tag": [None, 1.0, None, 1.0],
            "climate_summary_nm": [None, 8.0, None, 8.0],
            "qn_climate_summary_nm": [None, 1.0, None, 1.0],
            "climate_summary_vpm": [None, 6.4, None, 6.4],
            "qn_climate_summary_vpm": [None, 1.0, None, 1.0],
            "climate_summary_pm": [None, 1008.6, None, 1008.6],
            "qn_climate_summary_pm": [None, 1.0, None, 1.0],
            "climate_summary_tmk": [None, 0.5, None, 0.5],
            "qn_climate_summary_tmk": [None, 1.0, None, 1.0],
            "climate_summary_upm": [None, 97.0, None, 97.0],
            "qn_climate_summary_upm": [None, 1.0, None, 1.0],
            "climate_summary_txk": [None, 0.7, None, 0.7],
            "qn_climate_summary_txk": [None, 1.0, None, 1.0],
            "climate_summary_tnk": [None, 0.2, None, 0.2],
            "qn_climate_summary_tnk": [None, 1.0, None, 1.0],
            "climate_summary_tgk": [None, None, None, None],
            "qn_climate_summary_tgk": [None, None, None, None],
            "precipitation_more_rs": [0.6, 0.2, 0.6, 0.2],
            "qn_precipitation_more_rs": [1.0, 1.0, 1.0, 1.0],
            "precipitation_more_rsf": [1.0, 8.0, 1.0, 8.0],
            "qn_precipitation_more_rsf": [1.0, 1.0, 1.0, 1.0],
            "precipitation_more_sh_tag": [0.0, 0.0, 0.0, 0.0],
            "qn_precipitation_more_sh_tag": [1.0, 1.0, 1.0, 1.0],
            "precipitation_more_nsh_tag": [None, None, None, None],
            "qn_precipitation_more_nsh_tag": [None, None, None, None],
        },
        schema={
            "station_id": pl.String,
            "dataset": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "climate_summary_fx": pl.Float64,
            "qn_climate_summary_fx": pl.Float64,
            "climate_summary_fm": pl.Float64,
            "qn_climate_summary_fm": pl.Float64,
            "climate_summary_rsk": pl.Float64,
            "qn_climate_summary_rsk": pl.Float64,
            "climate_summary_rskf": pl.Float64,
            "qn_climate_summary_rskf": pl.Float64,
            "climate_summary_sdk": pl.Float64,
            "qn_climate_summary_sdk": pl.Float64,
            "climate_summary_shk_tag": pl.Float64,
            "qn_climate_summary_shk_tag": pl.Float64,
            "climate_summary_nm": pl.Float64,
            "qn_climate_summary_nm": pl.Float64,
            "climate_summary_vpm": pl.Float64,
            "qn_climate_summary_vpm": pl.Float64,
            "climate_summary_pm": pl.Float64,
            "qn_climate_summary_pm": pl.Float64,
            "climate_summary_tmk": pl.Float64,
            "qn_climate_summary_tmk": pl.Float64,
            "climate_summary_upm": pl.Float64,
            "qn_climate_summary_upm": pl.Float64,
            "climate_summary_txk": pl.Float64,
            "qn_climate_summary_txk": pl.Float64,
            "climate_summary_tnk": pl.Float64,
            "qn_climate_summary_tnk": pl.Float64,
            "climate_summary_tgk": pl.Float64,
            "qn_climate_summary_tgk": pl.Float64,
            "precipitation_more_rs": pl.Float64,
            "qn_precipitation_more_rs": pl.Float64,
            "precipitation_more_rsf": pl.Float64,
            "qn_precipitation_more_rsf": pl.Float64,
            "precipitation_more_sh_tag": pl.Float64,
            "qn_precipitation_more_sh_tag": pl.Float64,
            "precipitation_more_nsh_tag": pl.Float64,
            "qn_precipitation_more_nsh_tag": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_result_tidy_convert_units(settings_humanize_false_drop_nulls_false):
    """Test for actual values (format) in metric units"""
    request = DwdObservationRequest(
        parameters=[("daily", "kl")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_false_drop_nulls_false,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    given_df = request.values.all().df
    assert given_df.columns == [
        "station_id",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "fm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "fx",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "nm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "pm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1008.600,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "rsk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.2,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "rskf",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "sdk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "shk_tag",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "tgk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "tmk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.5,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "tnk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.2,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "txk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.7,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "upm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.9700,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "vpm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 6.400,
                "quality": 1.0,
            },
        ],
        schema={
            "station_id": pl.String,
            "dataset": pl.String,
            "parameter": pl.Utf8,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observations_urban_values(default_settings):
    """Test DWD Observation urban stations"""
    request = DwdObservationRequest(
        parameters=[("hourly", "urban_air_temperature")],
        periods="historical",
        start_date="2022-06-01",
        settings=default_settings,
    ).filter_by_station_id("00399")
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        {
            "station_id": ["00399"] * 2,
            "dataset": ["urban_temperature_air"] * 2,
            "parameter": [
                "humidity",
                "temperature_air_mean_2m",
            ],
            "date": [dt.datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC"))] * 2,
            "value": [
                0.83,
                13.4,
            ],
            "quality": [3.0, 3.0],
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
@pytest.mark.parametrize(
    "dataset",
    [
        "urban_pressure",
        "urban_temperature_air",
        "urban_precipitation",
        "urban_temperature_soil",
        "urban_sun",
        "urban_wind",
    ],
)
def test_dwd_observations_urban_values_basic(dataset, default_settings):
    request = DwdObservationRequest(
        parameters=[("hourly", dataset)],
        start_date="2022-01-01",
        end_date="2022-01-31",
        settings=default_settings,
    ).filter_by_name(name="Berlin-Alexanderplatz")
    given_df = request.values.all().df
    assert not given_df.drop_nulls(Columns.VALUE.value).is_empty()


@pytest.mark.remote
def test_dwd_observation_data_10_minutes_result_tidy(settings_humanize_false_convert_units_false):
    """Test for actual values (format) in metric units"""
    request = DwdObservationRequest(
        parameters=[("minute_10", "temperature_air", "pressure_air_site")],
        start_date="1999-12-31 21:00",
        end_date="1999-12-31 22:00",
        settings=settings_humanize_false_convert_units_false,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 00, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 10, tzinfo=ZoneInfo("UTC")),
                "value": 995.9,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 20, tzinfo=ZoneInfo("UTC")),
                "value": 995.9,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 30, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 40, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 50, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 22, 00, tzinfo=ZoneInfo("UTC")),
                "value": 996.1,
                "quality": 1.0,
            },
        ],
        schema={
            "station_id": pl.Utf8,
            "dataset": pl.Utf8,
            "parameter": pl.Utf8,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_monthly_tidy(default_settings):
    """Test for actual values (format) in metric units"""
    request = DwdObservationRequest(
        parameters=[DwdObservationMetadata.monthly.climate_summary.precipitation_height],
        start_date="2020-01-01T00:00:00",
        end_date="2020-12-01T00:00:00",
        settings=default_settings,
    ).filter_by_station_id("00433")
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 34.0,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")),
                "value": 83.2,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 3, 1, tzinfo=ZoneInfo("UTC")),
                "value": 30.3,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 4, 1, tzinfo=ZoneInfo("UTC")),
                "value": 22.7,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 5, 1, tzinfo=ZoneInfo("UTC")),
                "value": 33.3,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 35.8,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 7, 1, tzinfo=ZoneInfo("UTC")),
                "value": 46.8,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 43.2,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 9, 1, tzinfo=ZoneInfo("UTC")),
                "value": 52.8,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 10, 1, tzinfo=ZoneInfo("UTC")),
                "value": 58.2,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 16.4,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 12, 1, tzinfo=ZoneInfo("UTC")),
                "value": 22.1,
                "quality": 9.0,
            },
        ],
        schema={
            "station_id": pl.Utf8,
            "dataset": pl.Utf8,
            "parameter": pl.Utf8,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


def test_create_humanized_column_names_mapping():
    """Test for function to create a mapping to humanized column names"""
    kl_daily_hcnm = {
        "fx": "wind_gust_max",
        "fm": "wind_speed",
        "rsk": "precipitation_height",
        "rskf": "precipitation_form",
        "sdk": "sunshine_duration",
        "shk_tag": "snow_depth",
        "nm": "cloud_cover_total",
        "vpm": "pressure_vapor",
        "pm": "pressure_air_site",
        "tmk": "temperature_air_mean_2m",
        "upm": "humidity",
        "txk": "temperature_air_max_2m",
        "tnk": "temperature_air_min_2m",
        "tgk": "temperature_air_min_0_05m",
    }
    hcnm = (
        DwdObservationRequest(
            [("daily", "kl")],
            ["recent"],
        )
        .filter_by_station_id(
            (0,),
        )
        .values._create_humanized_parameters_mapping()
    )

    assert set(kl_daily_hcnm.items()).issubset(set(hcnm.items()))


@pytest.mark.remote
def test_tidy_up_data(settings_humanize_false_drop_nulls_false):
    """Test for function to format data"""
    request = DwdObservationRequest(
        parameters=[("daily", "kl")],
        periods="historical",
        start_date="2019-01-23 00:00:00",
        settings=settings_humanize_false_drop_nulls_false,
    ).filter_by_station_id(("01048",))
    df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "date": dt.datetime(2019, 1, 23),
                "qn_3": 10,
                "fx": 11.8,
                "fm": 5.8,
                "qn_4": 3,
                "rsk": 0.0,
                "rskf": 0.0,
                "sdk": 7.1,
                "shk_tag": 0.0,
                "nm": 2.3,
                "vpm": 3.2,
                "pm": 975.4,
                "tmk": -5.5,
                "upm": 79.17,
                "txk": -1.7,
                "tnk": -7.9,
                "tgk": -11.4,
            },
        ],
        orient="row",
    )
    given_df = request.values._tidy_up_df(df, DwdObservationMetadata.daily.climate_summary)
    given_df = request.values._organize_df_columns(given_df, "01048", DwdObservationMetadata.daily.climate_summary)
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "fx",
                "date": dt.datetime(2019, 1, 23),
                "value": 11.8,
                "quality": 10,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "fm",
                "date": dt.datetime(2019, 1, 23),
                "value": 5.8,
                "quality": 10,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "rsk",
                "date": dt.datetime(2019, 1, 23),
                "value": 0.0,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "rskf",
                "date": dt.datetime(2019, 1, 23),
                "value": 0.0,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "sdk",
                "date": dt.datetime(2019, 1, 23),
                "value": 7.1,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "shk_tag",
                "date": dt.datetime(2019, 1, 23),
                "value": 0.0,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "nm",
                "date": dt.datetime(2019, 1, 23),
                "value": 2.3,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "vpm",
                "date": dt.datetime(2019, 1, 23),
                "value": 3.2,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "pm",
                "date": dt.datetime(2019, 1, 23),
                "value": 975.4,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "tmk",
                "date": dt.datetime(2019, 1, 23),
                "value": -5.5,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "upm",
                "date": dt.datetime(2019, 1, 23),
                "value": 79.17,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "txk",
                "date": dt.datetime(2019, 1, 23),
                "value": -1.7,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "tnk",
                "date": dt.datetime(2019, 1, 23),
                "value": -7.9,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "tgk",
                "date": dt.datetime(2019, 1, 23),
                "value": -11.4,
                "quality": 3,
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_weather_phenomena(settings_humanize_false_convert_units_false):
    """Test for DWD weather phenomena data, thanks saschnet (https://github.com/saschnet) for providing the sample,
    see also https://github.com/earthobservations/wetterdienst/issues/647
    """
    request = DwdObservationRequest(
        parameters=[("hourly", "weather_phenomena")],
        start_date=dt.datetime(year=2022, month=3, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(year=2022, month=3, day=31, tzinfo=ZoneInfo("UTC")),
        settings=settings_humanize_false_convert_units_false,
    )
    given_df = request.all().df.drop_nulls()
    assert len(given_df) > 0


@pytest.mark.remote
def test_dwd_observation_tidy_empty_df_no_start_end_date(default_settings):
    """Test for DWD observation data with expected empty df for the case that no start and end date is given"""
    request = DwdObservationRequest(
        parameters=[("minute_10", "wind")],
        periods="now",
        settings=default_settings,
    ).filter_by_station_id("01736")
    assert request.values.all().df.is_empty()


@pytest.mark.remote
def test_dwd_observation_not_tidy_empty_df_no_start_end_date(settings_wide_shape):
    """Test for DWD observation data with expected empty df for the case that no start and end date is given"""
    request = DwdObservationRequest(
        parameters=[("minute_10", "wind")],
        periods="now",
        settings=settings_wide_shape,
    ).filter_by_station_id("01736")
    assert request.values.all().df.is_empty()


@pytest.mark.remote
def test_dwd_observation_solar_daily(default_settings):
    """Test DWD observation solar daily data"""
    # Snippet provided by https://github.com/pedroalencar1
    request = DwdObservationRequest(
        parameters=[("daily", "solar")],
        start_date=dt.datetime(1950, 1, 1),
        end_date=dt.datetime(2021, 12, 31),
        settings=default_settings,
    ).filter_by_station_id(station_id=[3987])
    assert not request.values.all().df.get_column("value").drop_nulls().is_empty()


@pytest.mark.remote
def test_dwd_observation_solar_hourly():
    """Test DWD observation solar hourly data"""
    # Snippet provided by @lasinludwig
    settings = Settings(
        ts_shape="long",
        ts_convert_units=False,
        ts_skip_empty=True,
        ts_skip_threshold=0.90,
        ts_skip_criteria="min",
        ts_drop_nulls=True,
    )
    latlon_bremen = 53.0980433, 8.7747248
    # request for radiation
    request = DwdObservationRequest(
        parameters=[("hourly", "solar", "radiation_global")],
        start_date=dt.datetime(2022, 1, 1, 0, 0),
        end_date=dt.datetime(2022, 12, 31, 23, 59),
        settings=settings,
    ).filter_by_distance(latlon_bremen, 500)
    values_df = next(request.values.query()).df
    assert values_df.get_column("value").sum() == 417997.0


@pytest.mark.remote
def test_dwd_observation_data_10_minutes_missing_data(settings_humanize_false_convert_units_false):
    """Test for actual values with correctly dropped -999 values"""
    request = DwdObservationRequest(
        parameters=[("minute_10", "precipitation", "precipitation_height")],
        start_date="1991-01-01 00:00",
        end_date="1992-12-31 23:00",
        settings=settings_humanize_false_convert_units_false,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    df = request.values.all().df
    assert df.filter(pl.col("value").eq(-999)).is_empty()


@pytest.mark.remote
def test_dwd_observation_data_subdaily_wind_extreme_data(default_settings):
    """Test dwd observation subdaily wind extreme values"""
    request = DwdObservationRequest(
        parameters=[("subdaily", "wind_extreme")],
        settings=default_settings,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    df = request.values.all().df
    df = df.drop_nulls("value")
    df = df.sort("parameter").group_by(["parameter"], maintain_order=True).head(1)
    assert df.to_dicts() == [
        {
            "dataset": "wind_extreme",
            "date": dt.datetime(1991, 11, 1, 21, 0, tzinfo=ZoneInfo("UTC")),
            "parameter": "wind_gust_max_last_3h",
            "quality": 1.0,
            "station_id": "01048",
            "value": 14.4,
        },
        {
            "dataset": "wind_extreme",
            "date": dt.datetime(1990, 6, 2, 18, 0, tzinfo=ZoneInfo("UTC")),
            "parameter": "wind_gust_max_last_6h",
            "quality": 1.0,
            "station_id": "01048",
            "value": 6.2,
        },
    ]


@pytest.mark.remote
def test_dwd_observation_data_5minute_precipitation_data_tidy(default_settings):
    request = DwdObservationRequest(
        parameters=[("minute_5", "precipitation", "precipitation_height")],
        start_date="2023-08-25 00:00",
        end_date="2023-08-27 00:00",
        settings=default_settings,
    ).filter_by_rank(
        latlon=(49.853706, 8.66311),
        rank=1,
    )
    values = request.values.all().df
    assert values.get_column("value").sum() == 23.82


@pytest.mark.remote
def test_dwd_observation_data_5minute_precipitation_data_recent(default_settings):
    request = DwdObservationRequest(
        parameters=[
            ("minute_5", "precipitation", "precipitation_height_rocker"),
            ("minute_5", "precipitation", "precipitation_height_droplet"),
        ],
        periods=["recent", "now"],
        settings=default_settings,
    ).filter_by_rank(
        latlon=(49.853706, 8.66311),
        rank=1,
    )
    values = request.values.all().df
    assert values.get_column("value").is_not_null().sum() == 0


@pytest.mark.remote
def test_dwd_observation_data_1minute_precipitation_data_tidy(default_settings):
    request = DwdObservationRequest(
        parameters=[("minute_1", "precipitation", "precipitation_height_droplet")],
        start_date="1990-01-01 00:00",
        end_date="1995-01-01 00:10",
        settings=default_settings,
    ).filter_by_station_id(1048)
    values = request.values.all().df
    assert round(values.get_column("value").sum(), 2) == 2681.8


@pytest.mark.remote
def test_dwd_observation_data_daily_climate_summary_custom_units():
    """Test for custom unit conversion"""
    unit_targets = {
        "temperature": "degree_fahrenheit",
        "fraction": "percent",
        "pressure": "pascal",
        "speed": "kilometer_per_hour",
    }
    request = DwdObservationRequest(
        parameters=[("daily", "kl")],
        start_date="2022-01-01",
        settings=Settings(ts_unit_targets=unit_targets),
    ).filter_by_station_id("1048")
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "cloud_cover_total",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 95.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "humidity",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 78.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "precipitation_form",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "pressure_air_site",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 99560.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "pressure_vapor",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1060.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "snow_depth",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "sunshine_duration",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 53.96,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 52.52,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "temperature_air_min_0_05m",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 37.76,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 43.52,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "wind_gust_max",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 44.28,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "dataset": "climate_summary",
                "parameter": "wind_speed",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 18.36,
                "quality": 10.0,
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
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
@pytest.mark.parametrize(
    "dataset",
    [
        dataset
        for resolution in DwdObservationMetadata
        for dataset in resolution
        if resolution.value in (Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10)
    ],
)
def test_dwd_observation_datasets_high_resolution(default_settings, dataset):
    request = DwdObservationRequest(
        parameters=dataset,
        settings=default_settings,
    ).all()
    df_stations = request.df
    assert not df_stations.drop_nulls().is_empty()
    given_df = next(request.values.query()).df
    assert not given_df.is_empty()
    assert given_df.get_column("quality").is_not_null().mean() >= 0.99


@pytest.mark.remote
@pytest.mark.parametrize(
    "dataset",
    [
        dataset
        for resolution in DwdObservationMetadata
        for dataset in resolution
        if resolution.value not in (Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10)
    ],
)
def test_dwd_observation_datasets_low_resolution(default_settings, dataset):
    request = DwdObservationRequest(
        parameters=dataset,
        settings=default_settings,
    ).all()
    df_stations = request.df
    assert not df_stations.drop_nulls().is_empty()
    given_df = next(request.values.query()).df
    assert not given_df.is_empty()
    assert given_df.get_column("quality").is_not_null().mean() >= 0.99
