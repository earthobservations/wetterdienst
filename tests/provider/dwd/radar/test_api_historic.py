# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import re
from datetime import datetime, timedelta
from io import BytesIO

import pybufrkit
import pytest
import pytz
import requests
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


def test_radar_request_radolan_cdc_hourly_alignment_1():
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
    )

    assert request.start_date == datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0)


def test_radar_request_radolan_cdc_hourly_alignment_2():
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
    )

    assert request.start_date == datetime(year=2019, month=8, day=7, hour=23, minute=50, second=0)


@pytest.mark.remote
def test_radar_request_radolan_cdc_historic_hourly_data():
    """
    Verify data acquisition for RADOLAN_CDC/hourly/historical.
    """

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date="2019-08-08 00:50:00",
    )

    assert request == DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date=datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0),
    )

    radolan_hourly_backup_url = (
        "https://github.com/earthobservations/testdata/raw/main/"
        "opendata.dwd.de/climate_environment/CDC/grids_germany/"
        "hourly/radolan/historical/bin/2019/radolan_hourly_201908080050"
    )

    payload = requests.get(radolan_hourly_backup_url, timeout=10)

    radolan_hourly = BytesIO(payload.content)

    radolan_hourly_test = next(request.query()).data

    assert radolan_hourly.getvalue() == radolan_hourly_test.getvalue()


@pytest.mark.remote
def test_radar_request_radolan_cdc_historic_daily_data():
    """
    Verify data acquisition for RADOLAN_CDC/daily/historical.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date="2019-08-08 00:50:00",
    )

    assert request == DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date=datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0),
    )

    radolan_daily_backup_url = (
        "https://github.com/earthobservations/testdata/raw/main/"
        "opendata.dwd.de/climate_environment/CDC/grids_germany/"
        "daily/radolan/historical/bin/2019/radolan_daily_201908080050"
    )

    payload = requests.get(radolan_daily_backup_url, timeout=10)

    radolan_hourly = BytesIO(payload.content)

    radolan_hourly_test = next(request.query()).data

    assert radolan_hourly.getvalue() == radolan_hourly_test.getvalue()


@pytest.mark.remote
def test_radar_request_composite_historic_hg_yesterday(prefixed_radar_locations):
    """
    Example for testing radar/composite FX for a specific date.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.HG_REFLECTIVITY,
        start_date=timestamp,
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
            "datasize": 5280000,
            "datetime": IsDatetime(approx=timestamp, delta=timedelta(minutes=10)),
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
                IsStr(regex="|".join(prefixed_radar_locations)), length=(10, len(prefixed_radar_locations))
            ),
            "radolanversion": "P300001H",
        }
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_composite_historic_hg_timerange():
    """
    Example for testing radar/composite FX for a timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.HG_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(minutes=10),
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of results.
    assert len(results) == 2

    # Verify all timestamps are properly propagated from the tarfile.
    assert all(
        request.start_date == result.timestamp or request.start_date + timedelta(minutes=5) for result in results
    )


@pytest.mark.remote
def test_radar_request_composite_historic_radolan_rw_yesterday(radar_locations):
    """
    Verify acquisition of radar/composite/radolan_rw data works
    when using a specific date.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=timestamp,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": IsDatetime(approx=timestamp, delta=timedelta(minutes=65)),
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
        }
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_composite_historic_radolan_rw_timerange(radar_locations):
    """
    Verify acquisition of radar/composite/radolan_rw data works
    when using a specific date, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(hours=3),
    )
    results = list(request.query())

    # Verify number of results.
    assert len(results) == 3

    buffer = results[0].data

    # Verify data.
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": IsDatetime(approx=timestamp, delta=timedelta(minutes=65)),
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
        }
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_site_historic_dx_yesterday():
    """
    Verify acquisition of radar/site/DX data works
    when using a specific date.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
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
            "datetime": IsDatetime(approx=timestamp.replace(tzinfo=pytz.UTC), delta=timedelta(minutes=65)),
            "dopplerfilter": 4,
            "elevprofile": IsList(IsNumeric(ge=0.8, le=0.9), length=8),
            "message": "",
            "producttype": "DX",
            "radarid": "10132",
            "statfilter": 0,
            "version": " 2",
        }
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_site_historic_dx_timerange():
    """
    Verify acquisition of radar/site/DX data works
    when using a specific date, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(hours=0.5),
        site=DwdRadarSite.BOO,
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
            "datetime": IsDatetime(approx=timestamp.replace(tzinfo=pytz.UTC), delta=timedelta(minutes=65)),
            "dopplerfilter": 4,
            "elevprofile": IsList(IsNumeric(ge=0.8, le=0.9), length=8),
            "message": "",
            "producttype": "DX",
            "radarid": "10132",
            "statfilter": 0,
            "version": " 2",
        }
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_site_historic_pe_binary_yesterday():
    """
    Verify acquisition of radar/site/PE_ECHO_TOP data works
    when using a specific date.

    This time, we will use the BINARY data format.
    """

    # Acquire data from yesterday at this time.
    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BINARY,
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
def test_radar_request_site_historic_pe_bufr():
    """
    Verify acquisition of radar/site/PE_ECHO_TOP data works
    when using a specific date.

    This time, we will use the BUFR data format.
    """

    # Acquire data from yesterday at this time.
    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BUFR,
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


@pytest.mark.remote
@pytest.mark.parametrize(
    "fmt",
    [
        DwdRadarDataFormat.BINARY,
        DwdRadarDataFormat.BUFR,
    ],
)
def test_radar_request_site_historic_pe_timerange(fmt):
    """
    Verify acquisition of radar/site/PE_ECHO_TOP data works
    when using date ranges.
    The proof will use these parameters to acquire data:
    - start_date: Yesterday at this time
    - end_date:   start_date + 1 hour
    This time, we will test both the BINARY and BUFR data format.
    """

    start_date = datetime.utcnow() - timedelta(days=1)
    end_date = timedelta(hours=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP,
        start_date=start_date,
        end_date=end_date,
        site=DwdRadarSite.BOO,
        fmt=fmt,
    )

    assert request.start_date.minute % 5 == 0

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) >= 1

    # TODO: Verify data.


@pytest.mark.xfail
@pytest.mark.remote
def test_radar_request_site_historic_px250_bufr_yesterday():
    """
    Example for testing radar/site PX250 for a specific date.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PX250_REFLECTIVITY,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
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
    bufr_timestamp = datetime(
        bufr.year.value,
        bufr.month.value,
        bufr.day.value,
        bufr.hour.value,
        bufr.minute.value,
    )
    assert timestamp_aligned == bufr_timestamp


