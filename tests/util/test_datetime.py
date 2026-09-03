# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for datetime utilities."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.util.datetime import (
    parse_date,
    parse_date_span,
    parse_date_window,
    raster_minutes,
    round_minutes,
)


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
