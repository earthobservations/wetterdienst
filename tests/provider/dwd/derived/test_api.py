# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD derived data."""

import datetime
from collections.abc import Collection
from unittest.mock import patch
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal, assert_series_equal

from wetterdienst import Settings
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.derived import DwdDerivedMetadata, DwdDerivedRequest


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
        start_date=start_date,
        end_date=end_date,
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
    default_settings.ts_shape = "long"
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "heating_degreedays",
            "heating_degreedays",
        ),
        settings=default_settings,
        start_date=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
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
        "date",
        "value",
        "quality",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["00044"] * 3,
            "resolution": ["monthly"] * 3,
            "dataset": ["heating_degreedays"] * 3,
            "parameter": ["heating_degreedays"] * 3,
            "date": [
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 9, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "value": [
                12.3,
                98.5,
                93.0,
            ],
            "quality": [
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
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_recent_data_result_wide_single_parameter(
    default_settings: Settings,
) -> None:
    """Test for actual values (wide)."""
    default_settings.ts_shape = "wide"
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "heating_degreedays",
            "heating_degreedays",
        ),
        settings=default_settings,
        start_date=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
        periods=[
            "historical",
        ],
    ).filter_by_station_id(station_id="00044")
    given_df = request.values.all().df
    assert given_df.columns == [
        "station_id",
        "resolution",
        "dataset",
        "date",
        "heating_degreedays",
        "qn_heating_degreedays",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["00044"] * 3,
            "resolution": ["monthly"] * 3,
            "dataset": ["heating_degreedays"] * 3,
            "date": [
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 9, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "heating_degreedays": [
                12.3,
                98.5,
                93.0,
            ],
            "qn_heating_degreedays": [
                None,
                None,
                None,
            ],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "heating_degreedays": pl.Float64,
            "qn_heating_degreedays": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_recent_data_result_long_single_parameter_missing_month_heating_degree_days(
    default_settings: Settings,
) -> None:
    """Test for actual values (long), where no data exists for a month."""
    default_settings.ts_shape = "long"
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "heating_degreedays",
            "heating_degreedays",
        ),
        settings=default_settings,
        start_date=datetime.datetime(year=2023, month=3, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2023, month=5, day=1, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id(station_id="00044")
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
        {
            "station_id": ["00044"] * 2,
            "resolution": ["monthly"] * 2,
            "dataset": ["heating_degreedays"] * 2,
            "parameter": ["heating_degreedays"] * 2,
            "date": [
                datetime.datetime(2023, 3, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2023, 5, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "value": [
                430.7,
                201.9,
            ],
            "quality": [
                None,
                None,
            ],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_historical_data_result_long_single_parameter_missing_month_cooling_degree_hours(
    default_settings: Settings,
) -> None:
    """Test for actual values (long), where no data exists for a month."""
    default_settings.ts_shape = "long"
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "cooling_degreehours_13",
            "cooling_degreehours",
        ),
        settings=default_settings,
        start_date=datetime.datetime(year=2014, month=6, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2014, month=8, day=1, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id(station_id="00044")
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
        {
            "station_id": ["00044"] * 2,
            "resolution": ["monthly"] * 2,
            "dataset": ["cooling_degreehours_13"] * 2,
            "parameter": ["cooling_degreehours"] * 2,
            "date": [
                datetime.datetime(2014, 6, 1, tzinfo=ZoneInfo("UTC")),
                datetime.datetime(2014, 8, 1, tzinfo=ZoneInfo("UTC")),
            ],
            "value": [2240.6, 2549.5],
            "quality": [
                None,
                None,
            ],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_historical_data_result_long_multiple_reference_temperatures(
    default_settings: Settings,
) -> None:
    """Test for actual values (long)."""
    default_settings.ts_shape = "long"
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
        start_date=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
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
        "date",
        "value",
        "quality",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["00071"] * 8,
            "resolution": ["monthly"] * 8,
            "dataset": ["cooling_degreehours_13"] * 4 + ["cooling_degreehours_16"] * 4,
            "parameter": ["amount_cooling_hours", "amount_hours", "cooling_days", "cooling_degreehours"] * 2,
            "date": [
                datetime.datetime(2014, 7, 1, tzinfo=ZoneInfo("UTC")),
            ]
            * 8,
            "value": [
                624.0,
                744.0,
                29.0,
                3015.2,
                350.0,
                744.0,
                28.0,
                1505.7,
            ],
            "quality": [
                None,
            ]
            * 8,
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_recent_data_result_long_single_dataset(
    default_settings: Settings,
) -> None:
    """Test for actual values (long)."""
    default_settings.ts_shape = "long"
    request = DwdDerivedRequest(
        parameters=(
            "monthly",
            "heating_degreedays",
        ),
        settings=default_settings,
        start_date=datetime.datetime(year=2014, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2014, month=9, day=1, tzinfo=ZoneInfo("UTC")),
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
        "date",
        "value",
        "quality",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["00044"] * 9,
            "resolution": ["monthly"] * 9,
            "dataset": ["heating_degreedays"] * 9,
            "parameter": [
                "amount_days_per_month",
                "amount_days_per_month",
                "amount_days_per_month",
                "amount_heating_degreedays_per_month",
                "amount_heating_degreedays_per_month",
                "amount_heating_degreedays_per_month",
                "heating_degreedays",
                "heating_degreedays",
                "heating_degreedays",
            ],
            "date": [
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
                31.0,
                31.0,
                30.0,
                2.0,
                14.0,
                15.0,
                12.3,
                98.5,
                93.0,
            ],
            "quality": [
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
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
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
    default_settings.ts_shape = "long"
    request = DwdDerivedRequest(
        parameters=[
            (
                "monthly",
                "climate_correction_factor",
            ),
        ],
        settings=default_settings,
        start_date=datetime.datetime(year=2019, month=9, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2020, month=3, day=1, tzinfo=ZoneInfo("UTC")),
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
        "date",
        "value",
        "quality",
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["01067"] * 7,
            "resolution": ["monthly"] * 7,
            "dataset": ["climate_correction_factor"] * 7,
            "parameter": ["climate_correction_factor"] * 7,
            "date": [
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
            "quality": [
                None,
            ]
            * 7,
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="col",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_monthly_soil_ztumi_long(default_settings: Settings) -> None:
    """Test monthly soil ztumi dataset."""
    default_settings.ts_shape = "long"
    request = DwdDerivedRequest(
        parameters=[DwdDerivedMetadata.monthly.soil.ztumi],
        settings=default_settings,
        start_date=datetime.datetime(year=2024, month=5, day=1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2024, month=7, day=1, tzinfo=ZoneInfo("UTC")),
        periods=["historical"],
    ).filter_by_station_id(station_id="00150")

    expected_dict = [
        {
            "station_id": "00150",
            "resolution": "monthly",
            "dataset": "soil",
            "parameter": "ztumi",
            "date": datetime.datetime(2024, 5, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 0.0,
            "quality": None,
        },
        {
            "station_id": "00150",
            "resolution": "monthly",
            "dataset": "soil",
            "parameter": "ztumi",
            "date": datetime.datetime(2024, 6, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 0.0,
            "quality": None,
        },
        {
            "station_id": "00150",
            "resolution": "monthly",
            "dataset": "soil",
            "parameter": "ztumi",
            "date": datetime.datetime(2024, 7, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 0.0,
            "quality": None,
        },
    ]

    assert request.values.all().df.to_dicts() == expected_dict


@pytest.mark.remote
def test_dwd_hourly_radiation_surface_irradiance_long(default_settings: Settings) -> None:
    """Test hourly radiation surface irradiance dataset (placeholder expected_df)."""
    default_settings.ts_shape = "long"
    request = DwdDerivedRequest(
        parameters=[DwdDerivedMetadata.hourly.radiation_global.surface_irradiance],
        settings=default_settings,
        start_date=datetime.datetime(year=2024, month=5, day=5, hour=8, tzinfo=ZoneInfo("UTC")),
        end_date=datetime.datetime(year=2024, month=5, day=5, hour=13, tzinfo=ZoneInfo("UTC")),
        periods=["historical"],
    ).filter_by_station_id(station_id="18001")

    expected_dict = [
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "surface_irradiance",
            "date": datetime.datetime(2024, 5, 5, 8, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 103.0,
            "quality": 503.0,
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "surface_irradiance",
            "date": datetime.datetime(2024, 5, 5, 9, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 114.0,
            "quality": 503.0,
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "surface_irradiance",
            "date": datetime.datetime(2024, 5, 5, 10, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 74.0,
            "quality": 503.0,
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "surface_irradiance",
            "date": datetime.datetime(2024, 5, 5, 11, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 42.0,
            "quality": 503.0,
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "surface_irradiance",
            "date": datetime.datetime(2024, 5, 5, 12, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 26.0,
            "quality": 503.0,
        },
        {
            "station_id": "18001",
            "resolution": "hourly",
            "dataset": "radiation_global",
            "parameter": "surface_irradiance",
            "date": datetime.datetime(2024, 5, 5, 13, 0, tzinfo=ZoneInfo(key="UTC")),
            "value": 84.0,
            "quality": 503.0,
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
        start_date=start_date,
        end_date=end_date,
    ).filter_by_station_id(station_id="00044")

    values = request.values
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
        start_date=None,
        end_date=None,
    ).filter_by_station_id(station_id="00044")

    values = request.values
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
    ).filter_by_station_id(station_id="00044")

    values = request.values
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
    ).filter_by_station_id(station_id="00044")

    values = request.values
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
            ("monthly", "heating_degreedays", "heating_degreedays"),
        ],
        settings=default_settings,
    ).filter_by_station_id(station_id="00044")

    values = request.values
    rename_mapping = _column_name_mapping = {
        "Monatsgradtage": "heating_degreedays",
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
            "date": [input_date],
            "value": [12.3],
            "quality": [
                None,
            ],
        },
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
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
    ).filter_by_station_id(station_id="00044")

    values = request.values

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
    ).filter_by_station_id(station_id="00044")

    values = request.values
    start_date, end_date = values._get_date_range_for_year_starting_in_month(month_of_year)  # noqa: SLF001
    assert start_date == expected_start_date
    assert end_date == expected_end_date
