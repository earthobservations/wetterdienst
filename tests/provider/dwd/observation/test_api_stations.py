# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from dirty_equals import IsDatetime, IsDict
from polars.testing import assert_frame_equal

from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
)
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest


@pytest.fixture
def expected_df():
    return pl.DataFrame(
        [
            {
                "station_id": "00001",
                "start_date": dt.datetime(1937, 1, 1, tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime(1986, 6, 30, tzinfo=ZoneInfo("UTC")),
                "latitude": 47.8413,
                "longitude": 8.8493,
                "height": 478.0,
                "name": "Aach",
                "state": "Baden-Württemberg",
            }
        ],
        orient="row",
    )


@pytest.mark.remote
def test_dwd_observations_stations_filter(default_settings, expected_df):
    # Existing combination of parameters
    request = DwdObservationRequest(
        parameters=("daily", "climate_summary"),
        periods="historical",
        settings=default_settings,
    ).filter_by_station_id(station_id=("00001",))
    given_df = request.df
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observations_urban_stations(default_settings):
    """Test DWD Observation urban stations"""
    request = DwdObservationRequest(
        parameters=[("hourly", "urban_air_temperature")],
        periods="historical",
        settings=default_settings,
    ).all()
    assert request.station_id.to_list() == ["00399", "13667", "15811", "15818", "19711", "19844"]


@pytest.mark.remote
def test_dwd_observations_stations_filter_name(default_settings, expected_df):
    # Existing combination of parameters
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        periods="historical",
        settings=default_settings,
    ).filter_by_name(name="Aach")
    given_df = request.df
    assert_frame_equal(given_df, expected_df)


# TODO: move this test to test_io.py
@pytest.mark.remote
def test_dwd_observations_stations_geojson(default_settings):
    # Existing combination of parameters
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        periods="historical",
        settings=default_settings,
    ).filter_by_station_id(station_id=("00001",))
    assert not request.df.is_empty()
    geojson = request.to_ogc_feature_collection()
    assert geojson.keys() == {"data"}
    properties = geojson["data"]["features"][0]["properties"]
    geometry = geojson["data"]["features"][0]["geometry"]
    assert properties == {
        "id": "00001",
        "start_date": "1937-01-01T00:00:00+00:00",
        "end_date": "1986-06-30T00:00:00+00:00",
        "name": "Aach",
        "state": "Baden-Württemberg",
    }
    assert geometry == {
        "type": "Point",
        "coordinates": [8.8493, 47.8413, 478.0],
    }


@pytest.mark.remote
def test_dwd_observations_stations_minute_1(default_settings):
    # Existing combination of parameters
    request = DwdObservationRequest(
        parameters=[("minute_1", "precipitation")],
        periods="historical",
        settings=default_settings,
    ).filter_by_station_id("00003")
    given_df = request.df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "00003",
                "start_date": dt.datetime(1891, 1, 1, tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime(2012, 4, 6, tzinfo=ZoneInfo("UTC")),
                "latitude": 50.7827,
                "longitude": 6.0941,
                "height": 202.0,
                "name": "Aachen",
                "state": "Nordrhein-Westfalen",
            }
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observations_stations_name_with_comma():
    request = DwdObservationRequest(
        parameters=[("monthly", "kl")],
        periods="recent",
    )
    stations = request.all()
    stations = stations.df.filter(pl.col("station_id").is_in(["00314", "03164", "06272"]))
    assert stations.to_dicts() == [
        IsDict(
            {
                "station_id": "00314",
                "start_date": dt.datetime(1881, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_date": IsDatetime,
                "latitude": 51.1604,
                "longitude": 14.5042,
                "height": 234.0,
                "name": "Kubschütz, Kr. Bautzen",
                "state": "Sachsen",
            }
        ),
        IsDict(
            {
                "station_id": "03164",
                "start_date": dt.datetime(1881, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_date": IsDatetime,
                "latitude": 50.8492,
                "longitude": 8.7745,
                "height": 187.0,
                "name": "Cölbe, Kr. Marburg-Biedenkopf",
                "state": "Hessen",
            }
        ),
        IsDict(
            {
                "station_id": "06272",
                "start_date": dt.datetime(2004, 10, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_date": IsDatetime,
                "latitude": 50.8426,
                "longitude": 10.2518,
                "height": 284.0,
                "name": "Salzungen, Bad-Gräfen-Nitzendorf",
                "state": "Thüringen",
            }
        ),
    ]


@pytest.mark.remote
def test_dwd_observation_stations():
    skip_resolutions = [DwdObservationMetadata.minute_1]
    failed = []
    for resolution in DwdObservationMetadata:
        if resolution in skip_resolutions:
            continue
        for dataset in resolution:
            try:
                DwdObservationRequest(parameters=dataset).all()
            except Exception:
                failed.append(f"{resolution} - {dataset}")
    assert not failed
