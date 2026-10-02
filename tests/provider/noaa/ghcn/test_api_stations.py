# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for NOAA GHCN stations."""

import datetime as dt
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.util.network import File


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
                "elevation": 10.1,
                "latitude": 17.1167,
                "longitude": -61.7833,
                "name": "ST JOHNS COOLIDGE FLD",
                "region": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "ACW00011647",
                "start_date": dt.datetime(1957, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 19.2,
                "latitude": 17.1333,
                "longitude": -61.7833,
                "name": "ST JOHNS",
                "region": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AE000041196",
                "start_date": dt.datetime(1944, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 34.0,
                "latitude": 25.333,
                "longitude": 55.517,
                "name": "SHARJAH INTER. AIRP",
                "region": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AEM00041194",
                "start_date": dt.datetime(1983, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 10.4,
                "latitude": 25.255,
                "longitude": 55.364,
                "name": "DUBAI INTL",
                "region": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AEM00041217",
                "start_date": dt.datetime(1983, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 26.8,
                "latitude": 24.433,
                "longitude": 54.651,
                "name": "ABU DHABI INTL",
                "region": None,
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(df.drop("end_date"), df_expected)


def test_noaa_ghcn_daily_stations_missing_elevation(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A station that `ghcnd-stations.txt` lists at -999.9, its missing value, has a null elevation (GH-2247).

    The rows are copied from `ghcnd-stations.txt` and `ghcnd-inventory.txt` as NOAA publishes them.
    """
    stations = (
        "ACW00011604  17.1167  -61.7833   10.1    ST JOHNS COOLIDGE FLD                       \n"
        "ASN00001011 -16.0497  124.9500 -999.9    PANTA DOWNS                                 \n"
    )
    inventory = "ACW00011604  17.1167  -61.7833 TMAX 1949 1949\nASN00001011 -16.0497  124.9500 PRCP 1966 1969\n"
    contents = {"ghcnd-stations.txt": stations, "ghcnd-inventory.txt": inventory}

    def fake_download_file(url: str, **_kwargs: object) -> File:
        content = contents[url.rsplit("/", 1)[-1]]
        return File(url=url, content=BytesIO(content.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all().df
    assert df.select("station_id", "elevation").rows() == [("ACW00011604", 10.1), ("ASN00001011", None)]
