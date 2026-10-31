# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The calm of the directions of the fastest and peak winds of GHCN daily (GH-3648, the rule of GH-3222).

The peak gust WSFG of 0 with the source flag C (Environment Canada) is a gust not reported, below 31 km/h, and is null
with `raw:0` as its direction is (GH-3655); any other 0 is a reading.

The daily files write a direction of 0 for a day without one: beside a speed of 0 it is no direction, a calm or a gust
the source did not report, null with `raw:0`, and beside a wind that blows it is a reading that stays. The rows are the
ones NOAA wrote, read key-less on 2026-10-30 from the per-station files at
ncei.noaa.gov/data/global-historical-climatology-network-daily/access/ and cut to the columns of the pair; the speeds
are the tenths of m/s of the readme. WDFI and WDFM have no 0 in 8,410 and 28,815 directions of the 9 files read, so
their rows are made up (`test_the_instant_and_the_mile_follow_the_rule`).
"""

import datetime as dt

import polars as pl
import pytest

from tests.provider.value_stubs import serve
from wetterdienst import Options, Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest, api

_PAIRS = {
    "wdf1": ("wind_direction_gust_max_1min", "wsf1", "wind_gust_max_1min"),
    "wdf2": ("wind_direction_gust_max_2min", "wsf2", "wind_gust_max_2min"),
    "wdf5": ("wind_direction_gust_max_5sec", "wsf5", "wind_gust_max_5sec"),
    "wdfg": ("wind_direction_gust_max", "wsfg", "wind_gust_max"),
    "wdfi": ("wind_direction_gust_max_instant", "wsfi", "wind_gust_max_instant"),
    "wdfm": ("wind_direction_gust_max_1mile", "wsfm", "wind_gust_max_1mile"),
}


def _file(station: str, name: str, date: str, cells: dict[str, tuple[str, str]]) -> bytes:
    """Write one row of an `access` file: the identity of the station, then each element and its attributes."""
    header = ['"STATION"', '"DATE"', '"LATITUDE"', '"LONGITUDE"', '"ELEVATION"', '"NAME"']
    row = [f'"{station}"', f'"{date}"', '"44.0"', '"-71.0"', '"10.0"', f'"{name}"']
    for element, (value, attributes) in cells.items():
        header += [f'"{element.upper()}"', f'"{element.upper()}_ATTRIBUTES"']
        row += [f'"{value}"', f'"{attributes}"']
    return ("\n".join([",".join(header), ",".join(row)]) + "\n").encode("utf8")


def _daily(monkeypatch: pytest.MonkeyPatch, station: str, body: bytes, date: str, element: str) -> pl.DataFrame:
    """Read the direction and the speed of an element pair with the null rows kept."""
    direction, _, speed = _PAIRS[element]
    stations = f"{station}  44.0000  -71.0000   10.0 NH TEST STATION                                  \n"
    inventory = f"{station}  44.0000  -71.0000 {element.upper()} 1948 2026\n"
    serve(
        monkeypatch,
        api,
        {
            "ghcnd-stations": stations.encode("utf8"),
            "ghcnd-inventory": inventory.encode("utf8"),
            f"access/{station}": body,
        },
    )
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", direction), ("daily", "data", speed)],
        start=date,
        end=date,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    ).filter_by_station_id(station)
    return request.values().all().df


def _rows(df: pl.DataFrame, parameter: str) -> list[tuple[dt.date, float | None, str]]:
    return (
        df.filter(pl.col("parameter") == parameter)
        .select(pl.col("timestamp").dt.date(), "value", "quality_flags")
        .rows()
    )


# (element, station, date, direction cell, speed cell): the 0 beside a speed of 0 of four stations of the files
_CALMS = [
    ("wdf1", "USW00023232", "1969-11-01", ("    0", ",,X"), ("    0", ",,X")),
    ("wdf2", "USW00023232", "1998-04-01", ("    0", ",,X"), ("    0", ",,X")),
    ("wdf5", "USW00014710", "1999-01-25", ("    0", ",,W"), ("    0", ",,W")),
    ("wdfg", "CAN03031640", "1955-01-01", ("    0", ",,C"), ("    0", ",,C")),
]
# the 0 beside a wind that blows, of two stations: 44.3 and 28.6 m/s
_BLOWING = [
    ("wdf2", "USW00012844", "1997-05-05", ("    0", ",,X"), ("  443", ",,X")),
    ("wdf5", "USW00014755", "1998-04-04", ("    0", ",,W"), ("  286", ",,W")),
]


@pytest.mark.parametrize(("element", "station", "date", "direction", "speed"), _CALMS, ids=[c[0] for c in _CALMS])
def test_a_direction_of_0_beside_a_speed_of_0_is_no_direction(
    monkeypatch: pytest.MonkeyPatch,
    element: str,
    station: str,
    date: str,
    direction: tuple[str, str],
    speed: tuple[str, str],
) -> None:
    """The 0 of the direction is null and keeps `raw:0` as the last token.

    The speed of 0 of the US rows is a reading. At CAN03031640 (flag C) it is not: every WSFG of 0 sits beside a WDFG of
    0 and the smallest above is 8.6 m/s, Environment Canada's "gust below 31 km/h, not reported", so that speed is null
    with `raw:0` too (GH-3655).
    """
    speed_element = _PAIRS[element][1]
    body = _file(station, "TEST STATION", date, {element: direction, speed_element: speed})
    df = _daily(monkeypatch, station, body, date, element)
    day = dt.date.fromisoformat(date)
    flag = direction[1].split(",")[2]
    assert _rows(df, _PAIRS[element][0]) == [(day, None, f"source:{flag},raw:0")]
    if station == "CAN03031640":
        assert _rows(df, _PAIRS[element][2]) == [(day, None, f"source:{flag},raw:0")]
    else:
        assert _rows(df, _PAIRS[element][2]) == [(day, 0.0, f"source:{flag}")]


@pytest.mark.parametrize(("element", "station", "date", "direction", "speed"), _BLOWING, ids=[c[0] for c in _BLOWING])
def test_a_direction_of_0_beside_a_wind_that_blows_stays(
    monkeypatch: pytest.MonkeyPatch,
    element: str,
    station: str,
    date: str,
    direction: tuple[str, str],
    speed: tuple[str, str],
) -> None:
    """The 0 is a reading: only the speed of exactly 0 makes it a calm (GH-3222)."""
    speed_element = _PAIRS[element][1]
    body = _file(station, "TEST STATION", date, {element: direction, speed_element: speed})
    df = _daily(monkeypatch, station, body, date, element)
    day = dt.date.fromisoformat(date)
    flag = direction[1].split(",")[2]
    assert _rows(df, _PAIRS[element][0]) == [(day, 0.0, f"source:{flag}")]
    assert _rows(df, _PAIRS[element][2]) == [(day, pytest.approx(int(speed[0]) / 10), f"source:{flag}")]


# the peak gust of two stations of the files, one day each, as NOAA wrote them (direction in degrees, speed in tenths of
# m/s; read 2026-10-31): CAN03031640 (flag C) on 1955-01-01 is the gust not reported, a 0 beside a 0, and on 1955-04-06
# the smallest one reported, 8.6 m/s; USW00013904 (flag X) on 1948-03-15 has a 0 as well, beside a direction of 30
_GUSTS = [
    ("CAN03031640", "1955-01-01", ("    0", ",,C"), ("    0", ",,C"), None, "source:C,raw:0"),
    ("CAN03031640", "1955-04-06", ("  250", ",,C"), ("   86", ",,C"), 8.6, "source:C"),
    ("USW00013904", "1948-03-15", ("   30", ",,X"), ("    0", ",,X"), 0.0, "source:X"),
]


@pytest.mark.parametrize(("station", "date", "direction", "speed", "value", "flags"), _GUSTS)
def test_a_peak_gust_of_0_from_environment_canada_is_a_gust_not_reported(
    monkeypatch: pytest.MonkeyPatch,
    station: str,
    date: str,
    direction: tuple[str, str],
    speed: tuple[str, str],
    value: float | None,
    flags: str,
) -> None:
    """The WSFG of 0 of flag C is null with `raw:0`; a reported gust of flag C and a 0 of any other source stay.

    The 0 of the last row is a reading: a station of flag X (USW00013904 has 11 of 7,271 in WSFG, none beside a
    WDFG of 0), so the rule is the source's, not the number's. The direction of the last row stays too.
    """
    body = _file(station, "TEST STATION", date, {"wdfg": direction, "wsfg": speed})
    df = _daily(monkeypatch, station, body, date, "wdfg")
    day = dt.date.fromisoformat(date)
    assert _rows(df, "wind_gust_max") == [(day, pytest.approx(value) if value is not None else None, flags)]
    # the direction is null beside the gust not reported (GH-3648), and stays beside a gust, a 0 of flag X included
    degrees = None if value is None else float(direction[0])
    assert _rows(df, "wind_direction_gust_max") == [
        (day, degrees, flags if value is None else flags.split(",", maxsplit=1)[0]),
    ]


@pytest.mark.synthetic_values
@pytest.mark.parametrize("element", ["wdf2", "wdf5"])
def test_only_the_peak_gust_is_a_gust_not_reported(monkeypatch: pytest.MonkeyPatch, element: str) -> None:
    """The inventory has WSFG and no other speed at a CAN station, so a 0 of flag C in WSF2 or WSF5 is made up here.

    Nothing says it is a gust not reported, and it stays a 0 (the direction beside it is null by the rule of a calm).
    """
    speed_element = _PAIRS[element][1]
    body = _file(
        "CAN03031640", "CLARESHOLM", "1955-01-01", {element: ("    0", ",,C"), speed_element: ("    0", ",,C")}
    )
    df = _daily(monkeypatch, "CAN03031640", body, "1955-01-01", element)
    assert _rows(df, _PAIRS[element][2]) == [(dt.date(1955, 1, 1), 0.0, "source:C")]
    assert _rows(df, _PAIRS[element][0]) == [(dt.date(1955, 1, 1), None, "source:C,raw:0")]


@pytest.mark.synthetic_values
@pytest.mark.parametrize("element", ["wdfi", "wdfm"])
def test_the_instant_and_the_mile_follow_the_rule(monkeypatch: pytest.MonkeyPatch, element: str) -> None:
    """No 0 of WDFI or WDFM was found in the files read, so the rows are made up: the pair follows the rule too."""
    speed_element = _PAIRS[element][1]
    calm = _file(
        "USW00014755", "MOUNT WASHINGTON", "1970-01-01", {element: ("    0", ",,X"), speed_element: ("    0", ",,X")}
    )
    blows = _file(
        "USW00014755", "MOUNT WASHINGTON", "1970-01-01", {element: ("    0", ",,X"), speed_element: ("  125", ",,X")}
    )
    df = _daily(monkeypatch, "USW00014755", calm, "1970-01-01", element)
    assert _rows(df, _PAIRS[element][0]) == [(dt.date(1970, 1, 1), None, "source:X,raw:0")]
    df = _daily(monkeypatch, "USW00014755", blows, "1970-01-01", element)
    assert _rows(df, _PAIRS[element][0]) == [(dt.date(1970, 1, 1), 0.0, "source:X")]


def test_a_missing_speed_leaves_the_0_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 0 beside no speed at all tells nothing about a calm, so it stays (GH-3222)."""
    body = _file("USW00014755", "MOUNT WASHINGTON", "1998-04-04", {"wdf5": ("    0", ",,W"), "wsf5": ("", "")})
    df = _daily(monkeypatch, "USW00014755", body, "1998-04-04", "wdf5")
    assert _rows(df, "wind_direction_gust_max_5sec") == [(dt.date(1998, 4, 4), 0.0, "source:W")]
