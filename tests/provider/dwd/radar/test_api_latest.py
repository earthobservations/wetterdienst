# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import re
from datetime import datetime

import pytest
import wradlib as wrl

from tests.provider.dwd.radar import station_reference_pattern_unsorted
from wetterdienst.provider.dwd.radar import DwdRadarValues
from wetterdienst.provider.dwd.radar.metadata import DwdRadarDate, DwdRadarParameter
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
from wetterdienst.util.datetime import round_minutes


@pytest.mark.xfail(reason="Out of service", strict=True)
@pytest.mark.remote
def test_radar_request_composite_latest_rx_reflectivity():
    """
    Example for testing radar COMPOSITES latest.
    """

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RX_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
    )

    buffer = next(request.query())[1]
    payload = buffer.getvalue()

    month_year = datetime.utcnow().strftime("%m%y")
    header = (
        f"RX......10000{month_year}BY 8101..VS 3SW   ......PR E\\+00INT   5GP 900x 900MS "
        f"..<{station_reference_pattern_unsorted}>"
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:160])


@pytest.mark.remote
def test_radar_request_composite_latest_rw_reflectivity():
    """
    Example for testing radar COMPOSITES (RADOLAN) latest.
    """

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
    )

    results = list(request.query())

    if len(results) == 0:
        raise pytest.skip("Data currently not available")

    buffer = results[0][1]
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.parse_dwd_composite_header(requested_header)

    # Verify data.
    assert datetime.utcnow().strftime("%m%y") == requested_attrs["datetime"].strftime("%m%y")

    attrs = {
        "producttype": "RW",
        "precision": 0.1,
        "formatversion": 3,
        "intervalseconds": 3600,
        "nrow": 900,
        "ncol": 900,
        "radarlocations": [
            "asb",
            "boo",
            "ros",
            "hnr",
            "umd",
            "pro",
            "ess",
            "fld",
            "drs",
            "neu",
            "nhb",
            "oft",
            "eis",
            "tur",
            "isn",
            "fbg",
            "mem",
        ],
        "moduleflag": 1,
    }

    # radar locations can change over time -> check if at least 10 radar locations
    # were found and at least 5 of them match with the provided one
    assert len(requested_attrs["radarlocations"]) >= 10
    assert len(list(set(requested_attrs["radarlocations"]) & set(attrs["radarlocations"]))) >= 5

    skip_attrs = ["radarid", "maxrange", "datasize", "datetime", "radarlocations", "radolanversion"]
    for attr in skip_attrs:
        requested_attrs.pop(attr, None)
    del attrs["radarlocations"]

    assert requested_attrs == attrs


@pytest.mark.remote
def test_radar_request_site_latest_dx_reflectivity():
    """
    Example for testing radar SITES latest.
    """

    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
        site=DwdRadarSite.BOO,
    )

    buffer = next(request.query())[1]
    requested_header = wrl.io.read_radolan_header(buffer)
    requested_attrs = wrl.io.radolan.parse_dx_header(requested_header)

    # Verify data.
    timestamp_aligned = round_minutes(datetime.utcnow(), 5)
    assert timestamp_aligned.strftime("%m%y") == requested_attrs["datetime"].strftime("%m%y")

    attrs = {
        "producttype": "DX",
        "version": " 2",
        "cluttermap": 0,
        "dopplerfilter": 4,
        "statfilter": 0,
        "elevprofile": [0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
        "message": "",
    }

    skip_attrs = ["radarid", "datetime", "bytes"]
    for attr in skip_attrs:
        requested_attrs.pop(attr, None)

    assert requested_attrs == attrs
