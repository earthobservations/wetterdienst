# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.


import pytest
import wradlib as wrl

from tests.provider.dwd.radar import station_reference_pattern_unsorted
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
def test_radar_request_site_most_recent_sweep_pcp_v_hdf5():
    """
    Example for testing radar sites most recent full SWEEP_PCP,
    this time in OPERA HDF5 (ODIM_H5) format.
    """
    import h5py

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
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

    assert hdf["/dataset1/data1/data"].shape == (360, 600)


@pytest.mark.remote
def test_radar_request_site_most_recent_sweep_vol_v_hdf5():
    """
    Example for testing radar sites most recent full SWEEP_VOL,
    this time in OPERA HDF5 (ODIM_H5) format.
    """
    import h5py

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    # assert 8 <= len(results) <= 10

    buffer = results[0].data
    payload = buffer.getvalue()

    # Verify data.
    assert payload.startswith(b"\x89HDF\r\n")

    # Verify more details.
    # wddump ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092917055800-boo-10132-hd5  # noqa:E501,B950

    hdf = h5py.File(buffer, "r")

    assert hdf["/how/radar_system"] is not None
    assert hdf["/how"].attrs.get("task") == b"Sc_Vol-5Min-NG-01_BOO"
    assert hdf["/what"].attrs.get("source") == b"WMO:10132,NOD:deboo"

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    assert hdf["/dataset1/data1/data"].shape in ((360, 720), (361, 720))

    # Verify that the second file is the second scan / elevation level.
    buffer = results[1].data
    hdf = h5py.File(buffer, "r")
    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 2


def test_radar_request_radolan_cdc_most_recent():
    """
    Example for testing radar sites most recent RADOLAN_CDC.
    """

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        period=DwdRadarPeriod.RECENT,
        start_date=DwdRadarDate.MOST_RECENT,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 1

    buffer = results[0].data
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    # Verify data.
    attrs = {
        "producttype": "SF",
        "datetime": request.start_date.to_pydatetime(),
        "radarid": "10000",
        "datasize": 1620000,
        "maxrange": "150 km",
        # "radolanversion": "2.29.1",
        "precision": 0.1,
        "intervalseconds": 86400,
        "nrow": 900,
        "ncol": 900,
        "radarlocations": [
            "asb",
            "boo",
            "ros",
            "hnr",
            "umd",
            "pro",
            "ess",
            "fld",
            "drs",
            "neu",
            "nhb",
            "oft",
            "eis",
            "tur",
            "isn",
            "fbg",
            "mem",
        ],
        # "radardays": [
        #     "asb 24",
        #     "boo 24",
        #     "drs 24",
        #     "eis 24",
        #     "ess 24",
        #     "fbg 24",
        #     "fld 24",
        #     "hnr 24",
        #     "isn 24",
        #     "mem 24",
        #     "neu 24",
        #     "nhb 24",
        #     "oft 24",
        #     "pro 24",
        #     "ros 24",
        #     "tur 24",
        #     "umd 24",
        # ],
    }
    del requested_attrs["radolanversion"]
    del requested_attrs["radardays"]

    # radarlocations can change over time -> check if at least 10 radar locations were found
    # and at least 5 of them match with the provided one
    assert len(requested_attrs["radarlocations"]) >= 10
    assert (
        len(list(set(requested_attrs["radarlocations"]) & set(attrs["radarlocations"])))
        >= 5
    )
    del requested_attrs["radarlocations"]
    del attrs["radarlocations"]

    assert requested_attrs == attrs
