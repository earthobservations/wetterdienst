# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for radar sites."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from dirty_equals import IsDatetime, IsDict, IsInt, IsList, IsNumeric, IsStr

from wetterdienst import Settings
from wetterdienst.provider.dwd.radar import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarParameter,
    DwdRadarPeriod,
    DwdRadarResolution,
    DwdRadarValues,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
from wetterdienst.util.datetime import round_minutes

h5py = pytest.importorskip("h5py", reason="h5py not installed")
wrl = pytest.importorskip("wradlib", reason="wradlib not installed")


def test_radar_request_radolan_cdc_hourly_alignment_1(default_settings: Settings) -> None:
    """Verify the alignment of RADOLAN_CDC timestamps to designated interval marks of HH:50.

    Here, the given timestamp is at 00:53 and will be floored to 00:50.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start="2019-08-08 00:53:53",
        settings=default_settings,
    )

    assert request.start == dt.datetime(
        year=2019,
        month=8,
        day=8,
        hour=0,
        minute=50,
        second=0,
        tzinfo=ZoneInfo("UTC"),
    )


def test_radar_request_radolan_cdc_hourly_alignment_2(default_settings: Settings) -> None:
    """Verify the alignment of RADOLAN_CDC timestamps to designated interval marks of HH:50.

    Here, the given timestamp is at 00:42 and will be floored to 23:50 on the previous day.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start="2019-08-08 00:42:42",
        settings=default_settings,
    )

    assert request.start == dt.datetime(
        year=2019,
        month=8,
        day=7,
        hour=23,
        minute=50,
        second=0,
        tzinfo=ZoneInfo("UTC"),
    )


@pytest.mark.remote
def test_radar_request_radolan_cdc_historic_hourly_data(default_settings: Settings, radar_locations: list[str]) -> None:
    """Verify data acquisition for RADOLAN_CDC/hourly/historical."""
    timestamp = dt.datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0, tzinfo=ZoneInfo("UTC"))
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    # Verify number of results.
    assert len(results) == 1

    # Verify data.
    first = results[0]

    requested_header = wrl.io.read_radolan_header(first.data)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": IsDatetime(approx=timestamp.replace(tzinfo=None), delta=dt.timedelta(minutes=10)),
            "formatversion": 3,
            "intervalseconds": 3600,
            "maxrange": "150 km",
            "moduleflag": 1,
            "ncol": 900,
            "nrow": 900,
            "precision": 0.1,
            "producttype": "RW",
            "radarid": "10000",
            "radarlocations": IsList(IsStr(regex="|".join(radar_locations)), length=(10, len(radar_locations))),
            "radolanversion": "2.21.0",
        },
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_radolan_cdc_historic_daily_data(default_settings: Settings, radar_locations: list[str]) -> None:
    """Verify data acquisition for RADOLAN_CDC/daily/historical."""
    timestamp = dt.datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0, tzinfo=ZoneInfo("UTC"))
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        period=DwdRadarPeriod.HISTORICAL,
        start=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    # Verify number of results.
    assert len(results) == 1

    # Verify data.
    first = results[0]

    requested_header = wrl.io.read_radolan_header(first.data)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    radar_locations_pattern = r"|".join(radar_locations)
    days_sub = r"\s\d{2}"
    radardays_pattern = f"({radar_locations_pattern}){days_sub}"

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": IsDatetime(approx=timestamp.replace(tzinfo=None), delta=dt.timedelta(minutes=10)),
            "formatversion": 3,
            "intervalseconds": 86400,
            "maxrange": "150 km",
            "ncol": 900,
            "nrow": 900,
            "precision": 0.1,
            "producttype": "SF",
            "radarid": "10000",
            "radardays": IsList(IsStr(regex=radardays_pattern), length=(10, len(radar_locations))),
            "radarlocations": IsList(IsStr(regex=radar_locations_pattern), length=(10, len(radar_locations))),
            "radolanversion": "2.21.0",
        },
    )

    assert requested_attrs == attrs


