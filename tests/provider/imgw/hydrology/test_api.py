# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the IMGW hydrology API."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyRequest


def _expected_station(resolution: str) -> pl.DataFrame:
    """Provide expected DataFrame for station."""
    return pl.DataFrame(
        [
            {
                "resolution": resolution,
                "dataset": "hydrology",
                "station_id": "150190130",
                "start_date": None,
                "end_date": None,
                "latitude": 50.350278,
                "longitude": 19.185556,
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


@pytest.mark.remote
def test_imgw_hydrology_api_daily() -> None:
    """Test fetching of daily hydrology data."""
    request = ImgwHydrologyRequest(
        parameters=[("daily", "hydrology")],
        start_date="2010-08-01",
    ).filter_by_station_id("150190130")
    assert_frame_equal(request.df, _expected_station("daily"))
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
            "station_id": pl.Enum(["150190130"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["hydrology"]),
            "parameter": pl.Enum(["discharge", "stage"]),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected)


@pytest.mark.remote
def test_imgw_hydrology_api_monthly() -> None:
    """Test fetching of monthly hydrology data."""
    request = ImgwHydrologyRequest(
        parameters=[("monthly", "hydrology")],
        start_date="2010-06-01",
    ).filter_by_station_id("150190130")
    assert_frame_equal(request.df, _expected_station("monthly"))
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
            "station_id": pl.Enum(["150190130"]),
            "resolution": pl.Enum(["monthly"]),
            "dataset": pl.Enum(["hydrology"]),
            "parameter": pl.Enum(
                ["discharge_max", "discharge_mean", "discharge_min", "stage_max", "stage_mean", "stage_min"]
            ),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)


@pytest.mark.remote
def test_imgw_hydrology_api_daily_consolidated_yearly_file() -> None:
    """IMGW consolidated daily hydrology into one zip per year from 2023 onwards.

    2023's zip uses a semicolon-separated, unquoted CSV export; 2024's zip wraps each
    row in a broken extra pair of quotes. This exercises both, via the hydrological-year
    shift that maps calendar 2023-11-01 into the "2024" file.
    """
    request = ImgwHydrologyRequest(
        parameters=[("daily", "hydrology")],
        start_date="2023-11-01",
        end_date="2023-11-01",
    ).filter_by_station_id("149180020")
    values = request.values.all()
    df_expected = pl.DataFrame(
        [
            {
                "station_id": "149180020",
                "resolution": "daily",
                "dataset": "hydrology",
                "parameter": "discharge",
                "date": dt.datetime(2023, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 25.4,
                "quality": None,
            },
            {
                "station_id": "149180020",
                "resolution": "daily",
                "dataset": "hydrology",
                "parameter": "stage",
                "date": dt.datetime(2023, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 113.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.Enum(["149180020"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["hydrology"]),
            "parameter": pl.Enum(["discharge", "stage"]),
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected)


@pytest.mark.remote
def test_imgw_hydrology_api_monthly_recent_export_formats() -> None:
    """2023 and 2024 monthly hydrology exports each use a different CSV quirk (see api.py)."""
    for start_date, expected_max, expected_mean, expected_min in [
        ("2023-06-01", 50.6, 17.7, 9.76),
        ("2024-06-01", 216.0, 36.7, 16.7),
    ]:
        request = ImgwHydrologyRequest(
            parameters=[("monthly", "hydrology")],
            start_date=start_date,
        ).filter_by_station_id("149180020")
        values = request.values.all()
        discharge = values.df.filter(pl.col("parameter").cast(pl.String).str.starts_with("discharge")).sort("parameter")
        assert discharge.get_column("value").to_list() == [expected_max, expected_mean, expected_min]
