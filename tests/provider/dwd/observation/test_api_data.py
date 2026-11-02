# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation metadata."""

import datetime as dt
import logging
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from freezegun import freeze_time
from polars.testing import assert_frame_equal

from tests.conftest import IS_CI, IS_WINDOWS
from tests.provider.value_stubs import STUBS, stations_result
from wetterdienst import Options, Resolution, Settings
from wetterdienst.metadata.period import Period
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.values import shape_provider_frame
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest, DwdObservationValues
from wetterdienst.provider.dwd.observation.metadata import (
    DwdObservationMetadata,
)
from wetterdienst.util.network import File


@pytest.fixture
def dwd_climate_summary_wide_columns() -> list[str]:
    """Provide expected columns for climate summary wide DataFrame."""
    return [
        "station_id",
        "resolution",
        "dataset",
        "timestamp",
        "fx",
        "fx_quality_flags",
        "fm",
        "fm_quality_flags",
        "rsk",
        "rsk_quality_flags",
        "rskf",
        "rskf_quality_flags",
        "sdk",
        "sdk_quality_flags",
        "shk_tag",
        "shk_tag_quality_flags",
        "nm",
        "nm_quality_flags",
        "vpm",
        "vpm_quality_flags",
        "pm",
        "pm_quality_flags",
        "tmk",
        "tmk_quality_flags",
        "upm",
        "upm_quality_flags",
        "txk",
        "txk_quality_flags",
        "tnk",
        "tnk_quality_flags",
        "tgk",
        "tgk_quality_flags",
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
    given_df = request.values().all().df
    assert given_df.select(pl.col("station_id")).to_series().unique().to_list() == ["02011"]
    assert (
        # is_in over names that may be absent from the (period="now", possibly empty) result
        given_df.filter(pl.col("dataset").is_in(["wind", "temperature_air"]))
        .select(pl.col("value"))
        .drop_nulls()
        .is_empty()
    )


def test_request_period_historical(default_settings: Settings) -> None:
    """Test for historical period."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start="1971-01-01",
        settings=default_settings,
    )
    assert request.periods == {Period.HISTORICAL}


def test_request_period_historical_recent(default_settings: Settings) -> None:
    """Test for historical and recent period."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start="1971-01-01",
        end=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=400),
        settings=default_settings,
    )
    assert request.periods == {
        Period.HISTORICAL,
        Period.RECENT,
    }


def test_request_period_historical_recent_now(default_settings: Settings) -> None:
    """Test for historical, recent and now period.

    `10_minutes/temperature_air` rather than `daily/climate_summary` because the periods derived
    from an interval are checked against the ones the dataset publishes, and climate_summary has
    no `now` release -- see `test_request_period_now_narrows_to_what_the_dataset_publishes`.
    """
    request = DwdObservationRequest(
        parameters=[("10_minutes", "temperature_air")],
        start="1971-01-01",
        end=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None),
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
        parameters=[("10_minutes", "temperature_air")],
        start=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert request.periods == {Period.RECENT, Period.NOW}


