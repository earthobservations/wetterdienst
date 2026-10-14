# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Verify acquisition of DWD MOSMIX station list.

Please note that in the original data, the values in the `LAT` and `LON`
columns are in "Degrees Minutes" format (`<degrees>.<degrees minutes>`.),
and not in "Decimal Degrees".

Source: https://www.dwd.de/EN/ourservices/met_application_mosmix/mosmix_stations.cfg?view=nasPublication&nn=495490
"""

import datetime as dt
from io import BytesIO

import polars as pl
import pytest
from dirty_equals import IsInt, IsTuple
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.provider.dwd import catalogue
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.util.network import File


@pytest.fixture
def mosmix_stations_schema() -> dict:
    """Provide schema for MOSMIX station list."""
    return {
        "resolution": pl.String,
        "dataset": pl.String,
        "station_id": pl.String,
        "icao_id": pl.String,
        "start_timestamp": pl.Datetime(time_zone="UTC"),
        "end_timestamp": pl.Datetime(time_zone="UTC"),
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "elevation": pl.Float64,
        "name": pl.String,
        "region": pl.String,
    }


@pytest.mark.remote
def test_dwd_mosmix_stations_success(default_settings: Settings, mosmix_stations_schema: dict) -> None:
    """Verify full MOSMIX station list."""
    # Acquire data.
    given_df = DwdMosmixRequest(parameters=[("hourly", "large")], settings=default_settings).all().df
    assert not given_df.is_empty()
    # Verify size of dataframe with all records.
    assert given_df.shape == IsTuple(IsInt(ge=5500), 11)
    # Verify content of dataframe. For reference purposes,
    # we use the first and the last record of the list.
    expected_df = pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "large",
                "station_id": "01001",
                "icao_id": "ENJA",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 70.93,
                "longitude": -8.67,
                "elevation": 10.0,
                "name": "JAN MAYEN",
                "region": None,
            },
            {
                "resolution": "hourly",
                "dataset": "large",
                "station_id": "Z949",
                "icao_id": None,
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 47.58,
                "longitude": 13.02,
                "elevation": 1200.0,
                "name": "JENNER",
                "region": None,
            },
        ],
        schema=mosmix_stations_schema,
        orient="row",
    )
    assert_frame_equal(given_df[[0, -1], :], expected_df)


@pytest.mark.xfail(reason="polars min currently not working as expected with strings")
@pytest.mark.remote
def test_dwd_mosmix_stations_filtered(default_settings: Settings, mosmix_stations_schema: dict) -> None:
    """Verify MOSMIX station list filtering by station identifier."""
    # Acquire data.
    stations = DwdMosmixRequest(parameters=[("hourly", "large")], settings=default_settings)
    given_df = stations.all().df
    assert not given_df.is_empty()
    assert given_df.select(pl.all().max()).to_dicts()[0] == {
        "station_id": "Z949",
        "icao_id": "ZYTX",
        "start_timestamp": None,
        "end_timestamp": None,
        "latitude": 79.98,
        "longitude": 179.33,
        "elevation": 4670.0,
        "name": "ZWOENITZ",
        "region": None,
    }
    assert given_df.select(pl.all().min()).to_dicts()[0] == {
        "station_id": "01001",
        "icao_id": "AFDU",
        "start_timestamp": None,
        "end_timestamp": None,
        "latitude": -75.45,
        "longitude": -176.17,
        "elevation": -350.0,
        "name": "16N55W",
        "region": None,
    }
    station_names_sorted = given_df.sort(pl.col("name").str.len_chars()).get_column("name").to_list()
    assert station_names_sorted[:5] == ["ELM", "PAU", "SAL", "AUE", "HOF"]
    assert station_names_sorted[-5:] == [
        "KARLSRUHE/BADEN-BADE",
        "FELDBERG/MECKLENBURG",
        "HINTERHORNBACH/OESTE",
        "UNTERGSCHWEND/OESTER",
        "ACHENKIRCH/OESTERREI",
    ]
    # Filter dataframe.
    given_df = given_df.filter(pl.col("station_id").is_in(["01001", "72306", "83891", "94767"]))
    # Verify content of filtered dataframe.
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "01001",
                "icao_id": "ENJA",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 70.93,
                "longitude": -8.67,
                "elevation": 10.0,
                "name": "JAN MAYEN",
                "region": None,
            },
            {
                "station_id": "72306",
                "icao_id": "KRDU",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 35.87,
                "longitude": -78.78,
                "elevation": 132.0,
                "name": "RALEIGH/DURHAM NC.",
                "region": None,
            },
            {
                "station_id": "83891",
                "icao_id": "SBLJ",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": -27.8,
                "longitude": -50.33,
                "elevation": 937.0,
                "name": "LAGES",
                "region": None,
            },
            {
                "station_id": "94767",
                "icao_id": "YSSY",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": -33.95,
                "longitude": 151.18,
                "elevation": 6.0,
                "name": "SYDNEY AIRPORT",
                "region": None,
            },
        ],
        schema=mosmix_stations_schema,
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_mosmix_available_issues(default_settings: Settings) -> None:
    """Verify available_issues returns a non-empty sorted list of UTC datetimes."""
    issues = DwdMosmixRequest.available_issues("10147", default_settings)
    assert len(issues) > 0
    assert all(isinstance(i, dt.datetime) for i in issues)
    assert all(i.tzinfo is not None for i in issues)
    assert issues == sorted(issues)


def _serve_catalogue(monkeypatch: pytest.MonkeyPatch, rows: str) -> None:
    """Serve `mosmix_stationskatalog.cfg` with these rows under its header, as DWD writes it."""
    body = (
        "ID    ICAO NAME                 LAT    LON     ELEV\n----- ---- -------------------- -----  ------- -----\n"
    ) + rows
    monkeypatch.setattr(
        catalogue,
        "download_file",
        lambda *, url, **_: File(url=url, content=BytesIO(body.encode("latin-1")), status=200),
    )


def _positions(settings: Settings) -> dict[str, tuple[float, float]]:
    df = DwdMosmixRequest(parameters=[("hourly", "small")], settings=settings).all().df
    return {row["station_id"]: (row["latitude"], row["longitude"]) for row in df.iter_rows(named=True)}


def test_dwd_mosmix_stations_javea_is_east_of_greenwich(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """JAVEA/YUNTAMIEN is published at 0 deg 10' west and read at 0 deg 10' east (GH-2646).

    The rows are copied from `mosmix_stationskatalog.cfg`. Javea (Xabia) lies at 38.79 / +0.16 (GHCN hourly
    `SPM00008370`: 38.7842 / 0.1667); Bordeaux, at -0.42 in minutes, and Hamburg are left as listed.
    """
    _serve_catalogue(
        monkeypatch,
        "07510 LFBD BORDEAUX              44.50   -0.42    49\n"
        "08370 ---- JAVEA/YUNTAMIEN       38.47   -0.10    15\n"
        "10147 EDDH HAMBURG-FU.           53.38   10.00    16\n",
    )
    positions = _positions(default_settings)
    assert positions["08370"] == pytest.approx((38.78, 0.17), abs=5e-3)
    assert positions["07510"] == pytest.approx((44.83, -0.70), abs=5e-3)
    assert positions["10147"] == pytest.approx((53.63, 10.0), abs=5e-3)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        # DWD has put the sign right: read as it is, not turned west again
        pytest.param("08370 ---- JAVEA/YUNTAMIEN       38.47    0.10    15\n", (38.78, 0.17), id="corrected-upstream"),
        # DWD has moved the station: not the position the table recorded, so not touched
        pytest.param("08370 ---- JAVEA/YUNTAMIEN       38.50   -0.10    15\n", (38.83, -0.17), id="moved-north"),
        pytest.param("08370 ---- JAVEA/YUNTAMIEN       38.47   -0.20    15\n", (38.78, -0.33), id="moved-west"),
    ],
)
def test_dwd_mosmix_stations_a_position_that_is_not_the_recorded_one_is_read_as_it_is(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    row: str,
    expected: tuple[float, float],
) -> None:
    """The correction applies only while DWD publishes the position recorded in the table (GH-2646)."""
    _serve_catalogue(monkeypatch, row)
    assert _positions(default_settings)["08370"] == pytest.approx(expected, abs=5e-3)
