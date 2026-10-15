# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD derived data."""

import datetime
from collections.abc import Collection
from io import BytesIO
from itertools import permutations
from unittest.mock import patch
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal, assert_series_equal

from wetterdienst import Options, Settings
from wetterdienst.metadata.period import Period
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.derived import DwdDerivedMetadata, DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as dwd_derived_api
from wetterdienst.provider.dwd.derived.api import DwdDerivedValues
from wetterdienst.util.network import File


def _values_of(request: DwdDerivedRequest, station_id: str = "00044") -> DwdDerivedValues:
    """Build the values object for one station without looking that station up.

    The date arithmetic and the url parsing below live on the values object, which is reached
    through a `StationsResult`. Going there via `filter_by_station_id` would download DWD's
    station index, which turns a unit test over a string like `somefile_202510.csv` into a test
    that needs the internet. Only the request and the settings behind it are read, so a station
    frame carrying nothing but the id is enough.
    """
    df_stations = pl.DataFrame(
        [
            {
                "resolution": request.parameters[0].dataset.resolution.name,
                "dataset": request.parameters[0].dataset.name,
                "station_id": station_id,
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 52.9336,
                "longitude": 8.2370,
                "elevation": 44.0,
                "name": "Grossenkneten",
                "region": "Niedersachsen",
            }
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
        },
        orient="row",
    )
    sr = StationsResult(
        stations=request,
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.BY_STATION_ID,
    )
    return DwdDerivedValues.from_stations(sr)


@pytest.mark.remote
@pytest.mark.parametrize(
    ("period", "start_date", "end_date"),
    [
        (
            Period.RECENT,
            datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2014, month=10, day=1, tzinfo=ZoneInfo("UTC")),
        ),
        (
            Period.HISTORICAL,
            datetime.datetime(year=2024, month=7, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2024, month=10, day=1, tzinfo=ZoneInfo("UTC")),
        ),
    ],
)
def test_dwd_derived_data_empty_out_of_range_dates(
    default_settings: Settings,
    period: Period,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
) -> None:
    """Test for empty values for out of range dates."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        periods=period,
        settings=default_settings,
        start=start_date,
        end=end_date,
    ).filter_by_station_id(station_id="00044")

    fetched_df = request.values.all().df
    assert fetched_df.is_empty()


@pytest.mark.remote
def test_dwd_derived_data_empty_nonexisting_station(
    default_settings: Settings,
) -> None:
    """Test for empty values for nonexisting station."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        settings=default_settings,
    ).filter_by_station_id(station_id="-1")

    fetched_df = request.values.all().df
    assert fetched_df.is_empty()