@freeze_time(dt.datetime(2022, 1, 29, 2, 30, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_now(default_settings: Settings) -> None:
    """Test for now period."""
    request = DwdObservationRequest(
        parameters=[("10_minutes", "temperature_air")],
        start=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert request.periods == {Period.NOW}


@freeze_time(dt.datetime(2021, 3, 28, 18, 38, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_now_fixed_date(default_settings: Settings) -> None:
    """Test for now period with fixed date."""
    request = DwdObservationRequest(
        parameters=[("10_minutes", "temperature_air")],
        start=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert Period.NOW in request.periods


def test_request_period_now_previous_hour(default_settings: Settings) -> None:
    """Test for now period with previous hour."""
    request = DwdObservationRequest(
        parameters=[("10_minutes", "temperature_air")],
        start=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=1),
        settings=default_settings,
    )
    assert Period.NOW in request.periods


@freeze_time(dt.datetime(2022, 1, 29, 2, 30, tzinfo=ZoneInfo("Europe/Berlin")))
def test_request_period_now_narrows_to_what_the_dataset_publishes(default_settings: Settings) -> None:
    """An interval reaching into today reads the newest release the dataset actually has.

    `daily/climate_summary` is published as historical and recent only. The derived `now` used to
    stand, so the request carried a period the dataset has no release for and read no station index
    at all -- `.all()` reported no stations, where asking for `periods="now"` outright raises for
    the same datasets.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=2),
        settings=default_settings,
    )
    assert request.periods == {Period.RECENT}


def test_request_period_empty(default_settings: Settings) -> None:
    """Test for empty periods.

    An interval reaching no release at all has nothing to read and nothing to fall back to, so it
    stays empty rather than being widened to the dataset's newest release.
    """
    # No period (for example in future)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) + dt.timedelta(days=720),
        settings=default_settings,
    )
    assert request.periods == set()


@pytest.mark.remote
def test_dwd_observation_data_leaves_out_dates_the_station_did_not_record(options_drop_nulls_false: Options) -> None:
    """Test that a request reaching back before a station started returns only what it recorded.

    Station 01048 begins on 1934-01-01 and the request opens five days earlier. Those five days
    used to come back as rows of nulls, spelled out by a grid built from the request; the nulls
    left in the frame are now the station's own -- the parameters it did not measure on days it
    did report.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start="1933-12-27",  # few days before official start
        end="1934-01-04",  # few days after official start,
        options=options_drop_nulls_false,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values().all().df
    assert given_df.get_column("timestamp").min() == dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert given_df.height == 56  # 14 parameters over the 4 recorded days
    assert given_df.get_column("value").is_null().sum() == 16


@pytest.mark.remote
def test_dwd_observation_data_result_missing_data(options_drop_nulls_false: Options) -> None:
    """Test that a window the station has no reading for comes back empty rather than as a null.

    Not dropping nulls keeps the nulls a provider reports; it does not invent a row for a
    timestamp nothing was ever recorded at.
    """
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_2m")],
        start="2020-06-09 12:00:00",  # no data at this time (reason unknown)
        end="2020-06-09 12:00:00",
        options=options_drop_nulls_false,
    ).filter_by_station_id(
        station_id=["03348"],
    )

    assert request.values().all().df.is_empty()


@pytest.mark.remote
def test_dwd_observation_data_result_all_missing_data(default_settings: Settings) -> None:
    """Test for DataFrame having empty values for dates where the station should not have values."""
    request = DwdObservationRequest(
        parameters=[DwdObservationMetadata.minute_10.precipitation.precipitation_amount],
        start=dt.datetime(2021, 10, 4, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2021, 10, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(["05435"])
    given_df = request.values().all().df
    assert given_df.is_empty()


@pytest.mark.remote
def test_dwd_observation_data_result_wide_single_dataset(
    options_humanize_false_convert_units_false_wide_shape: Options,
    dwd_climate_summary_wide_columns: list[str],
) -> None:
    """Test for actual values (wide).

    The request opens the day before the station's first, which returns no row of its own -- what
    a station did not record is absent from the frame rather than spelled out as a row of nulls.

    The `quality_flags` column of a null value carries the text the file wrote for it as its last
    token: `raw:-999` where the file writes -999 for the quality byte too, `1,raw:-999` where it
    has one.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start="1933-12-31",  # few days before official start
        end="1934-01-01",  # few days after official start,
        options=options_humanize_false_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values().all().df
    assert given_df.columns == dwd_climate_summary_wide_columns
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "timestamp": [dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "fx": [None],
            "fx_quality_flags": ["raw:-999"],
            "fm": [None],
            "fm_quality_flags": ["raw:-999"],
            "rsk": [0.2],
            "rsk_quality_flags": ["1"],
            "rskf": [8.0],
            "rskf_quality_flags": ["1"],
            "sdk": [None],
            "sdk_quality_flags": ["1,raw:-999"],
            "shk_tag": [0.0],
            "shk_tag_quality_flags": ["1"],
            "nm": [8.0],
            "nm_quality_flags": ["1"],
            "vpm": [6.4],
            "vpm_quality_flags": ["1"],
            "pm": [1008.60],
            "pm_quality_flags": ["1"],
            "tmk": [0.5],
            "tmk_quality_flags": ["1"],
            "upm": [97.00],
            "upm_quality_flags": ["1"],
            "txk": [0.7],
            "txk_quality_flags": ["1"],
            "tnk": [0.2],
            "tnk_quality_flags": ["1"],
            "tgk": [None],
            "tgk_quality_flags": ["1,raw:-999"],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "fx": pl.Float64,
            "fx_quality_flags": pl.String,
            "fm": pl.Float64,
            "fm_quality_flags": pl.String,
            "rsk": pl.Float64,
            "rsk_quality_flags": pl.String,
            "rskf": pl.Float64,
            "rskf_quality_flags": pl.String,
            "sdk": pl.Float64,
            "sdk_quality_flags": pl.String,
            "shk_tag": pl.Float64,
            "shk_tag_quality_flags": pl.String,
            "nm": pl.Float64,
            "nm_quality_flags": pl.String,
            "vpm": pl.Float64,
            "vpm_quality_flags": pl.String,
            "pm": pl.Float64,
            "pm_quality_flags": pl.String,
            "tmk": pl.Float64,
            "tmk_quality_flags": pl.String,
            "upm": pl.Float64,
            "upm_quality_flags": pl.String,
            "txk": pl.Float64,
            "txk_quality_flags": pl.String,
            "tnk": pl.Float64,
            "tnk_quality_flags": pl.String,
            "tgk": pl.Float64,
            "tgk_quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(
        given_df,
        expected_df,
    )


@pytest.mark.remote
def test_dwd_observation_data_result_wide_single_parameter(
    options_humanize_false_convert_units_false_wide_shape: Options,
) -> None:
    """Test for actual values (wide).

    The request opens the day before the station's first, which returns no row of its own -- what
    a station did not record is absent from the frame rather than spelled out as a row of nulls.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "precipitation_amount")],
        start="1933-12-31",  # few days before official start
        end="1934-01-01",  # few days after official start,
        options=options_humanize_false_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values().all().df
    assert given_df.columns == [
        "station_id",
        "resolution",
        "dataset",
        "timestamp",
        "rsk",
        "rsk_quality_flags",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "timestamp": [dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "rsk": [0.2],
            "rsk_quality_flags": ["1"],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "rsk": pl.Float64,
            "rsk_quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_result_wide_convert_units(
    options_humanize_false_wide_shape: Options,
    dwd_climate_summary_wide_columns: list[str],
) -> None:
    """Test for actual values (wide) in metric units.

    The request opens the day before the station's first, which returns no row of its own.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start="1933-12-31",  # few days before official start
        end="1934-01-01",  # few days after official start,
        options=options_humanize_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values().all().df
    assert given_df.columns == dwd_climate_summary_wide_columns
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "timestamp": [dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "fx": [None],
            "fx_quality_flags": ["raw:-999"],
            "fm": [None],
            "fm_quality_flags": ["raw:-999"],
            "rsk": [0.2],
            "rsk_quality_flags": ["1"],
            "rskf": [8.0],
            "rskf_quality_flags": ["1"],
            "sdk": [None],
            "sdk_quality_flags": ["1,raw:-999"],
            "shk_tag": [0.0],
            "shk_tag_quality_flags": ["1"],
            "nm": [1.0],
            "nm_quality_flags": ["1"],
            "vpm": [6.400],
            "vpm_quality_flags": ["1"],
            "pm": [1008.600],
            "pm_quality_flags": ["1"],
            "tmk": [0.5],
            "tmk_quality_flags": ["1"],
            "upm": [0.9700],
            "upm_quality_flags": ["1"],
            "txk": [0.7],
            "txk_quality_flags": ["1"],
            "tnk": [0.2],
            "tnk_quality_flags": ["1"],
            "tgk": [None],
            "tgk_quality_flags": ["1,raw:-999"],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "fx": pl.Float64,
            "fx_quality_flags": pl.String,
            "fm": pl.Float64,
            "fm_quality_flags": pl.String,
            "rsk": pl.Float64,
            "rsk_quality_flags": pl.String,
            "rskf": pl.Float64,
            "rskf_quality_flags": pl.String,
            "sdk": pl.Float64,
            "sdk_quality_flags": pl.String,
            "shk_tag": pl.Float64,
            "shk_tag_quality_flags": pl.String,
            "nm": pl.Float64,
            "nm_quality_flags": pl.String,
            "vpm": pl.Float64,
            "vpm_quality_flags": pl.String,
            "pm": pl.Float64,
            "pm_quality_flags": pl.String,
            "tmk": pl.Float64,
            "tmk_quality_flags": pl.String,
            "upm": pl.Float64,
            "upm_quality_flags": pl.String,
            "txk": pl.Float64,
            "txk_quality_flags": pl.String,
            "tnk": pl.Float64,
            "tnk_quality_flags": pl.String,
            "tgk": pl.Float64,
            "tgk_quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_result_wide_two_datasets(
    options_humanize_false_convert_units_false_wide_shape: Options,
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
        start="1933-12-31",  # few days before official start
        end="1934-01-01",  # few days after official start,
        options=options_humanize_false_convert_units_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values().all().df
    expected_df = pl.DataFrame(
        {
            "station_id": ["01048"] * 2,
            "resolution": ["daily"] * 2,
            "dataset": [None, None],
            "timestamp": [
                dt.datetime(1933, 12, 31, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "climate_summary_fx": [None, None],
            "climate_summary_fx_quality_flags": [None, "raw:-999"],
            "climate_summary_fm": [None, None],
            "climate_summary_fm_quality_flags": [None, "raw:-999"],
            "climate_summary_rsk": [None, 0.2],
            "climate_summary_rsk_quality_flags": [None, "1"],
            "climate_summary_rskf": [None, 8.0],
            "climate_summary_rskf_quality_flags": [None, "1"],
            "climate_summary_sdk": [None, None],
            "climate_summary_sdk_quality_flags": [None, "1,raw:-999"],
            "climate_summary_shk_tag": [None, 0.0],
            "climate_summary_shk_tag_quality_flags": [None, "1"],
            "climate_summary_nm": [None, 8.0],
            "climate_summary_nm_quality_flags": [None, "1"],
            "climate_summary_vpm": [None, 6.4],
            "climate_summary_vpm_quality_flags": [None, "1"],
            "climate_summary_pm": [None, 1008.6],
            "climate_summary_pm_quality_flags": [None, "1"],
            "climate_summary_tmk": [None, 0.5],
            "climate_summary_tmk_quality_flags": [None, "1"],
            "climate_summary_upm": [None, 97.0],
            "climate_summary_upm_quality_flags": [None, "1"],
            "climate_summary_txk": [None, 0.7],
            "climate_summary_txk_quality_flags": [None, "1"],
            "climate_summary_tnk": [None, 0.2],
            "climate_summary_tnk_quality_flags": [None, "1"],
            "climate_summary_tgk": [None, None],
            "climate_summary_tgk_quality_flags": [None, "1,raw:-999"],
            "precipitation_more_rs": [0.6, 0.2],
            "precipitation_more_rs_quality_flags": ["1", "1"],
            "precipitation_more_rsf": [1.0, 8.0],
            "precipitation_more_rsf_quality_flags": ["1", "1"],
            "precipitation_more_sh_tag": [0.0, 0.0],
            "precipitation_more_sh_tag_quality_flags": ["1", "1"],
            "precipitation_more_nsh_tag": [None, None],
            "precipitation_more_nsh_tag_quality_flags": ["1,raw:-999", "1,raw:-999"],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "climate_summary_fx": pl.Float64,
            "climate_summary_fx_quality_flags": pl.String,
            "climate_summary_fm": pl.Float64,
            "climate_summary_fm_quality_flags": pl.String,
            "climate_summary_rsk": pl.Float64,
            "climate_summary_rsk_quality_flags": pl.String,
            "climate_summary_rskf": pl.Float64,
            "climate_summary_rskf_quality_flags": pl.String,
            "climate_summary_sdk": pl.Float64,
            "climate_summary_sdk_quality_flags": pl.String,
            "climate_summary_shk_tag": pl.Float64,
            "climate_summary_shk_tag_quality_flags": pl.String,
            "climate_summary_nm": pl.Float64,
            "climate_summary_nm_quality_flags": pl.String,
            "climate_summary_vpm": pl.Float64,
            "climate_summary_vpm_quality_flags": pl.String,
            "climate_summary_pm": pl.Float64,
            "climate_summary_pm_quality_flags": pl.String,
            "climate_summary_tmk": pl.Float64,
            "climate_summary_tmk_quality_flags": pl.String,
            "climate_summary_upm": pl.Float64,
            "climate_summary_upm_quality_flags": pl.String,
            "climate_summary_txk": pl.Float64,
            "climate_summary_txk_quality_flags": pl.String,
            "climate_summary_tnk": pl.Float64,
            "climate_summary_tnk_quality_flags": pl.String,
            "climate_summary_tgk": pl.Float64,
            "climate_summary_tgk_quality_flags": pl.String,
            "precipitation_more_rs": pl.Float64,
            "precipitation_more_rs_quality_flags": pl.String,
            "precipitation_more_rsf": pl.Float64,
            "precipitation_more_rsf_quality_flags": pl.String,
            "precipitation_more_sh_tag": pl.Float64,
            "precipitation_more_sh_tag_quality_flags": pl.String,
            "precipitation_more_nsh_tag": pl.Float64,
            "precipitation_more_nsh_tag_quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_result_tidy_convert_units(options_humanize_false_drop_nulls_false: Options) -> None:
    """Test for actual values (tidy) in metric units.

    The nulls stay (`drop_nulls=False`) and each carries the text the file wrote for it as the last
    `quality_flags` token: `raw:-999`, after the quality byte where the file has one (`1,raw:-999`);
    a file that writes -999 for the quality byte too leaves `raw:-999` alone.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "kl")],
        start="1933-12-31",  # few days before official start
        end="1934-01-01",  # few days after official start,
        options=options_humanize_false_drop_nulls_false,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    given_df = request.values().all().df
    assert given_df.columns == [
        "station_id",
        "resolution",
        "dataset",
        "parameter",
        "timestamp",
        "value",
        "quality_flags",
    ]
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "fm",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality_flags": "raw:-999",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "fx",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality_flags": "raw:-999",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "nm",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "pm",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 1008.600,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "rsk",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.2,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "rskf",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.0,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "sdk",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality_flags": "1,raw:-999",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "shk_tag",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "tgk",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": None,
                "quality_flags": "1,raw:-999",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "tmk",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.5,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "tnk",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.2,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "txk",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.7,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "upm",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.9700,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "vpm",
                "timestamp": dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 6.400,
                "quality_flags": "1",
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
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
        # a datetime is the instant: a date alone is the whole day, 24 hours of both parameters (GH-3133)
        start=dt.datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id("00399")
    given_df = request.values().all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "00399",
                "resolution": "hourly",
                "dataset": "urban_temperature_air",
                "parameter": "humidity_relative",
                "timestamp": dt.datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 0.83,
                "quality_flags": "3",
            },
            {
                "station_id": "00399",
                "resolution": "hourly",
                "dataset": "urban_temperature_air",
                "parameter": "temperature_air_2m",
                "timestamp": dt.datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 13.4,
                "quality_flags": "3",
            },
        ],
        orient="col",
    ).with_columns(
        pl.col("station_id"),
        pl.col("quality_flags").cast(pl.String),
        pl.col("resolution"),
        pl.col("dataset"),
        pl.col("parameter"),
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
        start="2022-01-01",
        end="2022-01-31",
        settings=default_settings,
    ).filter_by_name(name="Berlin-Alexanderplatz")
    given_df = request.values().all().df
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
                "timestamp": [
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
                "timestamp": [
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
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda *args, **kwargs: [File(url="https://example.invalid/file.zip", content=BytesIO(), status=200)],  # noqa: ARG005
    )
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
        request=request,
        df=pl.DataFrame(),
        _df_all=pl.DataFrame(),
        _stations_filter=StationsFilter.ALL,
    )
    values = DwdObservationValues.from_stations(stations_result)
    given_df = values._collect_station_parameter_or_dataset("00011", dataset)  # noqa: SLF001
    # the provider hands over the text of the file, which the core reads as the number it writes
    given_df = shape_provider_frame(given_df, station_id="00011", dataset=dataset)
    given_df = given_df.filter(pl.col("parameter") == "tt_tu").sort("timestamp")
    # 9.9 over recent's 1.1 shows the rank decides rather than the value sort, and the null over
    # recent's 2.2 that a missing historical measurement is not quietly filled from a later period.
    # `_tidy_up_df` drops the quality flags wherever the value is null, hence the None beside it
    assert given_df.get_column("value").to_list() == [9.9, None]
    assert given_df.get_column("quality_flags").to_list() == ["3", None]


