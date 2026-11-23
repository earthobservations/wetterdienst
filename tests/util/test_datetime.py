# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for datetime utilities."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.exceptions import InvalidTimeIntervalError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.datetime import (
    add_months,
    is_plausible_update,
    mktimerange,
    newest,
    parse_date,
    parse_date_span,
    parse_date_window,
    parse_source_date,
    raster_minutes,
    round_minutes,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_raster_50min_regular() -> None:
    """Test rastering of minutes."""
    tm = dt.datetime(2010, 1, 1, 0, 56, 56, tzinfo=ZoneInfo("UTC"))
    tm_aligned = raster_minutes(tm, 50)
    assert tm_aligned == dt.datetime(2010, 1, 1, 0, 50, tzinfo=ZoneInfo("UTC"))


def test_raster_50min_wrap() -> None:
    """Test rastering of minutes."""
    tm = dt.datetime(2010, 1, 1, 0, 42, 42, tzinfo=ZoneInfo("UTC"))
    tm_aligned = raster_minutes(tm, 50)
    assert tm_aligned == dt.datetime(2009, 12, 31, 23, 50, tzinfo=ZoneInfo("UTC"))


def test_round_5min() -> None:
    """Test rounding to 5 minutes."""
    tm = dt.datetime(2010, 1, 1, 0, 4, 42, tzinfo=ZoneInfo("UTC"))
    tm_aligned = round_minutes(tm, 5)
    assert tm_aligned == dt.datetime(2010, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))


def test_parse_date() -> None:
    """Test parsing of date strings."""
    assert parse_date("2020") == dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02") == dt.datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02-02") == dt.datetime(2020, 2, 2, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02-02 02") == dt.datetime(2020, 2, 2, 2, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02-02 02:02") == dt.datetime(2020, 2, 2, 2, 2, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02-02 02:02:02") == dt.datetime(2020, 2, 2, 2, 2, 2, tzinfo=ZoneInfo("UTC"))
    with pytest.raises(ValueError, match="date_string 02/02/2020 could not be parsed"):
        parse_date("02/02/2020")
    with pytest.raises(ValueError, match=r"date_string 02\.02\.2020 could not be parsed"):
        parse_date("02.02.2020")


def test_parse_date_span() -> None:
    """A date string names a span as precise as it is written."""
    utc = ZoneInfo("UTC")
    assert parse_date_span("2020") == (dt.datetime(2020, 1, 1, tzinfo=utc), dt.datetime(2021, 1, 1, tzinfo=utc))
    assert parse_date_span("2020-02") == (dt.datetime(2020, 2, 1, tzinfo=utc), dt.datetime(2020, 3, 1, tzinfo=utc))
    assert parse_date_span("2020-02-02") == (dt.datetime(2020, 2, 2, tzinfo=utc), dt.datetime(2020, 2, 3, tzinfo=utc))
    # the basic and week forms name a day as much as the extended one does
    assert parse_date_span("20200202") == (dt.datetime(2020, 2, 2, tzinfo=utc), dt.datetime(2020, 2, 3, tzinfo=utc))
    assert parse_date_span("2020-W06-7") == (dt.datetime(2020, 2, 9, tzinfo=utc), dt.datetime(2020, 2, 10, tzinfo=utc))


def test_parse_date_span_time_names_one_instant() -> None:
    """A date carrying a time names one instant, however the two are written.

    `datetime.fromisoformat` takes any single character between the date and the time, so looking
    for a "T" or a space called `2020-02-02t02` a date and answered it with the 24 hours following
    02:00 -- a day of readings offset by two hours, rather than the reading at 02:00.
    """
    utc = ZoneInfo("UTC")
    for date_string in ("2020-02-02T02", "2020-02-02t02", "2020-02-02 02"):
        assert parse_date_span(date_string) == (dt.datetime(2020, 2, 2, 2, tzinfo=utc), None), date_string
    # a zone offset is a time of day too, however unusually it is written
    assert parse_date_span("2020-02-02+02:00")[1] is None


def test_parse_date_window() -> None:
    """The window covers the span from its first to its last instant."""
    utc = ZoneInfo("UTC")
    last_moment = dt.timedelta(microseconds=1)
    assert parse_date_window("2020-02") == (
        dt.datetime(2020, 2, 1, tzinfo=utc),
        dt.datetime(2020, 3, 1, tzinfo=utc) - last_moment,
    )
    # an instant is a window of itself, so a filter closed on both sides keeps exactly it
    instant = dt.datetime(2020, 2, 2, 2, tzinfo=utc)
    assert parse_date_window("2020-02-02T02") == (instant, instant)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(
            "2026-10-26T06:54:51.123000+00:00", dt.datetime(2026, 10, 26, 6, 54, 51, 123000, tzinfo=dt.UTC), id="utc"
        ),
        pytest.param(
            "2026-10-26T08:54:51+02:00", dt.datetime(2026, 10, 26, 6, 54, 51, tzinfo=dt.UTC), id="another zone is UTC"
        ),
        pytest.param("2026-10-26T06:54:51", dt.datetime(2026, 10, 26, 6, 54, 51, tzinfo=dt.UTC), id="no zone is UTC"),
        pytest.param("2026-10-26T06:54:51Z", dt.datetime(2026, 10, 26, 6, 54, 51, tzinfo=dt.UTC), id="Z"),
        pytest.param("", None, id="empty"),
        pytest.param("yesterday", None, id="no date"),
        pytest.param(None, None, id="none"),
        pytest.param(20261026, None, id="not text"),
        pytest.param("9999-12-31T23:59:59-01:00", None, id="UTC time out of range"),
        pytest.param("0001-01-01T00:00:00+01:00", None, id="UTC time before the first year"),
        pytest.param("1970-01-01T00:00:00+00:00", None, id="the epoch is no date of an update"),
        pytest.param("1989-12-31T23:59:59+00:00", None, id="before 1990"),
        pytest.param("1990-01-01T00:00:00+00:00", dt.datetime(1990, 1, 1, tzinfo=dt.UTC), id="1990"),
    ],
)
def test_parse_source_date(text: object, expected: dt.datetime | None) -> None:
    """The date a source states for an update is read into UTC, and what is no plausible date is none (GH-2567)."""
    assert parse_source_date(text) == expected