@pytest.mark.remote
@pytest.mark.parametrize("parameter", [DwdRadarParameter.RV_REFLECTIVITY, DwdRadarParameter.WN_REFLECTIVITY])
def test_radar_request_composite_historic_timerange(parameter: DwdRadarParameter, default_settings: Settings) -> None:
    """Example for testing radar/composite RV and WN for a timerange (GH-3279).

    A run is one .tar holding an ODIM HDF5 file for the analysis and each of the 24 forecasts, dated to the run.
    """
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=parameter,
        start=timestamp,
        end=dt.timedelta(minutes=10),
        settings=default_settings,
    )

    results = list(request.query())

    # two runs, of which DWD may drop one
    assert len(results) in (25, 50)

    # Verify all timestamps are properly propagated from the tarfile.
    assert {result.timestamp for result in results} <= {request.start, request.start + dt.timedelta(minutes=5)}
    leads = [result.filename.split("_")[-1] for result in results[:25]]
    assert leads == [f"{lead:03d}-hd5" for lead in range(0, 125, 5)]

    # Verify data.
    for result in results[:1]:
        with h5py.File(result.data, mode="r") as f:
            assert f.attrs["Conventions"] == b"ODIM_H5/V2_3"
            assert f["what"].attrs["object"] == b"COMP"
            assert f["dataset1/data1/data"].shape == (1200, 1100)


@pytest.mark.xfail(reason="UnicodeDecodeError: invalid start byte")
@pytest.mark.remote
def test_radar_request_composite_historic_radolan_rw_yesterday(
    default_settings: Settings,
    radar_locations: list[str],
) -> None:
    """Verify acquisition of radar/composite/radolan_rw data works when using a specific date."""
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    requested_attrs["datetime"] = requested_attrs["datetime"].replace(tzinfo=None)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": IsDatetime(approx=timestamp, delta=dt.timedelta(minutes=65)),
            "formatversion": 3,
            "intervalseconds": 3600,
            "maxrange": "150 km",
            "moduleflag": 1,
            "ncol": 900,
            "nrow": 900,
            "precision": 0.1,
            "producttype": "RW",
            "radarid": "10000",
            "radarlocations": IsList(IsStr(regex="|".join(radar_locations)), length=(10, len(radar_locations))),
            "radolanversion": "2.29.1",
        },
    )

    assert requested_attrs == attrs


