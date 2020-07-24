from datetime import datetime

import pytest
import dateparser
from pandas import Timestamp

from wetterdienst.additionals.time_handling import mktimerange, parse_datetime
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


def test_parse_datetime():
    assert parse_datetime("2020-05-01") == datetime(2020, 5, 1, 0, 0)
    assert parse_datetime("2020-05-01T13:14:15") == datetime(2020, 5, 1, 13, 14, 15)
    assert parse_datetime("2020-05-01T13") == datetime(2020, 5, 1, 13, 0)


def test_mktimerange_annual():

    assert mktimerange(TimeResolution.ANNUAL, dateparser.parse("2019")) == (
        Timestamp("2019-01-01 00:00:00"),
        Timestamp("2019-12-31 00:00:00"),
    )

    assert mktimerange(
        TimeResolution.ANNUAL, dateparser.parse("2010"), dateparser.parse("2020")
    ) == (Timestamp("2010-01-01 00:00:00"), Timestamp("2020-12-31 00:00:00"))


def test_mktimerange_monthly():

    assert mktimerange(TimeResolution.MONTHLY, dateparser.parse("2020-05")) == (
        Timestamp("2020-05-01 00:00:00"),
        Timestamp("2020-05-31 00:00:00"),
    )

    assert mktimerange(
        TimeResolution.MONTHLY, dateparser.parse("2017-01"), dateparser.parse("2019-12")
    ) == (Timestamp("2017-01-01 00:00:00"), Timestamp("2019-12-31 00:00:00"))


def test_mktimerange_invalid():

    with pytest.raises(NotImplementedError):
        mktimerange(TimeResolution.DAILY, dateparser.parse("2020-05-01"))