def test_is_plausible_update_allows_a_clock_that_is_a_little_ahead() -> None:
    """A source whose clock is a few hours ahead of ours is dated as it says; a day beyond that is not plausible."""
    now = dt.datetime.now(dt.UTC)

    assert is_plausible_update(now - dt.timedelta(days=30))
    assert is_plausible_update(now + dt.timedelta(hours=3))
    assert not is_plausible_update(now + dt.timedelta(days=2))
    assert not is_plausible_update(dt.datetime(1989, 12, 31, tzinfo=dt.UTC))
    assert not is_plausible_update(dt.datetime(9999, 12, 31, tzinfo=dt.UTC))
    assert is_plausible_update(dt.datetime(2026, 1, 1))  # noqa: DTZ001 (read as UTC)


def test_newest() -> None:
    """The newest of some dates, one without a zone read as UTC, none for no date."""
    old = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    new = dt.datetime(2026, 10, 26, 7, tzinfo=dt.timezone(dt.timedelta(hours=1)))

    assert newest([old, new]) == new
    assert newest([dt.datetime(2026, 1, 1)]) == old  # noqa: DTZ001 (read as UTC)
    assert newest([]) is None


# --- the calendar arithmetic that replaced dateutil's `relativedelta` (GH-4349) ---

_ZONES = {
    "naive": None,
    "utc": ZoneInfo("UTC"),
    "berlin": ZoneInfo("Europe/Berlin"),
    "warsaw": ZoneInfo("Europe/Warsaw"),
    "fixed -03:30": dt.timezone(dt.timedelta(hours=-3, minutes=-30)),
}


def _days(first: int = 1990, last: int = 2030) -> list[dt.date]:
    """Every day of the years."""
    start = dt.date(first, 1, 1)
    return [start + dt.timedelta(days=i) for i in range((dt.date(last, 12, 31) - start).days + 1)]


def _same(actual: dt.datetime, expected: dt.datetime) -> bool:
    """Whether two timestamps are the same wall-clock time with the same zone object and offset."""
    return (
        actual.isoformat() == expected.isoformat() and actual.tzinfo is expected.tzinfo and actual.fold == expected.fold
    )


def _outcome(call: Callable[[], dt.datetime]) -> dt.datetime | type[Exception]:
    """Return the result of a call, or the type of the error it raised."""
    try:
        return call()
    except (OverflowError, ValueError) as e:
        return type(e)


@pytest.mark.parametrize("zone", list(_ZONES))
def test_add_months_is_relativedelta_over_every_day_of_1990_to_2030(zone: str) -> None:
    """Test that `add_months` gives what `relativedelta` gave, for months and years, forward and back."""
    relativedelta = pytest.importorskip("dateutil.relativedelta").relativedelta
    tzinfo = _ZONES[zone]
    for day in _days():
        # 02:30 sits in the gap of the spring change and in the repeated hour of the autumn one
        for hour, minute in ((0, 0), (2, 30), (23, 59)):
            for fold in (0, 1):
                start = dt.datetime(day.year, day.month, day.day, hour, minute, 15, 500, tzinfo=tzinfo, fold=fold)
                for months in (1, -1, 2, -2, 12, -12, 13, -13, 24):
                    expected = start + relativedelta(months=months)
                    assert _same(add_months(start, months), expected), (start, months)
                assert _same(add_months(start, 12), start + relativedelta(years=1)), start


