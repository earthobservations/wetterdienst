import re
from datetime import datetime

import pytest

from wetterdienst import DWDRadarRequest
from wetterdienst.util.datetime import round_minutes
from wetterdienst.dwd.radar.metadata import RadarParameter, RadarDate
from wetterdienst.dwd.radar.sites import RadarSite


@pytest.mark.remote
def test_radar_request_composite_latest_rx_reflectivity():
    """
    Example for testing radar COMPOSITES latest.
    """

    request = DWDRadarRequest(
        parameter=RadarParameter.RX_REFLECTIVITY,
        start_date=RadarDate.LATEST,
    )

    buffer = next(request.collect_data())[1]
    payload = buffer.getvalue()

    month_year = datetime.utcnow().strftime("%m%y")
    header = (
        f"RX......10000{month_year}BY 8101..VS 3SW   2.28.1PR E\\+00INT   5GP 900x 900MS "  # noqa:E501,B950
        f"..<asb,boo,ros,hnr,umd,pro,ess,fld,drs,neu,(nhb,)?oft,eis,tur,(isn,)?fbg,mem>"
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:160])


@pytest.mark.remote
def test_radar_request_composite_latest_rw_reflectivity():
    """
    Example for testing radar COMPOSITES (RADOLAN) latest.
    """

    request = DWDRadarRequest(
        parameter=RadarParameter.RW_REFLECTIVITY,
        start_date=RadarDate.LATEST,
    )

    buffer = next(request.collect_data())[1]
    payload = buffer.getvalue()

    month_year = datetime.utcnow().strftime("%m%y")
    header = (
        f"RW......10000{month_year}"
        f"BY16201..VS 3SW   2.28.1PR E-01INT  60GP 900x 900MF 00000001MS "
        f"..<asb,boo,ros,hnr,umd,pro,ess,fld,drs,neu,(nhb,)?oft,eis,tur,(isn,)?fbg,mem>"
    )

    assert re.match(bytes(header, encoding="ascii"), payload[:160])


@pytest.mark.remote
def test_radar_request_site_latest_dx_reflectivity():
    """
    Example for testing radar SITES latest.
    """

    request = DWDRadarRequest(
        parameter=RadarParameter.DX_REFLECTIVITY,
        start_date=RadarDate.LATEST,
        site=RadarSite.BOO,
    )

    buffer = next(request.collect_data())[1]
    payload = buffer.getvalue()

    timestamp_aligned = round_minutes(datetime.utcnow(), 5)
    day_hour = timestamp_aligned.strftime("%d%H")
    month_year = timestamp_aligned.strftime("%m%y")
    header = f"DX{day_hour}..10132{month_year}BY.....VS 2CO0CD4CS0EP0.80.80.80.80.80.80.80.8MS"  # noqa:E501,B950
    assert re.match(bytes(header, encoding="ascii"), payload[:160])
