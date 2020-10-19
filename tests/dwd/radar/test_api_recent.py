from datetime import timedelta, datetime

import h5py
import pytest

from wetterdienst.dwd.radar import DWDRadarData, RadarParameter
from wetterdienst.dwd.radar.metadata import RadarDataFormat, RadarDataSubset
from wetterdienst.dwd.radar.sites import RadarSite


@pytest.mark.remote
def test_radar_request_site_recent_sweep_pcp_v_hdf5():
    """
    Example for testing radar sites SWEEP_PCP with timerange.
    """

    request = DWDRadarData(
        parameter=RadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=datetime.utcnow() - timedelta(hours=1),
        end_date=datetime.utcnow(),
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.SIMPLE,
    )

    results = list(request.collect_data())

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

    assert hdf["/dataset1/data1/data"].shape == (360, 600)


@pytest.mark.remote
def test_radar_request_site_recent_sweep_vol_v_hdf5():
    """
    Example for testing radar sites SWEEP_VOL with timerange.
    """

    request = DWDRadarData(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=datetime.utcnow() - timedelta(minutes=20),
        end_date=datetime.utcnow(),
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.SIMPLE,
    )

    results = list(request.collect_data())

    # Verify number of results.
    assert len(results) >= 20

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
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1
