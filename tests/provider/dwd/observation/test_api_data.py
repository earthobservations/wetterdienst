# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime, timezone

import pandas as pd
import pytest
import pytz
from freezegun import freeze_time
from pandas import Timestamp
from pandas._testing import assert_frame_equal

from wetterdienst import Parameter
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationParameter,
)


@pytest.fixture
def dwd_climate_summary_tabular_columns():
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
        parameter=[
            "temperature_air",
            "wind",
            "precipitation",
        ],
        resolution="minute_10",
        period="now",
        settings=default_settings,
    ).filter_by_rank(latlon=(52.384630, 9.733908), rank=1)
    given_df = request.values.all().df
    assert given_df.station_id.unique() == ["02011"]
    assert given_df.query("dataset == 'wind' | dataset == 'temperature_air'").dropna(subset="value").empty


def test_request_period_historical(default_settings):
    # Historical period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
        settings=default_settings,
    )
    assert request.period == [
        Period.HISTORICAL,
    ]


def test_request_period_historical_recent(default_settings):
    # Historical and recent period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
        end_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(days=400),
        settings=default_settings,
    )
    assert request.period == [
        Period.HISTORICAL,
        Period.RECENT,
    ]


def test_request_period_historical_recent_now(default_settings):
    # Historical, recent and now period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
        end_date=pd.Timestamp(datetime.utcnow()),
        settings=default_settings,
    )
    assert request.period == [
        Period.HISTORICAL,
        Period.RECENT,
        Period.NOW,
    ]


@freeze_time(datetime(2022, 1, 29, 1, 30, tzinfo=pytz.timezone(Timezone.GERMANY.value)))
def test_request_period_recent_now(default_settings):
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(hours=2),
        settings=default_settings,
    )
    assert request.period == [Period.RECENT, Period.NOW]


@freeze_time(datetime(2022, 1, 29, 2, 30, tzinfo=pytz.timezone(Timezone.GERMANY.value)))
def test_request_period_now(default_settings):
    # Now period
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(hours=2),
        settings=default_settings,
    )
    assert request.period == [Period.NOW]


@freeze_time(datetime(2021, 3, 28, 18, 38, tzinfo=pytz.timezone(Timezone.GERMANY.value)))
def test_request_period_now_fixed_date(default_settings):
    # Now period
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(hours=2),
        settings=default_settings,
    )
    assert Period.NOW in request.period


def test_request_period_empty(default_settings):
    # No period (for example in future)
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) + pd.Timedelta(days=720),
        settings=default_settings,
    )
    assert request.period == []


@pytest.mark.remote
def test_dwd_observation_data_result_missing_data(default_settings):
    """Test for DataFrame having empty values for dates where the station should not
    have values"""
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-27",  # few days before official start
        end_date="1934-01-04",  # few days after official start,
        settings=default_settings,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df.drop("quality", axis=1)
    assert not given_df.query("date.dt.year in (1933, 1934)").dropna().empty
    request = DwdObservationRequest(
        parameter=DwdObservationParameter.HOURLY.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.HOURLY,
        start_date="2020-06-09 12:00:00",  # no data at this time (reason unknown)
        end_date="2020-06-09 12:00:00",
        settings=default_settings,
    ).filter_by_station_id(
        station_id=["03348"],
    )
    given_df = request.values.all().df
    expected_df = pd.DataFrame(
        {
            "station_id": pd.Categorical(["03348"]),
            "dataset": pd.Categorical(["temperature_air"]),
            "parameter": pd.Categorical(["temperature_air_mean_200"]),
            "date": [datetime(2020, 6, 9, 12, 0, 0, tzinfo=pytz.UTC)],
            "value": pd.Series([pd.NA], dtype=pd.Float64Dtype()).astype(float),
            "quality": pd.Series([pd.NA], dtype=pd.Float64Dtype()).astype(float),
        }
    )
    assert_frame_equal(
        given_df,
        expected_df,
        check_categorical=False,
    )


@pytest.mark.remote
def test_dwd_observation_data_result_all_missing_data(default_settings):
    request = DwdObservationRequest(
        parameter=Parameter.PRECIPITATION_HEIGHT.name,
        resolution=DwdObservationResolution.MINUTE_10,
        start_date=datetime(2021, 10, 3),
        end_date=datetime(2021, 10, 5),
        settings=default_settings,
    ).filter_by_station_id(["05435"])
    given_df = request.values.all().df
    assert given_df.value.dropna().empty


