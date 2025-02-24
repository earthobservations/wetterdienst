# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the NOAA Global Historical Climatology Network (GHCN) API."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnMetadata, NoaaGhcnRequest


@pytest.mark.slow
@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        (dt.datetime(2015, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (dt.datetime(2015, 1, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (dt.datetime(2015, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (
            dt.datetime(2015, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2022, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
        ),
    ],
)
def test_api_amsterdam(start_date: dt.datetime, end_date: dt.datetime, default_settings: Settings) -> None:
    """Test fetching of Amsterdam weather data."""
    request = NoaaGhcnRequest(
        parameters=[NoaaGhcnMetadata.daily.data.temperature_air_mean_2m],
        start_date=start_date,
        end_date=end_date,
        settings=default_settings,
    ).filter_by_name("DE BILT")
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "NLM00006260",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2021, 1, 1, 23, tzinfo=ZoneInfo("UTC")),
                "value": 3.7,
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
    assert_frame_equal(
        given_df.filter(pl.col("date").eq(dt.datetime(2021, 1, 1, 23, tzinfo=ZoneInfo("UTC")))),
        expected_df,
    )
