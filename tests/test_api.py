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
            "STATION_ID",
            "FROM_DATE",
            "TO_DATE",
            "HEIGHT",
            "LATITUDE",
            "LONGITUDE",
            "STATION_NAME",
            "STATE",
        }
    )

    assert not stations.empty

    values = next(request.values.query()).df

    # TODO: DWD Forecast has no quality
    assert set(values.columns).issuperset(
        {"STATION_ID", "PARAMETER", "DATE", "VALUE", "QUALITY"}
    )

    assert not values.empty