@pytest.mark.parametrize(
    ("input_period", "expected_request_period"),
    [
        (
            Period.RECENT,
            {Period.RECENT},
        ),
        (
            Period.HISTORICAL,
            {Period.HISTORICAL},
        ),
        (
            "recent",
            {Period.RECENT},
        ),
        (
            "historical",
            {Period.HISTORICAL},
        ),
        (
            ["recent", "historical"],
            {Period.HISTORICAL, Period.RECENT},
        ),
        (
            None,
            {Period.HISTORICAL, Period.RECENT},
        ),
    ],
)
def test_request_period(
    default_settings: Settings, input_period: Collection[Period | str] | None, expected_request_period: set[Period]
) -> None:
    """Test for properly parsing input period."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        settings=default_settings,
        periods=input_period,
    )
    assert request.periods == expected_request_period


@pytest.mark.remote
def test_dwd_recent_data_result_long_single_parameter(
    default_settings: Settings,
) -> None:
    """Test for actual values (long)."""
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "heating_degreedays",
            "heating_degree_day",
        ),
        settings=default_settings,
        options=Options(shape="long"),
        start=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
        periods=[
            "historical",
        ],
    ).filter_by_station_id(station_id="00044")
    given_df = request.values.all().df
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
        {
            "station_id": ["00044"] * 3,
            "resolution": ["monthly"] * 3,
            "dataset": ["heating_degreedays"] * 3,
            "parameter": ["heating_degree_day"] * 3,
            "timestamp": [
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 9, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "value": [
                12.3,
                98.5,
                93.0,
            ],
            "quality_flags": [
                None,
                None,
                None,
            ],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_recent_data_result_wide_single_parameter(
    default_settings: Settings,
) -> None:
    """Test for actual values (wide)."""
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "heating_degreedays",
            "heating_degree_day",
        ),
        settings=default_settings,
        options=Options(shape="wide"),
        start=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
        periods=[
            "historical",
        ],
    ).filter_by_station_id(station_id="00044")
    given_df = request.values.all().df
    assert given_df.columns == [
        "station_id",
        "resolution",
        "dataset",
        "timestamp",
        "heating_degree_day",
        "heating_degree_day_quality_flags",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["00044"] * 3,
            "resolution": ["monthly"] * 3,
            "dataset": ["heating_degreedays"] * 3,
            "timestamp": [
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 9, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "heating_degree_day": [
                12.3,
                98.5,
                93.0,
            ],
            "heating_degree_day_quality_flags": [
                None,
                None,
                None,
            ],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "heating_degree_day": pl.Float64,
            "heating_degree_day_quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_recent_data_result_long_single_parameter_missing_month_heating_degree_days(
    default_settings: Settings,
) -> None:
    """Test for actual values (long), where no data exists for a month."""
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "heating_degreedays",
            "heating_degree_day",
        ),
        settings=default_settings,
        options=Options(shape="long"),
        start=datetime.datetime(year=2023, month=3, day=1, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2023, month=5, day=1, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id(station_id="00044")
    given_df = request.values.all().df
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
        {
            "station_id": ["00044"] * 2,
            "resolution": ["monthly"] * 2,
            "dataset": ["heating_degreedays"] * 2,
            "parameter": ["heating_degree_day"] * 2,
            "timestamp": [
                datetime.datetime(2023, 3, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2023, 5, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "value": [
                430.7,
                201.9,
            ],
            "quality_flags": [
                None,
                None,
            ],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_historical_data_result_long_single_parameter_missing_month_cooling_degree_hours(
    default_settings: Settings,
) -> None:
    """Test for actual values (long), where no data exists for a month."""
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "cooling_degreehours_13",
            "cooling_degree_hour",
        ),
        settings=default_settings,
        options=Options(shape="long"),
        start=datetime.datetime(year=2014, month=6, day=1, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id(station_id="00044")
    given_df = request.values.all().df
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
        {
            "station_id": ["00044"] * 2,
            "resolution": ["monthly"] * 2,
            "dataset": ["cooling_degreehours_13"] * 2,
            "parameter": ["cooling_degree_hour"] * 2,
            "timestamp": [
                datetime.datetime(2014, 6, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "value": [2240.6, 2549.5],
            "quality_flags": [
                None,
                None,
            ],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_historical_data_result_long_multiple_reference_temperatures(
    default_settings: Settings,
) -> None:
    """Test for actual values (long)."""
    request = DwdDerivedRequest(
        parameters=[
            (
                "monthly",
                "cooling_degreehours_13",
            ),
            (
                "monthly",
                "cooling_degreehours_16",
            ),
        ],
        settings=default_settings,
        options=Options(shape="long"),
        start=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        periods=[
            "historical",
        ],
    ).filter_by_station_id(station_id="00071")
    given_df = request.values.all().df
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
        {
            "station_id": ["00071"] * 8,
            "resolution": ["monthly"] * 8,
            "dataset": ["cooling_degreehours_13"] * 4 + ["cooling_degreehours_16"] * 4,
            "parameter": [
                "cooling_degree_hour",
                "count_days_cooling_degree",
                "count_hours_cooling_degree",
                "count_hours_in_month",
            ]
            * 2,
            "timestamp": [
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
            ]
            * 8,
            "value": [
                3015.2,
                29.0,
                624.0,
                744.0,
                1505.7,
                28.0,
                350.0,
                744.0,
            ],
            "quality_flags": [None] * 8,
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_recent_data_result_long_single_dataset(
    default_settings: Settings,
) -> None:
    """Test for actual values (long)."""
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "heating_degreedays",
        ),
        settings=default_settings,
        options=Options(shape="long"),
        start=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
        periods=[
            "historical",
        ],
    ).filter_by_station_id(station_id="00044")
    given_df = request.values.all().df
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
        {
            "station_id": ["00044"] * 9,
            "resolution": ["monthly"] * 9,
            "dataset": ["heating_degreedays"] * 9,
            "parameter": [
                "count_days_heating_degree",
                "count_days_heating_degree",
                "count_days_heating_degree",
                "count_days_in_month",
                "count_days_in_month",
                "count_days_in_month",
                "heating_degree_day",
                "heating_degree_day",
                "heating_degree_day",
            ],
            "timestamp": [
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 9, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 9, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 9, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "value": [
                2.0,
                14.0,
                15.0,
                31.0,
                31.0,
                30.0,
                12.3,
                98.5,
                93.0,
            ],
            "quality_flags": [
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_recent_data_result_long_climate_correction_factor(
    default_settings: Settings,
) -> None:
    """Test for actual values (long).

    Note that we cannot use historical data for stability since DWD only provides recent data.
    """
    request = DwdDerivedRequest(
        parameters=[
            (
                "monthly",
                "climate_correction_factor",
            ),
        ],
        settings=default_settings,
        options=Options(shape="long"),
        start=datetime.datetime(year=2019, month=9, day=1, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2020, month=3, day=1, tzinfo=ZoneInfo("UTC")),
        periods=[
            "recent",
        ],
    ).filter_by_station_id(station_id="01067")

    given_df = request.values.all().df
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
        {
            "station_id": ["01067"] * 7,
            "resolution": ["monthly"] * 7,
            "dataset": ["climate_correction_factor"] * 7,
            "parameter": ["climate_correction_factor"] * 7,
            "timestamp": [
                datetime.datetime(2019, 9, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2019, 10, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2019, 11, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2019, 12, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2020, 3, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "value": [
                1.24,
                1.24,
                1.23,
                1.23,
                1.22,
                1.19,
                1.14,
            ],
            "quality_flags": [None] * 7,
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_monthly_soil_ztumi_long(default_settings: Settings) -> None:
    """Test monthly soil ztumi dataset."""
    request = DwdDerivedRequest(
        parameters=[DwdDerivedMetadata.monthly.soil.thawing_thickness_bare_ground_max_month],
        settings=default_settings,
        options=Options(shape="long"),
        start=datetime.datetime(year=2024, month=5, day=1, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2024, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        periods=["historical"],
    ).filter_by_station_id(station_id="00150")

    expected_dict = [
        {
            "station_id": "00150",
            "resolution": "monthly",
            "dataset": "soil",
            "parameter": "thawing_thickness_bare_ground_max_month",
            "timestamp": datetime.datetime(2024, 5, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 0.0,
            "quality_flags": None,
        },
        {
            "station_id": "00150",
            "resolution": "monthly",
            "dataset": "soil",
            "parameter": "thawing_thickness_bare_ground_max_month",
            "timestamp": datetime.datetime(2024, 6, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 0.0,
            "quality_flags": None,
        },
        {
            "station_id": "00150",
            "resolution": "monthly",
            "dataset": "soil",
            "parameter": "thawing_thickness_bare_ground_max_month",
            "timestamp": datetime.datetime(2024, 7, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 0.0,
            "quality_flags": None,
        },
    ]

    assert request.values.all().df.to_dicts() == expected_dict


@pytest.mark.remote
def test_dwd_hourly_radiation_radiation_global_long(default_settings: Settings) -> None:
    """Test hourly radiation surface irradiance dataset (placeholder expected_df)."""
    request = DwdDerivedRequest(
        parameters=[DwdDerivedMetadata.hourly.radiation_global.radiation_global],
        settings=default_settings,
        options=Options(shape="long"),
        start=datetime.datetime(year=2024, month=5, day=5, hour=8, tzinfo=ZoneInfo("UTC")),
        end=datetime.datetime(year=2024, month=5, day=5, hour=13, tzinfo=ZoneInfo("UTC")),
        periods=["historical"],
    ).filter_by_station_id(station_id="18001")

    expected_dict = [
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "radiation_global",
            "timestamp": datetime.datetime(2024, 5, 5, 8, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 103.0,
            "quality_flags": "503",
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "radiation_global",
            "timestamp": datetime.datetime(2024, 5, 5, 9, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 114.0,
            "quality_flags": "503",
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "radiation_global",
            "timestamp": datetime.datetime(2024, 5, 5, 10, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 74.0,
            "quality_flags": "503",
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "radiation_global",
            "timestamp": datetime.datetime(2024, 5, 5, 11, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 42.0,
            "quality_flags": "503",
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "radiation_global",
            "timestamp": datetime.datetime(2024, 5, 5, 12, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 26.0,
            "quality_flags": "503",
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "radiation_global",
            "timestamp": datetime.datetime(2024, 5, 5, 13, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 84.0,
            "quality_flags": "503",
        },
    ]

    assert request.values.all().df.to_dicts() == expected_dict


@pytest.mark.parametrize(
    ("start_date", "end_date", "expected_range"),
    [
        (
            datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2014, month=10, day=13, tzinfo=ZoneInfo("UTC")),
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=10, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
        (
            datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2014, month=7, day=13, tzinfo=ZoneInfo("UTC")),
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
        (
            datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
        (
            None,
            datetime.datetime(year=2000, month=5, day=3, tzinfo=ZoneInfo("UTC")),
            pl.Series(
                [
                    datetime.datetime(year=2000, month=5, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
        (
            datetime.datetime(year=2000, month=5, day=3, tzinfo=ZoneInfo("UTC")),
            None,
            pl.Series(
                [
                    datetime.datetime(year=2000, month=5, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
        (
            datetime.datetime(2025, 1, 1, 6, 30, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(2025, 3, 1, 6, 30, tzinfo=ZoneInfo("UTC")),
            pl.Series(
                [
                    datetime.datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(2025, 2, 1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(2025, 3, 1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
        (
            # 1 January in Germany is still 31 December in UTC, and the month is the UTC one
            datetime.datetime(2025, 1, 1, tzinfo=ZoneInfo("Europe/Berlin")),
            datetime.datetime(2025, 3, 1, tzinfo=ZoneInfo("Europe/Berlin")),
            pl.Series(
                [
                    datetime.datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(2025, 2, 1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
    ],
    ids=[
        "start_and_end_in_different_months",
        "start_and_end_within_a_month",
        "start_equals_end",
        "no_start",
        "no_end",
        "time_of_day_is_dropped",
        "offset_is_converted_to_utc",
    ],
)
def test_get_first_day_of_months_to_fetch(
    default_settings: Settings,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    expected_range: pl.Series,
) -> None:
    """Test for getting dates for months to fetch from input dates."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        settings=default_settings,
        start=start_date,
        end=end_date,
    )

    values = _values_of(request)
    months_to_fetch = values._get_first_day_of_months_to_fetch(request.parameters[0])  # noqa: SLF001
    assert_series_equal(months_to_fetch, expected_range, check_names=False)


