import pytest

from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.road.api import DwdRoadRequest, DwdRoadStationGroup
from wetterdienst.util.eccodes import ensure_eccodes, ensure_pdbufr
from wetterdienst.util.network import list_remote_files_fsspec


@pytest.mark.skipif(not ensure_eccodes() or not ensure_pdbufr(), reason="eccodes and/or pdbufr not installed")
@pytest.mark.remote
def test_dwd_road_weather():
    request = DwdRoadRequest(parameters=[("15_minutes", "data", "temperature_air_mean_2m")]).filter_by_station_id(
        "A006"
    )
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
    values = request.values.all().df.drop_nulls(subset="value")
    assert -40 <= values.get_column("value").min() <= 40  # approx. -+40 K


@pytest.mark.xfail(reason="number of station groups may change")
def test_dwd_road_weather_station_groups():
    url = "https://opendata.dwd.de/weather/weather_reports/road_weather_stations/"
    files = list_remote_files_fsspec(
        url=url,
        settings=Settings(),
        ttl=CacheExpiry.METAINDEX,
    )
    files = {file[len(url) :].split("/")[0] for file in files}
    if "quality-assured" in files:
        files.remove("quality-assured")
    assert files == {group.value for group in DwdRoadStationGroup}
