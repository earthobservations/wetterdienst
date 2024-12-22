# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import re
from zoneinfo import ZoneInfo

import pybufrkit
import pytest
from dirty_equals import IsDatetime, IsDict, IsInt, IsList, IsNumeric, IsStr

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


def test_radar_request_radolan_cdc_hourly_alignment_1(default_settings):
    """
    Verify the alignment of RADOLAN_CDC timestamps
    to designated interval marks of HH:50.

    Here, the given timestamp is at 00:53
    and will be floored to 00:50.
    """

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date="2019-08-08 00:53:53",
        settings=default_settings,
    )

    assert request.start_date == dt.datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0)


def test_radar_request_radolan_cdc_hourly_alignment_2(default_settings):
    """
    Verify the alignment of RADOLAN_CDC timestamps
    to designated interval marks of HH:50.

    Here, the given timestamp is at 00:42
    and will be floored to 23:50 on the previous day.
    """

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date="2019-08-08 00:42:42",
        settings=default_settings,
    )

    assert request.start_date == dt.datetime(year=2019, month=8, day=7, hour=23, minute=50, second=0)


@pytest.mark.remote
def test_radar_request_radolan_cdc_historic_hourly_data(default_settings, radar_locations):
    """
    Verify data acquisition for RADOLAN_CDC/hourly/historical.
    """
    timestamp = dt.datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0)
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    assert len(results) == 1

    # Verify data.
    first = results[0]

    requested_header = wrl.io.read_radolan_header(first.data)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": IsDatetime(approx=timestamp, delta=dt.timedelta(minutes=10)),
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
def test_radar_request_radolan_cdc_historic_daily_data(default_settings, radar_locations):
    """
    Verify data acquisition for RADOLAN_CDC/daily/historical.
    """
    timestamp = dt.datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0)
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

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
            "datetime": IsDatetime(approx=timestamp, delta=dt.timedelta(minutes=10)),
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
def test_radar_request_composite_historic_hg_yesterday(prefixed_radar_locations, default_settings):
    """
    Example for testing radar/composite FX for a specific date.
    """
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.HG_REFLECTIVITY,
        start_date=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    assert len(results) == 1

    # Verify data.
    first = results[0]

    requested_header = wrl.io.read_radolan_header(first.data)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    prefixed_radar_locations_pattern = re.compile(r"|".join(prefixed_radar_locations))

    attrs = IsDict(
        {
            "datasize": 5280000,
            "datetime": IsDatetime(approx=timestamp, delta=dt.timedelta(minutes=10)),
            "formatversion": 5,
            "intervalseconds": 300,
            "maxrange": "100 km",
            "moduleflag": 8,
            "ncol": 1100,
            "nrow": 1200,
            "precision": 1.0,
            "predictiontime": 0,
            "producttype": "HG",
            "radarid": "10000",
            "radarlocations": IsList(
                IsStr(regex=prefixed_radar_locations_pattern),
                length=(10, len(prefixed_radar_locations)),
            ),
            "radolanversion": IsStr(regex="P4100.H"),
        },
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_composite_historic_hg_timerange(default_settings):
    """
    Example for testing radar/composite FX for a timerange.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.HG_REFLECTIVITY,
        start_date=timestamp,
        end_date=dt.timedelta(minutes=10),
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    assert len(results) == 2

    # Verify all timestamps are properly propagated from the tarfile.
    assert all(
        request.start_date == result.timestamp or request.start_date + dt.timedelta(minutes=5) for result in results
    )


@pytest.mark.remote
def test_radar_request_composite_historic_radolan_rw_yesterday(radar_locations, default_settings):
    """
    Verify acquisition of radar/composite/radolan_rw data works
    when using a specific date.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

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


@pytest.mark.remote
def test_radar_request_composite_historic_radolan_rw_timerange(radar_locations, default_settings):
    """
    Verify acquisition of radar/composite/radolan_rw data works
    when using a specific date, with timerange.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=timestamp,
        end_date=dt.timedelta(hours=3),
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
def test_radar_request_site_historic_dx_yesterday(default_settings):
    """
    Verify acquisition of radar/site/DX data works
    when using a specific date.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

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
def test_radar_request_site_historic_dx_timerange(default_settings):
    """
    Verify acquisition of radar/site/DX data works
    when using a specific date, with timerange.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start_date=timestamp,
        end_date=dt.timedelta(hours=0.5),
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

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
def test_radar_request_site_historic_pe_binary_yesterday(default_settings):
    """
    Verify acquisition of radar/site/PE_ECHO_TOP data works
    when using a specific date.

    This time, we will use the BINARY data format.
    """

    # Acquire data from yesterday at this time.
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BINARY,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)

    date_time = request.start_date.strftime("%d%H")
    month_year = request.start_date.strftime("%m%y")
    header = (
        f"PE{date_time}..10132{month_year}BY ....?VS 1LV12  1.0  2.0  3.0  4.0  5.0  "
        f"6.0  7.0  8.0  9.0 10.0 11.0 12.0CO0CD0CS0ET 5.0FL....MS"
    )

    assert re.match(header, requested_header)


@pytest.mark.remote
def test_radar_request_site_historic_pe_bufr(default_settings):
    """
    Verify acquisition of radar/site/PE_ECHO_TOP data works
    when using a specific date.

    This time, we will use the BUFR data format.
    """

    # Acquire data from yesterday at this time.
    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BUFR,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    buffer = results[0].data
    payload = buffer.getvalue()

    # Verify data.
    header = b"\x00\x00\x00\x00\x00...BUFR"
    assert re.match(header, payload), payload[:20]

    # Read BUFR file.
    decoder = pybufrkit.decoder.Decoder()
    decoder.process(payload, info_only=True)


@pytest.mark.xfail(reason="month_year not matching start_date")
@pytest.mark.remote
@pytest.mark.parametrize(
    "fmt",
    [
        DwdRadarDataFormat.BINARY,
        DwdRadarDataFormat.BUFR,
    ],
)
def test_radar_request_site_historic_pe_timerange(fmt, default_settings):
    """
    Verify acquisition of radar/site/PE_ECHO_TOP data works
    when using date ranges.
    The proof will use these parameters to acquire data:
    - start_date: Yesterday at this time
    - end_date:   start_date + 1 hour
    This time, we will test both the BINARY and BUFR data format.
    """

    start_date = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)
    end_date = dt.timedelta(hours=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP,
        start_date=start_date,
        end_date=end_date,
        site=DwdRadarSite.BOO,
        fmt=fmt,
        settings=default_settings,
    )

    assert request.start_date.minute % 5 == 0

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) >= 1

    if fmt == DwdRadarDataFormat.BINARY:
        buffer = results[0].data
        payload = buffer.getvalue()
        month_year = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None).strftime("%m%y")
        header = (
            f"PE......10132{month_year}BY ....VS 1LV12  "
            "1.0  2.0  3.0  4.0  5.0  6.0  7.0  8.0  9.0 10.0 11.0 12.0"
            "CO0CD0CS0ET 5.0FL9999MS"
        )
        assert re.match(bytes(header, encoding="ascii"), payload[:115])


@pytest.mark.remote
def test_radar_request_site_historic_px250_bufr_yesterday(default_settings):
    """
    Example for testing radar/site PX250 for a specific date.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PX250_REFLECTIVITY,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    buffer = results[0].data
    payload = buffer.getvalue()

    # Verify data.
    header = b"\x00\x00\x00\x00\x00...BUFR"
    assert re.match(header, payload), payload[:20]

    # Read BUFR file.
    decoder = pybufrkit.decoder.Decoder()
    bufr = decoder.process(payload, info_only=True)

    # Verify timestamp in BUFR metadata.
    timestamp_aligned = round_minutes(timestamp, 5)
    bufr_timestamp = dt.datetime(
        bufr.year.value,
        bufr.month.value,
        bufr.day.value,
        bufr.hour.value,
        bufr.minute.value,
    )
    assert timestamp_aligned == bufr_timestamp


@pytest.mark.remote
def test_radar_request_site_historic_px250_bufr_timerange(default_settings):
    """
    Example for testing radar/site PX250 for a specific date, with timerange.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PX250_REFLECTIVITY,
        start_date=timestamp,
        end_date=dt.timedelta(hours=1),
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 12


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_hdf5_yesterday(default_settings):
    """
    Example for testing radar/site sweep_vol_v for a specific date.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        site=DwdRadarSite.ASB,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of elements.
    assert len(results) == 10

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_hdf5_yesterday(default_settings):
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

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

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_hdf5_timerange(default_settings):
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format, with timerange.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        end_date=dt.timedelta(hours=1),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) in (12, 13)

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 1
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_hdf5_timerange(default_settings):
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format, with timerange.
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        end_date=dt.timedelta(hours=0.5),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == IsInt(ge=51, le=60)

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_radvor_re_yesterday(prefixed_radar_locations, default_settings):
    """
    Verify acquisition of radar/radvor/re data works
    when using a specific date. Querying one point
    in time should yield 25 results for a single
    5 minute time step.

    https://opendata.dwd.de/weather/radar/radvor/re/
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RE_REFLECTIVITY,
        start_date=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 25

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": request.start_date,
            "formatversion": 5,
            "intervalseconds": 3600,
            "maxrange": "100 km",
            "moduleflag": 8,
            "ncol": 900,
            "nrow": 900,
            "precision": 0.001,
            "predictiontime": 0,
            "producttype": "RE",
            "quantification": 16,
            "radarid": "10000",
            "radarlocations": IsList(
                IsStr(regex="|".join(prefixed_radar_locations)),
                length=(10, len(prefixed_radar_locations)),
            ),
            "radolanversion": IsStr(regex="P4100.H"),
        },
    )

    assert requested_attrs == attrs, str(requested_attrs)


@pytest.mark.remote
def test_radar_request_radvor_re_timerange(default_settings, station_reference_pattern_sorted_prefixed):
    """
    Verify acquisition of radar/radvor/re data works
    when using a specific date. Querying for 15 minutes
    worth of data should yield 75 results.

    https://opendata.dwd.de/weather/radar/radvor/re/
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RE_REFLECTIVITY,
        start_date=timestamp,
        end_date=dt.timedelta(minutes=3 * 5),
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 3 * 25

    buffer = results[0].data
    requested_header = wrl.io.read_radolan_header(buffer)
    month_year = request.start_date.strftime("%m%y")

    pattern = (
        f"RE......10000{month_year}BY   162....VS 5SW  P4100.HPR E-03INT  60GP 900x 900VV 000MF 00000008QN 016MS"
        f"...<{station_reference_pattern_sorted_prefixed}>"
    )
    assert re.match(pattern, requested_header[:200]), requested_header[:200]


