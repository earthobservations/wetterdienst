# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst import Settings, Wetterdienst


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,kwargs,station_id",
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
        # Environment and Climate Change Canada
        # ("eccc", "observation", {"parameter": "daily", "resolution": "daily"}), # noqa: E800
        # NOAA Ghcn
        ("noaa", "ghcn", {"parameter": "precipitation_height"}, None),
        # WSV Pegelonline
        ("wsv", "pegel", {"parameter": "water_level"}, None),
        # EA Hydrology
        ("ea", "hydrology", {"parameter": "flow", "resolution": "daily"}, None),
        # NWS Observation
        ("nws", "observation", {"parameter": "precipitation_height"}, "KBHM"),
        # Eaufrance Hubeau
        ("eaufrance", "hubeau", {"parameter": "flow"}, None),  # noqa: E800
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

    Settings.si_units = si_units

    # All stations_result
    if station_id:
        request = api(**kwargs).filter_by_station_id(station_id=station_id)
    else:
        request = api(**kwargs).all()

    stations = request.df

    # Check stations_result DataFrame columns
    assert set(stations.columns).issuperset(
        {
            "station_id",
            "from_date",
            "to_date",
            "height",
            "latitude",
            "longitude",
            "name",
            "state",
        }
    )

    # Check that there are actually stations_result
    assert not stations.empty

    # Query first DataFrame from values
    values = next(request.values.query()).df

    assert set(values.columns).issuperset({"station_id", "parameter", "date", "value", "quality"})

    values = values.drop(columns="quality").dropna(axis=0)

    assert not values.empty
