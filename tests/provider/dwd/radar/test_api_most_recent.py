# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest
from dirty_equals import IsDict, IsList, IsStr

from wetterdienst.provider.dwd.radar import (
    DwdRadarParameter,
    DwdRadarPeriod,
    DwdRadarValues,
)
from wetterdienst.provider.dwd.radar.metadata import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarDate,
    DwdRadarResolution,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


@pytest.mark.remote
def test_radar_request_site_most_recent_sweep_pcp_v_hdf5(default_settings):
    """
    Example for testing radar sites most recent full SWEEP_PCP,
    this time in OPERA HDF5 (ODIM_H5) format.
    """
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    assert len(results) == 1

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

    assert hdf["/dataset1/data1/data"].shape in ((360, 600), (359, 600), (358, 600))


@pytest.mark.remote
def test_radar_request_site_most_recent_sweep_vol_v_hdf5(default_settings):
    """
    Example for testing radar sites most recent full SWEEP_VOL,
    this time in OPERA HDF5 (ODIM_H5) format.
    """
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    assert 4 <= len(results) <= 10

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

    assert hdf["/dataset1/data1/data"].shape in ((360, 720), (361, 720), (358, 720))

    # Verify that the second file is the second scan / elevation level.
    buffer = results[1].data
    hdf = h5py.File(buffer, "r")
    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 2


@pytest.mark.remote
def test_radar_request_radolan_cdc_most_recent(default_settings, radar_locations):
    """
    Example for testing radar sites most recent RADOLAN_CDC.
    """

    wrl = pytest.importorskip("wradlib", reason="wradlib not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        period=DwdRadarPeriod.RECENT,
        start_date=DwdRadarDate.MOST_RECENT,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 1

    buffer = results[0].data
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    # Verify data.
    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": request.start_date,
            "formatversion": 3,
            "intervalseconds": 86400,
            "maxrange": "150 km",
            "ncol": 900,
            "nrow": 900,
            "precision": 0.1,
            "producttype": "SF",
            "radardays": IsList(IsStr(regex=" [0-9]?[0-9]?|".join(radar_locations)), length=(10, len(radar_locations))),
            "radarid": "10000",
            "radarlocations": IsList(IsStr(regex="|".join(radar_locations)), length=(10, len(radar_locations))),
            "radolanversion": "2.29.1",
        },
    )

    assert requested_attrs == attrs