@pytest.mark.remote
def test_radar_request_radvor_rq_yesterday(radar_locations, default_settings):
    """
    Verify acquisition of radar/radvor/rq data works
    when using a specific date. Querying one point
    in time should yield 3 results for a single
    15 minute time step.

    https://opendata.dwd.de/weather/radar/radvor/rq/
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RQ_REFLECTIVITY,
        start_date=timestamp,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 3

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": request.start_date,
            "formatversion": 5,
            "intervalseconds": 3600,
            "maxrange": "100 km",
            "moduleflag": 8,
            "ncol": 900,
            "nrow": 900,
            "precision": 0.1,
            "predictiontime": 0,
            "producttype": "RQ",
            "quantification": IsInt(ge=0, le=1),
            "radarid": "10000",
            "radarlocations": IsList(IsStr(regex="|".join(radar_locations)), length=(10, len(radar_locations))),
            "radolanversion": "2.29.1",
        },
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_radvor_rq_timerange(radar_locations, default_settings):
    """
    Verify acquisition of radar/radvor/rq data works
    when using a specific date. Querying for 45 minutes
    worth of data should yield 9 results.

    https://opendata.dwd.de/weather/radar/radvor/rq/
    """

    timestamp = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RQ_REFLECTIVITY,
        start_date=timestamp,
        end_date=dt.timedelta(minutes=3 * 15),
        settings=default_settings,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 3 * 3

    requested_header = wrl.io.read_radolan_header(results[0].data)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": request.start_date,
            "formatversion": 5,
            "intervalseconds": 3600,
            "maxrange": "100 km",
            "moduleflag": 8,
            "ncol": 900,
            "nrow": 900,
            "precision": 0.1,
            "predictiontime": 0,
            "producttype": "RQ",
            "quantification": IsInt(ge=0, le=1),
            "radarid": "10000",
            "radarlocations": IsList(IsStr(regex="|".join(radar_locations)), length=(10, len(radar_locations))),
            "radolanversion": "2.29.1",
        },
    )

    assert requested_attrs == attrs
