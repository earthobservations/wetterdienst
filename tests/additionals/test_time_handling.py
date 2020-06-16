import pytest
from dateparser import parse as parsedate
from pandas import Timestamp

from python_dwd.additionals.time_handling import mktimerange
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


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
