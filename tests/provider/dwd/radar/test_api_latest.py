# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for radar API (latest)."""

import datetime as dt
import re
from zoneinfo import ZoneInfo

import pytest
from dirty_equals import IsDatetime, IsDict, IsInt, IsList, IsNumeric

from tests.provider.dwd.radar.odim import assert_rw_file
from wetterdienst import Settings
from wetterdienst.provider.dwd.radar import DwdRadarValues
from wetterdienst.provider.dwd.radar.metadata import (
    RADAR_PARAMETERS_SITES,
    DwdRadarDataSubset,
    DwdRadarDate,
    DwdRadarParameter,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [DwdRadarParameter.RV_REFLECTIVITY, DwdRadarParameter.WN_REFLECTIVITY],
)
def test_radar_request_composite_latest_reflectivity(parameter: DwdRadarParameter, default_settings: Settings) -> None:
    """Example for testing radar COMPOSITES latest: the analysis of the latest run, an ODIM HDF5 file (GH-3279)."""
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(
        parameter=parameter,
        start=DwdRadarDate.LATEST,
        settings=default_settings,
    )

    results = list(request.query())
    assert len(results) == 1
    result = results[0]

    # the first file of the .tar of the run, at the lead time 0, dated to the run
    assert re.fullmatch(rf"composite_{parameter.value}_\d{{8}}_\d{{4}}_000-hd5", result.filename)
    assert result.timestamp == IsDatetime(
        approx=dt.datetime.now(ZoneInfo("UTC")),
        delta=dt.timedelta(minutes=90),
    )

    with h5py.File(result.data, mode="r") as f:
        assert f.attrs["Conventions"] == b"ODIM_H5/V2_3"
        assert f["what"].attrs["object"] == b"COMP"
        assert f["dataset1/data1/data"].shape == (1200, 1100)


@pytest.mark.remote
def test_radar_request_composite_latest_rw_reflectivity(default_settings: Settings, radar_locations: list[str]) -> None:
    """Example for testing radar COMPOSITES (RADOLAN) latest: RW, which DWD names `bin` and publishes as ODIM HDF5."""
    pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start=DwdRadarDate.LATEST,
        settings=default_settings,
    )

    results = list(request.query())

    assert len(results) == 1, "DWD holds no file for this request"
    assert results[0].url == "https://opendata.dwd.de/weather/radar/radolan/rw/raa01-rw_10000-latest-dwd---bin.hdf5"

    # the hour that ends at the time of the file, which DWD publishes some 25 minutes after it
    end = assert_rw_file(results[0].data, radar_locations)
    assert end == IsDatetime(approx=dt.datetime.now(ZoneInfo("UTC")), delta=dt.timedelta(minutes=90))


@pytest.mark.remote
def test_radar_request_site_latest_dx_reflectivity(default_settings: Settings) -> None:
    """Example for testing radar SITES latest."""
    wrl = pytest.importorskip("wradlib", reason="wradlib not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start=DwdRadarDate.LATEST,
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )

    buffer = next(request.query())[1]
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.radolan.parse_dx_header(requested_header)
    requested_attrs["datetime"] = requested_attrs["datetime"].replace(tzinfo=None)

    # Verify data.
    attrs = IsDict(
        {
            "bytes": IsInt(gt=0),
            "cluttermap": 0,
            "datetime": IsDatetime(
                approx=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None),
                delta=dt.timedelta(minutes=65),
            ),
            "dopplerfilter": 4,
            "elevprofile": IsList(IsNumeric(ge=0.8, le=0.9), length=8),
            "message": "",
            "producttype": "DX",
            "radarid": "10132",
            "statfilter": 0,
            "version": " 2",
        },
    )

    assert requested_attrs == attrs


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "subset"),
    [
        (DwdRadarParameter.DX_REFLECTIVITY, None),
        (DwdRadarParameter.PE_ECHO_TOP, None),
        (DwdRadarParameter.SWEEP_PCP_ZDR, None),
        (DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H, DwdRadarDataSubset.UNFILTERED),
        (DwdRadarParameter.HX_REFLECTIVITY, None),
        (DwdRadarParameter.VII_INTEGRATED_ICE, None),
        (DwdRadarParameter.YW_REFLECTIVITY, None),
    ],
)
def test_radar_request_latest_is_dated_by_the_scan_time_in_the_file(
    parameter: DwdRadarParameter, subset: DwdRadarDataSubset | None, default_settings: Settings
) -> None:
    """Test that the latest file, whose name has no time, answers the time of its scan (GH-3299)."""
    pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(
        parameter=parameter,
        start=DwdRadarDate.LATEST,
        site=DwdRadarSite.BOO if parameter in RADAR_PARAMETERS_SITES else None,
        subset=subset,
        settings=default_settings,
    )

    results = list(request.query())

    assert results, "DWD holds no file for this request"
    for result in results:
        assert result.timestamp == IsDatetime(approx=dt.datetime.now(ZoneInfo("UTC")), delta=dt.timedelta(minutes=90))
