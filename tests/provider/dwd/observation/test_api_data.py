# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation metadata."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from freezegun import freeze_time
from polars.testing import assert_frame_equal

from tests.conftest import IS_CI, IS_WINDOWS
from wetterdienst import Resolution, Settings
from wetterdienst.metadata.period import Period
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest, DwdObservationValues
from wetterdienst.provider.dwd.observation.metadata import (
    DwdObservationMetadata,
)


@pytest.fixture
def dwd_climate_summary_wide_columns() -> list[str]:
    """Provide expected columns for climate summary wide DataFrame."""
    return [
        "station_id",
        "resolution",
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
def test_dwd_observation_data_empty(default_settings: Settings) -> None:
    """Test for empty DataFrame."""
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
        # dataset is Enum in aggregated results; cast to String so is_in tolerates values that are
        # absent from the (period="now", possibly empty) result instead of raising on the cast
        given_df.filter(pl.col("dataset").cast(pl.String).is_in(["wind", "temperature_air"]))
        .select(pl.col("value"))
        .drop_nulls()
        .is_empty()
    )


def test_request_period_historical(default_settings: Settings) -> None:
    """Test for historical period."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1971-01-01",
        settings=default_settings,
    )
    assert request.periods == {Period.HISTORICAL}


def test_request_period_historical_recent(default_settings: Settings) -> None:
    """Test for historical and recent period."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1971-01-01",
        end_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=400),
        settings=default_settings,
    )
    assert request.periods == {
        Period.HISTORICAL,
        Period.RECENT,
    }


def test_request_period_historical_recent_now(default_settings: Settings) -> None:
    """Test for historical, recent and now period."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1971-01-01",
        end_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None),
        settings=default_settings,
    )
    assert request.periods == {
        Period.HISTORICAL,
        Period.RECENT,
        Period.NOW,
    }


@freeze_time(dt.datetime(2022, 1, 29, 1, 30, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_recent_now(default_settings: Settings) -> None:
    """Test for recent and now period."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert request.periods == {Period.RECENT, Period.NOW}


