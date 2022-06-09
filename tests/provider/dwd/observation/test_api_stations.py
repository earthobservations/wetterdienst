# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime

import pandas as pd
import pytest
import pytz
from pandas._testing import assert_frame_equal

from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest

EXPECTED_DF = pd.DataFrame(
    {
        "station_id": pd.Series(["00001"], dtype=str),
        "from_date": [datetime(1937, 1, 1, tzinfo=pytz.UTC)],
        "to_date": [datetime(1986, 6, 30, tzinfo=pytz.UTC)],
        "height": pd.Series([478.0], dtype=float),
        "latitude": pd.Series([47.8413], dtype=float),
        "longitude": pd.Series([8.8493], dtype=float),
        "name": pd.Series(["Aach"], dtype=str),
        "state": pd.Series(["Baden-Württemberg"], dtype=str),
    }
)


@pytest.mark.remote
def test_dwd_observations_stations_filter():

    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
    )

    df = request.filter_by_station_id(station_id=("00001",)).df

    assert not df.empty

    assert_frame_equal(df, EXPECTED_DF)


@pytest.mark.remote
def test_dwd_observations_stations_filter_name():

    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
    )

    df = request.filter_by_name(name="Aach").df

    assert not df.empty

    assert_frame_equal(df, EXPECTED_DF)


@pytest.mark.remote
def test_dwd_observations_stations_filter_empty():

    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
    )

    df = request.filter_by_station_id(station_id=("FizzBuzz",)).df

    assert df.empty


@pytest.mark.remote
def test_dwd_observations_stations_filter_name_empty():

    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
    )

    df = request.filter_by_name(name="FizzBuzz").df

    assert df.empty


def test_dwd_observations_stations_fail():
    with pytest.raises(TypeError):
        DwdObservationRequest(
            DwdObservationDataset.CLIMATE_SUMMARY,
            DwdObservationResolution.DAILY,
            DwdObservationPeriod.HISTORICAL,
        ).filter_by_station_id(name="FizzBuzz")

    with pytest.raises(TypeError):
        DwdObservationRequest(
            DwdObservationDataset.CLIMATE_SUMMARY,
            DwdObservationResolution.DAILY,
            DwdObservationPeriod.HISTORICAL,
        ).filter_by_name(name=123)


@pytest.mark.remote
def test_dwd_observations_stations_geojson():

    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
    )

    results = request.filter_by_station_id(station_id=("00001",))

    assert not results.df.empty

    geojson = results.to_ogc_feature_collection()

    properties = geojson["features"][0]["properties"]
    geometry = geojson["features"][0]["geometry"]

    assert properties["name"] == "Aach"
    assert properties["state"] == "Baden-Württemberg"

    assert geometry == {
        "type": "Point",
        "coordinates": [8.8493, 47.8413, 478.0],
    }
