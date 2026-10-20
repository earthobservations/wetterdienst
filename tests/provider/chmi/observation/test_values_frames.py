# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames the core hands out for CHMI's values, the five resolutions and the empty answers (GH-2627).

The files are the shapes CHMI writes (`dly-`, `mly-`, `yrs-`, `10m-` and `1h-` files of Cheb, 0-20000-0-11406), served
through the provider's own reader. `tests/provider/frames.snapshot.json` records what the core made of each, which is
the net under moving the shaping of the frame (the identity columns, the empty frame) out of the provider.
"""

from __future__ import annotations

import datetime as dt
from io import BytesIO

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.chmi.observation import ChmiObservationRequest
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.util.network import File

CHEB = "0-20000-0-11406"
UTC = dt.UTC

_DAILY_T = (
    "STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},T,AVG,2020-01-01T00:00Z,-3.0,,0.0,\n"
    f"{CHEB},T,20:00,2020-01-01T20:00Z,-1.0,,0.0,\n"
    f"{CHEB},T,AVG,2020-01-02T00:00Z,,,4.0,\n"
    f"{CHEB},T,AVG,2020-01-03T00:00Z,-2.5,,3.0,\n"
)
_DAILY_SRA = (
    "STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},SRA,06:00,2020-01-01T06:00Z,0.0,T,0.0,\n"
    f"{CHEB},SRA,06:00,2020-01-02T06:00Z,1.2,,0.0,\n"
)
_MONTHLY_T = (
    "STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
    f"{CHEB},T,2020,1,AVG,AVG,1.1,,,\n"
    f"{CHEB},T,2020,2,AVG,AVG,2.3,,I,\n"
    f"{CHEB},T,2020,2,AVG,MAX,9.0,*,,\n"
)
_MONTHLY_SRA = (
    "STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
    f"{CHEB},SRA,2020,1,06:00,SUM,21.3,,,\n"
)
_ANNUAL_T = (
    "STATION,ELEMENT,YEAR,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
    f"{CHEB},T,2018,AVG,AVG,9.7,,,\n"
    f"{CHEB},T,2019,AVG,AVG,10.1,,I,\n"
)
_TEN_MINUTES_T_JANUARY = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},T,2020-01-31T23:50Z,-2.8,,0.0,\n"
    f"{CHEB},T,2020-01-31T23:40Z,,,4.0,\n"
)
_TEN_MINUTES_T_FEBRUARY = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},T,2020-02-01T00:00Z,-2.7,,0.0,\n"
    f"{CHEB},T,2020-02-01T00:10Z,-2.6,,1.0,\n"
)
_HOURLY_TD = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},Td,2020-01-01T00:00Z,-3.9,,0.0,\n"
    f"{CHEB},Td,2020-01-01T01:00Z,-3.7,,0.0,\n"
)
_HOURLY_SRA1H = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},SRA1H,2020-01-01T00:00Z,0.0,T,0.0,\n"
    f"{CHEB},SRA1H,2020-01-01T01:00Z,0.3,,0.0,\n"
)


def _serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> list[str]:
    """Serve the files by the tail of their url; any other file of the portal is a 404, as for a station without it."""
    asked: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        asked.append(url)
        for tail, body in files.items():
            if url.endswith(tail):
                return File(url=url, content=BytesIO(body.encode()), status=200)
        return File(url=url, content=FileNotFoundError(url), status=404)

    monkeypatch.setattr(chmi_api, "download_file", download_file)
    return asked


def _values(
    resolution: str,
    *,
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
    drop_nulls: bool = True,
) -> pl.DataFrame:
    request = ChmiObservationRequest(
        parameters=[(resolution, "data")],
        start=start,
        end=end,
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, resolution, "data", CHEB).values().all().df


def _assert_the_long_form(df: pl.DataFrame, *, resolution: str) -> None:
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["resolution"].unique().to_list() == [resolution]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["station_id"].unique().to_list() == [CHEB]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")


def test_chmi_daily_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The daily files of T and SRA: one TIMEFUNC each, a missing value (quality 4) is kept null beside its code."""
    _serve(monkeypatch, {f"dly-{CHEB}-T.csv": _DAILY_T, f"dly-{CHEB}-SRA.csv": _DAILY_SRA})
    df = _values("daily", start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 3, tzinfo=UTC))
    _assert_the_long_form(df, resolution="daily")
    assert df.height == 4
    kept = _values(
        "daily", start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 3, tzinfo=UTC), drop_nulls=False
    )
    assert kept.height == 5
    assert kept.filter(pl.col("value").is_null())["quality_flags"].to_list() == ["4"]
    assert kept.filter(pl.col("parameter").eq("precipitation_amount")).sort("timestamp")["quality_flags"].to_list() == [
        "0,element:T",
        "0",
    ]


