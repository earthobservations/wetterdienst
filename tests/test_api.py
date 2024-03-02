# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest
import zoneinfo

from wetterdienst import Settings, Wetterdienst
from wetterdienst.util.eccodes import ensure_eccodes


@pytest.mark.remote
@pytest.mark.parametrize(
    ("provider", "network", "kwargs", "station_id"),
    [
        # German Weather Service (DWD)
        # historical observation
        (
            "dwd",
            "observation",
            {"parameter": "kl", "resolution": "daily", "period": "recent"},
            None,
        ),
        # station forecasts
        ("dwd", "mosmix", {"parameter": "large", "mosmix_type": "large"}, None),
        ("dwd", "dmo", {"parameter": "icon", "dmo_type": "icon"}, None),
        # road weather
        pytest.param(
            "dwd",
            "road",
            {"parameter": "temperature_air_mean_200"},
            None,
            marks=pytest.mark.skipif(not ensure_eccodes(), reason="eccodes not installed"),
        ),
        # Environment and Climate Change Canada
        pytest.param(
            "eccc", "observation", {"parameter": "daily", "resolution": "daily"}, None, marks=pytest.mark.xfail
        ),  # noqa: E800, ERA001
        # IMGW Hydrology
        ("imgw", "hydrology", {"parameter": "hydrology", "resolution": "daily"}, None),
        # IMGW Meteorology
        ("imgw", "meteorology", {"parameter": "climate", "resolution": "daily"}, "249200180"),
        # NOAA Ghcn
        ("noaa", "ghcn", {"parameter": "precipitation_height", "resolution": "hourly"}, "AQC00914594"),
        ("noaa", "ghcn", {"parameter": "precipitation_height", "resolution": "daily"}, "AQC00914594"),
        # WSV Pegelonline
        ("wsv", "pegel", {"parameter": "stage"}, None),
        # EA Hydrology
        pytest.param(
            "ea", "hydrology", {"parameter": "discharge", "resolution": "daily"}, None, marks=pytest.mark.xfail
        ),
        # NWS Observation
        ("nws", "observation", {"parameter": "temperature_air_mean_200"}, "KBHM"),
        # Eaufrance Hubeau
        pytest.param("eaufrance", "hubeau", {"parameter": "discharge"}, None, marks=pytest.mark.xfail),  # noqa: E800
        # ZAMG Observation
        ("geosphere", "observation", {"parameter": "precipitation_height", "resolution": "daily"}, "5882"),
    ],
)
@pytest.mark.parametrize("si_units", (False, True))
@pytest.mark.slow
def test_api(provider, network, kwargs, si_units, station_id):
    """Test main wetterdienst API"""
    # Build API
    api = Wetterdienst(provider, network)
    # Discover parameters
    assert api.discover()
    settings = Settings(ts_si_units=si_units, ignore_env=True)
    # All stations_result
    if station_id:
        request = api(**kwargs, settings=settings).filter_by_station_id(station_id=station_id)
    else:
        request = api(**kwargs, settings=settings).all()
    stations = request.df
    first_start_date = stations.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    first_end_date = stations.get_column("end_date").to_list()[0]
    if first_end_date:
        assert first_end_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    # Check stations_result DataFrame columns
    assert set(stations.columns).issuperset(
        {
            "station_id",
            "start_date",
            "end_date",
            "latitude",
            "longitude",
            "height",
            "name",
            "state",
        }
    )
    # Check that there are actually stations_result
    assert not stations.is_empty()
    # Query first DataFrame from values
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset({"station_id", "parameter", "date", "value", "quality"})
    assert not values.drop_nulls(subset="value").is_empty()
