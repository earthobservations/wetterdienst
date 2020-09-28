import re

import h5py
import pytest

from wetterdienst import DWDRadarRequest, RadarParameter, TimeResolution
from wetterdienst.dwd.radar.metadata import RadarDate, RadarDataFormat, RadarDataSubset
from wetterdienst.dwd.radar.sites import RadarSite


@pytest.mark.remote
def test_radar_request_site_most_recent_sweep_pcp_v_hdf5():
    """
    Example for testing radar sites most recent full SWEEP_PCP,
    this time in OPERA HDF5 (ODIM_H5) format.
    """

    request = DWDRadarRequest(
        parameter=RadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=RadarDate.MOST_RECENT,
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.SIMPLE,
    )

    results = list(request.collect_data())

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

    request = DWDRadarRequest(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=RadarDate.MOST_RECENT,
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.SIMPLE,
    )

    results = list(request.collect_data())

    # Verify number of results.
    assert len(results) == 10

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

    assert hdf["/dataset1/data1/data"].shape == (360, 180)

    # Verify that the second file is the second scan / elevation level.
    buffer = results[1].data
    hdf = h5py.File(buffer, "r")
    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 2


def test_radar_request_radolan_cdc_most_recent():
    """
    Example for testing radar sites most recent RADOLAN_CDC.
    """

    request = DWDRadarRequest(
        parameter=RadarParameter.RADOLAN_CDC,
        time_resolution=TimeResolution.DAILY,
        start_date=RadarDate.MOST_RECENT,
    )

    results = list(request.collect_data())

    assert len(results) == 1

    payload = results[0].data.getvalue()

    # Verify data.
    # TODO: Use wradlib to parse binary format.
    # https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_format.html
    date_time = request.start_date.strftime("%d%H%M")
    month_year = request.start_date.strftime("%m%y")
    header = (
        f"SF{date_time}10000{month_year}BY.......VS 3SW   2.28.1PR E-01INT1440GP 900x 900MS "  # noqa:E501,B950
        f"..<asb,boo,ros,hnr,umd,pro,ess,fld,drs,neu,(nhb,)?oft,eis,tur,(isn,)?fbg,mem>"
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:180])
