# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import re
from zoneinfo import ZoneInfo

import pytest
from dirty_equals import IsDatetime, IsDict, IsInt, IsList, IsNumeric, IsStr

from wetterdienst.provider.dwd.radar import DwdRadarValues
from wetterdienst.provider.dwd.radar.metadata import DwdRadarDate, DwdRadarParameter
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


@pytest.mark.remote
def test_radar_request_composite_latest_rv_reflectivity(default_settings, station_reference_pattern_sorted_prefixed):
    """
    Example for testing radar COMPOSITES latest.
    """

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RV_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
        settings=default_settings,
    )

    buffer = next(request.query())[1]
    payload = buffer.getvalue()

    month_year = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None).strftime("%m%y")
    header = (
        f"RV......10000{month_year}BY   2640...VS 5SW ........PR E-02INT   5GP1200x1100VV 000MF 00000008MS"
        f"...<{station_reference_pattern_sorted_prefixed}>"
    )
    assert re.match(bytes(header, encoding="ascii"), payload[:200]), payload[:200]


@pytest.mark.remote
def test_radar_request_composite_latest_rw_reflectivity(default_settings, radar_locations):
    """
    Example for testing radar COMPOSITES (RADOLAN) latest.
    """

    wrl = pytest.importorskip("wradlib", reason="wradlib not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
        settings=default_settings,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    buffer = results[0][1]
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    # Verify data.
    attrs = IsDict(
        {
            "datasize": 1620000,
            "datetime": IsDatetime(
                approx=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None),
                delta=dt.timedelta(minutes=90),
            ),
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
def test_radar_request_site_latest_dx_reflectivity(default_settings):
    """
    Example for testing radar SITES latest.
    """

    wrl = pytest.importorskip("wradlib", reason="wradlib not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
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
