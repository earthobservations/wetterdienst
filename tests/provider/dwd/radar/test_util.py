# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for radar utilities."""

from io import BytesIO

import pytest
from fsspec.implementations.http import HTTPFileSystem

from wetterdienst.provider.dwd.radar.util import RADAR_DT_PATTERN, get_date_string_from_filename, verify_hdf5

HDF5_EXAMPLE = (
    "https://github.com/earthobservations/testdata/raw/main/opendata.dwd.de"
    "/weather/radar/sites/sweep_vol_v/ess/hdf5/filter_polarimetric"
    "/ras07-vol5minng01_sweeph5onem_vradh_00-2021040423555700-ess-10410-hd5"
)


def test_radar_get_date_from_filename() -> None:
    """Test date extraction from radar filename."""
    date = get_date_string_from_filename(
        "sweep_pcp_v_0-20200926143033_10132--buf.bz2",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "202009261430"

    date = get_date_string_from_filename(
        "ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "202009261430"

    date = get_date_string_from_filename(
        "ras07-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "202009261430"

    date = get_date_string_from_filename(
        "rab02-tt_10132-20200926161533-boo---buf",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "202009261615"

    date = get_date_string_from_filename(
        "rab02-tt_10132-2301010000-boo---buf",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "2301010000"


@pytest.mark.remote
def test_radar_verify_hdf5_valid() -> None:
    """Test valid HDF5 file."""
    pytest.importorskip("h5py", reason="h5py not installed")
    httpfs = HTTPFileSystem()

    buffer = BytesIO(httpfs.cat(HDF5_EXAMPLE))

    verify_hdf5(buffer)


def test_radar_verify_hdf5_invalid() -> None:
    """Test invalid HDF5 file."""
    pytest.importorskip("h5py", reason="h5py not installed")

    buffer = BytesIO()
    with pytest.raises(Exception, match=r"Unable to (synchronously )?open file \(file signature not found\)"):
        verify_hdf5(buffer)