def test_a_value_that_is_no_number_is_null_and_counted_not_an_error(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The provider hands over the text of a cell, and the core reads it: one that is no number is null (GH-2627).

    The provider cast the value to Float64 itself and strictly, so a cell that is no number (and no sentinel, which
    the parser has mapped to null) raised and lost the whole station. The core does the cast now, leniently, and
    counts the cells it could not read in one debug line. The parser decodes the letters DWD writes in the files
    (`V_N_I`, `V_VV_I`) and drops the text columns (`WW_Text`), so no file of the recent directories of the
    observations and the urban climate that were read on 2026-10-20 (two stations of each dataset) reaches the cast
    with a cell that is none, and what a reader sees changes only for a file DWD writes differently one day.
    """
    dataset = DwdObservationMetadata.hourly.temperature_air
    frame = pl.LazyFrame(
        {
            "station_id": ["00011", "00011"],
            "timestamp": [
                dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
                dt.datetime(2024, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "qn": ["3", "3"],
            "tt_tu": ["9.9", "n/a"],
        },
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *args, **kwargs: pl.Series(["https://example.invalid/file.zip"]),  # noqa: ARG005
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda *args, **kwargs: [File(url="https://example.invalid/file.zip", content=BytesIO(), status=200)],  # noqa: ARG005
    )
    monkeypatch.setattr(dwd_observation_api, "parse_climate_observations_data", lambda *_args: frame)
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air")],
        periods={"recent"},
        settings=default_settings,
    )
    result = StationsResult(
        request=request,
        df=pl.DataFrame(),
        _df_all=pl.DataFrame(),
        _stations_filter=StationsFilter.ALL,
    )
    handed_over = DwdObservationValues.from_stations(result)._collect_station_parameter_or_dataset("00011", dataset)  # noqa: SLF001
    assert handed_over["value"].dtype == pl.String
    with caplog.at_level(logging.DEBUG, logger="wetterdienst.model.values"):
        df = shape_provider_frame(handed_over, station_id="00011", dataset=dataset, provider="DwdObservationValues")
    assert df["value"].dtype == pl.Float64
    assert df.sort("timestamp")["value"].to_list() == [9.9, None]
    assert [record.getMessage() for record in caplog.records if "no number" in record.getMessage()] == [
        "DwdObservationValues: 1 of 2 value cells are no number and are null"
    ]


def _serve_historical_files(monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> None:
    """Serve the historical product files of one station, by the name of their zip, from the test."""
    monkeypatch.setattr(DwdObservationValues, "_get_historical_date_ranges", lambda *_, **__: None)
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *_, **__: pl.Series([f"https://example.invalid/{name}" for name in files]),
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda *_, **__: [
            File(url=f"https://example.invalid/{name}", content=BytesIO(product.encode("latin-1")), status=200)
            for name, product in files.items()
        ],
    )


def _seam_values(resolution: str, dataset: str, parameter: str, station_id: str, settings: Settings) -> pl.DataFrame:
    """Give the values of one parameter around the turn of the year 2000 of the files served."""
    request = DwdObservationRequest(
        parameters=[(resolution, dataset, parameter)],
        periods={Period.HISTORICAL},
        start=dt.datetime(1999, 12, 31, 20, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2000, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
        settings=settings,
        options=Options(drop_nulls=False),
    )
    return stations_result(request, resolution, dataset, station_id).values().all().df.sort("timestamp")


@pytest.mark.parametrize("reverse", [False, True])
def test_dwd_10_minutes_historical_files_meet_at_the_year_2000_without_loss(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, *, reverse: bool
) -> None:
    """Test that the UTC stamps 1999-12-31 23:00 to 23:50 of the 2000 file are not dropped as MEZ ones (GH-2815).

    The file that ends in 1999 stamps in MEZ (last stamp 199912312350 = 22:50 UTC) and the one of 2000 in UTC,
    beginning with 199912312300: both hold the same digits, which are not the same instants. Station 01048,
    read 2026-10-13: -0.7 degC at 23:50 MEZ, -0.8 degC at 23:00 UTC.
    """
    before = (
        "STATIONS_ID;MESS_DATUM;QN;PP_10;TT_10;TM5_10;RF_10;TD_10\n"
        "       1048;199912312330;    1;  996.2;  -0.6;  -2.3;  92.0;  -1.8\n"
        "       1048;199912312340;    1;  996.3;  -0.6;  -2.2;  92.0;  -1.8\n"
        "       1048;199912312350;    1;  996.4;  -0.7;  -2.7;  92.0;  -1.8\n"
    )
    after = "STATIONS_ID;MESS_DATUM;  QN;PP_10;TT_10;TM5_10;RF_10;TD_10;eor\n" + "".join(
        f"       1048;{stamp};    1;  996.4;  {value};  -1.4;  94.0;  -1.7;eor\n"
        for stamp, value in [
            ("199912312300", "-0.8"),
            ("199912312310", "-0.8"),
            ("199912312320", "-0.8"),
            ("199912312330", "-0.8"),
            ("199912312340", "-0.9"),
            ("199912312350", "-0.9"),
            ("200001010000", "-1.0"),
        ]
    )
    files = {
        "10minutenwerte_TU_01048_19911119_19991231_hist.zip": before,
        "10minutenwerte_TU_01048_20000101_20091231_hist.zip": after,
    }
    if reverse:
        files = dict(reversed(files.items()))
    _serve_historical_files(monkeypatch, files)
    df = _seam_values("10_minutes", "air_temperature", "temperature_air_2m", "01048", default_settings)
    assert df.get_column("timestamp").to_list() == [
        dt.datetime(1999, 12, 31, h, m, tzinfo=ZoneInfo("UTC")) for h, m in [(22, 30), (22, 40), (22, 50)]
    ] + [dt.datetime(1999, 12, 31, 23, m, tzinfo=ZoneInfo("UTC")) for m in range(0, 60, 10)] + [
        dt.datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC"))
    ]
    assert df.get_column("value").to_list() == [-0.6, -0.6, -0.7, -0.8, -0.8, -0.8, -0.8, -0.9, -0.9, -1.0]


@pytest.mark.parametrize("reverse", [False, True])
def test_dwd_10_minutes_historical_wind_stamps_of_1999_file_beyond_midnight_are_mez(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, *, reverse: bool
) -> None:
    """Test that the stamps 2000-01-01 00:00 to 00:50 in the MEZ file of 1999 are told from the UTC ones (GH-2815).

    The wind file of 1999 goes on into 2000 in MEZ (station 01048, read 2026-10-13: 200001010000 reads 2.4 m/s there
    and 199912312300 in the 2000 file reads the same 2.4, that is the instant 23:00 UTC; the UTC 00:00 reads 3.4).
    The year of the stamp took the former as UTC and had it compete with the latter for 00:00 UTC.
    """
    before = (
        "STATIONS_ID;MESS_DATUM;  QN;FF_10;DD_10;eor\n"
        "       1048;199912312350;    1;   2.7; 170;eor\n"
        "       1048;200001010000;    1;   2.4; 170;eor\n"
        "       1048;200001010010;    1;   2.5; 170;eor\n"
    )
    after = (
        "STATIONS_ID;MESS_DATUM;  QN;FF_10;DD_10;eor\n"
        "       1048;199912312300;    1;   2.4; 170;eor\n"
        "       1048;199912312310;    1;   2.5; 170;eor\n"
        "       1048;200001010000;    1;   3.4; 160;eor\n"
    )
    files = {
        "10minutenwerte_wind_01048_19911122_19991231_hist.zip": before,
        "10minutenwerte_wind_01048_20000101_20091231_hist.zip": after,
    }
    if reverse:
        files = dict(reversed(files.items()))
    _serve_historical_files(monkeypatch, files)
    df = _seam_values("10_minutes", "wind", "wind_speed_mean", "01048", default_settings)
    assert df.get_column("timestamp").to_list() == [
        dt.datetime(1999, 12, 31, 22, 50, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1999, 12, 31, 23, 0, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1999, 12, 31, 23, 10, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")),
    ]
    assert df.get_column("value").to_list() == [2.7, 2.4, 2.5, 3.4]


@pytest.mark.parametrize("reverse", [False, True])
def test_dwd_10_minutes_historical_stamps_listed_twice_keep_the_row_that_is_not_a_copy(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, *, reverse: bool
) -> None:
    """Test that of a stamp the 1999 file lists twice, the copy of the 2000 file's row is dropped (GH-2829).

    Station 00963, read 2026-10-15: the file of 1999 lists 199912312300 to 199912312350 twice. One row of each is
    the reading at 23:xx MEZ, the other the one at 00:xx MEZ on 2000-01-01 that the 2000 file holds as 199912312300
    to 199912312350 UTC. The 1-minute file of December 1999 has rain at 00:19 and 00:46 MEZ of 2000-01-01, which
    the 10 minute stamps 00:20 and 00:50 carry (0.1 mm) and no row of 23:xx MEZ does. The copy comes first at 23:20
    and second at 23:50, so neither the first nor the last row can be kept; at 23:40 the two rows are the same.
    A stamp listed twice elsewhere (22:40 MEZ here, a placeholder first, as in the file of station 03086) is settled
    on the row that has a value (GH-2996).
    """
    before = (
        "STATIONS_ID;MESS_DATUM;  QN;RWS_DAU_10;RWS_10;RWS_IND_10\n"
        "        963;199912312240;    1;-999;   -999;\n"
        "        963;199912312240;    1;-999;   0.00; 0\n"
        "        963;199912312250;    1;-999;   0.00; 0\n"
        "        963;199912312300;    1;-999;   0.00; 3\n"
        "        963;199912312300;    1;-999;   0.00; 0\n"
        "        963;199912312310;    1;-999;   0.00; 3\n"
        "        963;199912312310;    1;-999;   0.00; 0\n"
        "        963;199912312320;    1;-999;   0.10; 1\n"
        "        963;199912312320;    1;-999;   0.00; 0\n"
        "        963;199912312330;    1;-999;   0.00; 3\n"
        "        963;199912312330;    1;-999;   0.00; 0\n"
        "        963;199912312340;    1;-999;   0.00; 3\n"
        "        963;199912312340;    1;-999;   0.00; 3\n"
        "        963;199912312350;    1;-999;   0.00; 3\n"
        "        963;199912312350;    1;-999;   0.10; 1\n"
    )
    after = (
        "STATIONS_ID;MESS_DATUM;  QN;RWS_DAU_10;RWS_10;RWS_IND_10;eor\n"
        "        963;199912312300;    1;-999;   0.00;   3;eor\n"
        "        963;199912312310;    1;-999;   0.00;   3;eor\n"
        "        963;199912312320;    1;-999;   0.10;   1;eor\n"
        "        963;199912312330;    1;-999;   0.00;   3;eor\n"
        "        963;199912312340;    1;-999;   0.00;   3;eor\n"
        "        963;199912312350;    1;-999;   0.10;   1;eor\n"
        "        963;200001010000;    1;-999;   0.00;   1;eor\n"
    )
    files = {
        "10minutenwerte_nieder_00963_19960613_19991231_hist.zip": before,
        "10minutenwerte_nieder_00963_20000101_20091231_hist.zip": after,
    }
    if reverse:
        files = dict(reversed(files.items()))
    _serve_historical_files(monkeypatch, files)
    amount = _seam_values("10_minutes", "precipitation", "precipitation_amount", "00963", default_settings)
    index = _seam_values("10_minutes", "precipitation", "precipitation_index", "00963", default_settings)
    # 21:50 UTC is the stamp 22:50 MEZ, 22:00 to 22:50 UTC the readings of 23:00 to 23:50 MEZ, 23:00 to 23:50 UTC
    # those of the 2000 file (00:00 to 00:50 MEZ)
    expected_timestamps = [
        dt.datetime(1999, 12, 31, 21, 40, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1999, 12, 31, 21, 50, tzinfo=ZoneInfo("UTC")),
        *[dt.datetime(1999, 12, 31, h, m, tzinfo=ZoneInfo("UTC")) for h in (22, 23) for m in range(0, 60, 10)],
        dt.datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")),
    ]
    assert amount.get_column("timestamp").to_list() == expected_timestamps
    assert index.get_column("timestamp").to_list() == expected_timestamps
    assert amount.get_column("value").to_list() == [0.0] * 10 + [0.1, 0.0, 0.0, 0.1, 0.0]
    assert index.get_column("value").to_list() == [0.0] * 6 + [3.0] * 4 + [1.0, 3.0, 3.0, 1.0, 1.0]


@pytest.mark.parametrize("with_recent", [False, True])
def test_dwd_10_minutes_historical_stamp_listed_twice_with_a_placeholder_keeps_the_row_with_a_value(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, *, with_recent: bool
) -> None:
    """Test that a placeholder row, whichever comes first, loses to the row of its stamp that has a value (GH-2996).

    The file of station 03086 for 1996 to 1999 (read 2026-10-15, 182,928 rows) lists every stamp from 199908041000
    to 199912312350 twice: one row is the reading, the other a placeholder with `-999` in RWS_10 and an empty
    RWS_IND_10. The reading comes first at 920 of the 1002 stamps, the placeholder at 74 and the 8 others hold two
    readings or two placeholders. The first row was kept, so the 74 lost their value; with a second period the rows
    are ordered by their values before the first is taken, and about 1000 did.
    """
    historical = (
        "STATIONS_ID;MESS_DATUM;  QN;RWS_DAU_10;RWS_10;RWS_IND_10\n"
        "        3086;199908040950;    1;-999;   0.00; 0\n"
        "        3086;199908041000;    1;-999;   0.00; 0\n"
        "        3086;199908041000;    1;-999;   -999;\n"
        "        3086;199908041010;    1;-999;   -999;\n"
        "        3086;199908041010;    1;-999;   0.20; 1\n"
        "        3086;199908041020;    1;-999;   -999;\n"
        "        3086;199908041020;    1;-999;   -999;\n"
        "        3086;199908041030;    1;-999;   0.00; 0\n"
        "        3086;199908041030;    1;-999;   0.00; 0\n"
    )
    recent = (
        "STATIONS_ID;MESS_DATUM;  QN;RWS_DAU_10;RWS_10;RWS_IND_10;eor\n"
        "        3086;202610010000;    3;   10;   0.10;   1;eor\n"
    )
    files = {"10minutenwerte_nieder_03086_19960701_19991231_hist.zip": historical}
    if with_recent:
        files["10minutenwerte_nieder_03086_akt.zip"] = recent
    monkeypatch.setattr(DwdObservationValues, "_get_historical_date_ranges", lambda *_, **__: None)
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda _station, _dataset, period, *_, **__: pl.Series(
            [name for name in files if period == (Period.RECENT if "akt" in name else Period.HISTORICAL)],
            dtype=pl.String,
        ),
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda remote_files, *_, **__: [
            File(url=f"https://example.invalid/{name}", content=BytesIO(files[name].encode("latin-1")), status=200)
            for name in remote_files
        ],
    )
    request = DwdObservationRequest(
        parameters=[("10_minutes", "precipitation", "precipitation_amount")],
        periods={Period.HISTORICAL, Period.RECENT} if with_recent else {Period.HISTORICAL},
        start=dt.datetime(1999, 8, 4, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1999, 8, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
        options=Options(drop_nulls=False),
    )
    df = stations_result(request, "10_minutes", "precipitation", "03086").values().all().df.sort("timestamp")
    # 08:50 to 09:30 UTC are the stamps 09:50 to 10:30 MEZ
    assert df.get_column("timestamp").to_list() == [
        dt.datetime(1999, 8, 4, 8, 50, tzinfo=ZoneInfo("UTC")),
        *[dt.datetime(1999, 8, 4, 9, minute, tzinfo=ZoneInfo("UTC")) for minute in (0, 10, 20, 30)],
    ]
    # a lone reading, the reading first (09:00), the placeholder first (09:10), two placeholders (09:20, no value),
    # two readings (09:30)
    assert df.get_column("value").to_list() == [0.0, 0.0, 0.2, None, 0.0]


def test_dwd_5_minutes_historical_row_after_the_last_day_of_the_december_1999_file_is_dropped(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the row 200001010000 of the December 1999 file is no reading at 23:00 UTC (GH-2827).

    Station 03811, read 2026-10-15: the file begins with 200001010000 and has no 199912312355; its RS_IND_05 is 0,
    that of the January file at 200001010000 UTC is 2, and the 1-minute indicator is 2 at 00:00 UTC and 0 at 23:56
    to 23:59 UTC. So the row is the 00:00 UTC one made of the four minutes the file has, not the missing 23:55 MEZ,
    and the January file holds it whole.
    """
    before = (
        "STATIONS_ID;MESS_DATUM;QN_5min;RS_IND_05;RS_05;RTH_05;RWH_05;eor\n"
        "       3811;200001010000;    3;   0;   -999;   0.00;   0.00;eor\n"
        "       3811;199912312345;    3;   2;   -999;   0.00;   0.00;eor\n"
        "       3811;199912312350;    3;   2;   -999;   0.00;   0.00;eor\n"
    )
    after = (
        "STATIONS_ID;MESS_DATUM;QN_5min;RS_IND_05;RS_05;RTH_05;RWH_05;eor\n"
        "       3811;200001010000;    3;   2;   -999;   0.00;   0.00;eor\n"
        "       3811;200001010005;    3;   2;   -999;   0.00;   0.00;eor\n"
    )
    _serve_historical_files(
        monkeypatch,
        {
            "5minutenwerte_nieder_03811_20000101_20000131_hist.zip": after,
            "5minutenwerte_nieder_03811_19991201_19991231_hist.zip": before,
        },
    )
    df = _seam_values("5_minutes", "precipitation", "precipitation_index", "03811", default_settings)
    assert df.get_column("timestamp").to_list() == [
        dt.datetime(1999, 12, 31, 22, 45, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1999, 12, 31, 22, 50, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2000, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2000, 1, 1, 0, 5, tzinfo=ZoneInfo("UTC")),
    ]
    assert df.get_column("value").to_list() == [2.0, 2.0, 2.0, 2.0]


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
    given_df = request.values().all().df
    assert not given_df.is_empty()
    now = dt.datetime.now(ZoneInfo("UTC"))
    # `now` holds the current day only, while `recent` reaches 500 days back -- the span is what
    # tells the two apart at any hour of the day, where the newest timestamp alone would not
    assert given_df.get_column("timestamp").min() >= now - dt.timedelta(days=2)
    assert given_df.get_column("timestamp").max() >= now - dt.timedelta(days=2)


@pytest.mark.remote
def test_dwd_observations_urban_10_minutes_historical(default_settings: Settings) -> None:
    """The 10 minute urban `historical` period reaches back beyond what `recent` covers (GH-1875)."""
    request = DwdObservationRequest(
        parameters=[("10_minutes", "urban_wind", "wind_direction_mean")],
        periods="historical",
        start="2016-01-01",
        end="2016-01-02",
        settings=default_settings,
    ).filter_by_station_id("00399")
    given_df = request.values().all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "00399",
                "resolution": "10_minutes",
                "dataset": "urban_wind",
                "parameter": "wind_direction_mean",
                "timestamp": dt.datetime(2016, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 230.0,
                "quality_flags": "3",
            },
        ],
        orient="row",
    ).with_columns(
        pl.col("station_id"),
        pl.col("quality_flags").cast(pl.String),
        pl.col("resolution"),
        pl.col("dataset"),
        pl.col("parameter"),
    )
    assert_frame_equal(given_df.head(1), expected_df)


