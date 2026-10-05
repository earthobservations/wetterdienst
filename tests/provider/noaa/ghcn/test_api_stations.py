# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for NOAA GHCN stations."""

import datetime as dt
import logging
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.core.util import one_row_per_station
from wetterdienst.exceptions import LocationOutOfRangeError
from wetterdienst.provider.noaa.ghcn import NoaaGhcnMetadata, NoaaGhcnRequest
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
    """A station that `ghcnh-station-list.csv` lists at -999.9 or -999.0 has a null elevation (GH-2260, GH-2352).

    The rows are copied from `ghcnh-station-list.csv` as NOAA publishes it. NOAA's GHCNh
    documentation names only -999.9 as missing, but -999.0, on BOGUS ALGERIAN and 92 other rows, is
    a placeholder too.
    """
    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", _fake_ghcn_download_file)
    df = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=default_settings).all().df
    assert df.select("station_id", "elevation").rows() == [
        ("ACM00078861", 10.0),
        ("AGM00060350", None),
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
        ("hourly", "AGM00060350", None, None, None),
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


def test_noaa_ghcn_daily_stations_brazilian_zero_elevation(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A Brazilian (BR0) station the daily list puts at 0.0 has a null elevation; a 0.0 elsewhere stays (GH-2362).

    The rows are copied from `ghcnd-stations.txt` and `ghcnd-inventory.txt` as NOAA publishes them
    (2026-10-04). ALFENAS lies at about 880 m in Minas Gerais; DE KOOG is on the Dutch island of Texel.
    """
    contents = {
        "ghcnd-stations.txt": (
            "BR002145042 -21.4500  -45.9400    0.0    ALFENAS                                     \n"
            "NLE00101883  53.1000    4.7667    0.0    DE KOOG                                     \n"
        ),
        "ghcnd-inventory.txt": (
            "BR002145042 -21.4500  -45.9400 PRCP 1983 1999\nNLE00101883  53.1000    4.7667 PRCP 1950 2026\n"
        ),
    }

    def fake_download_file(url: str, **_kwargs: object) -> File:
        content = contents[url.rsplit("/", 1)[-1]]
        return File(url=url, content=BytesIO(content.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all().df
    assert df.select("station_id", "elevation").rows() == [("BR002145042", None), ("NLE00101883", 0.0)]


# rows copied from `ghcnh-station-list.csv`, `ghcnd-stations.txt` and `ghcnd-inventory.txt` as NOAA
# publishes them (2026-10-04). MXM00076840 is ARRIAGA on the Chiapas coast in the hourly list (and in
# its hourly data), TEMOSACHI in Chihuahua, 2007 km away, in the daily one. GORYACHKOVKA is 229.0 m
# in the hourly list and 0.0 m in the daily one, 9.4 km apart. The reef light KELP REEFS has no
# elevation in the hourly list (-999.9) and 0.0 m in the daily one, at the same place
GHCNH_FAR_APART_OR_ZERO = (
    "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
    "CAN01013998,48.548,-123.237,-999.9,,KELP REEFS,,,,CWZO,CA\n"
    "MXM00076840,16.2333,-93.9,48.0,,ARRIAGA  CHIS.,,,76840,,MX\n"
    "UPM00033676,48.333,28.75,229.0,,GORYACHKOVKA,,,33676,,UA\n"
)
GHCND_STATIONS_FAR_APART_OR_ZERO = (
    "CAN01013998  48.5477 -123.2370    0.0 BC KELP REEFS                                  \n"
    "MXM00076840  28.9500 -107.8167 1931.8    TEMOSACHI (OBS)                        76840\n"
    "UPM00033676  48.3670   28.8670    0.0    GORYACHKOVKA                           33676\n"
)
GHCND_INVENTORY_FAR_APART_OR_ZERO = (
    "CAN01013998  48.5477 -123.2370 WDFG 2018 2026\n"
    "MXM00076840  28.9500 -107.8167 TMAX 1961 2026\n"
    "UPM00033676  48.3670   28.8670 TMAX 1979 1984\n"
)


@pytest.mark.parametrize(
    "parameters",
    [
        pytest.param([("hourly", "data"), ("daily", "data")], id="hourly-first"),
        pytest.param([("daily", "data"), ("hourly", "data")], id="daily-first"),
    ],
)
@pytest.mark.parametrize(
    "ghcnh_station_list",
    [
        pytest.param(GHCNH_FAR_APART_OR_ZERO, id="as-listed"),
        # GORYACHKOVKA's hourly row moved onto the daily list's position, so that the 5 km rule
        # passes it and only the 0.0 rule keeps its height
        pytest.param(GHCNH_FAR_APART_OR_ZERO.replace("48.333,28.75,", "48.367,28.867,"), id="at-daily-position"),
    ],
)
def test_noaa_ghcn_stations_hourly_and_daily_keep_their_own_elevation(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    parameters: list[tuple[str, str]],
    ghcnh_station_list: str,
) -> None:
    """A station the lists put over 5 km apart, or at 0.0 m in the daily one, keeps its hourly height (GH-2336).

    ARRIAGA's hourly row is not given TEMOSACHI's 1931.8 m, and GORYACHKOVKA's not the daily list's
    0.0 m (GH-2362), in either order of the parameters. KELP REEFS, which the hourly list gives no
    height, takes the daily 0.0 m.
    """
    contents = {
        "ghcnh-station-list.csv": ghcnh_station_list,
        "ghcnd-stations.txt": GHCND_STATIONS_FAR_APART_OR_ZERO,
        "ghcnd-inventory.txt": GHCND_INVENTORY_FAR_APART_OR_ZERO,
    }

    def fake_download_file(url: str, **_kwargs: object) -> File:
        content = contents[url.rsplit("/", 1)[-1]]
        return File(url=url, content=BytesIO(content.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=parameters, settings=default_settings).all().df
    assert sorted(df.select("resolution", "station_id", "elevation").rows()) == [
        ("daily", "CAN01013998", 0.0),
        ("daily", "MXM00076840", 1931.8),
        ("daily", "UPM00033676", 0.0),
        ("hourly", "CAN01013998", 0.0),
        ("hourly", "MXM00076840", 48.0),
        ("hourly", "UPM00033676", 229.0),
    ]


# rows copied from `ghcnh-station-list.csv` as NOAA publishes it (2026-10-04). BOGUS ARGENTINEAN and
# NAME AND LOC UNKN are listed at 0.0, 0.0; BOGUS AUSTRIAN at 47.117, 13.733, between MARIAPFARR and
# MAUTERNDORF. GREENWICH ROYAL OBSERVATORY (longitude 0.0) and PONTIANAK BORNEO (latitude 0.0) are
# real places on the prime meridian and the equator
GHCNH_WITHOUT_POSITION = (
    "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
    "ARM00087500,0.0,0.0,-999.0,,BOGUS ARGENTINEAN,,,87500,,AR\n"
    "ARM00087869,0.0,0.0,-999.0,,NAME AND LOC UNKN,,,87869,,AR\n"
    "AUM00011158,47.117,13.733,-999.0,,BOGUS AUSTRIAN,,,11158,,AT\n"
    "AUM00011162,47.1333,13.6833,1115.0,,MAUTERNDORF,,,11162,,AT\n"
    "AUM00011348,47.15,13.75,1151.0,,MARIAPFARR,,,11348,,AT\n"
    "GHU00065408,4.88,-1.77,8.0,,TAKORADI GHANA,,,,,GH\n"
    "IDU00096583,0.0,109.33,3.0,,PONTIANAK BORNEO,,,,,ID\n"
    "UKU68-00010,51.48,0.0,48.5,,GREENWICH ROYAL OBSERVATORY,,,,,GB\n"
)
GHCNH_WITHOUT_POSITION_IDS = {"ARM00087500", "ARM00087869", "AUM00011158"}


def _ghcnh_hourly_data(station_id: str) -> str:
    """Write a GHCNh data file of one row, at 1938-01-02 06:00, giving only the temperature.

    The -11.1 degC is BOGUS AUSTRIAN's first reading as `GHCNh_AUM00011158_por.psv` gives it.
    """
    parameters = [parameter.name_original for parameter in NoaaGhcnMetadata.hourly.data]
    columns = ["STATION", "DATE", *parameters]
    row = {"STATION": station_id, "DATE": "1938-01-02T06:00:00", "temperature": "-11.1"}
    return "|".join(columns) + "\n" + "|".join(row.get(column, "") for column in columns) + "\n"


def _fake_ghcn_download_file_without_position(url: str, **_kwargs: object) -> File:
    """Serve the hourly list above, and a data file for each of its stations, by file name."""
    file_name = url.rsplit("/", 1)[-1]
    if file_name == "ghcnh-station-list.csv":
        content = GHCNH_WITHOUT_POSITION
    else:
        content = _ghcnh_hourly_data(file_name.removeprefix("GHCNh_").removesuffix("_por.psv"))
    return File(url=url, content=BytesIO(content.encode("utf8")), status=200)


def test_noaa_ghcn_hourly_stations_without_position(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A station the hourly list puts at 0.0, 0.0, or names BOGUS, has no position (GH-2380).

    Only 0.0 on both axes is no position: a station on the equator or the prime meridian keeps its
    own.
    """
    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", _fake_ghcn_download_file_without_position)
    df = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=default_settings).all().df
    assert df.select("station_id", "latitude", "longitude").rows() == [
        ("ARM00087500", None, None),
        ("ARM00087869", None, None),
        ("AUM00011158", None, None),
        ("AUM00011162", 47.1333, 13.6833),
        ("AUM00011348", 47.15, 13.75),
        ("GHU00065408", 4.88, -1.77),
        ("IDU00096583", 0.0, 109.33),
        ("UKU68-00010", 51.48, 0.0),
    ]


@pytest.mark.parametrize(
    ("latlon", "nearest"),
    [
        pytest.param((47.117, 13.733), "AUM00011348", id="bogus-austrian"),
        pytest.param((0.0, 0.0), "GHU00065408", id="null-island"),
    ],
)
def test_noaa_ghcn_hourly_stations_without_position_not_ranked(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    latlon: tuple[float, float],
    nearest: str,
) -> None:
    """No distance search picks a station without a position (GH-2380).

    A rank search put BOGUS AUSTRIAN first at its listed position, and the two stations listed at
    0.0, 0.0 first there. Without a position, a rank search leaves them out rather than sorting
    their null distance first, and neither a search by distance nor one by bounding box picks them.
    """
    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", _fake_ghcn_download_file_without_position)
    request = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=default_settings)
    ranked = request.filter_by_rank(latlon=latlon, rank=2).df
    # MARIAPFARR 3.9 km from BOGUS AUSTRIAN's listed position, TAKORADI GHANA 577 km from 0.0, 0.0
    assert ranked.get_column("station_id").first() == nearest
    # the five stations with a position, each with a distance
    assert ranked.height == 5
    assert GHCNH_WITHOUT_POSITION_IDS.isdisjoint(ranked.get_column("station_id"))
    assert ranked.get_column("distance").null_count() == 0
    nearby = request.filter_by_distance(latlon=latlon, distance=20000).df
    assert GHCNH_WITHOUT_POSITION_IDS.isdisjoint(nearby.get_column("station_id"))
    everywhere = request.filter_by_bbox(left=-180, bottom=-90, right=180, top=90).df
    assert GHCNH_WITHOUT_POSITION_IDS.isdisjoint(everywhere.get_column("station_id"))