@pytest.mark.remote
def test_dwd_observation_data_result_tabular(
    settings_humanize_si_false_wide_shape, dwd_climate_summary_tabular_columns
):
    """Test for actual values (tabular)"""
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_si_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df
    assert list(given_df.columns.values) == dwd_climate_summary_tabular_columns
    expected_df = pd.DataFrame(
        {
            "station_id": pd.Categorical(["01048"] * 2),
            "dataset": pd.Categorical(["climate_summary"] * 2),
            "date": [
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
            ],
            "fx": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "qn_fx": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "fm": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "qn_fm": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "rsk": pd.to_numeric([pd.NA, 0.2], errors="coerce"),
            "qn_rsk": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "rskf": pd.to_numeric([pd.NA, 8], errors="coerce"),
            "qn_rskf": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "sdk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "qn_sdk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "shk_tag": pd.to_numeric([pd.NA, 0], errors="coerce"),
            "qn_shk_tag": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "nm": pd.to_numeric([pd.NA, 8.0], errors="coerce"),
            "qn_nm": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "vpm": pd.to_numeric([pd.NA, 6.4], errors="coerce"),
            "qn_vpm": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "pm": pd.to_numeric([pd.NA, 1008.60], errors="coerce"),
            "qn_pm": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "tmk": pd.to_numeric([pd.NA, 0.5], errors="coerce"),
            "qn_tmk": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "upm": pd.to_numeric([pd.NA, 97.00], errors="coerce"),
            "qn_upm": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "txk": pd.to_numeric([pd.NA, 0.7], errors="coerce"),
            "qn_txk": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "tnk": pd.to_numeric([pd.NA, 0.2], errors="coerce"),
            "qn_tnk": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "tgk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "qn_tgk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
        }
    )
    assert_frame_equal(
        given_df,
        expected_df,
        check_categorical=False,
    )


@pytest.mark.remote
def test_dwd_observation_data_result_tabular_si(
    settings_humanize_false_wide_shape, dwd_climate_summary_tabular_columns
):
    """Test for actual values (tabular) in metric units"""
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_false_wide_shape,
    ).filter_by_station_id(
        station_id=[1048],
    )
    given_df = request.values.all().df

    assert list(given_df.columns.values) == dwd_climate_summary_tabular_columns
    expected_df = pd.DataFrame(
        {
            "station_id": pd.Categorical(["01048"] * 2),
            "dataset": pd.Categorical(["climate_summary"] * 2),
            "date": [
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
            ],
            "fx": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "qn_fx": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "fm": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "qn_fm": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "rsk": pd.to_numeric([pd.NA, 0.2], errors="coerce"),
            "qn_rsk": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "rskf": pd.to_numeric([pd.NA, 8], errors="coerce"),
            "qn_rskf": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "sdk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "qn_sdk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "shk_tag": pd.to_numeric([pd.NA, 0], errors="coerce"),
            "qn_shk_tag": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "nm": pd.to_numeric([pd.NA, 100.0], errors="coerce"),
            "qn_nm": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "vpm": pd.to_numeric([pd.NA, 640.0], errors="coerce"),
            "qn_vpm": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "pm": pd.to_numeric([pd.NA, 100860.0], errors="coerce"),
            "qn_pm": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "tmk": pd.to_numeric([pd.NA, 273.65], errors="coerce"),
            "qn_tmk": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "upm": pd.to_numeric([pd.NA, 97.00], errors="coerce"),
            "qn_upm": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "txk": pd.to_numeric([pd.NA, 273.84999999999997], errors="coerce"),
            "qn_txk": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "tnk": pd.to_numeric([pd.NA, 273.34999999999997], errors="coerce"),
            "qn_tnk": pd.to_numeric([pd.NA, 1], errors="coerce"),
            "tgk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            "qn_tgk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
        }
    )
    assert_frame_equal(
        given_df,
        expected_df,
        check_categorical=False,
    )