@pytest.mark.parametrize("zone", list(_ZONES))
def test_mktimerange_is_relativedelta_over_every_day_of_1990_to_2030(zone: str) -> None:
    """Test that the first and last day of a month and of a year are what `relativedelta` gave."""
    relativedelta = pytest.importorskip("dateutil.relativedelta").relativedelta
    tzinfo = _ZONES[zone]
    for day in _days():
        start = dt.datetime(day.year, day.month, day.day, 13, 45, 1, tzinfo=tzinfo)
        date_from, date_to = mktimerange(Resolution.ANNUAL, start)
        assert _same(date_from, start + relativedelta(month=1, day=1)), start
        assert _same(date_to, start + relativedelta(month=12, day=31)), start
        date_from, date_to = mktimerange(Resolution.MONTHLY, start)
        assert _same(date_from, start + relativedelta(day=1)), start
        assert _same(date_to, start + relativedelta(day=31)), start


_UTC = ZoneInfo("UTC")


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (dt.datetime(2023, 1, 31, tzinfo=_UTC), 1, dt.datetime(2023, 2, 28, tzinfo=_UTC)),
        (dt.datetime(2024, 1, 31, tzinfo=_UTC), 1, dt.datetime(2024, 2, 29, tzinfo=_UTC)),
        (dt.datetime(2024, 2, 29, tzinfo=_UTC), 12, dt.datetime(2025, 2, 28, tzinfo=_UTC)),
        (dt.datetime(2024, 3, 31, tzinfo=_UTC), -1, dt.datetime(2024, 2, 29, tzinfo=_UTC)),
        (dt.datetime(2024, 1, 1, tzinfo=_UTC), -2, dt.datetime(2023, 11, 1, tzinfo=_UTC)),
        (dt.datetime(2024, 12, 15, tzinfo=_UTC), 2, dt.datetime(2025, 2, 15, tzinfo=_UTC)),
    ],
)
def test_add_months_clamps_to_the_end_of_a_shorter_month(
    start: dt.datetime,
    months: int,
    expected: dt.datetime,
) -> None:
    """Test the cases the clamping is for, without dateutil."""
    assert add_months(start, months) == expected


def test_mktimerange_ends_a_month_on_its_last_day() -> None:
    """Test the last day of 30-day months and of February, without dateutil."""
    for month, last in ((4, 30), (2, 28), (12, 31)):
        _, date_to = mktimerange(Resolution.MONTHLY, dt.datetime(2023, month, 10, tzinfo=_UTC))
        assert date_to == dt.datetime(2023, month, last, tzinfo=_UTC)
    _, date_to = mktimerange(Resolution.MONTHLY, dt.datetime(2024, 2, 10, tzinfo=_UTC))
    assert date_to == dt.datetime(2024, 2, 29, tzinfo=_UTC)


def test_add_months_keeps_the_wall_clock_across_a_change_of_dst() -> None:
    """Test that the same local time comes back after the clocks changed, with the zone it had."""
    berlin = ZoneInfo("Europe/Berlin")
    start = dt.datetime(2024, 3, 15, 12, 0, tzinfo=berlin)
    result = add_months(start, 1)
    assert result.tzinfo is berlin
    assert (result.hour, result.utcoffset()) == (12, dt.timedelta(hours=2))


@pytest.mark.parametrize("zone", list(_ZONES))
def test_add_months_outside_the_years_a_datetime_holds_is_relativedelta_too(zone: str) -> None:
    """Test that a result past year 9999 or before year 1 is the same error as it was, ``ValueError``."""
    relativedelta = pytest.importorskip("dateutil.relativedelta").relativedelta
    tzinfo = _ZONES[zone]
    starts = [
        dt.datetime(*ymd, tzinfo=tzinfo)
        for ymd in ((9999, 12, 31), (9999, 12, 1), (9999, 11, 30), (9998, 12, 31), (1, 1, 1), (1, 2, 28))
    ]
    for start in starts:
        for months in (1, -1, 2, -2, 12, -12, 24):
            expected = _outcome(lambda start=start, months=months: start + relativedelta(months=months))
            actual = _outcome(lambda start=start, months=months: add_months(start, months))
            if isinstance(expected, type):
                assert actual is expected, (start, months)
            else:
                assert not isinstance(actual, type), (start, months)
                assert _same(actual, expected), (start, months)


@pytest.mark.parametrize("text", ["9999", "9999-12", "9999-12-31"])
def test_parse_date_span_past_year_9999_is_an_invalid_time_interval(text: str) -> None:
    """Test that a span reaching past year 9999 is still told as `InvalidTimeIntervalError`."""
    with pytest.raises(InvalidTimeIntervalError):
        parse_date_span(text)
