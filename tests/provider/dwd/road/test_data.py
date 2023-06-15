import polars as pl
import pytest
from dirty_equals import IsDict, IsNumeric

from wetterdienst.provider.dwd.road.api import DwdRoadRequest
from wetterdienst.util.eccodes import ensure_eccodes, ensure_pdbufr


@pytest.mark.skipif(not ensure_eccodes() or not ensure_pdbufr(), reason="eccodes and/or pdbufr not installed")
@pytest.mark.remote
@pytest.mark.parametrize("parameter", ("minute_10", "temperature_air_mean_200"))
def test_dwd_road_weather(parameter):
    request = DwdRoadRequest(parameter).filter_by_station_id("A006")
    station_dict = request.to_dict()[0]
    assert station_dict == IsDict(
        {
            "height": 2.0,
            "latitude": 54.8892,
            "longitude": 8.9087,
            "name": "Boeglum",
            "road_name": "L5S",
            "road_sector": "2",
            "road_surface_type": 1,
            "road_surroundings_type": 2,
            "road_type": 1,
            "state": "SH",
            "station_group": "KK",
            "station_id": "A006",
        }
    ).settings(partial=True)
    values = (
        request.values.all().df.drop_nulls(subset="value").filter(pl.col("parameter").eq("temperature_air_mean_200"))
    )
    assert values.get_column("value").min() == IsNumeric(ge=230)  # approx. -40 K
    assert values.get_column("value").min() == IsNumeric(le=313)  # approx. +40 K
