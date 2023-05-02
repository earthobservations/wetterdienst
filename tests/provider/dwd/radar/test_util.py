# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime
import re
from io import BytesIO

import pytest
import requests

from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.radar.util import RADAR_DT_PATTERN, get_date_from_filename, verify_hdf5


def test_radar_get_date_from_filename():
    date = get_date_from_filename(
        "sweep_pcp_v_0-20200926143033_10132--buf.bz2", pattern=RADAR_DT_PATTERN, formats=[DatetimeFormat.YMDHM.value]
    )
    assert date == datetime.datetime(2020, 9, 26, 14, 30)

    date = get_date_from_filename(
        "ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5",
        pattern=RADAR_DT_PATTERN,
        formats=[DatetimeFormat.YMDHM.value],
    )
    assert date == datetime.datetime(2020, 9, 26, 14, 30)

    date = get_date_from_filename(
        "ras07-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5",
        pattern=RADAR_DT_PATTERN,
        formats=[DatetimeFormat.YMDHM.value],
    )
    assert date == datetime.datetime(2020, 9, 26, 14, 30)

    date = get_date_from_filename(
        "rab02-tt_10132-20200926161533-boo---buf", pattern=RADAR_DT_PATTERN, formats=[DatetimeFormat.YMDHM.value]
    )
    assert date == datetime.datetime(2020, 9, 26, 16, 15)

    date = get_date_from_filename(
        "rab02-tt_10132-2301010000-boo---buf", pattern=RADAR_DT_PATTERN, formats=[DatetimeFormat.ymdhm.value]
    )
    assert date == datetime.datetime(2023, 1, 1, 0, 0)


hdf5_example = (
    "https://github.com/earthobservations/testdata/raw/main/opendata.dwd.de"
    "/weather/radar/sites/sweep_vol_v/ess/hdf5/filter_polarimetric"
    "/ras07-vol5minng01_sweeph5onem_vradh_00-2021040423555700-ess-10410-hd5"
)


@pytest.mark.remote
def test_radar_verify_hdf5_valid():
    pytest.importorskip("h5py", reason="h5py not installed")

    buffer = BytesIO(requests.get(hdf5_example, timeout=10).content)

    verify_hdf5(buffer)


def test_radar_verify_hdf5_invalid():
    pytest.importorskip("h5py", reason="h5py not installed")

    with pytest.raises(Exception) as ex:
        buffer = BytesIO()
        verify_hdf5(buffer)

    assert ex.match(re.escape("Unable to open file (file signature not found)"))