@freeze_time(dt.datetime(2022, 1, 29, 2, 30, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_now(default_settings: Settings) -> None:
    """Test for now period."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert request.periods == {Period.NOW}


@freeze_time(dt.datetime(2021, 3, 28, 18, 38, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_now_fixed_date(default_settings: Settings) -> None:
    """Test for now period with fixed date."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert Period.NOW in request.periods


def test_request_period_now_previous_hour(default_settings: Settings) -> None:
    """Test for now period with previous hour."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=1),
        settings=default_settings,
    )
    assert Period.NOW in request.periods


def test_request_period_empty(default_settings: Settings) -> None:
    """Test for empty periods."""
    # No period (for example in future)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) + dt.timedelta(days=720),
        settings=default_settings,
    )
    assert request.periods == set()


@pytest.mark.remote
def test_dwd_observation_data_leaves_out_dates_the_station_did_not_record(settings_drop_nulls_false: Settings) -> None:
    """Test that a request reaching back before a station started returns only what it recorded.

    Station 01048 begins on 1934-01-01 and the request opens five days earlier. Those five days
    used to come back as rows of nulls, spelled out by a grid built from the request; the nulls
    left in the frame are now the station's own -- the parameters it did not measure on days it
    did report.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1933-12-27",  # few days before official start
        end_date="1934-01-04",  # few days after official start,
        settings=settings_drop_nulls_false,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert given_df.get_column("date").min() == dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert given_df.height == 56  # 14 parameters over the 4 recorded days
    assert given_df.get_column("value").is_null().sum() == 16


@pytest.mark.remote
def test_dwd_observation_data_result_missing_data(settings_drop_nulls_false: Settings) -> None:
    """Test that a window the station has no reading for comes back empty rather than as a null.

    Not dropping nulls keeps the nulls a provider reports; it does not invent a row for a
    timestamp nothing was ever recorded at.
    """
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_mean_2m")],
        start_date="2020-06-09 12:00:00",  # no data at this time (reason unknown)
        end_date="2020-06-09 12:00:00",
        settings=settings_drop_nulls_false,
    ).filter_by_station_id(
        station_id=["03348"],
    )

    assert request.values.all().df.is_empty()


@pytest.mark.remote
def test_dwd_observation_data_result_all_missing_data(default_settings: Settings) -> None:
    """Test for DataFrame having empty values for dates where the station should not have values."""
    request = DwdObservationRequest(
        parameters=[DwdObservationMetadata.minute_10.precipitation.precipitation_height],
        start_date=dt.datetime(2021, 10, 4, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 10, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(["05435"])
    given_df = request.values.all().df
    assert given_df.is_empty()


@pytest.mark.remote
def test_dwd_observation_data_result_wide_single_dataset(
    settings_humanize_false_convert_units_false_wide_shape: Settings,
    dwd_climate_summary_wide_columns: list[str],
) -> None:
    """Test for actual values (wide).

    The request opens the day before the station's first, which returns no row of its own -- what
    a station did not record is absent from the frame rather than spelled out as a row of nulls.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_false_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert given_df.columns == dwd_climate_summary_wide_columns
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "date": [dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "fx": [None],
            "qn_fx": [None],
            "fm": [None],
            "qn_fm": [None],
            "rsk": [0.2],
            "qn_rsk": [1.0],
            "rskf": [8.0],
            "qn_rskf": [1.0],
            "sdk": [None],
            "qn_sdk": [None],
            "shk_tag": [0.0],
            "qn_shk_tag": [1.0],
            "nm": [8.0],
            "qn_nm": [1.0],
            "vpm": [6.4],
            "qn_vpm": [1.0],
            "pm": [1008.60],
            "qn_pm": [1.0],
            "tmk": [0.5],
            "qn_tmk": [1.0],
            "upm": [97.00],
            "qn_upm": [1.0],
            "txk": [0.7],
            "qn_txk": [1.0],
            "tnk": [0.2],
            "qn_tnk": [1.0],
            "tgk": [None],
            "qn_tgk": [None],
        },
        schema={
            "station_id": pl.Enum(["01048"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["climate_summary"]),
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
    settings_humanize_false_convert_units_false_wide_shape: Settings,
) -> None:
    """Test for actual values (wide).

    The request opens the day before the station's first, which returns no row of its own -- what
    a station did not record is absent from the frame rather than spelled out as a row of nulls.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "precipitation_height")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_false_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert given_df.columns == [
        "station_id",
        "resolution",
        "dataset",
        "date",
        "rsk",
        "qn_rsk",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "date": [dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "rsk": [0.2],
            "qn_rsk": [1.0],
        },
        schema={
            "station_id": pl.Enum(["01048"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["climate_summary"]),
            "date": pl.Datetime(time_zone="UTC"),
            "rsk": pl.Float64,
            "qn_rsk": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_result_wide_convert_units(
    settings_humanize_false_wide_shape: Settings,
    dwd_climate_summary_wide_columns: list[str],
) -> None:
    """Test for actual values (wide) in metric units.

    The request opens the day before the station's first, which returns no row of its own.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert given_df.columns == dwd_climate_summary_wide_columns
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "date": [dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "fx": [None],
            "qn_fx": [None],
            "fm": [None],
            "qn_fm": [None],
            "rsk": [0.2],
            "qn_rsk": [1.0],
            "rskf": [8.0],
            "qn_rskf": [1.0],
            "sdk": [None],
            "qn_sdk": [None],
            "shk_tag": [0.0],
            "qn_shk_tag": [1.0],
            "nm": [1.0],
            "qn_nm": [1.0],
            "vpm": [6.400],
            "qn_vpm": [1.0],
            "pm": [1008.600],
            "qn_pm": [1.0],
            "tmk": [0.5],
            "qn_tmk": [1.0],
            "upm": [0.9700],
            "qn_upm": [1.0],
            "txk": [0.7],
            "qn_txk": [1.0],
            "tnk": [0.2],
            "qn_tnk": [1.0],
            "tgk": [None],
            "qn_tgk": [None],
        },
        schema={
            "station_id": pl.Enum(["01048"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["climate_summary"]),
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
    settings_humanize_false_convert_units_false_wide_shape: Settings,
) -> None:
    """Test that two datasets at one resolution share a row rather than duplicating it.

    Both datasets are daily, so they have the same timestamps and their columns sit side by side --
    which is what the dataset-name prefix on the columns is for. Keying the row on the dataset too
    used to emit each date twice, once per dataset, and fill both rows with both datasets' values,
    so the `precipitation_more` row reported a `climate_summary` value and the two rows differed
    only in the label. `dataset` is null because no single name describes a row spanning both.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary"), ("daily", "precipitation_more")],
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_false_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"] * 2,
            "resolution": ["daily"] * 2,
            "dataset": [None, None],
            "date": [
                dt.datetime(1933, 12, 31, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "climate_summary_fx": [None, None],
            "qn_climate_summary_fx": [None, None],
            "climate_summary_fm": [None, None],
            "qn_climate_summary_fm": [None, None],
            "climate_summary_rsk": [None, 0.2],
            "qn_climate_summary_rsk": [None, 1.0],
            "climate_summary_rskf": [None, 8.0],
            "qn_climate_summary_rskf": [None, 1.0],
            "climate_summary_sdk": [None, None],
            "qn_climate_summary_sdk": [None, None],
            "climate_summary_shk_tag": [None, 0.0],
            "qn_climate_summary_shk_tag": [None, 1.0],
            "climate_summary_nm": [None, 8.0],
            "qn_climate_summary_nm": [None, 1.0],
            "climate_summary_vpm": [None, 6.4],
            "qn_climate_summary_vpm": [None, 1.0],
            "climate_summary_pm": [None, 1008.6],
            "qn_climate_summary_pm": [None, 1.0],
            "climate_summary_tmk": [None, 0.5],
            "qn_climate_summary_tmk": [None, 1.0],
            "climate_summary_upm": [None, 97.0],
            "qn_climate_summary_upm": [None, 1.0],
            "climate_summary_txk": [None, 0.7],
            "qn_climate_summary_txk": [None, 1.0],
            "climate_summary_tnk": [None, 0.2],
            "qn_climate_summary_tnk": [None, 1.0],
            "climate_summary_tgk": [None, None],
            "qn_climate_summary_tgk": [None, None],
            "precipitation_more_rs": [0.6, 0.2],
            "qn_precipitation_more_rs": [1.0, 1.0],
            "precipitation_more_rsf": [1.0, 8.0],
            "qn_precipitation_more_rsf": [1.0, 1.0],
            "precipitation_more_sh_tag": [0.0, 0.0],
            "qn_precipitation_more_sh_tag": [1.0, 1.0],
            "precipitation_more_nsh_tag": [None, None],
            "qn_precipitation_more_nsh_tag": [None, None],
        },
        schema={
            "station_id": pl.Enum(["01048"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum([]),
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
def test_dwd_observation_data_result_tidy_convert_units(settings_humanize_false_drop_nulls_false: Settings) -> None:
    """Test for actual values (tidy) in metric units."""
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
        "resolution",
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
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "fm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "fx",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "nm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "pm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1008.600,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "rsk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.2,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "rskf",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "sdk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "shk_tag",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "tgk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality": None,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "tmk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.5,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "tnk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.2,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "txk",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.7,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "upm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.9700,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "vpm",
                "date": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 6.400,
                "quality": 1.0,
            },
        ],
        schema={
            "station_id": pl.Enum(["01048"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["climate_summary"]),
            "parameter": pl.Enum(
                ["fm", "fx", "nm", "pm", "rsk", "rskf", "sdk", "shk_tag", "tgk", "tmk", "tnk", "txk", "upm", "vpm"]
            ),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observations_urban_values(default_settings: Settings) -> None:
    """Test DWD Observation urban stations with values."""
    request = DwdObservationRequest(
        parameters=[("hourly", "urban_air_temperature")],
        periods="historical",
        start_date="2022-06-01",
        settings=default_settings,
    ).filter_by_station_id("00399")
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "00399",
                "resolution": "hourly",
                "dataset": "urban_temperature_air",
                "parameter": "humidity",
                "date": dt.datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.83,
                "quality": 3.0,
            },
            {
                "station_id": "00399",
                "resolution": "hourly",
                "dataset": "urban_temperature_air",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 13.4,
                "quality": 3.0,
            },
        ],
        orient="col",
    ).with_columns(
        pl.col("station_id").cast(pl.Enum(["00399"])),
        pl.col("resolution").cast(pl.Enum(["hourly"])),
        pl.col("dataset").cast(pl.Enum(["urban_temperature_air"])),
        pl.col("parameter").cast(pl.Enum(["humidity", "temperature_air_mean_2m"])),
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
def test_dwd_observations_urban_values_basic(default_settings: Settings, dataset: str) -> None:
    """Test DWD Observation urban stations with values."""
    request = DwdObservationRequest(
        parameters=[("hourly", dataset)],
        start_date="2022-01-01",
        end_date="2022-01-31",
        settings=default_settings,
    ).filter_by_name(name="Berlin-Alexanderplatz")
    given_df = request.values.all().df
    assert not given_df.drop_nulls(subset=["value"]).is_empty()


def test_period_precedence_on_overlapping_timestamps(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Where two periods report the same timestamp, the historical record wins.

    The frames are concatenated with `how="align"`, which orders the rows by the columns it aligns
    them on, so deduplicating with `keep="first"` alone takes whichever record sorts first on its
    values -- the lower reading, or a null wherever one period is missing a measurement the other
    has. The read order has to be carried as a rank and sorted on.
    """
    dataset = DwdObservationMetadata.hourly.temperature_air
    frames = {
        # the historical value sorts after the recent one, so a leftover value sort would lose it,
        # and its null at 01:00 would win a value sort it should not
        Period.HISTORICAL: pl.LazyFrame(
            {
                "station_id": ["00011", "00011"],
                "date": [
                    dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                    dt.datetime(2024, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                ],
                "qn": ["3", "3"],
                "tt_tu": ["9.9", None],
            },
        ),
        Period.RECENT: pl.LazyFrame(
            {
                "station_id": ["00011", "00011"],
                "date": [
                    dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                    dt.datetime(2024, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                ],
                "qn": ["1", "1"],
                "tt_tu": ["1.1", "2.2"],
            },
        ),
    }
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *args, **kwargs: pl.Series(["https://example.invalid/file.zip"]),  # noqa: ARG005
    )
    monkeypatch.setattr(dwd_observation_api, "download_climate_observations_data", lambda *args, **kwargs: [object()])  # noqa: ARG005
    monkeypatch.setattr(
        dwd_observation_api,
        "parse_climate_observations_data",
        lambda _files, _dataset, period: frames[period],
    )
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air")],
        periods={"historical", "recent"},
        settings=default_settings,
    )
    stations_result = StationsResult(
        stations=request,
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )
    values = DwdObservationValues.from_stations(stations_result)
    given_df = values._collect_station_parameter_or_dataset("00011", dataset)  # noqa: SLF001
    given_df = given_df.filter(pl.col("parameter") == "tt_tu").sort("date")
    # 9.9 over recent's 1.1 shows the rank decides rather than the value sort, and the null over
    # recent's 2.2 that a missing historical measurement is not quietly filled from a later period.
    # `_tidy_up_df` drops the quality wherever the value is null, hence the None beside it
    assert given_df.get_column("value").to_list() == [9.9, None]
    assert given_df.get_column("quality").to_list() == [3.0, None]


@pytest.mark.remote
def test_dwd_observations_urban_10_minutes_now(default_settings: Settings) -> None:
    """The 10 minute urban `now` period reaches today, not yesterday.

    The urban URL used to be pinned to the `recent` directory whatever the period, so a `now`
    request silently returned `recent` data ending at the previous midnight (GH-1875).
    """
    request = DwdObservationRequest(
        parameters=[("10_minutes", "urban_wind")],
        periods="now",
        settings=default_settings,
    ).filter_by_station_id("00399")
    given_df = request.values.all().df
    assert not given_df.is_empty()
    now = dt.datetime.now(ZoneInfo("UTC"))
    # `now` holds the current day only, while `recent` reaches 500 days back -- the span is what
    # tells the two apart at any hour of the day, where the newest timestamp alone would not
    assert given_df.get_column("date").min() >= now - dt.timedelta(days=2)
    assert given_df.get_column("date").max() >= now - dt.timedelta(days=2)


@pytest.mark.remote
def test_dwd_observations_urban_10_minutes_historical(default_settings: Settings) -> None:
    """The 10 minute urban `historical` period reaches back beyond what `recent` covers (GH-1875)."""
    request = DwdObservationRequest(
        parameters=[("10_minutes", "urban_wind", "wind_direction")],
        periods="historical",
        start_date="2016-01-01",
        end_date="2016-01-02",
        settings=default_settings,
    ).filter_by_station_id("00399")
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "00399",
                "resolution": "10_minutes",
                "dataset": "urban_wind",
                "parameter": "wind_direction",
                "date": dt.datetime(2016, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 230.0,
                "quality": 3.0,
            },
        ],
        orient="row",
    ).with_columns(
        pl.col("station_id").cast(pl.Enum(["00399"])),
        pl.col("resolution").cast(pl.Enum(["10_minutes"])),
        pl.col("dataset").cast(pl.Enum(["urban_wind"])),
        pl.col("parameter").cast(pl.Enum(["wind_direction"])),
    )
    assert_frame_equal(given_df.head(1), expected_df)


@pytest.mark.remote
def test_dwd_observation_data_10_minutes_result_tidy(settings_humanize_false_convert_units_false: Settings) -> None:
    """Test for actual values (format) in metric units."""
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
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 00, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 10, tzinfo=ZoneInfo("UTC")),
                "value": 995.9,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 20, tzinfo=ZoneInfo("UTC")),
                "value": 995.9,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 30, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 40, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 21, 50, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality": 1.0,
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "date": dt.datetime(1999, 12, 31, 22, 00, tzinfo=ZoneInfo("UTC")),
                "value": 996.1,
                "quality": 1.0,
            },
        ],
        schema={
            "station_id": pl.Enum(["01048"]),
            "resolution": pl.Enum(["10_minutes"]),
            "dataset": pl.Enum(["temperature_air"]),
            "parameter": pl.Enum(["pp_10"]),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_monthly_tidy(default_settings: Settings) -> None:
    """Test for actual values (format) in metric units."""
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
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 34.0,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")),
                "value": 83.2,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 3, 1, tzinfo=ZoneInfo("UTC")),
                "value": 30.3,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 4, 1, tzinfo=ZoneInfo("UTC")),
                "value": 22.7,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 5, 1, tzinfo=ZoneInfo("UTC")),
                "value": 33.3,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 35.8,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 7, 1, tzinfo=ZoneInfo("UTC")),
                "value": 46.8,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 43.2,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 9, 1, tzinfo=ZoneInfo("UTC")),
                "value": 52.8,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 10, 1, tzinfo=ZoneInfo("UTC")),
                "value": 58.2,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 16.4,
                "quality": 9.0,
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2020, 12, 1, tzinfo=ZoneInfo("UTC")),
                "value": 22.1,
                "quality": 9.0,
            },
        ],
        schema={
            "station_id": pl.Enum(["00433"]),
            "resolution": pl.Enum(["monthly"]),
            "dataset": pl.Enum(["climate_summary"]),
            "parameter": pl.Enum(["precipitation_height"]),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


def test_create_humanized_column_names_mapping() -> None:
    """Test create humanized column names mapping."""
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
        DwdObservationRequest(  # noqa: SLF001
            parameters=[("daily", "kl")],
            periods={"recent"},
        )
        .filter_by_station_id(
            (0,),
        )
        .values._create_humanized_parameters_mapping()
    )

    assert set(kl_daily_hcnm.items()).issubset(set(hcnm.items()))


@pytest.mark.remote
def test_tidy_up_data(settings_humanize_false_drop_nulls_false: Settings) -> None:
    """Test tidy up data."""
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
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
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
    given_df = request.values._tidy_up_df(df)  # noqa: SLF001
    given_df = given_df.select(
        [
            "station_id",
            "parameter",
            "date",
            "value",
            "quality",
        ],
    )
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "parameter": "fx",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 11.8,
                "quality": 10,
            },
            {
                "station_id": "01048",
                "parameter": "fm",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 5.8,
                "quality": 10,
            },
            {
                "station_id": "01048",
                "parameter": "rsk",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "rskf",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "sdk",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 7.1,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "shk_tag",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "nm",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 2.3,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "vpm",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 3.2,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "pm",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 975.4,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "tmk",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": -5.5,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "upm",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 79.17,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "txk",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": -1.7,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "tnk",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": -7.9,
                "quality": 3,
            },
            {
                "station_id": "01048",
                "parameter": "tgk",
                "date": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": -11.4,
                "quality": 3,
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_weather_phenomena(settings_humanize_false_convert_units_false: Settings) -> None:
    """Test for DWD weather phenomena data.

    Thanks, @saschnet, for providing the sample!
    See also https://github.com/earthobservations/wetterdienst/issues/647.
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
def test_dwd_observation_tidy_empty_df_no_start_end_date(default_settings: Settings) -> None:
    """Test for DWD observation data with expected empty df for the case that no start and end date is given."""
    request = DwdObservationRequest(
        parameters=[("minute_10", "wind")],
        periods="now",
        settings=default_settings,
    ).filter_by_station_id("01736")
    assert request.values.all().df.is_empty()


@pytest.mark.remote
def test_dwd_observation_not_tidy_empty_df_no_start_end_date(settings_wide_shape: Settings) -> None:
    """Test for DWD observation data with expected empty df for the case that no start and end date is given."""
    request = DwdObservationRequest(
        parameters=[("minute_10", "wind")],
        periods="now",
        settings=settings_wide_shape,
    ).filter_by_station_id("01736")
    assert request.values.all().df.is_empty()


@pytest.mark.remote
def test_dwd_observation_solar_daily(default_settings: Settings) -> None:
    """Test DWD observation solar daily data.

    Thanks, @pedroalencar1, for providing the snippet.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "solar")],
        start_date=dt.datetime(1950, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 12, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(station_id=[3987])
    assert not request.values.all().df.get_column("value").drop_nulls().is_empty()


@pytest.mark.remote
def test_dwd_observation_solar_hourly(settings_convert_units_false: Settings) -> None:
    """Test DWD observation solar hourly data.

    Thanks, @lasinludwig, for providing the snippet.
    """
    latlon_bremen = 53.0980433, 8.7747248
    # request for radiation
    request = DwdObservationRequest(
        parameters=[("hourly", "solar", "radiation_global")],
        start_date=dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 12, 31, 23, 59, tzinfo=ZoneInfo("UTC")),
        settings=settings_convert_units_false,
    ).filter_by_distance(latlon_bremen, 500)
    values_df = next(request.values.query()).df
    assert values_df.get_column("value").sum() == 417914.0


@pytest.mark.remote
def test_dwd_observation_solar_hourly_timestamps_off(default_settings: Settings) -> None:
    """Test DWD observation solar hourly data with timestamps off by one minute.

    This is to test the rounding of timestamps to the nearest hour.

    Thanks, @nkiessling, for reporting the issue.
    """
    request = DwdObservationRequest(
        parameters=[("hourly", "solar", "radiation_global")],
        start_date=dt.datetime(2024, 12, 8, 0, 0, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2024, 12, 8, 23, 0, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(station_id="03987")
    values_df = next(request.values.query()).df
    assert len(values_df) == 24
    assert values_df.get_column("value").sum() == 46.0


@pytest.mark.remote
def test_dwd_observation_data_10_minutes_missing_data(settings_humanize_false_convert_units_false: Settings) -> None:
    """Test for actual values with correctly dropped -999 values."""
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
def test_dwd_observation_data_subdaily_wind_extreme_data(default_settings: Settings) -> None:
    """Test for DWD observation subdaily wind extreme data."""
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
            "station_id": "01048",
            "resolution": "subdaily",
            "dataset": "wind_extreme",
            "parameter": "wind_gust_max_last_3h",
            "date": dt.datetime(1991, 11, 1, 21, 0, tzinfo=ZoneInfo("UTC")),
            "value": 14.4,
            "quality": 1.0,
        },
        {
            "station_id": "01048",
            "resolution": "subdaily",
            "dataset": "wind_extreme",
            "parameter": "wind_gust_max_last_6h",
            "date": dt.datetime(1990, 6, 2, 18, 0, tzinfo=ZoneInfo("UTC")),
            "value": 6.2,
            "quality": 1.0,
        },
    ]


@pytest.mark.remote
def test_dwd_observation_data_5minute_precipitation_data(default_settings: Settings) -> None:
    """Test for DWD observation 5 minute precipitation data."""
    request = DwdObservationRequest(
        parameters=[("minute_5", "precipitation", "precipitation_height")],
        start_date="2023-08-25 00:00",
        end_date="2023-08-27 00:00",
        settings=default_settings,
    ).filter_by_station_id(station_id="01048")
    values = request.values.all().df
    assert round(values.get_column("value").sum(), 2) == 4.35


@pytest.mark.remote
def test_dwd_observation_data_5minute_precipitation_data_recent(default_settings: Settings) -> None:
    """Test for DWD observation 5 minute precipitation data with recent and now periods. This is actually missing."""
    request = DwdObservationRequest(
        parameters=[
            ("minute_5", "precipitation", "precipitation_height_rocker"),
            ("minute_5", "precipitation", "precipitation_height_droplet"),
        ],
        periods={"recent", "now"},
        settings=default_settings,
    ).filter_by_station_id(station_id="01048")
    values = request.values.all().df
    assert values.is_empty()


@pytest.mark.remote
def test_dwd_observation_data_1minute_precipitation_data_tidy(default_settings: Settings) -> None:
    """Test for DWD observation 1 minute precipitation data."""
    request = DwdObservationRequest(
        parameters=[("minute_1", "precipitation", "precipitation_height_droplet")],
        start_date="1990-01-01 00:00",
        end_date="1995-01-01 00:10",
        settings=default_settings,
    ).filter_by_station_id(1048)
    values = request.values.all().df
    assert round(values.get_column("value").sum(), 2) == 2681.8


@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "parameter"),
    [
        ("visibility", "visibility_range_measurement_method"),
        ("cloudiness", "cloud_cover_total_measurement_method"),
        ("cloud_type", "cloud_cover_total_measurement_method"),
    ],
)
def test_dwd_observation_measurement_method_indicators(
    default_settings: Settings,
    dataset: str,
    parameter: str,
) -> None:
    """Test that the letter-coded measurement method indicators reach the result.

    DWD writes these as `P` and `I`, which the Float64 value column cannot hold, so both were
    declared but dropped and a request for them returned an empty frame. They are decoded to 1 and
    2 respectively on the way in.
    """
    request = DwdObservationRequest(
        parameters=[("hourly", dataset, parameter)],
        periods="recent",
        settings=default_settings,
    ).filter_by_station_id("00096")
    values = request.values.all().df
    assert not values.is_empty()
    assert values.get_column("parameter").unique().to_list() == [parameter]
    assert set(values.get_column("value").drop_nulls().unique()) <= {1.0, 2.0}


@pytest.mark.remote
def test_dwd_observation_true_local_time_offset(settings_convert_units_false: Settings) -> None:
    """Test that the true local time offset carries the seasonal solar correction.

    The offset is the longitude correction plus the equation of time, so it has to *move* over the
    year -- a value that came out constant would mean the correction had been rounded away, which
    is exactly what happens to it in the timestamp.
    """

    def offsets(month: int) -> list[float]:
        request = DwdObservationRequest(
            parameters=[("hourly", "solar", "true_local_time_offset")],
            start_date=dt.datetime(2023, month, 10, 0, 0, tzinfo=ZoneInfo("UTC")),
            end_date=dt.datetime(2023, month, 10, 6, 0, tzinfo=ZoneInfo("UTC")),
            settings=settings_convert_units_false,
        ).filter_by_station_id("00183")
        return request.values.all().df.get_column("value").to_list()

    february, november = offsets(2), offsets(11)
    assert february
    assert november
    # the equation of time is near its minimum in February and its maximum in November, roughly
    # half an hour apart, about this station's ~55 minute longitude term
    assert max(february) < min(november)
    assert min(november) - max(february) > 20
    assert all(0 < offset < 120 for offset in february + november)


@pytest.mark.remote
def test_dwd_observation_data_daily_climate_summary_custom_units() -> None:
    """Test for custom unit conversion."""
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
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "cloud_cover_total",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 95.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "humidity",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 78.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "precipitation_form",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "precipitation_height",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "pressure_air_site",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 99560.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "pressure_vapor",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1060.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "snow_depth",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "sunshine_duration",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 53.96,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 52.52,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_min_0_05m",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 37.76,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 43.52,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "wind_gust_max",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 44.28,
                "quality": 10.0,
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "wind_speed",
                "date": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 18.36,
                "quality": 10.0,
            },
        ],
        schema={
            "station_id": pl.Enum(["01048"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["climate_summary"]),
            "parameter": pl.Enum(
                [
                    "cloud_cover_total",
                    "humidity",
                    "precipitation_form",
                    "precipitation_height",
                    "pressure_air_site",
                    "pressure_vapor",
                    "snow_depth",
                    "sunshine_duration",
                    "temperature_air_max_2m",
                    "temperature_air_mean_2m",
                    "temperature_air_min_0_05m",
                    "temperature_air_min_2m",
                    "wind_gust_max",
                    "wind_speed",
                ]
            ),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.skipif(IS_CI and IS_WINDOWS, reason="container crashes on Windows CI")
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
def test_dwd_observation_datasets_high_resolution(default_settings: Settings, dataset: DatasetModel) -> None:
    """Test for DWD observation data with high resolution."""
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
        # DwdObservationMetadata.subdaily.wind_extreme
        dataset
        for resolution in DwdObservationMetadata
        for dataset in resolution
        if resolution.value not in (Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10)
    ],
)
def test_dwd_observation_datasets_low_resolution(default_settings: Settings, dataset: DatasetModel) -> None:
    """Test for DWD observation data with low resolution."""
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
def test_dwd_observation_annual_climate_indices(default_settings: Settings) -> None:
    """Test DWD observation annual climate indices, counted over a closed historical year."""
    request = DwdObservationRequest(
        parameters=[("annual", "climate_indices")],
        periods=[Period.HISTORICAL],
        start_date=dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(1990, 12, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(station_id=["00003"])
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            ("00003", "annual", "climate_indices", "count_days_frost", 26.0),
            ("00003", "annual", "climate_indices", "count_days_hot", 6.0),
            ("00003", "annual", "climate_indices", "count_days_ice", 3.0),
            ("00003", "annual", "climate_indices", "count_days_summer", 31.0),
            ("00003", "annual", "climate_indices", "count_days_tropical_night", 1.0),
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "value": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(
        given_df.select("station_id", "resolution", "dataset", "parameter", "value"),
        expected_df,
        check_dtypes=False,
    )
    assert given_df.get_column("date").unique().to_list() == [dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC"))]
    assert given_df.get_column("quality").unique().to_list() == [10.0]


@pytest.mark.remote
def test_dwd_observation_monthly_precipitation_indices(default_settings: Settings) -> None:
    """Test DWD observation monthly precipitation indices, counted over a closed historical month.

    The thresholds are cumulative -- a day of 10 mm is counted by every threshold up to it -- so the
    counts have to fall monotonically as the threshold rises.
    """
    request = DwdObservationRequest(
        parameters=[("monthly", "precipitation_indices")],
        periods=[Period.HISTORICAL],
        start_date=dt.datetime(1990, 7, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(1990, 7, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(station_id=["00003"])
    given_df = request.values.all().df
    given = dict(given_df.select("parameter", "value").iter_rows())
    assert given == {
        "count_days_precipitation_height_ge_0_1mm": 10.0,
        "count_days_precipitation_height_ge_1mm": 7.0,
        "count_days_precipitation_height_ge_2_5mm": 4.0,
        "count_days_precipitation_height_ge_5mm": 2.0,
        "count_days_precipitation_height_ge_10mm": 1.0,
        "count_days_precipitation_height_ge_20mm": 0.0,
        "count_days_snow_depth_ge_1cm": 0.0,
        "count_days_snow_depth_ge_5cm": 0.0,
    }
    assert given_df.get_column("date").unique().to_list() == [dt.datetime(1990, 7, 1, tzinfo=ZoneInfo("UTC"))]