def test_chmi_monthly_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The monthly files pin TIMEFUNCTION and MDFUNCTION, and the period start is the stamp."""
    _serve(monkeypatch, {f"mly-{CHEB}-T.csv": _MONTHLY_T, f"mly-{CHEB}-SRA.csv": _MONTHLY_SRA})
    df = _values("monthly", start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 2, 1, tzinfo=UTC))
    _assert_the_long_form(df, resolution="monthly")
    assert df.height == 3
    assert df.sort("timestamp")["timestamp"].to_list()[-1] == dt.datetime(2020, 2, 1, tzinfo=UTC)


def test_chmi_annual_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The annual files have no MONTH column, and the year start is the stamp."""
    _serve(monkeypatch, {f"yrs-{CHEB}-T.csv": _ANNUAL_T})
    df = _values("annual", start=dt.datetime(2018, 1, 1, tzinfo=UTC), end=dt.datetime(2019, 1, 1, tzinfo=UTC))
    _assert_the_long_form(df, resolution="annual")
    assert df.sort("timestamp")["quality_flags"].to_list() == [None, "interrupted:I"]


def test_chmi_10_minutes_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 10 minute files are one per month: the two of January and February are read, the rest are 404."""
    asked = _serve(
        monkeypatch,
        {f"10m-{CHEB}-T-202001.csv": _TEN_MINUTES_T_JANUARY, f"10m-{CHEB}-T-202002.csv": _TEN_MINUTES_T_FEBRUARY},
    )
    df = _values(
        "10_minutes", start=dt.datetime(2020, 1, 31, 23, 40, tzinfo=UTC), end=dt.datetime(2020, 2, 1, 0, 10, tzinfo=UTC)
    )
    _assert_the_long_form(df, resolution="10_minutes")
    assert df.height == 3
    assert any(url.endswith("202002.csv") for url in asked)


def test_chmi_hourly_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hourly files of Td and SRA1H, one month; the P file of the dataset is a 404 and adds no row."""
    _serve(monkeypatch, {f"1h-{CHEB}-Td-202001.csv": _HOURLY_TD, f"1h-{CHEB}-SRA1H-202001.csv": _HOURLY_SRA1H})
    df = _values("hourly", start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 1, 1, tzinfo=UTC))
    _assert_the_long_form(df, resolution="hourly")
    assert df.height == 4


@pytest.mark.parametrize(
    ("resolution", "files"),
    [
        pytest.param("daily", {}, id="daily-no-file"),
        pytest.param("monthly", {}, id="monthly-no-file"),
        pytest.param("10_minutes", {}, id="10-minutes-no-file"),
        pytest.param(
            "daily", {f"dly-{CHEB}-T.csv": "STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"}, id="header-only"
        ),
        pytest.param(
            "daily",
            {f"dly-{CHEB}-T.csv": _DAILY_T.replace(",AVG,", ",MAX,")},
            id="no-timefunc-of-the-element",
        ),
        pytest.param(
            "monthly",
            {f"mly-{CHEB}-T.csv": _MONTHLY_T.replace(",AVG,AVG,", ",AVG,MIN,")},
            id="no-function-pair-of-the-element",
        ),
    ],
)
def test_chmi_without_a_reading_comes_out_as_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch, resolution: str, files: dict[str, str]
) -> None:
    """A station without the files of the dataset, or without the series this reader selects, has no rows."""
    _serve(monkeypatch, files)
    df = _values(resolution, start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 3, tzinfo=UTC))
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()


def test_chmi_subdaily_without_a_date_range_comes_out_as_the_empty_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The month files of the sub-daily resolutions are addressed by the range: with none, there is nothing to read."""
    asked = _serve(monkeypatch, {f"10m-{CHEB}-T-202001.csv": _TEN_MINUTES_T_JANUARY})
    df = _values("10_minutes")
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
    assert asked == []