def test_get_first_day_of_months_to_fetch_neither_start_nor_end_date_given(
    default_settings: Settings,
) -> None:
    """Test for getting dates for months to fetch when no input dates exist."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        settings=default_settings,
        start=None,
        end=None,
    )

    values = _values_of(request)
    months_to_fetch = values._get_first_day_of_months_to_fetch(request.parameters[0])  # noqa: SLF001

    assert min(months_to_fetch) == datetime.datetime(
        2000,
        1,
        1,
        tzinfo=ZoneInfo("UTC"),
    )
    assert max(months_to_fetch) == datetime.datetime(
        year=datetime.datetime.now(
            tz=ZoneInfo("UTC"),
        ).year,
        month=datetime.datetime.now(
            tz=ZoneInfo("UTC"),
        ).month,
        day=1,
        tzinfo=ZoneInfo("UTC"),
    )


@pytest.mark.parametrize(
    ("file_url", "expected_date"),
    [
        (
            "example.org/test.txt",
            None,
        ),
        (
            "example.org/somefile_202510.csv",
            datetime.datetime(year=2025, month=10, day=1, tzinfo=ZoneInfo("UTC")),
        ),
        ("example.org/somefile_2025.csv", None),
    ],
)
def test_extract_datetime_from_file_url_single_date_format(
    default_settings: Settings,
    file_url: str,
    expected_date: datetime.datetime,
) -> None:
    """Test for getting dates from file url."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        settings=default_settings,
    )

    values = _values_of(request)
    extracted_date = values._extract_datetime_from_file_url_single_date_format(file_url)  # noqa: SLF001
    if expected_date is None:
        assert extracted_date is None
    else:
        assert extracted_date == expected_date


