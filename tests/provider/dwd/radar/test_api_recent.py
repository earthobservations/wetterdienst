# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.provider.dwd.radar import DwdRadarParameter, DwdRadarValues
from wetterdienst.provider.dwd.radar.metadata import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite

h5py = pytest.importorskip("h5py", reason="h5py not installed")


@pytest.mark.remote
def test_radar_request_site_recent_sweep_pcp_v_hdf5(default_settings):
    """
    Example for testing radar sites SWEEP_PCP with timerange.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(hours=1),
        end_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    assert len(results) >= 12

    buffer = results[0].data
    payload = buffer.getvalue()

    # Verify data.
    assert payload.startswith(b"\x89HDF\r\n")

    # Verify more details.
    # wddump ras07-stqual-pcpng01_sweeph5onem_vradh_00-2020093000403400-boo-10132-hd5

    hdf = h5py.File(buffer, "r")

    assert hdf["/how/radar_system"] is not None
    assert hdf["/how"].attrs.get("task") == b"Sc_Pcp-NG-01_BOO"
    assert hdf["/what"].attrs.get("source") == b"WMO:10132,NOD:deboo"

    assert hdf["/how"].attrs.get("scan_count") == 1
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    assert hdf["/dataset1/data1/data"].shape in ((360, 600), (359, 600), (358, 600), (357, 600))


@pytest.mark.remote
def test_radar_request_site_recent_sweep_vol_v_hdf5(default_settings):
    """
    Example for testing radar sites SWEEP_VOL with timerange.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(minutes=20),
        end_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    assert len(results) >= 20

    buffer = results[0].data
    payload = buffer.getvalue()

    # Verify data.
    assert payload.startswith(b"\x89HDF\r\n")

    # Verify more details.
    # wddump ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092917055800-boo-10132-hd5

    hdf = h5py.File(buffer, "r")

    assert hdf["/how/radar_system"] is not None
    assert hdf["/how"].attrs.get("task") == b"Sc_Vol-5Min-NG-01_BOO"
    assert hdf["/what"].attrs.get("source") == b"WMO:10132,NOD:deboo"

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    assert hdf["/dataset1/data1/data"].shape in ((361, 720), (360, 720), (359, 720), (358, 720), (356, 720))

    # Verify that the second file is the second scan / elevation level.
    buffer = results[1].data
    hdf = h5py.File(buffer, "r")
    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1
