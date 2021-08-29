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
        f"RX......10000{month_year}BY 8101..VS 3SW   ......PR E\\+00INT   5GP 900x 900MS "  # noqa:E501,B950
        f"..<{station_reference_pattern_unsorted}>"  # noqa:E501,B950
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
    attrs = {
        "producttype": "RW",
        # 'datetime': 'TODO',
        "radarid": "10000",
        "datasize": 1620000,
        "maxrange": "150 km",
        "radolanversion": "2.29.1",
        "precision": 0.1,
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

    # TODO check datetime
    del requested_attrs["datetime"]

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

    timestamp_aligned = round_minutes(datetime.utcnow(), 5)
    month_year = timestamp_aligned.strftime("%m%y")

    # Verify data.
    header = f"DX......10132{month_year}BY.....VS 2CO0CD4CS0EP0.80.80.80.80.80.80.80.8MS"  # noqa:E501,B950
    assert re.match(header, requested_header)