@pytest.mark.parametrize("station_id", sorted(GHCNH_WITHOUT_POSITION_IDS))
def test_noaa_ghcn_hourly_stations_without_position_fetched_by_id(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, station_id: str
) -> None:
    """A station without a position is still listed and its values fetched by id (GH-2380).

    Its GeoJSON feature has a null geometry, and an estimate at its position is refused by name
    rather than failing on the missing coordinates.
    """
    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", _fake_ghcn_download_file_without_position)
    request = NoaaGhcnRequest(
        parameters=[NoaaGhcnMetadata.hourly.data.temperature_air_mean_2m],
        start_date=dt.datetime(1938, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(1938, 1, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    stations = request.filter_by_station_id(station_id)
    assert stations.df.select("station_id", "latitude", "longitude").rows() == [(station_id, None, None)]
    (feature,) = stations.to_ogc_feature_collection()["data"]["features"]
    assert feature["geometry"] is None
    values = stations.values.all().df
    assert values.select("station_id", "timestamp", "value").rows() == [
        (station_id, dt.datetime(1938, 1, 2, 6, tzinfo=ZoneInfo("UTC")), -11.1),
    ]
    with pytest.raises(LocationOutOfRangeError, match=f"station {station_id} has no position"):
        request.interpolate_by_station_id(station_id)
    with pytest.raises(LocationOutOfRangeError, match=f"station {station_id} has no position"):
        request.summarize_by_station_id(station_id)


@pytest.mark.parametrize(
    "parameters",
    [
        pytest.param([("hourly", "data"), ("daily", "data")], id="hourly-first"),
        pytest.param([("daily", "data"), ("hourly", "data")], id="daily-first"),
    ],
)
def test_noaa_ghcn_stations_position_by_id_from_the_row_that_has_one(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, parameters: list[tuple[str, str]]
) -> None:
    """A station whose hourly row has no position takes its daily row's, whichever is named first (GH-2380).

    No id in the lists has this today -- BOGUS AUSTRIAN is not in the daily list -- so the daily row
    is made up, at the position the hourly list gives.
    """
    contents = {
        "ghcnh-station-list.csv": GHCNH_WITHOUT_POSITION,
        "ghcnd-stations.txt": "AUM00011158  47.1170   13.7330 1100.0    BOGUS AUSTRIAN                         11158\n",
        "ghcnd-inventory.txt": "AUM00011158  47.1170   13.7330 TMAX 1938 1943\n",
    }

    def fake_download_file(url: str, **_kwargs: object) -> File:
        content = contents[url.rsplit("/", 1)[-1]]
        return File(url=url, content=BytesIO(content.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    request = NoaaGhcnRequest(parameters=parameters, settings=default_settings)
    assert request._get_position_by_station_id("AUM00011158") == (47.117, 13.733, 1100.0)  # noqa: SLF001


def test_noaa_ghcn_daily_values_time_zone_from_the_row_that_has_a_position(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A station's daily values find their time zone though its hourly row, named first, has no position (GH-2380).

    The daily reader puts a day's midnight in the station's own time zone, which it looks up by
    position. As above, the daily row is made up; the daily reading is -5.0 degC.
    """
    contents = {
        "ghcnh-station-list.csv": GHCNH_WITHOUT_POSITION,
        "ghcnd-stations.txt": "AUM00011158  47.1170   13.7330 1100.0    BOGUS AUSTRIAN                         11158\n",
        "ghcnd-inventory.txt": "AUM00011158  47.1170   13.7330 TMAX 1938 1943\n",
        "AUM00011158.csv": (
            '"STATION","DATE","LATITUDE","LONGITUDE","ELEVATION","NAME","TMAX","TMAX_ATTRIBUTES"\n'
            '"AUM00011158","1938-01-02","47.117","13.733","1100.0","BOGUS AUSTRIAN","  -50",",,E"\n'
        ),
        "GHCNh_AUM00011158_por.psv": _ghcnh_hourly_data("AUM00011158"),
    }

    def fake_download_file(url: str, **_kwargs: object) -> File:
        content = contents[url.rsplit("/", 1)[-1]]
        return File(url=url, content=BytesIO(content.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    request = NoaaGhcnRequest(
        parameters=[
            NoaaGhcnMetadata.hourly.data.temperature_air_mean_2m,
            NoaaGhcnMetadata.daily.data.temperature_air_max_2m,
        ],
        settings=default_settings,
    )
    df = request.filter_by_station_id("AUM00011158").values.all().df
    # midnight in Vienna, an hour ahead of UTC in January 1938
    assert sorted(df.select(pl.col("resolution").cast(pl.String), "timestamp", "value").rows()) == [
        ("daily", dt.datetime(1938, 1, 1, 23, tzinfo=ZoneInfo("UTC")), -5.0),
        ("hourly", dt.datetime(1938, 1, 2, 6, tzinfo=ZoneInfo("UTC")), -11.1),
    ]


def test_noaa_ghcn_rank_without_any_position_says_so(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    """A rank search over stations of which none has a position finds none, and says so (GH-2380)."""
    station_list = "\n".join(GHCNH_WITHOUT_POSITION.splitlines()[:4]) + "\n"

    def fake_download_file(url: str, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(station_list.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    request = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=default_settings)
    assert request.all().df.get_column("station_id").to_list() == sorted(GHCNH_WITHOUT_POSITION_IDS)
    with caplog.at_level(logging.INFO):
        ranked = request.filter_by_rank(latlon=(47.117, 13.733), rank=1)
    assert ranked.df.is_empty()
    assert "None of the stations has a position to be ranked by" in caplog.text
