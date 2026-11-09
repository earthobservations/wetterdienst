# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The dates `other-window-left-out` counts are compared on the key of the date, not on raw stamps (GH-3865).

The frame a station returns has its daily stamps cut to the day, and Frost stamps some series off midnight (the `PT6H`
precipitation at 06:00 at some stations). The dates of the series that was left out, compared as they were stamped,
were counted twice (06:00 of two days against one returned day) and a returned day was reported as left out (a series
stamped 10:00 against the same day cut to 00:00).
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from tests.provider.metno.frost.test_values_failures import _answered_by, _offset_answer, _told, _values
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.response_warnings import begin_response

UTC = dt.UTC
LEFT_OUT = "other-window-left-out"
AVAILABLE = {
    "data": [
        {
            "validFrom": "1940-01-01T00:00:00Z",
            "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0",
        }
    ]
}


def _read(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    resolution: str,
    name: str,
    element: str,
    readings: list[tuple[str, str, float]],
    start: dt.datetime,
    end: dt.datetime,
) -> pl.DataFrame:
    """Give the values of `name` at SN18700 that Frost answers with `readings` (stamp, offset, value) by `path`."""
    # a day that is long over: no window is open (GH-3856)
    monkeypatch.setattr(frost_api, "_now", lambda: dt.datetime(2030, 1, 1, tzinfo=UTC))
    requested = [(resolution, "data", name)]
    if path == "single":
        requested.append((resolution, "data", "wind_speed_mean"))
    values, _ = _values(
        monkeypatch,
        _answered_by(path, _offset_answer(element, readings), AVAILABLE),
        requested,
        start=start,
        end=end,
    )
    begin_response()
    return values.all().df.filter(pl.col("parameter") == name).sort("timestamp")


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize("off_midnight", [True, False], ids=["stamped-06:00", "stamped-00:00"])
def test_metno_frost_two_dates_of_the_other_series_one_of_them_returned_are_one_date_left_out(
    monkeypatch: pytest.MonkeyPatch, path: str, *, off_midnight: bool
) -> None:
    """Test that the other series' 01-01 and 01-02 against a returned 01-01 count 1, stamped 00:00 or 06:00.

    The kept series (`PT0H` mean) has 2020-01-01; the other (`PT6H`) 01-01 and 01-02, stamped 06:00 or 00:00; the window
    runs to 01-03. Stamped 06:00 it reported 2 left-out dates where the true count is 1.
    """
    hour = "06" if off_midnight else "00"
    readings = [
        ("2020-01-01T00:00:00.000Z", "PT0H", 1.0),
        (f"2020-01-01T{hour}:00:00.000Z", "PT6H", 2.0),
        (f"2020-01-02T{hour}:00:00.000Z", "PT6H", 3.0),
    ]

    df = _read(
        monkeypatch,
        path,
        "daily",
        "temperature_air_mean_2m",
        "mean(air_temperature P1D)",
        readings,
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 1, 3, tzinfo=UTC),
    )

    assert df["value"].to_list() == [1.0]
    (warning,) = _told(LEFT_OUT)
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
def test_metno_frost_a_day_both_series_stamp_at_ten_is_returned_and_not_told_as_left_out(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that a day whose `PT6H` (0.1) and `PT18H` (4.0) are both stamped 2026-11-07T10:00 is not left out.

    The day is returned (0.1); `other-window-left-out` said that 1 date was not in the answer, as the stamp of the other
    series (10:00) was compared to the day (00:00) the returned one is cut to.
    """
    stamp = "2026-11-07T10:00:00.000Z"

    df = _read(
        monkeypatch,
        path,
        "daily",
        "precipitation_amount",
        "sum(precipitation_amount P1D)",
        [(stamp, "PT6H", 0.1), (stamp, "PT18H", 4.0)],
        dt.datetime(2026, 11, 6, tzinfo=UTC),
        dt.datetime(2026, 11, 8, tzinfo=UTC),
    )

    assert df["value"].to_list() == [0.1]
    assert df["timestamp"].to_list() == [dt.datetime(2026, 11, 7, tzinfo=UTC)]
    assert _told(LEFT_OUT) == []


def test_metno_frost_a_date_of_the_other_series_stamped_off_midnight_on_the_last_day_of_the_window_is_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the window is cut on the day, as the core cuts the returned frame, which holds that day.

    The window ends 2020-01-03T00:00; the other series has 01-03 stamped 06:00, whose day the returned series would
    have been given. Compared as stamped it was past the end and not counted.
    """
    df = _read(
        monkeypatch,
        "batch",
        "daily",
        "temperature_air_mean_2m",
        "mean(air_temperature P1D)",
        [("2020-01-01T00:00:00.000Z", "PT0H", 1.0), ("2020-01-03T06:00:00.000Z", "PT6H", 3.0)],
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 1, 3, tzinfo=UTC),
    )

    assert df["value"].to_list() == [1.0]
    (warning,) = _told(LEFT_OUT)
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]


@pytest.mark.parametrize("path", ["batch", "discovery"])
def test_metno_frost_a_month_of_the_other_series_stamped_off_the_first_is_the_month_returned(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that the key of a month is the month: a series stamped 2020-01-01T06:00 is that of the 00:00 one.

    The returned `PT6H` precipitation has January; the `PT18H` series has January stamped 06:00 and February: one month
    is left out, not two.
    """
    readings = [
        ("2020-01-01T00:00:00.000Z", "PT6H", 1.0),
        ("2020-01-01T06:00:00.000Z", "PT18H", 2.0),
        ("2020-02-01T06:00:00.000Z", "PT18H", 3.0),
    ]

    df = _read(
        monkeypatch,
        path,
        "monthly",
        "precipitation_amount",
        "sum(precipitation_amount P1M)",
        readings,
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 3, 1, tzinfo=UTC),
    )

    assert df["value"].to_list() == [1.0]
    (warning,) = _told(LEFT_OUT)
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]


def test_metno_frost_the_wording_of_the_monthly_precipitation_is_not_that_of_a_day() -> None:
    """Test that the monthly sum names its series as months (GH-3867) and the daily one as 06-06 and 18-18 windows."""
    monthly = frost_api._LEFT_OUT_BECAUSE["sum(precipitation_amount P1M)"]  # noqa: SLF001
    daily = frost_api._LEFT_OUT_BECAUSE["sum(precipitation_amount P1D)"]  # noqa: SLF001

    assert "06-06" not in monthly
    assert "18-18" not in monthly
    assert "from 06 UTC on the last day of the previous month to 06 UTC on the last day of the month" in monthly
    assert "from 18 UTC on the last day of the previous month to 18 UTC on the last day of the month" in monthly
    assert "18-18 UTC series (`timeOffset` PT18H)" in daily
    assert "06-06 UTC series (`timeOffset` PT6H)" in daily
    assert "month" not in daily
