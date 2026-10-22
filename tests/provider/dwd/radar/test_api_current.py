# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD radar data access."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from dirty_equals import IsNumeric, IsTuple

from tests.provider.dwd.radar.published import (
    RADOLAN_CDC_DELAY,
    SWEEP_ELEVATION_1_DELAY,
    SWEEP_FIRST_FILE_DELAY,
    require_published,
)
from wetterdienst import Settings
from wetterdienst.provider.dwd.radar import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarDate,
    DwdRadarParameter,
    DwdRadarPeriod,
    DwdRadarResolution,
    DwdRadarValues,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite

h5py = pytest.importorskip("h5py", reason="h5py not installed")


@pytest.mark.remote
def test_radar_request_site_current_sweep_pcp_v_hdf5(default_settings: Settings) -> None:
    """Example for testing radar sites full current SWEEP_PCP.

    This time in OPERA HDF5 (ODIM_H5) format.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start=DwdRadarDate.CURRENT,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    results = list(request.query())

    require_published(results, request.start, SWEEP_FIRST_FILE_DELAY, "the sweep")

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

    shape = hdf["/dataset1/data1/data"].shape

    assert shape == IsTuple(IsNumeric(ge=358, le=361), 600)


@pytest.mark.remote
def test_radar_request_site_current_sweep_vol_v_hdf5_full(default_settings: Settings) -> None:
    """Example for testing radar sites full current SWEEP_VOL.

    This time in OPERA HDF5 (ODIM_H5) format.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start=DwdRadarDate.CURRENT,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    results = list(request.query())

    require_published(results, request.start, SWEEP_FIRST_FILE_DELAY, "the sweep")

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

    shape = hdf["/dataset1/data1/data"].shape

    assert shape == IsTuple(IsNumeric(ge=356, le=361), IsNumeric(ge=180, le=720))


@pytest.mark.remote
def test_radar_request_site_current_sweep_vol_v_hdf5_single(default_settings: Settings) -> None:
    """Example for testing radar sites single SWEEP_VOL of the slot that sweep 1 is published for.

    This time in OPERA HDF5 (ODIM_H5) format. The slot of now cannot be asked for: it is under 5 minutes old, and the
    sweep 1 is listed up to 323 s after it starts, so an empty answer could never be told from a late one. The slot
    `SWEEP_ELEVATION_1_DELAY` ago is at least that old.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - SWEEP_ELEVATION_1_DELAY,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        elevation=1,
        settings=default_settings,
    )

    results = list(request.query())

    assert results, "DWD holds no sweep 1 for a slot older than the time it takes to publish it"

    assert len(results) <= 1

    assert "vradh_01" in results[0].url

    buffer = results[0].data
    hdf = h5py.File(buffer, "r")

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 2


@pytest.mark.remote
@pytest.mark.parametrize(
    "resolution",
    [
        DwdRadarResolution.DAILY,
        DwdRadarResolution.HOURLY,
    ],
)
def test_radar_request_radolan_cdc_current(default_settings: Settings, resolution: DwdRadarResolution) -> None:
    """Verify data acquisition for current RADOLAN_CDC/daily+hourly.

    The file of the mark HH:50 is published 26 to 31 minutes later: the request for it is empty until then, and
    only until then it is no failure (`require_published`).
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        start=DwdRadarDate.CURRENT,
        resolution=resolution,
        period=DwdRadarPeriod.RECENT,
        settings=default_settings,
    )

    results = list(request.query())

    require_published(results, request.start, RADOLAN_CDC_DELAY, "the RADOLAN_CDC file")

    assert len(results) == 1


@pytest.mark.remote
def test_radar_request_radolan_cdc_current_5min(default_settings: Settings) -> None:
    """Verify failure for RADOLAN_CDC/5 minutes."""
    with pytest.raises(ValueError, match="RADOLAN_CDC only supports daily and hourly resolutions"):
        DwdRadarValues(
            parameter=DwdRadarParameter.RADOLAN_CDC,
            resolution=DwdRadarResolution.MINUTE_5,
            start=DwdRadarDate.CURRENT,
            settings=default_settings,
        )
