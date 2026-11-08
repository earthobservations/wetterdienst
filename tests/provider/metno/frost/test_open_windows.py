# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Frost serves the value of a window that has not closed, and the answer says so (GH-3856).

Measured on 2026-11-07: five minutes before 18 UTC `PT18H` maximum and minimum of that date were served at 456 and 461
stations, 15 % of the minima fell by 18:15, and nothing in the answer marks them (the `qualityCode` is the same).
The maintainer decided that a daily value of a window that has not closed at the time of the request is left out with
a `window-not-closed` warning, and that the value of the current month is returned, marked
`completeness:Incomplete`, with the same warning. The time of the request is `frost_api._now`, which these tests set.
"""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.metno.frost.test_values_failures import _answered_by, _offset_answer, _ok, _told, _values
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response

if TYPE_CHECKING:
    from wetterdienst.provider.metno.frost.api import MetnoFrostValues

UTC = dt.UTC
DATE = dt.datetime(2026, 11, 7, tzinfo=UTC)
CODE = "window-not-closed"
PATHS = ["batch", "single", "discovery"]
HOUR = dt.timedelta(hours=1)
MINUTE = dt.timedelta(minutes=1)
AVAILABLE = {
    "data": [
        {
            "validFrom": "1940-01-01T00:00:00Z",
            "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0",
        }
    ]
}


def _at(monkeypatch: pytest.MonkeyPatch, moment: dt.datetime) -> None:
    """Serve the requests of the test at `moment`."""
    monkeypatch.setattr(frost_api, "_now", lambda: moment)


def _read(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    resolution: str,
    name: str,
    element: str,
    readings: list[tuple[str, str, float]],
    start: dt.datetime,
    end: dt.datetime,
) -> MetnoFrostValues:
    """Give the values of `name` at SN18700, which Frost answers with `readings` (stamp, offset, value) by `path`."""
    answer = _offset_answer(element, readings)
    requested = [(resolution, "data", name)]
    if path == "single":
        # the single reader is reached by a parameter of a dataset whose batch 404s
        helper = {"annual": "cloud_cover_total_mean"}.get(resolution, "wind_speed_mean")
        requested.append((resolution, "data", helper if name != helper else "temperature_air_mean_2m"))
    values, _ = _values(monkeypatch, _answered_by(path, answer, AVAILABLE), requested, start=start, end=end)
    return values


def _stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# the daily series of Frost's table: the element, the offset of its standard, the parameter, when the window of the
# date D closes (D + the offset; the calendar day closes at the end of D)
DAILY = [
    pytest.param("max(air_temperature P1D)", "PT18H", "temperature_air_max_2m", 18 * HOUR, id="max-PT18H"),
    pytest.param("min(air_temperature P1D)", "PT18H", "temperature_air_min_2m", 18 * HOUR, id="min-PT18H"),
    pytest.param("sum(precipitation_amount P1D)", "PT6H", "precipitation_amount", 6 * HOUR, id="sum-PT6H"),
    pytest.param("mean(air_temperature P1D)", "PT0H", "temperature_air_mean_2m", 24 * HOUR, id="mean-PT0H"),
    # every other daily element is the calendar day (`PT0H`) and is told the same way
    pytest.param("mean(surface_air_pressure P1D)", "PT0H", "pressure_air_site_mean", 24 * HOUR, id="pressure-PT0H"),
    pytest.param("max(wind_speed P1D)", "PT0H", "wind_speed_rolling_mean_max", 24 * HOUR, id="wind-PT0H"),
]


MOMENTS = [
    pytest.param(-HOUR, True, id="an-hour-before"),
    pytest.param(-MINUTE, True, id="a-minute-before"),
    pytest.param(dt.timedelta(0), False, id="at-closing"),
    pytest.param(MINUTE, False, id="a-minute-after"),
]


def _check_daily(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    series: tuple[str, str, str, dt.timedelta],
    moment: dt.timedelta,
    *,
    open_: bool,
) -> None:
    """Serve the date D and the day before at `moment` from the closing of D, and check what is returned and told."""
    element, offset, name, closes_after = series
    previous = DATE - dt.timedelta(days=1)
    # a pressure of 1 hPa is no reading, which the core would reject
    base = 1000.0 if "pressure" in name else 1.0
    readings = [(_stamp(previous), offset, base), (_stamp(DATE), offset, base + 1)]
    _at(monkeypatch, DATE + closes_after + moment)
    values = _read(monkeypatch, path, "daily", name, element, readings, previous, DATE)
    begin_response()

    df = values.all().df.filter(pl.col("parameter") == name).sort("timestamp")

    assert df["value"].to_list() == ([base] if open_ else [base, base + 1])
    told = _told(CODE)
    if not open_:
        assert told == []
        return
    (warning,) = told
    full = f"daily/data/{name}"
    assert warning["parameter"] == full
    assert warning["stations"] == ["SN18700"]
    closes = (DATE + closes_after).strftime("%Y-%m-%d %H:%M")
    assert f"1 value of {full} (SN18700 1) is left out of the answer" in warning["message"]
    assert f"the earliest closes at {closes} UTC" in warning["message"]
    assert "They are not missing at the source" in warning["message"]
    # the source has the value: it is no "the source has no values", of the parameter or of the station
    assert [w for w in _told("parameter-without-rows") if w["parameter"] in (full, "daily/data")] == []
    assert _told("other-window-left-out") == []


@pytest.mark.parametrize(("element", "offset", "name", "closes_after"), DAILY)
@pytest.mark.parametrize(("moment", "open_"), MOMENTS)
def test_metno_frost_a_daily_value_of_an_open_window_is_left_out_and_told(
    monkeypatch: pytest.MonkeyPatch,
    element: str,
    offset: str,
    name: str,
    closes_after: dt.timedelta,
    moment: dt.timedelta,
    *,
    open_: bool,
) -> None:
    """Test that the value of a date whose window has not closed at the request is not returned, and a warning says so.

    The window of the date D closes at D + 18 h (the `PT18H` extremes), D + 6 h (the `PT6H` sum), at the end of D (the
    `PT0H` mean and every other daily element). The value of the day before has closed at every time of the test. A
    window that closes at the time of the request is closed.
    """
    _check_daily(monkeypatch, "batch", (element, offset, name, closes_after), moment, open_=open_)


@pytest.mark.parametrize("path", ["single", "discovery"])
@pytest.mark.parametrize("series", [DAILY[0].values[:4], DAILY[2].values[:4]], ids=["max-PT18H", "sum-PT6H"])
@pytest.mark.parametrize(("moment", "open_"), [MOMENTS[1].values, MOMENTS[2].values], ids=["open", "closed"])
def test_metno_frost_the_single_and_the_discovery_reader_leave_an_open_daily_value_out_too(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    series: tuple[str, str, str, dt.timedelta],
    moment: dt.timedelta,
    *,
    open_: bool,
) -> None:
    """Test that the three readers (the batch above, the single parameter and the time series discovery) agree."""
    _check_daily(monkeypatch, path, series, moment, open_=open_)


@pytest.mark.parametrize("path", PATHS)
def test_metno_frost_a_station_whose_only_value_is_open_has_rows_told_by_the_open_window(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that an answer emptied by an open window says that, and not that the source has no values."""
    _at(monkeypatch, DATE + 10 * HOUR)
    values = _read(
        monkeypatch,
        path,
        "daily",
        "temperature_air_max_2m",
        "max(air_temperature P1D)",
        [(_stamp(DATE), "PT18H", 2.0)],
        DATE,
        DATE,
    )
    begin_response()

    assert values.all().df.is_empty()

    (warning,) = _told(CODE)
    assert "1 value of daily/data/temperature_air_max_2m" in warning["message"]
    named = ("daily/data", "daily/data/temperature_air_max_2m")
    assert [w for w in _told("parameter-without-rows") if w["parameter"] in named] == []
    assert _told("station-without-rows") == []


