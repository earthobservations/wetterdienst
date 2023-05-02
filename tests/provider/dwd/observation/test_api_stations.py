# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest


@pytest.fixture
def expected_df():
    return pl.DataFrame(
        {
            "station_id": ["00001"],
            "from_date": [dt.datetime(1937, 1, 1, tzinfo=dt.timezone.utc)],
            "to_date": [dt.datetime(1986, 6, 30, tzinfo=dt.timezone.utc)],
            "height": [478.0],
            "latitude": [47.8413],
            "longitude": [8.8493],
            "name": ["Aach"],
            "state": ["Baden-Württemberg"],
        }
    )


@pytest.mark.remote
def test_dwd_observations_stations_filter(default_settings, expected_df):
    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
        settings=default_settings,
    ).filter_by_station_id(station_id=("00001",))
    given_df = request.df
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observations_urban_stations(default_settings):
    """Test DWD Observation urban stations"""
    request = DwdObservationRequest(
        parameter="urban_air_temperature", resolution="hourly", period="historical", settings=default_settings
    ).all()
    assert request.station_id.to_list() == ["00399", "13667", "15811", "15818"]


@pytest.mark.remote
def test_dwd_observations_stations_filter_name(default_settings, expected_df):
    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
        settings=default_settings,
    ).filter_by_name(name="Aach")
    given_df = request.df
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observations_stations_geojson(default_settings):
    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
        settings=default_settings,
    ).filter_by_station_id(station_id=("00001",))
    assert not request.df.is_empty()
    geojson = request.to_ogc_feature_collection()
    properties = geojson["features"][0]["properties"]
    geometry = geojson["features"][0]["geometry"]
    assert properties["name"] == "Aach"
    assert properties["state"] == "Baden-Württemberg"
    assert geometry == {
        "type": "Point",
        "coordinates": [8.8493, 47.8413, 478.0],
    }


@pytest.mark.remote
def test_dwd_observations_stations_minute_1(default_settings):
    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.PRECIPITATION,
        DwdObservationResolution.MINUTE_1,
        DwdObservationPeriod.HISTORICAL,
        settings=default_settings,
    ).filter_by_station_id("00003")
    given_df = request.df
    expected_df = pl.DataFrame(
        {
            "station_id": "00003",
            "from_date": dt.datetime(1891, 1, 1, tzinfo=dt.timezone.utc),
            "to_date": dt.datetime(2012, 4, 6, tzinfo=dt.timezone.utc),
            "height": 202.0,
            "latitude": 50.7827,
            "longitude": 6.0941,
            "name": "Aachen",
            "state": "Nordrhein-Westfalen",
        }
    )
    assert_frame_equal(given_df, expected_df)
