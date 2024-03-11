# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.util.datetime import parse_date, raster_minutes, round_minutes


def test_raster_50min_regular():
    tm = dt.datetime(2010, 1, 1, 0, 56, 56)
    tm_aligned = raster_minutes(tm, 50)
    assert tm_aligned == dt.datetime(2010, 1, 1, 0, 50)


def test_raster_50min_wrap():
    tm = dt.datetime(2010, 1, 1, 0, 42, 42)
    tm_aligned = raster_minutes(tm, 50)
    assert tm_aligned == dt.datetime(2009, 12, 31, 23, 50)


def test_round_5min():
    tm = dt.datetime(2010, 1, 1, 0, 4, 42)
    tm_aligned = round_minutes(tm, 5)
    assert tm_aligned == dt.datetime(2010, 1, 1, 0, 0)


def test_parse_date():
    assert parse_date("2020") == dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02") == dt.datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02-02") == dt.datetime(2020, 2, 2, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02-02 02") == dt.datetime(2020, 2, 2, 2, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02-02 02:02") == dt.datetime(2020, 2, 2, 2, 2, tzinfo=ZoneInfo("UTC"))
    assert parse_date("2020-02-02 02:02:02") == dt.datetime(2020, 2, 2, 2, 2, 2, tzinfo=ZoneInfo("UTC"))
    with pytest.raises(ValueError) as exec_info:
        parse_date("02/02/2020")
    assert exec_info.match("date_string 02/02/2020 could not be parsed")
    with pytest.raises(ValueError) as exec_info:
        parse_date("02.02.2020")
    assert exec_info.match("date_string 02.02.2020 could not be parsed")
