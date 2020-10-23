import re
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta

import h5py
import pybufrkit
import pytest

from wetterdienst.util.datetime import round_minutes
from wetterdienst.dwd.radar import (
    DWDRadarData,
    DWDRadarParameter,
    DWDRadarDataFormat,
    DWDRadarDataSubset,
    DWDRadarResolution,
    DWDRadarPeriod,
)
from wetterdienst.dwd.radar.sites import DWDRadarSite

HERE = Path(__file__).parent


def test_radar_request_radolan_cdc_hourly_alignment_1():
    """
    Verify the alignment of RADOLAN_CDC timestamps
    to designated interval marks of HH:50.

    Here, the given timestamp is at 00:53
    and will be floored to 00:50.
    """

    request = DWDRadarData(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.HOURLY,
        period=DWDRadarPeriod.HISTORICAL,
        start_date="2019-08-08 00:53:53",
    )

    assert request.start_date == datetime(
        year=2019, month=8, day=8, hour=0, minute=50, second=0
    )


def test_radar_request_radolan_cdc_hourly_alignment_2():
    """
    Verify the alignment of RADOLAN_CDC timestamps
    to designated interval marks of HH:50.

    Here, the given timestamp is at 00:42
    and will be floored to 23:50 on the previous day.
    """

    request = DWDRadarData(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.HOURLY,
        period=DWDRadarPeriod.HISTORICAL,
        start_date="2019-08-08 00:42:42",
    )

    assert request.start_date == datetime(
        year=2019, month=8, day=7, hour=23, minute=50, second=0
    )


@pytest.mark.remote
def test_radar_request_radolan_cdc_historic_hourly_data():
    """
    Verify data acquisition for RADOLAN_CDC/hourly/historical.
    """

    request = DWDRadarData(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.HOURLY,
        period=DWDRadarPeriod.HISTORICAL,
        start_date="2019-08-08 00:50:00",
    )

    assert request == DWDRadarData(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.HOURLY,
        period=DWDRadarPeriod.HISTORICAL,
        start_date=datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0),
    )

    with Path(HERE, "radolan_hourly_201908080050").open("rb") as f:
        radolan_hourly = BytesIO(f.read())

    radolan_hourly_test = next(request.collect_data()).data

    assert radolan_hourly.getvalue() == radolan_hourly_test.getvalue()


@pytest.mark.remote
def test_radar_request_radolan_cdc_historic_daily_data():
    """
    Verify data acquisition for RADOLAN_CDC/daily/historical.
    """

    request = DWDRadarData(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.DAILY,
        period=DWDRadarPeriod.HISTORICAL,
        start_date="2019-08-08 00:50:00",
    )

    assert request == DWDRadarData(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.DAILY,
        period=DWDRadarPeriod.HISTORICAL,
        start_date=datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0),
    )

    with Path(HERE, "radolan_daily_201908080050").open("rb") as f:
        radolan_hourly = BytesIO(f.read())

    radolan_hourly_test = next(request.collect_data()).data

    assert radolan_hourly.getvalue() == radolan_hourly_test.getvalue()


@pytest.mark.xfail
@pytest.mark.remote
def test_radar_request_composite_historic_fx_yesterday():
    """
    Example for testing radar/composite FX for a specific date.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.FX_REFLECTIVITY,
        start_date=timestamp,
    )

    results = list(request.collect_data())

    # Verify number of results.
    assert len(results) == 25

    # Verify data.
    payload = results[0].data.getvalue()

    # TODO: Use wradlib to parse binary format.
    # https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_format.html
    date_time = request.start_date.strftime("%d%H%M")
    month_year = request.start_date.strftime("%m%y")
    header = (
        f"FX{date_time}10000{month_year}BY.......VS 3SW   2.12.0PR E-01INT   5GP 900x 900VV 000MF 00000002MS "  # noqa:E501,B950
        f"..<asb,boo,ros,hnr,umd,pro,ess,fld,drs,neu,(nhb,)?oft,eis,tur,(isn,)?fbg,mem>"
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:160])


@pytest.mark.xfail
@pytest.mark.remote
def test_radar_request_composite_historic_fx_timerange():
    """
    Example for testing radar/composite FX for a timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.FX_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(minutes=10),
    )

    results = list(request.collect_data())

    # Verify number of results.
    assert len(results) == 50

    # Verify all timestamps are properly propagated from the tarfile.
    assert all(
        request.start_date == result.timestamp
        or request.start_date + timedelta(minutes=5)
        for result in results
    )


