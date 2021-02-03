# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import dateutil.parser
import pytest
import pytz

from wetterdienst import Resolution
from wetterdienst.util.datetime import mktimerange


def test_mktimerange_annual():
    assert mktimerange(
        Resolution.ANNUAL, dateutil.parser.isoparse("2019").replace(tzinfo=pytz.UTC)
    ) == (
        dateutil.parser.isoparse("2019-01-01 00:00:00Z"),
        dateutil.parser.isoparse("2019-12-31 00:00:00Z"),
    )
    assert mktimerange(
        Resolution.ANNUAL,
        dateutil.parser.isoparse("2010").replace(tzinfo=pytz.UTC),
        dateutil.parser.isoparse("2020").replace(tzinfo=pytz.UTC),
    ) == (
        dateutil.parser.isoparse("2010-01-01 00:00:00Z"),
        dateutil.parser.isoparse("2020-12-31 00:00:00Z"),
    )


def test_mktimerange_monthly():
    assert mktimerange(
        Resolution.MONTHLY, dateutil.parser.isoparse("2020-05").replace(tzinfo=pytz.UTC)
    ) == (
        dateutil.parser.isoparse("2020-05-01 00:00:00Z"),
        dateutil.parser.isoparse("2020-05-31 00:00:00Z"),
    )
    assert mktimerange(
        Resolution.MONTHLY,
        dateutil.parser.isoparse("2017-01").replace(tzinfo=pytz.UTC),
        dateutil.parser.isoparse("2019-12").replace(tzinfo=pytz.UTC),
    ) == (
        dateutil.parser.isoparse("2017-01-01 00:00:00Z"),
        dateutil.parser.isoparse("2019-12-31 00:00:00Z"),
    )


def test_mktimerange_invalid():
    with pytest.raises(NotImplementedError):
        mktimerange(Resolution.DAILY, dateutil.parser.isoparse("2020-05-01"))