@pytest.mark.remote
def test_dwd_observations_urban_10_minutes_sunshine_duration_is_hours(default_settings: Settings) -> None:
    """The urban 10 minute sunshine duration is in hours: a 10 minute interval holds at most 600 s (GH-2698).

    DWD's parameter sheet says "Minute", the values of station 00399 are 0.00 to 0.17 (10/60 rounded), which
    in seconds are 0 to 612. Read as minutes they would be at most 10.2 s.
    """
    request = DwdObservationRequest(
        parameters=[("10_minutes", "urban_solar", "sunshine_duration")],
        periods="recent",
        settings=default_settings,
    ).filter_by_station_id("00399")
    values = request.values().all().df.get_column("value")
    assert 300 < values.max() <= 612.0


@pytest.mark.remote
def test_dwd_observation_data_10_minutes_result_tidy(options_humanize_false_convert_units_false: Options) -> None:
    """Test for actual values (format) in metric units."""
    request = DwdObservationRequest(
        parameters=[("minute_10", "temperature_air", "pressure_air_site")],
        start="1999-12-31 21:00",
        end="1999-12-31 22:00",
        options=options_humanize_false_convert_units_false,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    given_df = request.values().all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "timestamp": dt.datetime(1999, 12, 31, 21, 00, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "timestamp": dt.datetime(1999, 12, 31, 21, 10, tzinfo=ZoneInfo("UTC")),
                "value": 995.9,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "timestamp": dt.datetime(1999, 12, 31, 21, 20, tzinfo=ZoneInfo("UTC")),
                "value": 995.9,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "timestamp": dt.datetime(1999, 12, 31, 21, 30, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "timestamp": dt.datetime(1999, 12, 31, 21, 40, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "timestamp": dt.datetime(1999, 12, 31, 21, 50, tzinfo=ZoneInfo("UTC")),
                "value": 996.0,
                "quality_flags": "1",
            },
            {
                "station_id": "01048",
                "resolution": "10_minutes",
                "dataset": "temperature_air",
                "parameter": "pp_10",
                "timestamp": dt.datetime(1999, 12, 31, 22, 00, tzinfo=ZoneInfo("UTC")),
                "value": 996.1,
                "quality_flags": "1",
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_data_monthly_tidy(default_settings: Settings) -> None:
    """Test for actual values (format) in metric units."""
    request = DwdObservationRequest(
        parameters=[DwdObservationMetadata.monthly.climate_summary.precipitation_amount],
        start="2020-01-01T00:00:00",
        end="2020-12-01T00:00:00",
        settings=default_settings,
    ).filter_by_station_id("00433")
    given_df = request.values().all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                "value": 34.0,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")),
                "value": 83.2,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 3, 1, tzinfo=ZoneInfo("UTC")),
                "value": 30.3,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 4, 1, tzinfo=ZoneInfo("UTC")),
                "value": 22.7,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 5, 1, tzinfo=ZoneInfo("UTC")),
                "value": 33.3,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 35.8,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 7, 1, tzinfo=ZoneInfo("UTC")),
                "value": 46.8,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 43.2,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 9, 1, tzinfo=ZoneInfo("UTC")),
                "value": 52.8,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 10, 1, tzinfo=ZoneInfo("UTC")),
                "value": 58.2,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 16.4,
                "quality_flags": "9",
            },
            {
                "station_id": "00433",
                "resolution": "monthly",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2020, 12, 1, tzinfo=ZoneInfo("UTC")),
                "value": 22.1,
                "quality_flags": "9",
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