@pytest.mark.remote
def test_radar_request_site_historic_px250_bufr_timerange():
    """
    Example for testing radar/site PX250 for a specific date, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.PX250_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(hours=1),
        site=DwdRadarSite.BOO,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 12


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_bufr_yesterday():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in BUFR format.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        site=DwdRadarSite.ASB,
        fmt=DwdRadarDataFormat.BUFR,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    buffer = results[1]
    payload = buffer.getvalue()

    # Read BUFR file.
    decoder = pybufrkit.decoder.Decoder()
    bufr = decoder.process(payload, info_only=True)

    # Verify timestamp in BUFR metadata.
    timestamp_aligned = round_minutes(timestamp, 5)
    bufr_timestamp = datetime(
        bufr.year.value + 2000,
        bufr.month.value,
        bufr.day.value,
        bufr.hour.value,
        bufr.minute.value,
    )
    assert timestamp_aligned == bufr_timestamp


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_bufr_timerange():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in BUFR format, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        end_date=timedelta(hours=1),
        site=DwdRadarSite.ASB,
        fmt=DwdRadarDataFormat.BUFR,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 12

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 1
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_bufr_yesterday():
    """
    Example for testing radar/site sweep_vol_v for a specific date,
    this time in BUFR format.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        site=DwdRadarSite.ASB,
        fmt=DwdRadarDataFormat.BUFR,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    buffer = results[1]
    payload = buffer.getvalue()

    # Read BUFR file.
    decoder = pybufrkit.decoder.Decoder()
    bufr = decoder.process(payload, info_only=True)

    # Verify timestamp in BUFR metadata.
    timestamp_aligned = round_minutes(timestamp, 5)
    bufr_timestamp = datetime(
        bufr.year.value + 2000,
        bufr.month.value,
        bufr.day.value,
        bufr.hour.value,
        bufr.minute.value,
    )
    assert timestamp_aligned == bufr_timestamp


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_bufr_timerange():
    """
    Example for testing radar/site sweep_vol_v for a specific date,
    this time in BUFR format, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        end_date=timedelta(hours=0.5),
        site=DwdRadarSite.ASB,
        fmt=DwdRadarDataFormat.BUFR,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 60

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 1
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_hdf5_yesterday():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
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
def test_radar_request_site_historic_sweep_pcp_v_hdf5_timerange():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        end_date=timedelta(hours=1),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 12

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 1
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_hdf5_yesterday():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
    )
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    # Verify number of elements.
    assert len(results) == 10

    # Get payload from first file.
    buffer = results[0].data
    payload = buffer.getvalue()

    # Verify data.
    assert payload.startswith(b"\x89HDF\r\n")

    # Verify more details.
    # h5dump ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092917055800-boo-10132-hd5

    hdf = h5py.File(buffer, "r")

    assert hdf["/how/radar_system"] is not None
    assert hdf["/how"].attrs.get("task") == b"Sc_Vol-5Min-NG-01_BOO"
    assert hdf["/what"].attrs.get("source") == b"WMO:10132,NOD:deboo"

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    assert hdf["/dataset1/data1/data"].shape in ((360, 180), (360, 720), (361, 720), (358, 720))

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))

    # Verify that the second file is the second scan / elevation level.
    buffer = results[1].data
    hdf = h5py.File(buffer, "r")
    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 2

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_hdf5_timerange():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        end_date=timedelta(hours=0.5),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) in (60, 59)

    hdf = h5py.File(results[0].data, "r")

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(timestamp.strftime("%Y%m%d"), encoding="ascii")
    assert hdf["/what"].attrs.get("time").startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))


@pytest.mark.remote
def test_radar_request_radvor_re_yesterday(prefixed_radar_locations):
    """
    Verify acquisition of radar/radvor/re data works
    when using a specific date. Querying one point
    in time should yield 25 results for a single
    5 minute time step.

    https://opendata.dwd.de/weather/radar/radvor/re/
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RE_REFLECTIVITY,
        start_date=timestamp,
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
            "datetime": request.start_date.to_pydatetime(),
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
                IsStr(regex="|".join(prefixed_radar_locations)), length=(10, len(prefixed_radar_locations))
            ),
            "radolanversion": "P300001H",
        }
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_radvor_re_timerange():
    """
    Verify acquisition of radar/radvor/re data works
    when using a specific date. Querying for 15 minutes
    worth of data should yield 75 results.

    https://opendata.dwd.de/weather/radar/radvor/re/
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RE_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(minutes=3 * 5),
    )

    # Verify number of elements.
    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    assert len(results) == 3 * 25

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_radvor_rq_yesterday(radar_locations):
    """
    Verify acquisition of radar/radvor/rq data works
    when using a specific date. Querying one point
    in time should yield 3 results for a single
    15 minute time step.

    https://opendata.dwd.de/weather/radar/radvor/rq/
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RQ_REFLECTIVITY,
        start_date=timestamp,
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
            "datetime": request.start_date.to_pydatetime(),
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
        }
    )

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_radvor_rq_timerange(radar_locations):
    """
    Verify acquisition of radar/radvor/rq data works
    when using a specific date. Querying for 45 minutes
    worth of data should yield 9 results.

    https://opendata.dwd.de/weather/radar/radvor/rq/
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RQ_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(minutes=3 * 15),
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
            "datetime": request.start_date.to_pydatetime(),
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
        }
    )

    assert requested_attrs == attrs