@pytest.mark.parametrize(("offset", "hour"), [("PT6H", 6), ("PT0H", 8)], ids=["PT6H-at-06", "PT0H-at-08"])
def test_metno_frost_the_snow_depth_is_a_reading_of_an_instant_and_is_never_open(
    monkeypatch: pytest.MonkeyPatch, offset: str, hour: int
) -> None:
    """Test that the daily snow depth, one reading, is returned on its own date whatever the series and the hour.

    It is the one daily element that is not the aggregate of a window (`surface_snow_thickness`, stamped at the time of
    its reading), so there is no window that could be open: read at 08:00 and asked for at 09:00, a `PT0H` series would
    close at the end of the date, which the reading has nothing to do with.
    """
    _at(monkeypatch, DATE + (hour + 1) * HOUR)
    values = _read(
        monkeypatch,
        "batch",
        "daily",
        "snow_depth",
        "surface_snow_thickness",
        [(_stamp(DATE + hour * HOUR), offset, 12.0)],
        DATE,
        DATE,
    )
    begin_response()

    assert values.all().df["value"].to_list() == [12.0]
    assert _told(CODE) == []


@pytest.mark.parametrize("path", PATHS)
def test_metno_frost_a_date_left_out_as_open_is_not_told_again_as_another_window(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that a date whose `PT6H` value is open and whose `PT18H` value exists is told once, as open."""
    previous = DATE - dt.timedelta(days=1)
    readings = [
        (_stamp(previous), "PT6H", 1.0),
        (_stamp(previous), "PT18H", 9.0),
        (_stamp(DATE), "PT6H", 2.0),
        (_stamp(DATE), "PT18H", 8.0),
    ]
    _at(monkeypatch, DATE + 5 * HOUR)
    values = _read(
        monkeypatch, path, "daily", "precipitation_amount", "sum(precipitation_amount P1D)", readings, previous, DATE
    )
    begin_response()

    assert values.all().df.filter(pl.col("parameter") == "precipitation_amount")["value"].to_list() == [1.0]

    assert len(_told(CODE)) == 1
    assert _told("other-window-left-out") == []


def test_metno_frost_an_open_date_beyond_the_window_of_the_request_is_not_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a value the core cuts off is no value left out."""
    previous = DATE - dt.timedelta(days=1)
    readings = [(_stamp(previous), "PT0H", 1.0), (_stamp(DATE), "PT0H", 2.0)]
    _at(monkeypatch, DATE + 5 * HOUR)
    values = _read(
        monkeypatch,
        "batch",
        "daily",
        "temperature_air_mean_2m",
        "mean(air_temperature P1D)",
        readings,
        previous,
        previous,
    )
    begin_response()

    assert values.all().df["value"].to_list() == [1.0]
    assert _told(CODE) == []


def test_metno_frost_an_open_precipitation_stamped_off_midnight_is_the_window_of_its_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a `PT6H` sum stamped 06:00 (the #3820 census found such stations) closes at 06 UTC of its date.

    The window is that of the date of the stamp, not of the stamp: the one stamped 2026-11-07T06:00 closes at 06:00 and
    not at noon, so at 06:30 it is returned.
    """
    stamp = _stamp(DATE + 6 * HOUR)
    _at(monkeypatch, DATE + 6 * HOUR + 30 * MINUTE)
    values = _read(
        monkeypatch,
        "batch",
        "daily",
        "precipitation_amount",
        "sum(precipitation_amount P1D)",
        [(stamp, "PT6H", 3.0)],
        DATE,
        DATE,
    )
    begin_response()

    assert values.all().df["value"].to_list() == [3.0]
    assert _told(CODE) == []


# the monthly series: the element, the offset, the parameter, when the window of November 2026 closes: the calendar
# month at the end of the month, the other offsets on the last day of it
MONTHLY = [
    pytest.param(
        "mean(air_temperature P1M)",
        "PT0H",
        "temperature_air_mean_2m",
        dt.datetime(2026, 12, 1, tzinfo=UTC),
        id="mean-PT0H",
    ),
    pytest.param(
        "sum(precipitation_amount P1M)",
        "PT6H",
        "precipitation_amount",
        dt.datetime(2026, 11, 30, 6, tzinfo=UTC),
        id="sum-PT6H",
    ),
    pytest.param(
        "max(air_temperature P1M)",
        "PT18H",
        "temperature_air_max_2m",
        dt.datetime(2026, 11, 30, 18, tzinfo=UTC),
        id="max-PT18H",
    ),
    pytest.param(
        "mean(wind_speed P1M)", "PT0H", "wind_speed_mean", dt.datetime(2026, 12, 1, tzinfo=UTC), id="wind-PT0H"
    ),
]


# the two periods a test serves by resolution: the one that has closed at every time of the test and the current one
PERIODS = {
    "monthly": (dt.datetime(2026, 10, 1, tzinfo=UTC), dt.datetime(2026, 11, 1, tzinfo=UTC)),
    "annual": (dt.datetime(2025, 1, 1, tzinfo=UTC), dt.datetime(2026, 1, 1, tzinfo=UTC)),
}


def _check_monthly(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    series: tuple[str, str, str, dt.datetime],
    moment: dt.timedelta,
    *,
    open_: bool,
    resolution: str = "monthly",
) -> None:
    """Serve a closed and the current period at `moment` from the closing of the current one; check the answer."""
    element, offset, name, closes = series
    october, november = PERIODS[resolution]
    readings = [(_stamp(october), offset, 1.0), (_stamp(november), offset, 2.0)]
    _at(monkeypatch, closes + moment)
    values = _read(monkeypatch, path, resolution, name, element, readings, october, november)
    begin_response()

    df = values.all().df.filter(pl.col("parameter") == name).sort("timestamp")

    assert df["value"].to_list() == [1.0, 2.0]
    flags = df["quality_flags"].to_list()
    assert flags[0] is None
    assert flags[1] == ("completeness:Incomplete" if open_ else None)
    told = _told(CODE)
    if not open_:
        assert told == []
        return
    (warning,) = told
    full = f"{resolution}/data/{name}"
    assert warning["parameter"] == full
    assert warning["stations"] == ["SN18700"]
    assert f"1 value of {full} (SN18700 1) is of a window that had not closed" in warning["message"]
    assert f"the earliest closes at {closes:%Y-%m-%d %H:%M} UTC" in warning["message"]
    assert "marked `completeness:Incomplete` in `quality_flags`" in warning["message"]


@pytest.mark.parametrize(("element", "offset", "name", "closes"), MONTHLY)
@pytest.mark.parametrize(("moment", "open_"), MOMENTS[1:])
def test_metno_frost_a_monthly_value_of_an_open_window_is_returned_marked_and_told(
    monkeypatch: pytest.MonkeyPatch,
    element: str,
    offset: str,
    name: str,
    closes: dt.datetime,
    moment: dt.timedelta,
    *,
    open_: bool,
) -> None:
    """Test that the month so far is returned with `completeness:Incomplete` and a warning, until its window closes.

    The calendar month (`PT0H`) closes at the end of the month, the `PT6H` sum at 06 UTC and the `PT18H` extremes at 18
    UTC of its last day (Frost: the window of the month "lasts continuously from the last day of the previous month"
    at the offset). October is closed at every time of the test and carries no token.
    """
    _check_monthly(monkeypatch, "batch", (element, offset, name, closes), moment, open_=open_)


@pytest.mark.parametrize("path", ["single", "discovery"])
@pytest.mark.parametrize(("moment", "open_"), [MOMENTS[1].values, MOMENTS[2].values], ids=["open", "closed"])
def test_metno_frost_the_single_and_the_discovery_reader_mark_an_open_month_too(
    monkeypatch: pytest.MonkeyPatch, path: str, moment: dt.timedelta, *, open_: bool
) -> None:
    """Test that the single parameter reader and the time series discovery mark the month as the batch does."""
    series = MONTHLY[1].values
    _check_monthly(monkeypatch, path, series, moment, open_=open_)


# the annual series: the calendar year closes at the end of the year, the other offsets on 31 December (Frost has the
# annual data "follow the same conventions as for seasonal and monthly data"): the closing time of the year 2026
ANNUAL = [
    pytest.param(
        "mean(air_temperature P1Y)",
        "PT0H",
        "temperature_air_mean_2m",
        dt.datetime(2027, 1, 1, tzinfo=UTC),
        id="mean-PT0H",
    ),
    pytest.param(
        "sum(precipitation_amount P1Y)",
        "PT6H",
        "precipitation_amount",
        dt.datetime(2026, 12, 31, 6, tzinfo=UTC),
        id="sum-PT6H",
    ),
    pytest.param(
        "max(air_temperature P1Y)",
        "PT18H",
        "temperature_air_max_2m",
        dt.datetime(2026, 12, 31, 18, tzinfo=UTC),
        id="max-PT18H",
    ),
]


@pytest.mark.parametrize(("element", "offset", "name", "closes"), ANNUAL)
@pytest.mark.parametrize(("moment", "open_"), MOMENTS[1:])
def test_metno_frost_an_annual_value_of_an_open_window_is_returned_marked_and_told(
    monkeypatch: pytest.MonkeyPatch,
    element: str,
    offset: str,
    name: str,
    closes: dt.datetime,
    moment: dt.timedelta,
    *,
    open_: bool,
) -> None:
    """Test that the year so far is marked like the month so far, until its window closes (GH-3856).

    The calendar year closes at the end of the year, the `PT6H` sum at 06 UTC and the `PT18H` extremes at 18 UTC of 31
    December. The year before is closed at every time of the test and carries no token.
    """
    _check_monthly(monkeypatch, "batch", (element, offset, name, closes), moment, open_=open_, resolution="annual")


@pytest.mark.parametrize("path", ["single", "discovery"])
def test_metno_frost_the_single_and_the_discovery_reader_mark_an_open_year_too(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that the single parameter reader and the time series discovery mark the year as the batch does."""
    element, offset, name, closes = ANNUAL[1].values
    _check_monthly(monkeypatch, path, (element, offset, name, closes), -MINUTE, open_=True, resolution="annual")


def test_metno_frost_the_token_of_an_open_month_comes_after_the_quality_code_and_before_the_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the token keeps the order of the column: the quality code, the kinds, then `raw`."""
    november = dt.datetime(2026, 11, 1, tzinfo=UTC)
    answer = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": _stamp(november),
                "observations": [
                    {"elementId": "mean(air_temperature P1M)", "value": 1.5, "qualityCode": 2, "timeOffset": "PT0H"}
                ],
            }
        ]
    }
    _at(monkeypatch, november + 3 * HOUR)
    values, _ = _values(
        monkeypatch,
        lambda url: _ok(url, answer),
        [("monthly", "data", "temperature_air_mean_2m")],
        start=november,
        end=november,
    )
    begin_response()

    assert values.all().df["quality_flags"].to_list() == ["2,completeness:Incomplete"]


@pytest.mark.parametrize(
    ("resolution", "stamp", "offset", "expected"),
    [
        # daily: the date D, closing at D + the offset, the calendar day at the end of D
        ("daily", "2026-11-07T00:00:00Z", "PT0H", "2026-11-08T00:00:00Z"),
        ("daily", "2026-11-07T00:00:00Z", "PT6H", "2026-11-07T06:00:00Z"),
        ("daily", "2026-11-07T00:00:00Z", "PT18H", "2026-11-07T18:00:00Z"),
        # a stamp off midnight is the date of the stamp
        ("daily", "2026-11-07T06:00:00Z", "PT6H", "2026-11-07T06:00:00Z"),
        ("daily", "2026-11-07T23:00:00Z", "PT0H", "2026-11-08T00:00:00Z"),
        ("daily", "2026-12-31T00:00:00Z", "PT0H", "2027-01-01T00:00:00Z"),
        # monthly: the offset counts from the last day of the month
        ("monthly", "2026-11-01T00:00:00Z", "PT0H", "2026-12-01T00:00:00Z"),
        ("monthly", "2026-11-01T00:00:00Z", "PT6H", "2026-11-30T06:00:00Z"),
        ("monthly", "2026-11-01T00:00:00Z", "PT18H", "2026-11-30T18:00:00Z"),
        ("monthly", "2026-10-01T00:00:00Z", "PT6H", "2026-10-31T06:00:00Z"),
        ("monthly", "2026-02-01T00:00:00Z", "PT6H", "2026-02-28T06:00:00Z"),
        ("monthly", "2024-02-01T00:00:00Z", "PT6H", "2024-02-29T06:00:00Z"),
        ("monthly", "2024-02-01T00:00:00Z", "PT0H", "2024-03-01T00:00:00Z"),
        ("monthly", "2026-12-01T00:00:00Z", "PT0H", "2027-01-01T00:00:00Z"),
        ("monthly", "2026-12-01T00:00:00Z", "PT18H", "2026-12-31T18:00:00Z"),
        ("monthly", "2026-11-01T06:00:00Z", "PT6H", "2026-11-30T06:00:00Z"),
        # annual: the offset counts from 31 December
        ("annual", "2026-01-01T00:00:00Z", "PT0H", "2027-01-01T00:00:00Z"),
        ("annual", "2026-01-01T00:00:00Z", "PT6H", "2026-12-31T06:00:00Z"),
        ("annual", "2026-01-01T00:00:00Z", "PT18H", "2026-12-31T18:00:00Z"),
        ("annual", "2024-01-01T00:00:00Z", "PT0H", "2025-01-01T00:00:00Z"),
    ],
)
def test_metno_frost_closing_time_of_a_window(resolution: str, stamp: str, offset: str, expected: str) -> None:
    """Test the time the window of a value closes, by resolution, stamp and offset."""
    element = "sum(precipitation_amount P1D)" if resolution == "daily" else "sum(precipitation_amount P1M)"
    df = pl.DataFrame({"referenceTime": [stamp], "elementId": [element], "timeOffset": [offset]}).with_columns(
        pl.col("referenceTime").str.to_datetime("%Y-%m-%dT%H:%M:%SZ").dt.replace_time_zone("UTC")
    )

    closes = df.select(frost_api._closes(df, resolution)).item()  # noqa: SLF001

    assert closes == dt.datetime.fromisoformat(expected)


def test_metno_frost_closing_time_of_an_observation_without_an_offset_is_that_of_its_element() -> None:
    """Test that a row without `timeOffset` closes at the offset its element names, else as the calendar day."""
    df = pl.DataFrame(
        {
            "referenceTime": ["2026-11-07T00:00:00Z"] * 3,
            "elementId": ["sum(precipitation_amount P1D)", "max(air_temperature P1D)", "mean(wind_speed P1D)"],
        }
    ).with_columns(pl.col("referenceTime").str.to_datetime("%Y-%m-%dT%H:%M:%SZ").dt.replace_time_zone("UTC"))

    closes = df.select(frost_api._closes(df, "daily")).to_series().to_list()  # noqa: SLF001

    assert closes == [
        dt.datetime(2026, 11, 7, 6, tzinfo=UTC),
        dt.datetime(2026, 11, 7, 18, tzinfo=UTC),
        dt.datetime(2026, 11, 8, tzinfo=UTC),
    ]


@pytest.mark.parametrize(
    ("cached_at", "open_"),
    [
        pytest.param(dt.datetime(2026, 11, 7, 17, 57, tzinfo=UTC), True, id="copy-made-before-closing"),
        pytest.param(dt.datetime(2026, 11, 7, 18, 0, 30, tzinfo=UTC), False, id="copy-made-after-closing"),
        pytest.param(None, False, id="copy-without-a-time"),
    ],
)
def test_metno_frost_a_cached_copy_is_of_the_time_it_was_made(
    monkeypatch: pytest.MonkeyPatch, cached_at: dt.datetime | None, *, open_: bool
) -> None:
    """Test that a copy made at 17:57 is not the final value of a window closing at 18:00, read at 18:01.

    Frost's answers are cached for five minutes: the state of the copy is what the value is, not the time it is read.
    """
    answer = _offset_answer("max(air_temperature P1D)", [(_stamp(DATE), "PT18H", 2.0)])
    _at(monkeypatch, DATE + 18 * HOUR + MINUTE)
    values, _ = _values(
        monkeypatch,
        lambda url: File(
            url=url,
            content=BytesIO(json.dumps(answer).encode()),
            status=200,
            cached_at=None if cached_at is None else cached_at.timestamp(),
        ),
        [("daily", "data", "temperature_air_max_2m")],
        start=DATE,
        end=DATE,
    )
    begin_response()

    df = values.all().df

    assert df["value"].to_list() == ([] if open_ else [2.0])
    assert len(_told(CODE)) == (1 if open_ else 0)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    ("asked", "open_"),
    [
        pytest.param(-MINUTE, True, id="asked-before-closing-arrives-after"),
        pytest.param(dt.timedelta(0), False, id="asked-at-closing"),
    ],
)
def test_metno_frost_a_window_that_closes_while_the_answer_is_on_its_way_is_open_in_it(
    monkeypatch: pytest.MonkeyPatch, path: str, asked: dt.timedelta, *, open_: bool
) -> None:
    """Test that the time of an answer with no copy time is when it was asked for, not when the download ended.

    With the cache off (or a save skipped) the answer has no `cached_at`. Asked at 17:59 for a window that closes at
    18:00, it is Frost's state of 17:59 even though it arrives at 18:01.
    """
    answer = _offset_answer("max(air_temperature P1D)", [(_stamp(DATE), "PT18H", 2.0)])
    clock = [DATE + 18 * HOUR + asked]
    monkeypatch.setattr(frost_api, "_now", lambda: clock[0])
    served = _answered_by(path, answer, AVAILABLE)

    def slow(url: str) -> File:
        # the download that brings the observations takes two minutes (the 404 of the batch and the listing do not)
        file = served(url)
        if file.status == 200 and "availableTimeSeries" not in url:
            clock[0] += 2 * MINUTE
        return file

    requested = [("daily", "data", "temperature_air_max_2m")]
    if path == "single":
        requested.append(("daily", "data", "wind_speed_mean"))
    values, _ = _values(monkeypatch, slow, requested, start=DATE, end=DATE)
    begin_response()

    df = values.all().df.filter(pl.col("parameter") == "temperature_air_max_2m")

    assert df["value"].to_list() == ([] if open_ else [2.0])
    assert len(_told(CODE)) == (1 if open_ else 0)


def test_metno_frost_the_clock_of_a_request_is_the_utc_time() -> None:
    """Test that the time a request is served at is UTC and the present."""
    before = dt.datetime.now(UTC)
    now = frost_api._now()  # noqa: SLF001
    assert before <= now <= dt.datetime.now(UTC)
    assert now.utcoffset() == dt.timedelta(0)