def test_create_humanized_column_names_mapping() -> None:
    """Test create humanized column names mapping."""
    kl_daily_hcnm = {
        "fx": "wind_gust_max",
        "fm": "wind_speed_mean",
        "rsk": "precipitation_amount",
        "rskf": "precipitation_form",
        "sdk": "sunshine_duration",
        "shk_tag": "snow_depth",
        "nm": "cloud_cover_total_mean",
        "vpm": "pressure_vapor_mean",
        "pm": "pressure_air_site_mean",
        "tmk": "temperature_air_mean_2m",
        "upm": "humidity_relative_mean",
        "txk": "temperature_air_max_2m",
        "tnk": "temperature_air_min_2m",
        "tgk": "temperature_air_min_0_05m",
    }
    # the mapping is read off the request's metadata, so the values object is built from an empty
    # station frame rather than through `filter_by_station_id`, which would download the station
    # index to answer a question about names
    request = DwdObservationRequest(
        parameters=[("daily", "kl")],
        periods={"recent"},
    )
    stations_result = StationsResult(
        request=request,
        df=pl.DataFrame(),
        _df_all=pl.DataFrame(),
        _stations_filter=StationsFilter.ALL,
    )
    hcnm = DwdObservationValues.from_stations(stations_result)._create_humanized_parameters_mapping()  # noqa: SLF001

    # per resolution and dataset (GH-3605): the rows of daily/climate_summary hold the names above
    daily = hcnm.filter(pl.col("resolution").eq("daily"), pl.col("dataset").eq("climate_summary"))
    assert set(kl_daily_hcnm.items()).issubset(set(zip(daily["parameter"], daily["humanized"], strict=True)))


