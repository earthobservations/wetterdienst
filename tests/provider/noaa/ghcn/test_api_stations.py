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


GHCNH_STATION_LIST = (
    "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
    "ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD   ANTIGUA (AUX.,,,78861,,AG\n"
    "AGM00060350,37.083,6.45,-999.0,,BOGUS ALGERIAN,,,60350,,DZ\n"
    "AOM00066116,-5.8667,13.4333,-999.9,,NOQUI,,,66116,,AO\n"
)
GHCND_STATIONS = "ACW00011604  17.1167  -61.7833   10.1    ST JOHNS COOLIDGE FLD                       \n"
GHCND_INVENTORY = "ACW00011604  17.1167  -61.7833 TMAX 1949 1949\n"


def _fake_ghcn_download_file(url: str, **_kwargs: object) -> File:
    """Serve the GHCN station lists from the fixtures in this module, by file name."""
    contents = {
        "ghcnh-station-list.csv": GHCNH_STATION_LIST,
        "ghcnd-stations.txt": GHCND_STATIONS,
        "ghcnd-inventory.txt": GHCND_INVENTORY,
    }
    content = contents[url.rsplit("/", 1)[-1]]
    return File(url=url, content=BytesIO(content.encode("utf8")), status=200)


def test_noaa_ghcn_hourly_stations_missing_elevation(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A station that `ghcnh-station-list.csv` lists at -999.9, its missing value, has a null elevation (GH-2260).

    The rows are copied from `ghcnh-station-list.csv` as NOAA publishes it. -999.0 is kept, as NOAA's
    GHCNh documentation names only -999.9 as missing.
    """
    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", _fake_ghcn_download_file)
    df = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=default_settings).all().df
    assert df.select("station_id", "elevation").rows() == [
        ("ACM00078861", 10.0),
        ("AGM00060350", -999.0),
        ("AOM00066116", None),
    ]


def test_noaa_ghcn_stations_hourly_and_daily(monkeypatch: pytest.MonkeyPatch, default_settings: Settings) -> None:
    """A request for both resolutions lists the stations of each, the hourly ones without dates (GH-2267).

    Only the daily list has an inventory, so only the daily stations have a start and end date.
    """
    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", _fake_ghcn_download_file)
    df = NoaaGhcnRequest(parameters=[("hourly", "data"), ("daily", "data")], settings=default_settings).all().df
    utc = ZoneInfo("UTC")
    assert df.select("resolution", "station_id", "start_date", "end_date", "elevation").rows() == [
        ("hourly", "ACM00078861", None, None, 10.0),
        ("hourly", "AGM00060350", None, None, -999.0),
        ("hourly", "AOM00066116", None, None, None),
        ("daily", "ACW00011604", dt.datetime(1949, 1, 1, tzinfo=utc), dt.datetime(1949, 12, 31, tzinfo=utc), 10.1),
    ]


def test_noaa_ghcn_hourly_stations_placeholder_elevation(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """The hourly list's 9999.0 and 8191.0 are null elevations, and the daily list's height stays (GH-2336).

    The rows are copied from `ghcnh-station-list.csv`, `ghcnd-stations.txt` and `ghcnd-inventory.txt`
    as NOAA publishes them. ELBE NO. 1 is a lightship in the North Sea, and the daily list puts
    DNEPRODZERJINSK at 148.0 m where the hourly list gives 9999.0.
    """
    contents = {
        "ghcnh-station-list.csv": (
            "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
            "GMMU0010434,54.02,8.22,8191.0,,ELBE NO. 1 GERMANY,,,10434,,DE\n"
            "UPM00033732,48.5,34.6,9999.0,,DNEPRODZERJINSK,,,33732,,UA\n"
        ),
        "ghcnd-stations.txt": "UPM00033732  48.5000   34.6000  148.0    DNEPRODZERJINSK                        33732\n",
        "ghcnd-inventory.txt": "UPM00033732  48.5000   34.6000 PRCP 1965 1990\n",
    }

    def fake_download_file(url: str, **_kwargs: object) -> File:
        content = contents[url.rsplit("/", 1)[-1]]
        return File(url=url, content=BytesIO(content.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=[("hourly", "data"), ("daily", "data")], settings=default_settings).all().df
    assert df.select("resolution", "station_id", "elevation").rows() == [
        ("hourly", "GMMU0010434", None),
        ("hourly", "UPM00033732", None),
        ("daily", "UPM00033732", 148.0),
    ]