@pytest.mark.parametrize(
    ("file_url", "expected_date"),
    [
        ("example.org/somefile_2025.csv", None),
        (
            "example.org/somefile_20250824_20260915.csv",
            datetime.datetime(year=2025, month=8, day=24, tzinfo=ZoneInfo("UTC")),
        ),
    ],
)
def test_extract_datetime_from_file_url_multiple_dates_format(
    default_settings: Settings,
    file_url: str,
    expected_date: datetime.datetime,
) -> None:
    """Test for getting dates from file url."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        settings=default_settings,
    )

    values = _values_of(request)
    extracted_date = values._extract_datetime_from_file_url_multiple_dates_format(file_url)  # noqa: SLF001
    if expected_date is None:
        assert extracted_date is None
    else:
        assert extracted_date == expected_date


def test_process_dataframe_to_expected_format(
    default_settings: Settings,
) -> None:
    """Test for processing df."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays", "heating_degree_day"),
        ],
        settings=default_settings,
    )

    values = _values_of(request)
    rename_mapping = _column_name_mapping = {
        "Monatsgradtage": "heating_degree_day",
    }
    input_df = pl.DataFrame(
        {
            "Monatsgradtage": [12.3],
        },
        schema={
            "Monatsgradtage": pl.Float64,
        },
        orient="col",
    )

    input_date = datetime.datetime(year=2000, month=5, day=3, tzinfo=ZoneInfo("UTC"))
    input_parameter = request.parameters[0]

    expected_df = pl.DataFrame(
        {
            "resolution": ["monthly"],
            "dataset": ["heating_degreedays"],
            "parameter": ["Monatsgradtage"],
            "timestamp": [input_date],
            "value": [12.3],
        },
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
        },
        orient="col",
    )

    processed_df = values._process_dataframe_to_expected_format(  # noqa: SLF001
        df=input_df, column_name_mapping=rename_mapping, date=input_date, parameter=input_parameter
    )
    assert_frame_equal(processed_df, expected_df)


