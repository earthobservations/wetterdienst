from datetime import datetime

import pytest
from dateparser import parse as parsedate
from pandas import Timestamp

from python_dwd.additionals.time_handling import mktimerange, parse_datetime, convert_datetime_hourly
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def test_parse_datetime():
    assert parse_datetime('2020-05-01') == datetime(2020, 5, 1, 0, 0)
    assert parse_datetime('2020-05-01T13:14:15') == datetime(2020, 5, 1, 13, 14, 15)
    assert parse_datetime('2020-05-01T13') == datetime(2020, 5, 1, 13, 0)


def test_mktimerange_annual():

    assert mktimerange(TimeResolution.ANNUAL, parsedate('2019')) == \
           (Timestamp('2019-01-01 00:00:00'), Timestamp('2019-12-31 00:00:00'))

    assert mktimerange(TimeResolution.ANNUAL, parsedate('2010'), parsedate('2020')) == \
           (Timestamp('2010-01-01 00:00:00'), Timestamp('2020-12-31 00:00:00'))


def test_mktimerange_monthly():

    assert mktimerange(TimeResolution.MONTHLY, parsedate('2020-05')) == \
           (Timestamp('2020-05-01 00:00:00'), Timestamp('2020-05-31 00:00:00'))

    assert mktimerange(TimeResolution.MONTHLY, parsedate('2017-01'), parsedate('2019-12')) == \
           (Timestamp('2017-01-01 00:00:00'), Timestamp('2019-12-31 00:00:00'))


def test_mktimerange_invalid():

    with pytest.raises(NotImplementedError):
        mktimerange(TimeResolution.DAILY, parsedate('2020-05-01'))


def test_convert_datetime_hourly():

    assert convert_datetime_hourly('2018121308') == Timestamp('2018-12-13 08:00:00')
    assert convert_datetime_hourly('2001010112:03') == Timestamp('2001-01-01 12:00:00')
