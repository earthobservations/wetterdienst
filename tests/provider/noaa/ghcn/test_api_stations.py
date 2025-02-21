# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for NOAA GHCN stations."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest


@pytest.mark.remote
def test_noaa_ghcn_stations(default_settings: Settings) -> None:
    """Test fetching of NOAA GHCN stations."""
    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all().df.head(5)
    df_expected = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "ACW00011604",
                "start_date": dt.datetime(1949, 1, 1, tzinfo=ZoneInfo("UTC")),
                "height": 10.1,
                "latitude": 17.1167,
                "longitude": -61.7833,
                "name": "ST JOHNS COOLIDGE FLD",
                "state": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "ACW00011647",
                "start_date": dt.datetime(1957, 1, 1, tzinfo=ZoneInfo("UTC")),
                "height": 19.2,
                "latitude": 17.1333,
                "longitude": -61.7833,
                "name": "ST JOHNS",
                "state": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AE000041196",
                "start_date": dt.datetime(1944, 1, 1, tzinfo=ZoneInfo("UTC")),
                "height": 34.0,
                "latitude": 25.333,
                "longitude": 55.517,
                "name": "SHARJAH INTER. AIRP",
                "state": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AEM00041194",
                "start_date": dt.datetime(1983, 1, 1, tzinfo=ZoneInfo("UTC")),
                "height": 10.4,
                "latitude": 25.255,
                "longitude": 55.364,
                "name": "DUBAI INTL",
                "state": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AEM00041217",
                "start_date": dt.datetime(1983, 1, 1, tzinfo=ZoneInfo("UTC")),
                "height": 26.8,
                "latitude": 24.433,
                "longitude": 54.651,
                "name": "ABU DHABI INTL",
                "state": None,
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(df.drop("end_date"), df_expected)