@pytest.mark.remote
def test_radar_request_composite_historic_radolan_rw_yesterday():
    """
    Verify acquisition of radar/composite/radolan_rw data works
    when using a specific date.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.RW_REFLECTIVITY,
        start_date=timestamp,
    )

    buffer = next(request.collect_data())[1]
    payload = buffer.getvalue()

    # Verify data.
    # TODO: Use wradlib to parse binary format.
    # https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_format.html
    date_time = request.start_date.strftime("%d%H%M")
    month_year = request.start_date.strftime("%m%y")
    header = (
        f"RW{date_time}10000{month_year}BY.......VS 3SW   2.28.1PR E-01INT  60GP 900x 900MF 00000001MS "  # noqa:E501,B950
        f"..<asb,boo,ros,hnr,umd,pro,ess,fld,drs,neu,(nhb,)?oft,eis,tur,(isn,)?fbg,mem>"
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:160])


@pytest.mark.remote
def test_radar_request_composite_historic_radolan_rw_timerange():
    """
    Verify acquisition of radar/composite/radolan_rw data works
    when using a specific date, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.RW_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(hours=3),
    )
    results = list(request.collect_data())

    # Verify number of results.
    assert len(results) == 3

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_site_historic_dx_yesterday():
    """
    Verify acquisition of radar/site/DX data works
    when using a specific date.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.DX_REFLECTIVITY,
        start_date=timestamp,
        site=DWDRadarSite.BOO,
    )

    buffer = next(request.collect_data())[1]
    payload = buffer.getvalue()

    # Verify data.
    # TODO: Use wradlib to parse binary format.
    # https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_format.html
    timestamp_aligned = round_minutes(timestamp, 5)
    date_time = timestamp_aligned.strftime("%d%H%M")
    month_year = timestamp_aligned.strftime("%m%y")
    header = f"DX{date_time}10132{month_year}BY.....VS 2CO0CD4CS0EP0.80.80.80.80.80.80.80.8MS"  # noqa:E501,B950

    assert re.match(bytes(header, encoding="ascii"), payload)


@pytest.mark.remote
def test_radar_request_site_historic_dx_timerange():
    """
    Verify acquisition of radar/site/DX data works
    when using a specific date, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.DX_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(hours=0.5),
        site=DWDRadarSite.BOO,
    )

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 6

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_site_historic_pe_binary_yesterday():
    """
    Verify acquisition of radar/site/PE_ECHO_TOP data works
    when using a specific date.

    This time, we will use the BINARY data format.
    """

    # Acquire data from yesterday at this time.
    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.PE_ECHO_TOP,
        start_date=timestamp,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BINARY,
    )

    buffer = next(request.collect_data())[1]
    payload = buffer.getvalue()

    # Verify data.
    # TODO: Use wradlib to parse binary format.
    # https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_format.html
    date_time = request.start_date.strftime("%d%H")
    month_year = request.start_date.strftime("%m%y")
    header = (
        f"PE{date_time}..10132{month_year}BY ....?VS 1LV12  1.0  2.0  3.0  4.0  5.0  "  # noqa:E501,B950
        f"6.0  7.0  8.0  9.0 10.0 11.0 12.0CO0CD0CS0ET 5.0FL....MS"
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:160])


