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
from wetterdienst.provider.noaa.ghcn.api import GHCND_WEST_LONGITUDE_STATIONS
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
                "start_timestamp": dt.datetime(1949, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 10.1,
                "latitude": 17.1167,
                "longitude": -61.7833,
                "name": "ST JOHNS COOLIDGE FLD",
                "region": None,
                "wmo_id": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "ACW00011647",
                "start_timestamp": dt.datetime(1957, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 19.2,
                "latitude": 17.1333,
                "longitude": -61.7833,
                "name": "ST JOHNS",
                "region": None,
                "wmo_id": None,
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AE000041196",
                "start_timestamp": dt.datetime(1944, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 34.0,
                "latitude": 25.333,
                "longitude": 55.517,
                "name": "SHARJAH INTER. AIRP",
                "region": None,
                "wmo_id": "41196",
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AEM00041194",
                "start_timestamp": dt.datetime(1983, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 10.4,
                "latitude": 25.255,
                "longitude": 55.364,
                "name": "DUBAI INTL",
                "region": None,
                "wmo_id": "41194",
            },
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "AEM00041217",
                "start_timestamp": dt.datetime(1983, 1, 1, tzinfo=ZoneInfo("UTC")),
                "elevation": 26.8,
                "latitude": 24.433,
                "longitude": 54.651,
                "name": "ABU DHABI INTL",
                "region": None,
                "wmo_id": "41217",
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
            "wmo_id": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(df.drop("end_timestamp"), df_expected)


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


def _serve_ghcnd(monkeypatch: pytest.MonkeyPatch, stations: str, inventory: str) -> None:
    contents = {"ghcnd-stations.txt": stations, "ghcnd-inventory.txt": inventory}

    def fake_download_file(url: str, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(contents[url.rsplit("/", 1)[-1]].encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)


def test_noaa_ghcn_daily_stations_west_longitude(monkeypatch: pytest.MonkeyPatch, default_settings: Settings) -> None:
    """Bordeaux, Caen and Valencia are west of Greenwich whichever sign the list gives (GH-2645).

    The rows are copied from `ghcnd-stations.txt` and `ghcnd-inventory.txt` as NOAA publishes them: an east
    longitude of 0.6914, 0.4558 and 0.3664 where the other catalogues have -0.70, -0.456 and -0.38. Tarbes,
    at 0.0, and Hamburg, east of Greenwich, are left as listed.
    """
    stations = (
        "FR000007510  44.8306    0.6914   47.0    BORDEAUX-MERIGNAC                      07510\n"
        "FRE00104044  49.1800    0.4558   67.0    CAEN-CARPIQUET                         07027\n"
        "FRE00104116  43.1881    0.0000  360.0    TARBES - OSSUN                         07621\n"
        "GM000010147  53.6350    9.9900   11.0    HAMBURG FUHLSBUETTEL           GSN     10147\n"
        "SP000008416  39.4806    0.3664   11.0    VALENCIA                               08285\n"
    )
    inventory = (
        "FR000007510  44.8306    0.6914 TMAX 1906 2026\n"
        "FRE00104044  49.1800    0.4558 TMAX 1945 2026\n"
        "FRE00104116  43.1881    0.0000 TMAX 1946 2026\n"
        "GM000010147  53.6350    9.9900 TMAX 1891 2026\n"
        "SP000008416  39.4806    0.3664 TMAX 1935 2026\n"
    )
    _serve_ghcnd(monkeypatch, stations, inventory)
    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all().df
    assert df.sort("station_id").select("station_id", "latitude", "longitude").rows() == [
        ("FR000007510", 44.8306, -0.6914),
        ("FRE00104044", 49.18, -0.4558),
        ("FRE00104116", 43.1881, 0.0),
        ("GM000010147", 53.635, 9.99),
        ("SP000008416", 39.4806, -0.3664),
    ]


def test_noaa_ghcn_daily_stations_west_longitude_corrected_list(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A list in which NOAA has put the sign right is read as it is, not turned east again (GH-2645).

    The row is the Bordeaux row of `ghcnd-stations.txt` with the sign of its longitude restored.
    """
    stations = "FR000007510  44.8306   -0.6914   47.0    BORDEAUX-MERIGNAC                      07510\n"
    inventory = "FR000007510  44.8306   -0.6914 TMAX 1906 2026\n"
    _serve_ghcnd(monkeypatch, stations, inventory)
    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all().df
    assert df.select("station_id", "longitude").rows() == [("FR000007510", -0.6914)]


GHCND_LOST_SIGN_ROWS = (
    "FRE00106203  43.9094    0.5003   59.0    MONT-DE-MARSAN                         07607",
    "SPE00101035  38.2828    0.5706   43.0    ALICANTE EL ALTET                           ",
    "SPE00101043  38.3725    0.4942   81.0    ALICANTE                                    ",
    "SPE00119999  39.9500    0.0714   35.0    CASTELLON                              08286",
    "SPE00120008  39.9892    0.0406   25.0    CASTELLON DE LA PLANA                       ",
    "SPE00120161  42.0831    0.3264  541.0    HUESCA                                      ",
    "SPE00120341  37.7889    0.8031    4.0    MURCIA/SAN JAVIER                           ",
    "SPE00120584  39.4867    0.4731   69.0    VALENCIA/AEROPUERTO                         ",
    "UK000003377  53.1658    0.5239   68.0    WADDINGTON                     GSN     03377",
    "UKE00105915  51.5608    0.1789  137.0    HAMPSTEAD                                   ",
    "UKE00105919  50.7808    0.6758    7.0    BOGNOR REGIS                                ",
    "UKE00105926  50.7839    0.9839    4.0    HAYLING ISLAND                              ",
    "UKE00107650  51.4789    0.4489   25.0    HEATHROW                                    ",
    "UKE00156848  53.0306    0.5017   63.0    CRANWELL                                    ",
    "UKE00156888  52.0142    0.5942   89.0    WOBURN                                      ",
    "UKW00015034  52.3500    0.1167   40.2    WYTON                                       ",
    "UKW00015035  53.1667    0.5167   72.2    WADDINGTON                                  ",
    "UKW00015041  53.3667    0.6833   21.0    STURGATE                                    ",
    "UV000005503  12.3500    1.5200  304.0    OUAGADOUGOU                                 ",
    "UVM00065505  12.4670    3.4830  300.0    DEDOUGOU                               65505",
    "AGE00135039  35.7297    0.6500   50.0    ORAN-HOPITAL MILITAIRE                      ",
    "AGE00147714  35.7700    0.8000   78.0    ORAN-CAP FALCON                             ",
    "AGE00147717  35.2000    0.6300  476.0    SIDI-BEL-ABBES                              ",
    "FRE00104957  43.2481    0.1550  312.0    ESPOEY                                      ",
    "UKE00100808  53.7667    0.3667    2.0    HULL                                        ",
    "UKE00105894  54.1050    0.6417  175.0    HIGH MOWTHORPE                              ",
    "UKE00105900  51.8067    0.3581  128.0    ROTHAMSTED                                  ",
    "UKE00156864  52.4008    0.2353   41.0    MONKS WOOD                                  ",
    "UKE00156884  51.3103    0.4744   38.0    WISLEY                                      ",
    "SP000007038  37.9769    0.7106    1.0    TORREVIEJA                             08433",
    "UKE00105927  51.1767    0.8481  115.0    ALICE HOLT LODGE                            ",
    "UKW00015014  52.3833    0.4167   74.1    MOLESWORTH                                  ",
    "UKW00015015  52.3000    0.5333   92.0    CHELVESTON                                  ",
    "UKW00015018  52.1000    0.0500   30.2    BASSINGBOURN                                ",
    "UKW00015033  52.3667    0.2167   49.1    HUNTINGTON                                  ",
)


def test_noaa_ghcn_daily_stations_west_longitude_more_stations(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """The 35 stations of GH-2886 are read west of Greenwich, as the other catalogues have them.

    The rows are copied from `ghcnd-stations.txt` as NOAA publishes them, each with an east longitude where the
    station lies west of it. Lowestoft, which does lie east of Greenwich, is left as listed (GH-2886).
    """
    lowestoft = "UKE00105899  52.4889    1.7500   25.0    LOWESTOFT                                   "
    stations = "\n".join((*GHCND_LOST_SIGN_ROWS, lowestoft)) + "\n"
    inventory = "".join(
        f"{row[:11]} {row[12:20]} {row[21:30]} TMAX 1950 2026\n" for row in (*GHCND_LOST_SIGN_ROWS, lowestoft)
    )
    _serve_ghcnd(monkeypatch, stations, inventory)
    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all().df
    expected = {row[:11]: -float(row[21:30]) for row in GHCND_LOST_SIGN_ROWS}
    expected["UKE00105899"] = 1.75
    assert dict(df.select("station_id", "longitude").rows()) == expected
    assert df.filter(pl.col("station_id") == "UKE00156848").select("latitude").item() == 53.0306
    # every id of the table is pinned by a raw row, here or in the Bordeaux, Caen and Valencia test above
    assert set(GHCND_WEST_LONGITUDE_STATIONS) == {row[:11] for row in GHCND_LOST_SIGN_ROWS} | {
        "FR000007510",
        "FRE00104044",
        "SP000008416",
    }


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
    assert df.select("resolution", "station_id", "start_timestamp", "end_timestamp", "elevation").rows() == [
        ("hourly", "ACM00078861", None, None, 10.0),
        ("hourly", "AGM00060350", None, None, None),
        ("hourly", "AOM00066116", None, None, None),
        ("daily", "ACW00011604", dt.datetime(1949, 1, 1, tzinfo=utc), dt.datetime(1949, 12, 31, tzinfo=utc), 10.1),
    ]


def test_noaa_ghcn_daily_station_reporting_this_year_has_no_end(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A station whose last inventory year is this one has a null end, not 31 December, which is ahead (GH-2643).

    The inventory gives only the year of the last observation, copied here as NOAA publishes it
    (`GM000010147  53.6350    9.9900 TMAX 1891 2026`). A station that stopped in an earlier year, last year
    included, ends on 31 December of that year, as it did.
    """
    this_year = dt.datetime.now(dt.UTC).year
    contents = {
        "ghcnd-stations.txt": (
            "GM000010147  53.6350    9.9900   11.0    HAMBURG FUHLSBUETTEL           GSN     10147\n"
            "ACW00011604  17.1167  -61.7833   10.1    ST JOHNS COOLIDGE FLD                       \n"
            "ACW00011647  17.1333  -61.7833   19.2    ST JOHNS                                    \n"
        ),
        "ghcnd-inventory.txt": (
            f"GM000010147  53.6350    9.9900 TMAX 1891 {this_year}\n"
            f"GM000010147  53.6350    9.9900 PRCP 1891 {this_year - 1}\n"
            "ACW00011604  17.1167  -61.7833 TMAX 1949 1949\n"
            f"ACW00011647  17.1333  -61.7833 TMAX 1957 {this_year - 1}\n"
        ),
    }

    def fake_download_file(url: str, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(contents[url.rsplit("/", 1)[-1]].encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all().df
    utc = ZoneInfo("UTC")
    assert df.select("station_id", "start_timestamp", "end_timestamp").rows() == [
        ("GM000010147", dt.datetime(1891, 1, 1, tzinfo=utc), None),
        ("ACW00011604", dt.datetime(1949, 1, 1, tzinfo=utc), dt.datetime(1949, 12, 31, tzinfo=utc)),
        ("ACW00011647", dt.datetime(1957, 1, 1, tzinfo=utc), dt.datetime(this_year - 1, 12, 31, tzinfo=utc)),
    ]


def test_noaa_ghcn_daily_stations_without_an_inventory_line_are_left_out(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    """A station of the list that the inventory has no line for has no data, and is not a station of the catalogue.

    The two station rows are copied as NOAA publishes them (2026-10-22): `CAN03010010` has no line in the
    inventory and its `access/CAN03010010.csv` is a 404, as are those of 145 more. `USC00144840` has a file, with
    PRCP flagged `Z` in every row, and no inventory line. 147 of the 133,039 stations are in this case (GH-3260).
    """
    _serve_ghcnd(
        monkeypatch,
        stations=(
            "GM000010147  53.6350    9.9900   11.0    HAMBURG FUHLSBUETTEL           GSN     10147\n"
            "CAN03010010  54.2833 -112.9667  664.0 AB ABEE AGDM                              71285\n"
            "USC00144840  39.2911  -96.2303  290.5 KS LOUISVILLE 5 NE                             \n"
        ),
        inventory="GM000010147  53.6350    9.9900 TMAX 1891 1990\n",
    )
    request = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings)
    assert request.all().df.get_column("station_id").to_list() == ["GM000010147"]
    with caplog.at_level(logging.INFO):
        found = request.filter_by_station_id(["CAN03010010", "USC00144840"]).df
    assert found.is_empty()
    assert "No station with station_id CAN03010010, USC00144840" in caplog.text


def test_noaa_ghcn_stations_hourly_and_daily_without_an_inventory_line_keep_the_hourly_row(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A station with hourly data and no inventory line keeps its hourly row, with the daily list's elevation (GH-3260).

    Only its daily row is left out: the hourly list writes `CAN03010010` at -999.9 where the daily list gives
    664.0, and the elevation is settled before the daily row goes.
    """
    contents = {
        "ghcnh-station-list.csv": (
            "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
            "CAN03010010,54.2833,-112.9667,-999.9,AB,ABEE AGDM,,,,,CA\n"
        ),
        "ghcnd-stations.txt": "CAN03010010  54.2833 -112.9667  664.0 AB ABEE AGDM                              71285\n",
        "ghcnd-inventory.txt": "GM000010147  53.6350    9.9900 TMAX 1891 1990\n",
    }

    def fake_download_file(url: str, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(contents[url.rsplit("/", 1)[-1]].encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=[("hourly", "data"), ("daily", "data")], settings=default_settings).all().df
    assert df.select("resolution", "station_id", "elevation").rows() == [("hourly", "CAN03010010", 664.0)]


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


def test_noaa_ghcn_stations_carry_the_wmo_number(monkeypatch: pytest.MonkeyPatch, default_settings: Settings) -> None:
    """A station's WMO number is a column of the station list, from the daily and the hourly list (GH-2019).

    The daily rows are copied from `ghcnd-stations.txt` (columns 81 to 85) and the hourly ones from
    `ghcnh-station-list.csv` (`WMO_ID`) as NOAA publishes them; a station without a number has none in
    either list. The hourly list also writes `400` (445 Spanish stations) and `open` where there is no
    number, which are no WMO numbers.
    """
    stations = (
        "GM000010147  53.6350    9.9900   11.0    HAMBURG FUHLSBUETTEL           GSN     10147\n"
        "ACW00011604  17.1167  -61.7833   10.1    ST JOHNS COOLIDGE FLD                       \n"
    )
    inventory = "GM000010147  53.6350    9.9900 TMAX 1891 2026\nACW00011604  17.1167  -61.7833 TMAX 1949 1949\n"
    hourly = (
        "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        "GMI0000EDDH,53.6304,9.9882,16.1,,HAMBURG,,,,EDDH,DE\n"
        "ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD   ANTIGUA (AUX.,,,78861,,AG\n"
        "SPN00000293,42.0,3.2,200.0,,BEGUR (CAP),,,400,,ES\n"
        "BPU40-00001,-3.0,30.0,800.0,,OPEN STATION,,,open,,BI\n"
    )
    contents = {"ghcnd-stations.txt": stations, "ghcnd-inventory.txt": inventory, "ghcnh-station-list.csv": hourly}

    def fake_download_file(url: str, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(contents[url.rsplit("/", 1)[-1]].encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=[("hourly", "data"), ("daily", "data")], settings=default_settings).all().df
    assert df.select("resolution", "station_id", "wmo_id").rows() == [
        ("hourly", "GMI0000EDDH", None),
        ("hourly", "ACM00078861", "78861"),
        ("hourly", "SPN00000293", None),
        ("hourly", "BPU40-00001", None),
        ("daily", "GM000010147", "10147"),
        ("daily", "ACW00011604", None),
    ]


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
    from tests.provider.value_stubs import ghcnh_psv  # noqa: PLC0415

    parameters = [parameter.name_original for parameter in NoaaGhcnMetadata.hourly.data]
    return ghcnh_psv(station_id, parameters, [("1938-01-02T06:00:00", {"temperature": "-11.1"})]).decode("utf8") + "\n"


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
        parameters=[NoaaGhcnMetadata.hourly.data.temperature_air_2m],
        start=dt.datetime(1938, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1938, 1, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    stations = request.filter_by_station_id(station_id)
    assert stations.df.select("station_id", "latitude", "longitude").rows() == [(station_id, None, None)]
    (feature,) = stations.to_ogc_feature_collection()["data"]["features"]
    assert feature["geometry"] is None
    values = stations.values().all().df
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


def test_noaa_ghcn_daily_values_are_stamped_though_the_first_row_has_no_position(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A station's daily values are stamped at 00:00 UTC though its hourly row, named first, has no position (GH-2380).

    The daily reader looked up the station's time zone by position to put a day's midnight in it, and so
    needed the row that has one; it stamps the date at 00:00 UTC now (GH-2683) and needs no position. As
    above, the daily row is made up; the daily reading is -5.0 degC.
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
            NoaaGhcnMetadata.hourly.data.temperature_air_2m,
            NoaaGhcnMetadata.daily.data.temperature_air_max_2m,
        ],
        settings=default_settings,
    )
    df = request.filter_by_station_id("AUM00011158").values().all().df
    assert sorted(df.select(pl.col("resolution"), "timestamp", "value").rows()) == [
        ("daily", dt.datetime(1938, 1, 2, tzinfo=ZoneInfo("UTC")), -5.0),
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


def test_noaa_ghcn_hourly_stations_minus_99_elevation(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """The hourly list's -99.0 is a null elevation, while a real height below sea level stays (GH-2377).

    The rows are copied from `ghcnh-station-list.csv` as NOAA publishes it (2026-10-05). GJBAKKI, in
    southwestern Iceland, is the only row listed at -99.0; SALTON SEA NAAF lies about 69 m below sea level.
    """
    station_list = (
        "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        "ICM00004919,64.2481,-21.023,-99.0,,GJBAKKI,,,04919,,IS\n"
        "USW00093118,33.2,-115.8333,-68.9,CA,SALTON SEA NAAF,,,,,US\n"
    )

    def fake_download_file(url: str, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(station_list.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=default_settings).all().df
    assert df.select("station_id", "elevation").rows() == [("ICM00004919", None), ("USW00093118", -68.9)]


def test_noaa_ghcn_daily_stations_minus_100_elevation(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """The daily list's -100.0 is a null elevation, while a real height below sea level stays (GH-2418).

    The rows are copied from `ghcnd-stations.txt` and `ghcnd-inventory.txt` as NOAA publishes them
    (2026-10-06). SKJOMEN_SLETTJORD, by a fjord near Narvik, is one of the four rows listed at -100.0;
    DEATH VALLEY NP lies about 59 m below sea level.
    """
    contents = {
        "ghcnd-stations.txt": (
            "SWE00140942  68.2900   17.3097 -100.0    SKJOMEN_SLETTJORD                           \n"
            "USC00042319  36.4625 -116.8672  -59.1 CA DEATH VALLEY NP                    HCN      \n"
        ),
        "ghcnd-inventory.txt": (
            "SWE00140942  68.2900   17.3097 PRCP 1971 2011\nUSC00042319  36.4625 -116.8672 PRCP 1961 2026\n"
        ),
    }

    def fake_download_file(url: str, **_kwargs: object) -> File:
        content = contents[url.rsplit("/", 1)[-1]]
        return File(url=url, content=BytesIO(content.encode("utf8")), status=200)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all().df
    assert df.select("station_id", "elevation").rows() == [("SWE00140942", None), ("USC00042319", -59.1)]


def test_noaa_ghcn_daily_stations_are_fetched_over_https(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """The station list and the inventory come from the bucket over https, as does the URL it names (GH-2766)."""
    fetched: list[str] = []

    def fake_download_file(url: str, **kwargs: object) -> File:
        fetched.append(url)
        return _fake_ghcn_download_file(url, **kwargs)

    monkeypatch.setattr("wetterdienst.provider.noaa.ghcn.api.download_file", fake_download_file)
    NoaaGhcnRequest(parameters=[("daily", "data")], settings=default_settings).all()
    assert sorted(url.rsplit("/", 1)[-1] for url in fetched) == ["ghcnd-inventory.txt", "ghcnd-stations.txt"]
    assert all(url.startswith("https://") for url in fetched)
    assert NoaaGhcnMetadata.url.startswith("https://")
