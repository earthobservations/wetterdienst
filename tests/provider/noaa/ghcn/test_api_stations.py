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
from wetterdienst.core.util import one_row_per_station
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
    GHCNh documentation names only -999.9 as missing; the undocumented 9999.0 and 8191.0 are nulled
    since GH-2336, and whether -999.0 should be too is GH-2352.
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
    DNEPRODZERJINSK at 148.0 m where the hourly list gives 9999.0. Requested at both resolutions,
    DNEPRODZERJINSK's hourly row takes the daily list's height.
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
    df = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=default_settings).all().df
    assert df.select("station_id", "elevation").rows() == [("GMMU0010434", None), ("UPM00033732", None)]
    df = NoaaGhcnRequest(parameters=[("hourly", "data"), ("daily", "data")], settings=default_settings).all().df
    assert df.select("resolution", "station_id", "elevation").rows() == [
        ("hourly", "GMMU0010434", None),
        ("hourly", "UPM00033732", 148.0),
        ("daily", "UPM00033732", 148.0),
    ]


# rows copied from `ghcnh-station-list.csv`, `ghcnd-stations.txt` and `ghcnd-inventory.txt` as NOAA
# publishes them (2026-10-04): the hourly list puts KUPINO at 1168.0 m, the daily one at 115.0 m; the
# daily list gives SMITHTON AERODROME no elevation (-999.9), the hourly one 107.3 m
GHCN_STATION_LISTS_DISAGREEING = {
    "ghcnh-station-list.csv": (
        "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        "ASN00091224,-40.8333,145.0833,107.3,,SMITHTON AERODROME,,,94952,,AU\n"
        'RSM00029706,54.37,77.28,1168.0,,"KUPINO,AMSG",,,29706,,RU\n'
    ),
    "ghcnd-stations.txt": (
        "ASN00091224 -40.8333  145.0833 -999.9    SMITHTON AERODROME                          \n"
        "RSM00029706  54.3670   77.2830  115.0    KUPINO                                 29706\n"
    ),
    "ghcnd-inventory.txt": (
        "ASN00091224 -40.8333  145.0833 PRCP 1961 1998\nRSM00029706  54.3670   77.2830 TMAX 1948 2025\n"
    ),
}


def _fake_ghcn_download_file_disagreeing(url: str, **_kwargs: object) -> File:
    """Serve the disagreeing GHCN station lists above, by file name."""
    content = GHCN_STATION_LISTS_DISAGREEING[url.rsplit("/", 1)[-1]]
    return File(url=url, content=BytesIO(content.encode("utf8")), status=200)


@pytest.mark.parametrize(
    "parameters",
    [
        pytest.param([("hourly", "data"), ("daily", "data")], id="hourly-first"),
        pytest.param([("daily", "data"), ("hourly", "data")], id="daily-first"),
    ],
)
def test_noaa_ghcn_stations_hourly_and_daily_take_the_daily_elevation(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, parameters: list[tuple[str, str]]
) -> None:
    """A station in both lists has the daily list's elevation on its hourly row, or its own where the daily has none.

    Whichever resolution the parameters name first, so the lookup by id reads the same elevation
    either way, and so does the interpolate/summarize walk whichever of a station's rows it ranks
    first (GH-2336).
    """
    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", _fake_ghcn_download_file_disagreeing)
    request = NoaaGhcnRequest(parameters=parameters, settings=default_settings)
    df = request.all().df
    assert sorted(df.select("resolution", "station_id", "elevation").rows()) == [
        ("daily", "ASN00091224", None),
        ("daily", "RSM00029706", 115.0),
        ("hourly", "ASN00091224", 107.3),
        ("hourly", "RSM00029706", 115.0),
    ]
    assert request._get_position_by_station_id("RSM00029706")[2] == 115.0  # noqa: SLF001
    assert request._get_position_by_station_id("ASN00091224")[2] == 107.3  # noqa: SLF001
    for ranked in (df, df.reverse()):
        assert sorted(one_row_per_station(ranked).select("station_id", "elevation").rows()) == [
            ("ASN00091224", 107.3),
            ("RSM00029706", 115.0),
        ]


@pytest.mark.parametrize(
    ("resolution", "expected"),
    [
        pytest.param("hourly", [("ASN00091224", 107.3), ("RSM00029706", 1168.0)], id="hourly"),
        pytest.param("daily", [("ASN00091224", None), ("RSM00029706", 115.0)], id="daily"),
    ],
)
def test_noaa_ghcn_stations_one_resolution_keeps_its_own_elevation(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    resolution: str,
    expected: list[tuple[str, float | None]],
) -> None:
    """A request for one resolution lists each station's elevation as that resolution's list gives it (GH-2336)."""
    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", _fake_ghcn_download_file_disagreeing)
    df = NoaaGhcnRequest(parameters=[(resolution, "data")], settings=default_settings).all().df
    assert df.select("station_id", "elevation").rows() == expected
