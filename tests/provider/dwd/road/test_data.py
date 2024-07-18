import polars as pl
import pytest

from wetterdienst.provider.dwd.road.api import DwdRoadRequest
from wetterdienst.util.eccodes import ensure_eccodes, ensure_pdbufr


@pytest.mark.skipif(not ensure_eccodes() or not ensure_pdbufr(), reason="eccodes and/or pdbufr not installed")
@pytest.mark.remote
@pytest.mark.parametrize("parameter", ("minute_10", "temperature_air_mean_2m"))
def test_dwd_road_weather(parameter):
    request = DwdRoadRequest(parameter).filter_by_station_id("A006")
    item = request.to_dict()["stations"][0]
    assert item == {
        "station_id": "A006",
        "start_date": None,
        "end_date": None,
        "latitude": 54.8892,
        "longitude": 8.9087,
        "height": 2.0,
        "name": "Boeglum",
        "state": "SH",
        "road_name": "L5S",
        "road_sector": "2",
        "road_surface_type": 1,
        "road_surroundings_type": 2,
        "road_type": 1,
        "station_group": "KK",
    }
    values = (
        request.values.all().df.drop_nulls(subset="value").filter(pl.col("parameter").eq("temperature_air_mean_2m"))
    )
    assert 230 <= values.get_column("value").min() <= 313  # approx. -+40 K