@pytest.mark.xfail(reason="UnicodeDecodeError: invalid start byte")
@pytest.mark.remote
def test_radar_request_composite_historic_radolan_rw_timerange(
    default_settings: Settings,
    radar_locations: list[str],
) -> None:
    """Verify acquisition of radar/composite/radolan_rw data works when using a specific date, with timerange."""
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start=timestamp,
        end=dt.timedelta(hours=3),
        settings=default_settings,
    )
    results = list(request.query())

    # Verify number of results.
    assert len(results) == IsInt(ge=18, le=19)

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    radarlocations_pattern = r"|".join(radar_locations)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": IsDatetime(approx=timestamp, delta=dt.timedelta(minutes=65)),
            "formatversion": 3,
            "intervalseconds": 3600,
            "maxrange": "150 km",
            "moduleflag": 1,
            "ncol": 900,
            "nrow": 900,
            "precision": 0.1,
            "producttype": "RW",
            "radarid": "10000",
            "radarlocations": IsList(IsStr(regex=radarlocations_pattern), length=(10, len(radar_locations))),
            "radolanversion": "2.29.1",
        },
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_site_historic_dx_yesterday(default_settings: Settings) -> None:
    """Verify acquisition of radar/site/DX data works when using a specific date."""
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start=timestamp,
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.radolan.parse_dx_header(requested_header)

    attrs = IsDict(
        {
            "bytes": IsInt(gt=0),
            "cluttermap": 0,
            "datetime": IsDatetime(approx=timestamp.replace(tzinfo=ZoneInfo("UTC")), delta=dt.timedelta(minutes=65)),
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
def test_radar_request_site_historic_dx_timerange(default_settings: Settings) -> None:
    """Verify acquisition of radar/site/DX data works when using a specific date, with timerange."""
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start=timestamp,
        end=dt.timedelta(hours=0.5),
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    assert len(results) == 6

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.radolan.parse_dx_header(requested_header)

    attrs = IsDict(
        {
            "bytes": IsInt(gt=0),
            "cluttermap": 0,
            "datetime": IsDatetime(approx=timestamp.replace(tzinfo=ZoneInfo("UTC")), delta=dt.timedelta(minutes=65)),
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
    "parameter",
    [
        DwdRadarParameter.LMAX_VOLUME_SCAN,
        DwdRadarParameter.PE_ECHO_TOP,
        DwdRadarParameter.PR_VELOCITY,
        DwdRadarParameter.PX250_REFLECTIVITY,
        DwdRadarParameter.PZ_CAPPI,
    ],
)
def test_radar_request_site_historic_hdf5_timerange(parameter: DwdRadarParameter, default_settings: Settings) -> None:
    """Verify acquisition of the radar/site HDF5 products works when using date ranges (GH-3279).

    The proof will use these parameters to acquire data:
    - start: Yesterday at this time
    - end:   start + 1 hour
    The format is not named: the products are served as ODIM HDF5 only.
    """
    start_date = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=parameter,
        start=start_date,
        end=dt.timedelta(hours=1),
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )

    assert request.start.minute % 5 == 0
    assert request.format == DwdRadarDataFormat.HDF5

    results = list(request.query())

    # a 1-hour window holds ~12-13 five-minute scans; DWD occasionally drops a scan, so tolerate a
    # small shortfall rather than asserting an exact count (which flakes on any gap)
    assert len(results) == IsInt(ge=10, le=13)
    assert all(result.timestamp >= request.start for result in results)

    # Verify data.
    with h5py.File(results[0].data, mode="r") as f:
        assert f.attrs["Conventions"] == b"ODIM_H5/V2_3"


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_hdf5_yesterday(default_settings: Settings) -> None:
    """Example for testing radar/site sweep_vol_v for a specific date."""
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start=timestamp,
        site=DwdRadarSite.ASB,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    # Verify number of elements.
    assert len(results) == 10

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_hdf5_yesterday(default_settings: Settings) -> None:
    """Example for testing radar/site sweep-precipitation for a specific date.

    This time in HDF5 format.
    """
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start=timestamp,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )
    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    # Verify number of elements.
    assert len(results) == 1

    # Get payload.
    buffer = results[0][1]
    payload = buffer.getvalue()

    # Verify data.
    assert payload.startswith(b"\x89HDF\r\n")

    # Verify more details.
    # h5dump ras07-stqual-pcpng01_sweeph5onem_vradh_00-2020093000403400-boo-10132-hd5

    hdf = h5py.File(buffer, "r")

    assert hdf["/how/radar_system"] is not None
    assert hdf["/how"].attrs.get("task") == b"Sc_Pcp-NG-01_BOO"
    assert hdf["/what"].attrs.get("source") == b"WMO:10132,NOD:deboo"

    assert hdf["/how"].attrs.get("scan_count") == 1
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    assert hdf["/dataset1/data1/data"].shape in ((360, 600), (359, 600), (358, 600), (357, 600))

    timestamp = round_minutes(request.start, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_hdf5_timerange(default_settings: Settings) -> None:
    """Example for testing radar/site sweep-precipitation for a specific date.

    This time in HDF5 format, with timerange.
    """
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start=timestamp,
        end=dt.timedelta(hours=1),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    # a 1-hour window holds ~12-13 five-minute scans; DWD occasionally drops a scan, so tolerate a
    # small shortfall rather than asserting an exact count (which flakes on any gap)
    assert len(results) == IsInt(ge=10, le=13)

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 1
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_hdf5_timerange(default_settings: Settings) -> None:
    """Example for testing radar/site sweep-precipitation for a specific date.

    This time in HDF5 format, with timerange.
    """
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start=timestamp,
        end=dt.timedelta(hours=0.5),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        msg = "Data currently not available"
        raise pytest.skip(msg)

    assert len(results) == IsInt(ge=51, le=60)

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))