@pytest.mark.remote
def test_radar_request_site_historic_pe_bufr():
    """
    Verify acquisition of radar/site/PE_ECHO_TOP data works
    when using a specific date.

    This time, we will use the BUFR data format.
    """

    # Acquire data from yesterday at this time.
    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.PE_ECHO_TOP,
        start_date=timestamp,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BUFR,
    )

    buffer = next(request.collect_data())[1]
    payload = buffer.getvalue()

    # Verify data.
    header = b"\x00\x00\x00\x00\x00...BUFR"
    assert re.match(header, payload), payload[:20]

    # Read BUFR file.
    decoder = pybufrkit.decoder.Decoder()
    decoder.process(payload, info_only=True)


@pytest.mark.remote
@pytest.mark.parametrize(
    "format",
    [
        DWDRadarDataFormat.BINARY,
        DWDRadarDataFormat.BUFR,
    ],
)
def test_radar_request_site_historic_pe_timerange(format):
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

    request = DWDRadarData(
        parameter=DWDRadarParameter.PE_ECHO_TOP,
        start_date=start_date,
        end_date=end_date,
        site=DWDRadarSite.BOO,
        fmt=format,
    )

    assert request.start_date.minute % 5 == 0

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 12

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_site_historic_px250_bufr_yesterday():
    """
    Example for testing radar/site PX250 for a specific date.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.PX250_REFLECTIVITY,
        start_date=timestamp,
        site=DWDRadarSite.BOO,
    )

    buffer = next(request.collect_data())[1]
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

    request = DWDRadarData(
        parameter=DWDRadarParameter.PX250_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(hours=1),
        site=DWDRadarSite.BOO,
    )

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 12

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_bufr_yesterday():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in BUFR format.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BUFR,
    )

    buffer = next(request.collect_data())[1]
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

    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        end_date=timedelta(hours=1),
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BUFR,
    )

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 12

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_bufr_yesterday():
    """
    Example for testing radar/site sweep_vol_v for a specific date,
    this time in BUFR format.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BUFR,
    )

    buffer = next(request.collect_data())[1]
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

    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        end_date=timedelta(hours=0.5),
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BUFR,
    )

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 60

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_hdf5_yesterday():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.HDF5,
        subset=DWDRadarDataSubset.SIMPLE,
    )
    results = list(request.collect_data())

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

    assert hdf["/dataset1/data1/data"].shape == (360, 600)

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(
        timestamp.strftime("%Y%m%d"), encoding="ascii"
    )
    assert (
        hdf["/what"]
        .attrs.get("time")
        .startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))
    )


@pytest.mark.remote
def test_radar_request_site_historic_sweep_pcp_v_hdf5_timerange():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=timestamp,
        end_date=timedelta(hours=1),
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.HDF5,
        subset=DWDRadarDataSubset.SIMPLE,
    )

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 12

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_hdf5_yesterday():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.HDF5,
        subset=DWDRadarDataSubset.SIMPLE,
    )
    results = list(request.collect_data())

    # Verify number of elements.
    assert len(results) == 10

    # Get payload from first file.
    buffer = results[0].data
    payload = buffer.getvalue()

    # Verify data.
    assert payload.startswith(b"\x89HDF\r\n")

    # Verify more details.
    # h5dump ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092917055800-boo-10132-hd5  # noqa:E501,B950

    hdf = h5py.File(buffer, "r")

    assert hdf["/how/radar_system"] is not None
    assert hdf["/how"].attrs.get("task") == b"Sc_Vol-5Min-NG-01_BOO"
    assert hdf["/what"].attrs.get("source") == b"WMO:10132,NOD:deboo"

    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 1

    assert hdf["/dataset1/data1/data"].shape == (360, 180)

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(
        timestamp.strftime("%Y%m%d"), encoding="ascii"
    )
    assert (
        hdf["/what"]
        .attrs.get("time")
        .startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))
    )

    # Verify that the second file is the second scan / elevation level.
    buffer = results[1].data
    hdf = h5py.File(buffer, "r")
    assert hdf["/how"].attrs.get("scan_count") == 10
    assert hdf["/dataset1/how"].attrs.get("scan_index") == 2

    timestamp = round_minutes(request.start_date, 5)
    assert hdf["/what"].attrs.get("date") == bytes(
        timestamp.strftime("%Y%m%d"), encoding="ascii"
    )
    assert (
        hdf["/what"]
        .attrs.get("time")
        .startswith(bytes(timestamp.strftime("%H%M"), encoding="ascii"))
    )


