# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for ECCC API."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from fsspec.exceptions import FSTimeoutError
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.provider.eccc.observation import EcccObservationRequest


@pytest.mark.xfail(raises=FSTimeoutError, strict=False, reason="ECCC server regularly times out")
@pytest.mark.remote
def test_eccc_api_stations(settings_convert_units_false: Settings) -> None:
    """Test fetching of ECCC stations."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start_date="1990-01-01",
        end_date="1990-01-02",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=(14,))
    given_df = request.df
    expected_df = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "14",
                "start_date": dt.datetime(1984, 1, 1, hour=8, tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime(1996, 11, 30, hour=8, tzinfo=ZoneInfo("UTC")),
                "latitude": 48.52,
                "longitude": -123.17,
                "height": 4.0,
                "name": "ACTIVE PASS",
                "state": "BC",
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.xfail(raises=FSTimeoutError, strict=False, reason="ECCC server regularly times out")
@pytest.mark.remote
def test_eccc_api_values(settings_convert_units_false: Settings) -> None:
    """Test fetching of ECCC data."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start_date="1979-11-02",
        end_date="1979-11-03",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("2",))
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "cooling_degree_day",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "heating_degree_day",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 11.7,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "precipitation_height",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "precipitation_height_liquid",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "snow_depth_new",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_max_2m",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 9.5,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 6.3,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_min_2m",
                "date": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 3.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.Enum(["2"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["data"]),
            "parameter": pl.Enum(
                [
                    "cooling_degree_day",
                    "heating_degree_day",
                    "precipitation_height",
                    "precipitation_height_liquid",
                    "snow_depth_new",
                    "temperature_air_max_2m",
                    "temperature_air_mean_2m",
                    "temperature_air_min_2m",
                ]
            ),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.xfail(raises=FSTimeoutError, strict=False, reason="ECCC server regularly times out")
@pytest.mark.remote
def test_eccc_degree_days_are_degree_days_not_day_counts(settings_convert_units_false: Settings) -> None:
    """Test that ECCC heating degree days hold a degree day value rather than a count of days.

    ECCC publishes the degree day total for the single day the record covers, ``18 - mean``, and not
    the number of days on which heating was required. The two were conflated once, which is what
    ``count_days_heating_degree`` used to mean here.
    """
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start_date="1979-11-02",
        end_date="1979-11-03",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("2",))
    df = request.values.all().df
    values = dict(df.select("parameter", "value").iter_rows())
    assert values["heating_degree_day"] == pytest.approx(18 - values["temperature_air_mean_2m"])
    # a count of days would be a whole number, and could never exceed the single day requested
    assert values["heating_degree_day"] > 1


@pytest.mark.xfail(raises=FSTimeoutError, strict=False, reason="ECCC server regularly times out")
@pytest.mark.remote
def test_eccc_hourly_returns_data(settings_convert_units_false: Settings) -> None:
    """Test that the hourly resolution returns data.

    It declared a copy of the *daily* field list, none of which the hourly collection publishes, so
    every hourly request came back empty. Station 4055 also exercises the station listing: it sits
    past the first 500 rows the OGC endpoint returns by default.
    """
    request = EcccObservationRequest(
        parameters=[("hourly", "data")],
        start_date="1972-06-01",
        end_date="1972-06-30",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("4055",))
    df = request.values.all().df
    assert not df.is_empty()
    values = dict(df.drop_nulls("value").select("parameter", "value").iter_rows())
    assert "temperature_air_mean_2m" in values
    # kPa, not hPa -- an hPa reading would be around 988
    pressure = df.filter(pl.col("parameter") == "pressure_air_site").get_column("value").drop_nulls()
    assert 80 < pressure.max() < 110
    # published in tens of degrees; without the decode every bearing sits inside 0..36
    direction = df.filter(pl.col("parameter") == "wind_direction").get_column("value").drop_nulls()
    assert direction.max() > 36


@pytest.mark.xfail(raises=FSTimeoutError, strict=False, reason="ECCC server regularly times out")
@pytest.mark.remote
def test_eccc_monthly_returns_data(settings_convert_units_false: Settings) -> None:
    """Test that the monthly resolution returns data.

    It declared bulk-CSV column headers the OGC API never returns, and crashed on `LOCAL_DATE`,
    which is "2023-06" for this collection rather than a full timestamp.
    """
    request = EcccObservationRequest(
        parameters=[("monthly", "data")],
        start_date="2015-01-01",
        end_date="2016-12-31",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("26",))
    df = request.values.all().df
    assert not df.is_empty()
    assert "temperature_air_mean_2m" in df.get_column("parameter").unique().to_list()
    # one row per month over the two years requested, so the year-month date parsed
    dates = df.get_column("date").unique()
    assert dates.len() == 24