@pytest.mark.remote
def test_dwd_observation_data_result_tidy_si(settings_humanize_false):
    """Test for actual values (format) in metric units"""
    request = DwdObservationRequest(
        parameter=["kl"],
        resolution="daily",
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        settings=settings_humanize_false,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    given_df = request.values.all().df
    assert list(given_df.columns.values) == [
        "station_id",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]
    expected_df = pd.DataFrame.from_records(
        [
            [
                "01048",
                "climate_summary",
                "fx",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "fx",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "fm",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "fm",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "rsk",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "rsk",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                0.2,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "rskf",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "rskf",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                8,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "sdk",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "sdk",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "shk_tag",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "shk_tag",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                0,
                1.0,
            ],
            [
                "01048",
                "climate_summary",
                "nm",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "nm",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                100,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "vpm",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "vpm",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                640,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "pm",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "pm",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                100860.0,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "tmk",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "tmk",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                273.65,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "upm",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "upm",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                97.00,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "txk",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "txk",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                273.84999999999997,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "tnk",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "tnk",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                273.34999999999997,
                1,
            ],
            [
                "01048",
                "climate_summary",
                "tgk",
                datetime(1933, 12, 31, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
            [
                "01048",
                "climate_summary",
                "tgk",
                datetime(1934, 1, 1, tzinfo=pytz.UTC),
                pd.NA,
                pd.NA,
            ],
        ],
        columns=["station_id", "dataset", "parameter", "date", "value", "quality"],
    )
    expected_df = expected_df.astype({"station_id": "category", "dataset": "category", "parameter": "category"})
    expected_df.value = pd.to_numeric(expected_df.value)
    expected_df.quality = pd.to_numeric(expected_df.quality)
    assert_frame_equal(
        given_df,
        expected_df,
        # Needed since pandas 1.2?
        check_categorical=False,
    )


@pytest.mark.remote
def test_dwd_observations_urban_values(default_settings):
    """Test DWD Observation urban stations"""
    request = DwdObservationRequest(
        parameter="urban_air_temperature",
        resolution="hourly",
        period="historical",
        start_date="2022-06-01",
        settings=default_settings,
    ).filter_by_station_id("00399")
    given_df = request.values.all().df
    expected_df = pd.DataFrame(
        {
            "station_id": pd.Categorical(["00399"] * 2),
            "dataset": pd.Categorical(["urban_temperature_air"] * 2),
            "parameter": pd.Categorical(["temperature_air_mean_200", "humidity"]),
            "date": [pd.Timestamp("2022-06-01", tz=pytz.utc)] * 2,
            "value": [286.54999999999995, 83.0],
            "quality": [3.0, 3.0],
        }
    )
    assert_frame_equal(given_df, expected_df, check_categorical=False)


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
        parameter=dataset,
        resolution="hourly",
        start_date="2022-01-01",
        end_date="2022-01-31",
        settings=default_settings,
    ).filter_by_name(name="Berlin-Alexanderplatz")
    given_df = request.values.all().df
    assert not given_df.value.empty


@pytest.mark.remote
def test_dwd_observation_data_10_minutes_result_tidy(settings_humanize_si_false):
    """Test for actual values (format) in metric units"""
    request = DwdObservationRequest(
        parameter=["pressure_air_site"],
        resolution="minute_10",
        start_date="1999-12-31 22:00",
        end_date="1999-12-31 23:00",
        settings=settings_humanize_si_false,
    ).filter_by_station_id(
        station_id=(1048,),
    )
    given_df = request.values.all().df
    expected_df = pd.DataFrame(
        {
            "station_id": pd.Categorical(["01048"] * 7),
            "dataset": pd.Categorical(["temperature_air"] * 7),
            "parameter": pd.Categorical(["pp_10"] * 7),
            "date": [
                datetime(1999, 12, 31, 22, 00, tzinfo=pytz.UTC),
                datetime(1999, 12, 31, 22, 10, tzinfo=pytz.UTC),
                datetime(1999, 12, 31, 22, 20, tzinfo=pytz.UTC),
                datetime(1999, 12, 31, 22, 30, tzinfo=pytz.UTC),
                datetime(1999, 12, 31, 22, 40, tzinfo=pytz.UTC),
                datetime(1999, 12, 31, 22, 50, tzinfo=pytz.UTC),
                datetime(1999, 12, 31, 23, 00, tzinfo=pytz.UTC),
            ],
            "value": pd.to_numeric(
                [
                    996.1,
                    996.2,
                    996.2,
                    996.2,
                    996.3,
                    996.4,
                    pd.NA,
                ],
                errors="coerce",
            ).astype(float),
            "quality": pd.to_numeric([1, 1, 1, 1, 1, 1, pd.NA], errors="coerce").astype(float),
        },
    )
    assert_frame_equal(
        given_df,
        expected_df,
        # Needed since pandas 1.2?
        check_categorical=False,
    )


@pytest.mark.remote
def test_dwd_observation_data_monthly_tidy(default_settings):
    """Test for actual values (format) in metric units"""
    request = DwdObservationRequest(
        parameter=[DwdObservationParameter.MONTHLY.PRECIPITATION_HEIGHT],
        resolution=DwdObservationResolution.MONTHLY,
        start_date="2020-01-01",
        end_date="2020-12-31",
        settings=default_settings,
    ).filter_by_station_id("00433")
    given_df = request.values.all().df
    expected_df = pd.DataFrame(
        {
            "station_id": pd.Categorical(["00433"] * 12),
            "dataset": pd.Categorical(["climate_summary"] * 12),
            "parameter": pd.Categorical(["precipitation_height"] * 12),
            "date": [
                Timestamp("2020-01-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-02-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-03-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-04-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-05-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-06-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-07-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-08-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-09-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-10-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-11-01 00:00:00+0000", tz="UTC"),
                Timestamp("2020-12-01 00:00:00+0000", tz="UTC"),
            ],
            "value": pd.to_numeric(
                [34.0, 83.2, 30.3, 22.7, 33.3, 35.8, 46.8, 43.2, 52.8, 58.2, 16.4, 22.1], errors="coerce"
            ),
            "quality": pd.to_numeric([9.0] * 12, errors="coerce"),
        },
    )
    assert_frame_equal(given_df, expected_df, check_categorical=False)


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
        "tmk": "temperature_air_mean_200",
        "upm": "humidity",
        "txk": "temperature_air_max_200",
        "tnk": "temperature_air_min_200",
        "tgk": "temperature_air_min_005",
    }
    hcnm = (
        DwdObservationRequest(
            ["kl"],
            "daily",
            ["recent"],
        )
        .filter_by_station_id(
            (0,),
        )
        .values._create_humanized_parameters_mapping()
    )

    assert set(kl_daily_hcnm.items()).issubset(set(hcnm.items()))


@pytest.mark.remote
def test_tidy_up_data(settings_humanize_false):
    """Test for function to format data"""
    request = DwdObservationRequest(
        parameter="kl",
        resolution="daily",
        period="historical",
        start_date="2019-01-23 00:00:00",
        settings=settings_humanize_false,
    ).filter_by_station_id(("01048",))
    df = pd.DataFrame(
        {
            "station_id": ["01048"],
            "date": [pd.Timestamp("2019-01-23 00:00:00")],
            "qn_3": [10],
            "fx": [11.8],
            "fm": [5.8],
            "qn_4": [3],
            "rsk": [0.0],
            "rskf": [0.0],
            "sdk": [7.1],
            "shk_tag": [0.0],
            "nm": [2.3],
            "vpm": [3.2],
            "pm": [975.4],
            "tmk": [-5.5],
            "upm": [79.17],
            "txk": [-1.7],
            "tnk": [-7.9],
            "tgk": [-11.4],
        }
    )
    given_df = request.values._tidy_up_df(df, request.parameter[0][1])
    given_df.quality = given_df.quality.astype(float)
    given_df = request.values._organize_df_columns(given_df, "01048", DwdObservationDataset.CLIMATE_SUMMARY)
    expected_df = pd.DataFrame(
        {
            "station_id": ["01048"] * 14,
            "dataset": ["climate_summary"] * 14,
            "parameter": [
                "fx",
                "fm",
                "rsk",
                "rskf",
                "sdk",
                "shk_tag",
                "nm",
                "vpm",
                "pm",
                "tmk",
                "upm",
                "txk",
                "tnk",
                "tgk",
            ],
            "date": [pd.Timestamp("2019-01-23 00:00:00")] * 14,
            "value": [
                11.8,
                5.8,
                0.0,
                0.0,
                7.1,
                0.0,
                2.3,
                3.2,
                975.4,
                -5.5,
                79.17,
                -1.7,
                -7.9,
                -11.4,
            ],
            "quality": pd.Series([10, 10, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], dtype=float),
        }
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observation_weather_phenomena(settings_humanize_si_false):
    """Test for DWD weather phenomena data, thanks saschnet (https://github.com/saschnet) for providing the sample,
    see also https://github.com/earthobservations/wetterdienst/issues/647
    """
    request = DwdObservationRequest(
        parameter=["weather"],
        resolution="hourly",
        start_date=datetime(year=2022, month=3, day=1, tzinfo=timezone.utc),
        end_date=datetime(year=2022, month=3, day=31, tzinfo=timezone.utc),
        settings=settings_humanize_si_false,
    )
    given_df = request.all().df.dropna()
    assert len(given_df) > 0


@pytest.mark.remote
def test_dwd_observation_tidy_empty_df_no_start_end_date(default_settings):
    """Test for DWD observation data with expected empty df for the case that no start and end date is given"""
    request = DwdObservationRequest(
        parameter=["wind"],
        resolution="minute_10",
        period="now",
        settings=default_settings,
    ).filter_by_station_id("01736")
    assert request.values.all().df.empty


@pytest.mark.remote
def test_dwd_observation_not_tidy_empty_df_no_start_end_date(settings_wide_shape):
    """Test for DWD observation data with expected empty df for the case that no start and end date is given"""
    request = DwdObservationRequest(
        parameter=["wind"],
        resolution="minute_10",
        period="now",
        settings=settings_wide_shape,
    ).filter_by_station_id("01736")
    assert request.values.all().df.empty


@pytest.mark.remote
def test_dwd_observation_solar_daily(default_settings):
    """Test DWD observation solar daily data"""
    # Snippet provided by https://github.com/pedroalencar1
    request = DwdObservationRequest(
        parameter="solar",
        resolution="daily",
        start_date=datetime(1950, 1, 1),
        end_date=datetime(2021, 12, 31),
        settings=default_settings,
    ).filter_by_station_id(station_id=[3987])
    assert not request.values.all().df.value.dropna().empty