@pytest.mark.remote
def test_radar_request_site_historic_sweep_vol_v_hdf5_timerange():
    """
    Example for testing radar/site sweep-precipitation for a specific date,
    this time in HDF5 format, with timerange.
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=timestamp,
        end_date=timedelta(hours=0.5),
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.HDF5,
        subset=DWDRadarDataSubset.SIMPLE,
    )

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 60

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_radvor_re_yesterday():
    """
    Verify acquisition of radar/radvor/re data works
    when using a specific date. Querying one point
    in time should yield 25 results for a single
    5 minute time step.

    https://opendata.dwd.de/weather/radar/radvor/re/
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.RE_REFLECTIVITY,
        start_date=timestamp,
    )

    results = list(request.collect_data())

    assert len(results) == 25

    payload = results[0].data.getvalue()

    # Verify data.
    # TODO: Use wradlib to parse binary format.
    # https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_format.html
    date_time = request.start_date.strftime("%d%H%M")
    month_year = request.start_date.strftime("%m%y")
    header = (
        f"RE{date_time}10000{month_year}BY.......VS 3SW P100004HPR E-03INT  60GP 900x 900VV 000MF 00000008QN "  # noqa:E501,B950
        f"016MS...<deasb,deboo,dedrs,deeis,deess,defbg,defld,dehnr,(deisn,)?demem(,deneu,denhb,deoft,depro,deros,detur,deumd)?>"  # noqa:E501,B950
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:200])


@pytest.mark.remote
def test_radar_request_radvor_re_timerange():
    """
    Verify acquisition of radar/radvor/re data works
    when using a specific date. Querying for 15 minutes
    worth of data should yield 75 results.

    https://opendata.dwd.de/weather/radar/radvor/re/
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.RE_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(minutes=3 * 5),
    )

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 3 * 25

    # TODO: Verify data.


@pytest.mark.remote
def test_radar_request_radvor_rq_yesterday():
    """
    Verify acquisition of radar/radvor/rq data works
    when using a specific date. Querying one point
    in time should yield 3 results for a single
    15 minute time step.

    https://opendata.dwd.de/weather/radar/radvor/rq/
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.RQ_REFLECTIVITY,
        start_date=timestamp,
    )

    results = list(request.collect_data())

    assert len(results) == 3

    payload = results[0].data.getvalue()

    # Verify data.
    # TODO: Use wradlib to parse binary format.
    # https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_format.html
    date_time = request.start_date.strftime("%d%H%M")
    month_year = request.start_date.strftime("%m%y")
    header = (
        f"RQ{date_time}10000{month_year}BY.......VS 3SW   2.28.1PR E-01INT  60GP 900x 900VV   0MF 00000008QN ...MS "  # noqa:E501,B950
        f"..<asb,boo,drs,eis,ess,fbg,fld,hnr,(isn,)?mem(,neu,nhb,oft,pro,ros,tur,umd)?>"
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:180])


@pytest.mark.remote
def test_radar_request_radvor_rq_timerange():
    """
    Verify acquisition of radar/radvor/rq data works
    when using a specific date. Querying for 45 minutes
    worth of data should yield 9 results.

    https://opendata.dwd.de/weather/radar/radvor/rq/
    """

    timestamp = datetime.utcnow() - timedelta(days=1)

    request = DWDRadarData(
        parameter=DWDRadarParameter.RQ_REFLECTIVITY,
        start_date=timestamp,
        end_date=timedelta(minutes=3 * 15),
    )

    # Verify number of elements.
    results = list(request.collect_data())
    assert len(results) == 3 * 3

    # TODO: Verify data.
