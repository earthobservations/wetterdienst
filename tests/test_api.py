# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst import Wetterdienst


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,kind,kwargs",
    [
        # German Weather Service (DWD)
        (
            "dwd",
            "observation",
            {"parameter": "kl", "resolution": "daily", "period": "recent"},
        ),
        ("dwd", "forecast", {"parameter": "large", "mosmix_type": "large"}),
        # Environment and Climate Change Canada
        ("eccc", "observation", {"parameter": "daily", "resolution": "daily"}),
    ],
)
def test_api(provider, kind, kwargs):
    """ Test main wetterdienst API """
    # Build API
    api = Wetterdienst(provider, kind)

    # Discover parameters
    assert api.discover()

    # All stations
    request = api(**kwargs).all()

    stations = request.df

    # Check stations DataFrame columns
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

    # Check that there are actually stations
    assert not stations.empty

    # Query first DataFrame from values
    values = next(request.values.query()).df

    # TODO: DWD Forecast has no quality
    assert set(values.columns).issuperset(
        {"station_id", "parameter", "date", "value", "quality"}
    )

    assert not values.empty