@pytest.mark.remote
def test_tidy_up_data(options_humanize_false_drop_nulls_false: Options) -> None:
    """Test tidy up data."""
    request = DwdObservationRequest(
        parameters=[("daily", "kl")],
        periods="historical",
        start="2019-01-23 00:00:00",
        options=options_humanize_false_drop_nulls_false,
    ).filter_by_station_id(("01048",))
    df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
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
    given_df = request.values()._tidy_up_df(df)  # noqa: SLF001
    given_df = given_df.select(
        [
            "station_id",
            "parameter",
            "timestamp",
            "value",
            "quality_flags",
        ],
    )
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "parameter": "fx",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 11.8,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "parameter": "fm",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 5.8,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "parameter": "rsk",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "rskf",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "sdk",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 7.1,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "shk_tag",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 0.0,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "nm",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 2.3,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "vpm",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 3.2,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "pm",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 975.4,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "tmk",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": -5.5,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "upm",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 79.17,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "txk",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": -1.7,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "tnk",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": -7.9,
                "quality_flags": "3",
            },
            {
                "station_id": "01048",
                "parameter": "tgk",
                "timestamp": dt.datetime(2019, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": -11.4,
                "quality_flags": "3",
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


def test_dwd_observation_weather_phenomena_returns_both_code_tables_as_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the hourly `weather` is DWD's code as written, from the 0-99 table and from the 100-199 one alike.

    DWD publishes the present weather in one column that holds two tables with disjoint numbers (21 and 61 of the
    WMO `ww` table, 123 and 100 of the second one), and `Wetter_Beschreibung.txt` gives the text of every code of
    both. Station 01048 reports from both within five hours of 2022-08-01 (read from its historical file on
    2026-10-15). Neither is translated into the other and `WW_Text`, which is the table's text for the code beside
    it, is not returned; -1, "Wetter wurde nicht gemeldet", is the only row without a weather (GH-2718, GH-2670).
    """
    stub = next(stub for stub in STUBS if stub.provider == "dwd/observation hourly/weather_phenomena")
    df = stub.build(monkeypatch, drop_nulls=False)
    assert df.get_column("parameter").unique().to_list() == ["weather"]
    assert df.sort("timestamp").get_column("value").to_list() == [None, 21.0, 61.0, 123.0, 100.0]
    # the -1 row keeps the text DWD wrote beside the null it was mapped to
    assert df.sort("timestamp").get_column("quality_flags").to_list() == ["3,raw:-1", "3", "3", "3", "3"]


@pytest.mark.remote
def test_dwd_observation_weather_phenomena(options_humanize_false_convert_units_false: Options) -> None:
    """Test for DWD weather phenomena data.

    Thanks, @saschnet, for providing the sample!
    See also https://github.com/earthobservations/wetterdienst/issues/647.
    """
    request = DwdObservationRequest(
        parameters=[("hourly", "weather_phenomena")],
        start=dt.datetime(year=2022, month=3, day=1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(year=2022, month=3, day=31, tzinfo=ZoneInfo("UTC")),
        options=options_humanize_false_convert_units_false,
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
    assert request.values().all().df.is_empty()


@pytest.mark.remote
def test_dwd_observation_not_tidy_empty_df_no_start_end_date(options_wide_shape: Options) -> None:
    """Test for DWD observation data with expected empty df for the case that no start and end date is given."""
    request = DwdObservationRequest(
        parameters=[("minute_10", "wind")],
        periods="now",
        options=options_wide_shape,
    ).filter_by_station_id("01736")
    assert request.values().all().df.is_empty()


@pytest.mark.remote
def test_dwd_observation_solar_daily(default_settings: Settings) -> None:
    """Test DWD observation solar daily data.

    Thanks, @pedroalencar1, for providing the snippet.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "solar")],
        start=dt.datetime(1950, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2021, 12, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(station_id=[3987])
    assert not request.values().all().df.get_column("value").drop_nulls().is_empty()


@pytest.mark.remote
def test_dwd_observation_solar_hourly(options_convert_units_false: Options) -> None:
    """Test DWD observation solar hourly data.

    Thanks, @lasinludwig, for providing the snippet.
    """
    latlon_bremen = 53.0980433, 8.7747248
    # request for radiation
    request = DwdObservationRequest(
        parameters=[("hourly", "solar", "radiation_global")],
        start=dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2022, 12, 31, 23, 59, tzinfo=ZoneInfo("UTC")),
        options=options_convert_units_false,
    ).filter_by_distance(latlon_bremen, 500)
    values_df = next(request.values().query()).df
    assert values_df.get_column("value").sum() == 417914.0