@pytest.mark.parametrize(
    ("input_range", "input_files_on_server", "expected_range"),
    [
        (
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=10, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
            [f"example.org/data_2014{str(i_month).zfill(2)}.csv" for i_month in range(1, 12)],
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=10, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
        (
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=10, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
            [f"example.org/data_2014{str(i_month).zfill(2)}.csv" for i_month in range(6, 8)],
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
        ),
        (
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=10, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
            [f"example.org/data_2015{str(i_month).zfill(2)}.csv" for i_month in range(6, 8)],
            pl.Series([]),
        ),
        (
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
            ["example.org/no_file_that_matches.txt"],
            pl.Series([]),
        ),
        (
            pl.Series(
                [
                    datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
                    datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
                ]
            ),
            [],
            pl.Series([]),
        ),
    ],
    ids=[
        "file_range_full_covers_date_range",
        "file_range_partially_covers_date_range",
        "file_range_does_not_cover_date_range",
        "file_range_no_matching_files_available",
        "file_range_no_files_available",
    ],
)
def test_filter_date_range_for_period(
    default_settings: Settings,
    input_range: pl.Series,
    input_files_on_server: list[str],
    expected_range: pl.Series,
) -> None:
    """Test for getting dates for months to fetch from input dates."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        settings=default_settings,
    )

    values = _values_of(request)

    with patch("wetterdienst.provider.dwd.derived.api.list_remote_files_fsspec") as mocked_function:
        mocked_function.return_value = input_files_on_server
        filtered_range = values._filter_date_range_for_period(  # noqa: SLF001
            date_range=input_range, period=Period.RECENT, dataset=request.parameters[0].dataset
        )
        assert_series_equal(filtered_range, expected_range, check_names=False, check_dtypes=False)


@pytest.mark.parametrize(
    ("month_of_year", "expected_start_date", "expected_end_date"),
    [
        (
            "202401",
            datetime.datetime(year=2024, month=1, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2024, month=12, day=31, tzinfo=ZoneInfo("UTC")),
        ),
        (
            "202501",
            datetime.datetime(year=2025, month=1, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2025, month=12, day=31, tzinfo=ZoneInfo("UTC")),
        ),
        (
            "202403",
            datetime.datetime(year=2024, month=3, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2025, month=2, day=28, tzinfo=ZoneInfo("UTC")),
        ),
        (
            "202303",
            datetime.datetime(year=2023, month=3, day=1, tzinfo=ZoneInfo("UTC")),
            datetime.datetime(year=2024, month=2, day=29, tzinfo=ZoneInfo("UTC")),
        ),
    ],
    ids=[
        "range_is_in_leap_year",
        "range_is_not_leap_year",
        "range_ends_in_february_no_leap_year",
        "range_ends_in_february_leap_year",
    ],
)
def test_get_date_range_for_year_starting_in_month(
    default_settings: Settings,
    month_of_year: str,
    expected_start_date: datetime.datetime,
    expected_end_date: datetime.datetime,
) -> None:
    """Test for getting dates for months to fetch from input dates."""
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "heating_degreedays"),
        ],
        settings=default_settings,
    )

    values = _values_of(request)
    start_date, end_date = values._get_date_range_for_year_starting_in_month(month_of_year)  # noqa: SLF001
    assert start_date == expected_start_date
    assert end_date == expected_end_date


@pytest.mark.parametrize("dataset", ["radiation_global", "sunshine_duration"])
def test_dwd_derived_hourly_uncertainty_is_read_from_the_column_of_its_own_dataset(dataset: str) -> None:
    """The uncertainty of a hourly derived quantity is `<prefix>_un_duett`, the column beside `<prefix>_duett`.

    DWD publishes `FG_DUETT` and `FG_UN_DUETT` for the global radiation and `SD_DUETT` and
    `SD_UN_DUETT` for the sunshine duration. The sunshine duration's uncertainty was declared with
    the radiation's column name, a column its file does not have, so it never came back (GH-2614).
    """
    parameters = {parameter.name: parameter.name_original for parameter in DwdDerivedMetadata["hourly"][dataset]}
    value = parameters[dataset]
    assert value.endswith("_duett")
    assert parameters[f"{dataset}_uncertainty"] == value.replace("_duett", "_un_duett")


@pytest.mark.remote
def test_dwd_derived_hourly_sunshine_duration_uncertainty_is_returned(default_settings: Settings) -> None:
    """The sunshine duration's uncertainty comes back beside the sunshine duration, from `SD_UN_DUETT`."""
    request = DwdDerivedRequest(
        parameters=[("hourly", "sunshine_duration")],
        periods="recent",
        settings=default_settings,
    ).filter_by_station_id("18000")
    df = request.values.all().df
    assert set(df.get_column("parameter").unique().to_list()) == {
        "sunshine_duration",
        "sunshine_duration_uncertainty",
    }


_HEATING_DEGREEDAYS_HEADER = (
    "#Monatsgradtage VDI 3807; erstellt: DWD, 20250103\n"
    "#Messnetz_id 4; mittlere Raumtemperatur (Grad Celsius): 20\n"
    "#Auswertezeitraum {period}\n"
    "#ID; geogr. Breite; geogr. Laenge;Station; Monat; Anzahl Tage; Monatsgradtage; Anzahl Heiztage; Mittelwert\n"
)
_COOLING_DEGREEHOURS_HEADER = (
    "#Kuehlgrade, erstellt: 20250103; Programm: kuehlgrade_alle_open_data_08_2.pl\n"
    "#Bezugstemperatur (Grad Celsius): 13\n"
    "ID;geogr. Breite;geogr. Laenge;Stationsname;Datum [jjjjmm];Anzahl Stunden;Anzahl Kuehlstunden;"
    "Kuehlgradestunden;Kuehltage\n"
)
_BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly"

# Files as DWD serves them (station 01048 for the degree days and hours, postal code 01067 for the
# climate correction factor, each beside a second row). A monthly file names the month it covers in
# its name and in its header; the climate correction factor file starts at the month it is named for.
_DERIVED_FILES = (
    {
        f"{_BASE_URL}/heating_degreedays/hdd_3807/recent/gradtage_{month}.csv": (
            _HEATING_DEGREEDAYS_HEADER.format(period=period)
            + f"00044;52.93; 8.24;            GROSSENKNETEN;{month};{days};111.1;{days};472.5\n"
            + f"01048;51.13;13.75;        DRESDEN-KLOTZSCHE;{month};{days};{value};{days};510.2\n"
        )
        for month, period, days, value in [
            ("202412", "01-DEC-2024 bis 31-DEC-2024", 31, "533.9"),
            ("202501", "01-JAN-2025 bis 31-JAN-2025", 31, "535.0"),
            ("202502", "01-FEB-2025 bis 28-FEB-2025", 28, "529.6"),
            ("202503", "01-MAR-2025 bis 31-MAR-2025", 31, "421.7"),
        ]
    }
    | {
        f"{_BASE_URL}/cooling_degreehours/cdh_13/recent/kuehlgrade_13_0_{month}.csv": (
            _COOLING_DEGREEHOURS_HEADER
            + f"00044;52.93; 8.24;        GROSSENKNETEN;{month};{hours};    9;    9.9;1\n"
            + f"01048;51.13;13.75;        DRESDEN-KLOTZSCHE;{month};{hours};{cooling_hours};{value};{days}\n"
        )
        for month, hours, cooling_hours, value, days in [
            ("202412", 744, "    1", "    0.2", 1),
            ("202501", 744, "    0", "    0.0", 0),
            ("202502", 672, "    4", "    3.7", 1),
            ("202503", 744, "   78", "  169.2", 13),
        ]
    }
    | {
        f"{_BASE_URL}/climate_correction_factor/recent/KF_{start}_{end}.csv": (
            f"DatAnf;DatEnd;PLZ;KF\n{start};{end};1067;{value}\n{start};{end};1069;9.99\n"
        )
        for start, end, value in [
            ("20241201", "20251130", "1.15"),
            ("20250101", "20251231", "1.14"),
            ("20250201", "20260131", "1.10"),
            ("20250301", "20260228", "1.11"),
        ]
    }
)
_JAN, _FEB, _MAR = (datetime.datetime(2025, month, 1, tzinfo=ZoneInfo("UTC")) for month in (1, 2, 3))
_DEC = datetime.datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))


