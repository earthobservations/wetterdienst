# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest


@pytest.mark.remote
def test_noaa_ghcn_stations(default_settings):
    df = NoaaGhcnRequest(parameter="daily", settings=default_settings).all().df.head(5)
    df_expected = pl.DataFrame(
        [
            {
                "station_id": "ACW00011604",
                "from_date": dt.datetime(1949, 1, 1, tzinfo=dt.timezone.utc),
                "height": 10.1,
                "latitude": 17.1167,
                "longitude": -61.7833,
                "name": "ST JOHNS COOLIDGE FLD",
                "state": None,
            },
            {
                "station_id": "ACW00011647",
                "from_date": dt.datetime(1957, 1, 1, tzinfo=dt.timezone.utc),
                "height": 19.2,
                "latitude": 17.1333,
                "longitude": -61.7833,
                "name": "ST JOHNS",
                "state": None,
            },
            {
                "station_id": "AE000041196",
                "from_date": dt.datetime(1944, 1, 1, tzinfo=dt.timezone.utc),
                "height": 34.0,
                "latitude": 25.333,
                "longitude": 55.517,
                "name": "SHARJAH INTER. AIRP",
                "state": None,
            },
            {
                "station_id": "AEM00041194",
                "from_date": dt.datetime(1983, 1, 1, tzinfo=dt.timezone.utc),
                "height": 10.4,
                "latitude": 25.255,
                "longitude": 55.364,
                "name": "DUBAI INTL",
                "state": None,
            },
            {
                "station_id": "AEM00041217",
                "from_date": dt.datetime(1983, 1, 1, tzinfo=dt.timezone.utc),
                "height": 26.8,
                "latitude": 24.433,
                "longitude": 54.651,
                "name": "ABU DHABI INTL",
                "state": None,
            },
        ],
        schema={
            "station_id": str,
            "from_date": pl.Datetime(time_zone="UTC"),
            "height": float,
            "latitude": float,
            "longitude": float,
            "name": str,
            "state": str,
        },
    )
    assert_frame_equal(df.drop(columns="to_date"), df_expected)
