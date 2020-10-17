import h5py
import pytest

from wetterdienst import DWDRadarData, RadarParameter, TimeResolution
from wetterdienst.dwd.radar.metadata import RadarDate, RadarDataFormat, RadarDataSubset
from wetterdienst.dwd.radar.sites import RadarSite


@pytest.mark.remote
def test_radar_request_site_current_sweep_pcp_v_hdf5():
    """
    Example for testing radar sites full current SWEEP_PCP,
    this time in OPERA HDF5 (ODIM_H5) format.
    """

    request = DWDRadarData(
        parameter=RadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=RadarDate.CURRENT,
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.SIMPLE,
    )

    results = list(request.collect_data())

    if results:

        buffer = results[0].data
        payload = buffer.getvalue()

        # Verify data.
        assert payload.startswith(b"\x89HDF\r\n")

        # Verify more details.
        # wddump ras07-stqual-pcpng01_sweeph5onem_vradh_00-2020093000403400-boo-10132-hd5  # noqa:E501,B950

        hdf = h5py.File(buffer, "r")

        assert hdf["/how/radar_system"] is not None
        assert hdf["/how"].attrs.get("task") == b"Sc_Pcp-NG-01_BOO"
        assert hdf["/what"].attrs.get("source") == b"WMO:10132,NOD:deboo"

        assert hdf["/how"].attrs.get("scan_count") == 1
        assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

        shape = hdf["/dataset1/data1/data"].shape

        assert shape == (360, 600) or shape == (361, 600)


@pytest.mark.remote
def test_radar_request_site_current_sweep_vol_v_hdf5_full():
    """
    Example for testing radar sites full current SWEEP_VOL,
    this time in OPERA HDF5 (ODIM_H5) format.
    """

    request = DWDRadarData(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=RadarDate.CURRENT,
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.SIMPLE,
    )

    results = list(request.collect_data())

    if results:

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

        shape = hdf["/dataset1/data1/data"].shape

        assert shape == (360, 180) or shape == (361, 180)


@pytest.mark.remote
def test_radar_request_site_current_sweep_vol_v_hdf5_single():
    """
    Example for testing radar sites single current SWEEP_VOL,
    this time in OPERA HDF5 (ODIM_H5) format.
    """

    request = DWDRadarData(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=RadarDate.CURRENT,
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.SIMPLE,
        elevation=1,
    )

    results = list(request.collect_data())

    assert len(results) <= 1

    if results:
        assert "vradh_01" in results[0].url

        buffer = results[0].data
        hdf = h5py.File(buffer, "r")

        assert hdf["/how"].attrs.get("scan_count") == 10
        assert hdf["/dataset1/how"].attrs.get("scan_index") == 2


@pytest.mark.remote
@pytest.mark.parametrize(
    "time_resolution",
    [
        TimeResolution.DAILY,
        TimeResolution.HOURLY,
    ],
)
def test_radar_request_radolan_cdc_current(time_resolution):
    """
    Verify data acquisition for current RADOLAN_CDC/daily+hourly.

    Remark: More often than not, this data is not
    available when looking at CURRENT.
    """

    request = DWDRadarData(
        parameter=RadarParameter.RADOLAN_CDC,
        start_date=RadarDate.CURRENT,
        time_resolution=time_resolution,
    )

    list(request.collect_data())


@pytest.mark.xfail
@pytest.mark.remote
def test_radar_request_radolan_cdc_current_5min():
    """
    Verify data acquisition for RADOLAN_CDC/5 minutes.

    FIXME: Does not work as expected yet.
    """

    request = DWDRadarData(
        parameter=RadarParameter.RADOLAN_CDC,
        time_resolution=TimeResolution.MINUTE_5,
        start_date=RadarDate.CURRENT,
    )

    list(request.collect_data())