def _serve_derived_files(url: str, **_: object) -> File:
    """Answer a download the way the DWD server does: the file, or a 404 for a month it does not have."""
    if url in _DERIVED_FILES:
        return File(url=url, content=BytesIO(_DERIVED_FILES[url].encode("latin-1")), status=200)
    return File(url=url, content=Exception("not found"), status=404)


@pytest.mark.parametrize(
    ("parameter", "station_id", "expected_values"),
    [
        (
            "monthly/heating_degreedays/heating_degree_day",
            "01048",
            {_DEC: 533.9, _JAN: 535.0, _FEB: 529.6, _MAR: 421.7},
        ),
        ("monthly/cooling_degreehours_13/cooling_degree_hour", "01048", {_DEC: 0.2, _JAN: 0.0, _FEB: 3.7, _MAR: 169.2}),
        (
            "monthly/climate_correction_factor/climate_correction_factor",
            "01067",
            {_DEC: 1.15, _JAN: 1.14, _FEB: 1.10, _MAR: 1.11},
        ),
    ],
)
@pytest.mark.parametrize(
    ("start", "end", "expected_months"),
    [
        # the day-of-month and the time of day of the request do not move the stamp off the first of
        # the month; January starts before the window does, so only the months from February are in it
        ("2025-01-01T06:30", "2025-03-01T06:30", [_FEB, _MAR]),
        # 1 January in Germany: the January value is stamped 2025-01-01 00:00 UTC, not 2025-01-31 23:00,
        # and the files fetched are those of the UTC months, not shifted by the hour of the offset
        ("2025-01-01T00:00+01:00", "2025-03-01T00:00+01:00", [_JAN, _FEB]),
        ("2025-01-01", "2025-03-01", [_JAN, _FEB, _MAR]),
    ],
    ids=["time_of_day", "offset", "midnight_utc"],
)
def test_dwd_derived_monthly_values_are_stamped_at_the_first_of_their_month(
    default_settings: Settings,
    parameter: str,
    station_id: str,
    expected_values: dict[datetime.datetime, float],
    start: str,
    end: str,
    expected_months: list[datetime.datetime],
) -> None:
    """A monthly value carries the first day of its month at 00:00 UTC, whatever time the request names (GH-2679).

    The stamp and the months fetched used to be the request's start moved to the first of its month,
    keeping its time of day and offset, so a request for 2025-01-01T00:00+01:00 stamped the value of
    January with 2025-01-31 23:00 UTC.
    """
    request = DwdDerivedRequest(parameters=[parameter], start=start, end=end, settings=default_settings)
    values = _values_of(request, station_id=station_id)
    with (
        patch("wetterdienst.provider.dwd.derived.api.download_file", side_effect=_serve_derived_files),
        patch("wetterdienst.provider.dwd.derived.api.list_remote_files_fsspec", return_value=list(_DERIVED_FILES)),
    ):
        df = values.all().df
    assert df.get_column("timestamp").to_list() == expected_months
    assert df.get_column("value").to_list() == [expected_values[month] for month in expected_months]


