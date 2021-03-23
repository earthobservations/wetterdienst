# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst import Wetterdienst


@pytest.mark.parametrize(
    "provider,kind,kwargs",
    [
        (
            "dwd",
            "observation",
            {"parameter": "kl", "resolution": "daily", "period": "recent"},
        ),
        ("dwd", "forecast", {"mosmix_type": "large"}),
    ],
)
def test_api(provider, kind, kwargs):
    api = Wetterdienst(provider, kind)

    request = api(**kwargs).all()

    stations = request.df

    assert set(stations.columns).issuperset(
        {
            "station_id",
            "from_date",
            "to_date",
            "height",
            "latitude",
            "longitude",
            "station_name",
            "state",
        }
    )

    assert not stations.empty

    values = next(request.values.query()).df

    # TODO: DWD Forecast has no quality
    assert set(values.columns).issuperset(
        {"station_id", "parameter", "date", "value", "quality"}
    )

    assert not values.empty
