# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from wetterdienst import Resolution
from wetterdienst.util.datetime import mktimerange

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()


def test_mktimerange_annual():
    assert mktimerange(Resolution.ANNUAL, dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))) == (
        dt.datetime.fromisoformat("2019-01-01 00:00:00+00:00"),
        dt.datetime.fromisoformat("2019-12-31 00:00:00+00:00"),
    )
    assert mktimerange(
        Resolution.ANNUAL,
        dt.datetime(2010, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
    ) == (
        dt.datetime.fromisoformat("2010-01-01 00:00:00Z"),
        dt.datetime.fromisoformat("2020-12-31 00:00:00Z"),
    )


def test_mktimerange_monthly():
    assert mktimerange(Resolution.MONTHLY, dt.datetime(2020, 5, 1, tzinfo=ZoneInfo("UTC"))) == (
        dt.datetime.fromisoformat("2020-05-01 00:00:00+00:00"),
        dt.datetime.fromisoformat("2020-05-31 00:00:00+00:00"),
    )
    assert mktimerange(
        Resolution.MONTHLY,
        dt.datetime(2017, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2019, 12, 1, tzinfo=ZoneInfo("UTC")),
    ) == (
        dt.datetime.fromisoformat("2017-01-01 00:00:00+00:00"),
        dt.datetime.fromisoformat("2019-12-31 00:00:00+00:00"),
    )


def test_mktimerange_invalid():
    with pytest.raises(NotImplementedError):
        mktimerange(Resolution.DAILY, dt.datetime.fromisoformat("2020-05-01"))