# The two period files of one station that both carry 2024-05-05 08:00 and 09:00, in the layout DWD serves. The
# frames are aligned on station, timestamp and quality before any value, so the recent file's quality (100) sorts
# ahead of the historical one's (500) and a leftover sort would take the recent record; the historical one has a
# `-999` at 09:00 where the recent file has a reading, which must not be quietly filled from the later period.
_OVERLAPPING_PERIOD_FILES = {
    "https://example.invalid/historical.txt": (
        "STATIONS_ID;MESS_DATUM;QN_952;FG_DUETT;FG_UN_DUETT;eor\n"
        "      18001;2024050508;  500;  103;   10;eor\n"
        "      18001;2024050509;  500; -999;   10;eor\n"
    ),
    "https://example.invalid/recent.txt": (
        "STATIONS_ID;MESS_DATUM;QN_952;FG_DUETT;FG_UN_DUETT;eor\n"
        "      18001;2024050508;  100;    5;   10;eor\n"
        "      18001;2024050509;  100;    7;   10;eor\n"
    ),
}


@pytest.mark.parametrize(
    "periods",
    list(permutations([Period.HISTORICAL, Period.RECENT])),
    ids=lambda periods: "-".join(period.value for period in periods),
)
def test_dwd_derived_period_precedence_does_not_depend_on_the_order_of_the_periods(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    periods: tuple[Period, ...],
) -> None:
    """Where two periods report the same timestamp, the historical record wins, whatever order they are visited in.

    The request keeps its periods in a set, whose iteration order varies from one interpreter run to the next, and
    the values used to keep one row per timestamp in the order they had been read in (GH-2792).
    """
    monkeypatch.setattr(
        dwd_derived_api,
        "create_file_list_for_climate_derived",
        lambda _station_id, _dataset, period, _settings: pl.Series([f"https://example.invalid/{period.value}.txt"]),
    )
    monkeypatch.setattr(
        dwd_derived_api,
        "download_climate_derived_data",
        lambda files, _settings: [
            File(url=url, content=BytesIO(_OVERLAPPING_PERIOD_FILES[url].encode("latin-1")), status=200)
            for url in files
        ],
    )
    request = DwdDerivedRequest(parameters=[("hourly", "radiation_global")], periods=periods, settings=default_settings)
    # the order the periods are iterated in: a set takes the order of its hashes, a list the one it is given
    request.periods = list(periods)
    values = _values_of(request, station_id="18001")
    given_df = values._collect_station_parameter_or_dataset("18001", DwdDerivedMetadata.hourly.radiation_global)  # noqa: SLF001
    given_df = given_df.filter(pl.col("parameter") == "fg_duett").sort("timestamp")
    # the historical 103 over the recent 5, and its null over the recent 7: `_tidy_up_df` keeps the flag of a
    # reading that is a sentinel, with the text DWD wrote beside it
    assert given_df.get_column("value").to_list() == [103.0, None]
    assert given_df.get_column("quality_flags").to_list() == ["500", "500,raw:-999"]