@pytest.mark.remote
def test_dwd_observation_solar_hourly_timestamps_off(default_settings: Settings) -> None:
    """Test DWD observation solar hourly data with timestamps off by one minute.

    This is to test the rounding of timestamps to the nearest hour.

    Thanks, @nkiessling, for reporting the issue.
    """
    request = DwdObservationRequest(
        parameters=[("hourly", "solar", "radiation_global")],
        start=dt.datetime(2024, 12, 8, 0, 0, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2024, 12, 8, 23, 0, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(station_id="03987")
    values_df = next(request.values().query()).df
    assert len(values_df) == 24
    assert values_df.get_column("value").sum() == 46.0


@pytest.mark.remote
def test_dwd_observation_data_10_minutes_missing_data(options_humanize_false_convert_units_false: Options) -> None:
    """Test for actual values with correctly dropped -999 values."""
    request = DwdObservationRequest(
        parameters=[("minute_10", "precipitation", "precipitation_amount")],
        start="1991-01-01 00:00",
        end="1992-12-31 23:00",
        options=options_humanize_false_convert_units_false,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    df = request.values().all().df
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
    df = request.values().all().df
    df = df.drop_nulls("value")
    df = df.sort("parameter").group_by(["parameter"], maintain_order=True).head(1)
    assert df.to_dicts() == [
        {
            "station_id": "01048",
            "resolution": "subdaily",
            "dataset": "wind_extreme",
            "parameter": "wind_gust_max_last_3h",
            "timestamp": dt.datetime(1991, 11, 1, 21, 0, tzinfo=ZoneInfo("UTC")),
            "value": 14.4,
            "quality_flags": "1",
        },
        {
            "station_id": "01048",
            "resolution": "subdaily",
            "dataset": "wind_extreme",
            "parameter": "wind_gust_max_last_6h",
            "timestamp": dt.datetime(1990, 6, 2, 18, 0, tzinfo=ZoneInfo("UTC")),
            "value": 6.2,
            "quality_flags": "1",
        },
    ]


@pytest.mark.remote
def test_dwd_observation_data_5minute_precipitation_data(default_settings: Settings) -> None:
    """Test for DWD observation 5 minute precipitation data."""
    request = DwdObservationRequest(
        parameters=[("minute_5", "precipitation", "precipitation_amount")],
        start="2023-08-25 00:00",
        end="2023-08-27 00:00",
        settings=default_settings,
    ).filter_by_station_id(station_id="01048")
    values = request.values().all().df
    assert round(values.get_column("value").sum(), 2) == 4.35


@pytest.mark.remote
def test_dwd_observation_data_5minute_precipitation_data_recent(default_settings: Settings) -> None:
    """Test for DWD observation 5 minute precipitation data with recent and now periods. This is actually missing."""
    request = DwdObservationRequest(
        parameters=[
            ("minute_5", "precipitation", "precipitation_amount_rocker"),
            ("minute_5", "precipitation", "precipitation_amount_droplet"),
        ],
        periods={"recent", "now"},
        settings=default_settings,
    ).filter_by_station_id(station_id="01048")
    values = request.values().all().df
    assert values.is_empty()


@pytest.mark.remote
def test_dwd_observation_data_1minute_precipitation_data_tidy(default_settings: Settings) -> None:
    """Test for DWD observation 1 minute precipitation data."""
    request = DwdObservationRequest(
        parameters=[("minute_1", "precipitation", "precipitation_amount_droplet")],
        start="1990-01-01 00:00",
        end="1995-01-01 00:10",
        settings=default_settings,
    ).filter_by_station_id(1048)
    values = request.values().all().df
    assert round(values.get_column("value").sum(), 2) == 2681.8


@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "parameter"),
    [
        ("visibility", "visibility_measurement_method"),
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
    values = request.values().all().df
    assert not values.is_empty()
    assert values.get_column("parameter").unique().to_list() == [parameter]
    assert set(values.get_column("value").drop_nulls().unique()) <= {1.0, 2.0}


@pytest.mark.remote
def test_dwd_observation_true_local_time_offset(options_convert_units_false: Options) -> None:
    """Test that the true local time offset carries the seasonal solar correction.

    The offset is the longitude correction plus the equation of time, so it has to *move* over the
    year -- a value that came out constant would mean the correction had been rounded away, which
    is exactly what happens to it in the timestamp.
    """

    def offsets(month: int) -> list[float]:
        request = DwdObservationRequest(
            parameters=[("hourly", "solar", "true_local_time_offset")],
            start=dt.datetime(2023, month, 10, 0, 0, tzinfo=ZoneInfo("UTC")),
            end=dt.datetime(2023, month, 10, 6, 0, tzinfo=ZoneInfo("UTC")),
            options=options_convert_units_false,
        ).filter_by_station_id("00183")
        return request.values().all().df.get_column("value").to_list()

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
        start="2022-01-01",
        options=Options(unit_targets=unit_targets),
    ).filter_by_station_id("1048")
    given_df = request.values().all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "cloud_cover_total_mean",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 95.0,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "humidity_relative_mean",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 78.0,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "precipitation_form",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "pressure_air_site_mean",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 99560.0,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "pressure_vapor_mean",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1060.0,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "snow_depth",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "sunshine_duration",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 53.96,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 52.52,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_min_0_05m",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 37.76,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_min_2m",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 43.52,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "wind_gust_max",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 44.28,
                "quality_flags": "10",
            },
            {
                "station_id": "01048",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "wind_speed_mean",
                "timestamp": dt.datetime(2022, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 18.36,
                "quality_flags": "10",
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
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
    given_df = next(request.values().query()).df
    assert not given_df.is_empty()
    assert given_df.get_column("quality_flags").is_not_null().mean() >= 0.99


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
    given_df = next(request.values().query()).df
    assert not given_df.is_empty()
    assert given_df.get_column("quality_flags").is_not_null().mean() >= 0.99


@pytest.mark.remote
def test_dwd_observation_annual_climate_indices(default_settings: Settings) -> None:
    """Test DWD observation annual climate indices, counted over a closed historical year."""
    request = DwdObservationRequest(
        parameters=[("annual", "climate_indices")],
        periods=[Period.HISTORICAL],
        start=dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1990, 12, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(station_id=["00003"])
    given_df = request.values().all().df
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
    assert given_df.get_column("timestamp").unique().to_list() == [dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC"))]
    assert given_df.get_column("quality_flags").unique().to_list() == ["10"]


@pytest.mark.remote
def test_dwd_observation_monthly_precipitation_indices(default_settings: Settings) -> None:
    """Test DWD observation monthly precipitation indices, counted over a closed historical month.

    The thresholds are cumulative -- a day of 10 mm is counted by every threshold up to it -- so the
    counts have to fall monotonically as the threshold rises.
    """
    request = DwdObservationRequest(
        parameters=[("monthly", "precipitation_indices")],
        periods=[Period.HISTORICAL],
        start=dt.datetime(1990, 7, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1990, 7, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(station_id=["00003"])
    given_df = request.values().all().df
    given = dict(given_df.select("parameter", "value").iter_rows())
    assert given == {
        "count_days_precipitation_amount_ge_0_1mm": 10.0,
        "count_days_precipitation_amount_ge_1mm": 7.0,
        "count_days_precipitation_amount_ge_2_5mm": 4.0,
        "count_days_precipitation_amount_ge_5mm": 2.0,
        "count_days_precipitation_amount_ge_10mm": 1.0,
        "count_days_precipitation_amount_ge_20mm": 0.0,
        "count_days_snow_depth_ge_1cm": 0.0,
        "count_days_snow_depth_ge_5cm": 0.0,
    }
    assert given_df.get_column("timestamp").unique().to_list() == [dt.datetime(1990, 7, 1, tzinfo=ZoneInfo("UTC"))]


def test_dwd_observation_tidy_up_writes_the_qn_code_as_a_flag_string() -> None:
    """The `QN` of a row is written in `quality_flags` as DWD writes it, and only where the row has a value (GH-2758).

    DWD pads its fields with spaces, so every column is read as text and the code arrives as "    3"; it was
    cast to a Float64 and came out as 3.0. The code sits in front of the columns it speaks for, and a
    null value takes no flag. The levels are those of the dataset descriptions ("QN = 3 : automatic control
    and correction", "QN = 10 : quality control finished, all corrections finished").
    """
    df = pl.DataFrame(
        {
            "station_id": ["01048", "01048"],
            "timestamp": [dt.datetime(2019, 1, day, tzinfo=ZoneInfo("UTC")) for day in (1, 2)],
            "qn_3": ["    3", "   10"],
            "fx": [11.8, None],
        },
    )
    given_df = DwdObservationValues._tidy_up_df(df)  # noqa: SLF001
    assert given_df.get_column("quality_flags").to_list() == ["3", None]
    assert given_df.schema["quality_flags"] == pl.String


def _p0(df: pl.DataFrame) -> list[tuple[float | None, str | None]]:
    """Give the value and the flags of the station pressure, by stamp."""
    rows = df.filter(pl.col("parameter").eq("pressure_air_site")).sort("timestamp")
    return list(zip(rows.get_column("value").to_list(), rows.get_column("quality_flags").to_list(), strict=True))


@pytest.mark.parametrize(
    ("elevation", "expected"),
    [
        # Berlin-Tempelhof, 48 m: 1007.5 hPa are expected, so 865 to 1082.5 are allowed: 909.5 is a slip that is 98 hPa
        # below, as far as Hurricane Irma's eye was (917.4 hPa at 3 m), and stays until the step check of GH-3681
        (48.0, [(1038.9, "1"), (909.5, "1"), (1009.6, "1")]),
        # a station list without an elevation leaves the reading to the bounds of the world, which it is inside of
        (None, [(1038.9, "1"), (909.5, "1"), (1009.6, "1")]),
        # the same readings at 500 m (954.6 hPa expected, 820 to 1030 allowed): 1038.9 is out, 909.5 is in
        (500.0, [(None, "1,rejected:elevation,raw:1038.9"), (909.5, "1"), (1009.6, "1")]),
        # and at 1,500 m (845.6 expected, 726 to 921 allowed): the two above 921 are out
        (
            1500.0,
            [(None, "1,rejected:elevation,raw:1038.9"), (909.5, "1"), (None, "1,rejected:elevation,raw:1009.6")],
        ),
    ],
)
def test_dwd_observation_data_station_pressure_is_held_to_the_elevation_of_the_station(
    monkeypatch: pytest.MonkeyPatch,
    elevation: float | None,
    expected: list[tuple[float | None, str | None]],
) -> None:
    """Test that the elevation of the station list decides which P0 is a reading, the rows of 00433 (GH-3627)."""
    from tests.provider.value_stubs import _dwd_observation  # noqa: PLC0415

    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;   P;  P0;eor\n"
        "        433;1994082920;    1; 1014.7; 1038.9;eor\n"
        "        433;1994082921;    1; 1015.4;  909.5;eor\n"
        "        433;1994082922;    1; 1015.5; 1009.6;eor\n"
    )
    df = _dwd_observation(
        monkeypatch, "hourly", "pressure", product, "00433", year=1994, drop_nulls=False, elevation=elevation
    )
    assert _p0(df) == expected
