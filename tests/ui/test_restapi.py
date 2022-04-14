# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest
from fastapi.testclient import TestClient

from wetterdienst.ui.restapi import app

client = TestClient(app)


def test_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "Wetterdienst - Open weather data for humans" in response.text


def test_robots():
    response = client.get("/robots.txt")
    assert response.status_code == 200


def test_no_provider():
    response = client.get(
        "/restapi/stations",
        params={
            "provider": "abc",
            "network": "abc",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "all": "true",
        },
    )

    assert "Choose provider and network from /restapi/coverage" in response.text


def test_no_network():
    response = client.get(
        "/restapi/stations",
        params={
            "provider": "dwd",
            "network": "abc",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "all": "true",
        },
    )

    assert "Choose provider and network from /restapi/coverage" in response.text


def test_data_range(capsys):
    response = client.get(
        "/restapi/values",
        params={
            "provider": "eccc",
            "network": "observation",
            "parameter": "precipitation_height",
            "resolution": "daily",
            "period": "historical",
            "name": "toronto",
        },
    )

    assert "Combination of provider ECCC and network OBSERVATION requires start and end date" in response.text


def test_dwd_stations_basic():

    response = client.get(
        "/restapi/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "all": "true",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == "00011"
    assert response.json()["data"][0]["name"] == "Donaueschingen (Landeplatz)"
    assert response.json()["data"][0]["latitude"] == 47.9737
    assert response.json()["data"][0]["longitude"] == 8.5205


def test_dwd_stations_geo():

    response = client.get(
        "/restapi/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "coordinates": "45.54,10.10",
            "rank": 5,
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == "03730"
    assert response.json()["data"][0]["name"] == "Oberstdorf"
    assert response.json()["data"][0]["latitude"] == 47.3984
    assert response.json()["data"][0]["longitude"] == 10.2759


def test_dwd_stations_sql():

    response = client.get(
        "/restapi/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "sql": "SELECT * FROM data WHERE lower(name) LIKE lower('%dresden%');",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == "01048"
    assert response.json()["data"][0]["name"] == "Dresden-Klotzsche"


def test_dwd_values_success(dicts_are_same):

    response = client.get(
        "/restapi/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "01359",
            "parameter": "kl",
            "resolution": "daily",
            "period": "historical",
            "date": "1982-01-01",
        },
    )
    assert response.status_code == 200
    assert dicts_are_same(
        response.json()["data"][0],
        {
            "station_id": "01359",
            "dataset": "climate_summary",
            "parameter": "wind_gust_max",
            "date": "1982-01-01T00:00:00+00:00",
            "value": 4.2,
            "quality": 10.0,
        },
    )


def test_dwd_values_no_station():

    response = client.get(
        "/restapi/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
        },
    )

    assert response.status_code == 200
    assert (
        "'Give one of the parameters: all (boolean), station (string), "
        "name (string), coordinates (float,float) and rank (integer), "
        "coordinates (float,float) and distance (float), "
        "bbox (left float, bottom float, right float, top float)'" in response.text
    )


def test_dwd_values_no_parameter():

    response = client.get(
        "/restapi/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "01048,4411",
            "resolution": "daily",
            "period": "recent",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Query arguments 'parameter', 'resolution' and 'date' are required"}


def test_dwd_values_no_resolution():

    response = client.get(
        "/restapi/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "stations_result": "01048,4411",
            "parameter": "kl",
            "period": "recent",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Query arguments 'parameter', 'resolution' and 'date' are required"}


@pytest.mark.remote
@pytest.mark.sql
def test_dwd_values_sql_tabular(dicts_are_same):

    response = client.get(
        "/restapi/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "01048,4411",
            "parameter": "kl",
            "resolution": "daily",
            "period": "historical",
            "date": "2020/2021",
            "sql-values": "SELECT * FROM data WHERE temperature_air_max_200 < 2.0",
            "tidy": False,
            "si-units": False,
        },
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert len(data) >= 8
    assert dicts_are_same(
        data[0],
        {
            "cloud_cover_total": 6.9,
            "dataset": "climate_summary",
            "date": "2020-01-25T00:00:00+00:00",
            "humidity": 88.88,
            "precipitation_form": 0.0,
            "precipitation_height": 0.0,
            "pressure_air_site": 993.88,
            "pressure_vapor": 4.6,
            "qn_3": 10.0,
            "qn_4": 3,
            "snow_depth": 0,
            "station_id": "01048",
            "sunshine_duration": 0.0,
            "temperature_air_max_200": -0.6,
            "temperature_air_mean_200": -2.2,
            "temperature_air_min_005": -6.6,
            "temperature_air_min_200": -4.6,
            "wind_gust_max": 4.6,
            "wind_speed": 1.9,
        },
    )


@pytest.mark.remote
@pytest.mark.sql
def test_dwd_values_sql_tidy(dicts_are_same):

    response = client.get(
        "/restapi/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "01048,4411",
            "parameter": "kl",
            "resolution": "daily",
            "date": "2019-12-01/2019-12-31",
            "sql-values": "SELECT * FROM data " "WHERE parameter='temperature_air_max_200' AND value < 1.5",
            "si-units": False,
        },
    )
    assert response.status_code == 200
    assert dicts_are_same(
        response.json()["data"][0],
        {
            "station_id": "01048",
            "dataset": "climate_summary",
            "parameter": "temperature_air_max_200",
            "date": "2019-12-28T00:00:00+00:00",
            "value": 1.3,
            "quality": 3.0,
        },
    )


@pytest.mark.remote
def test_api_values_missing_null():
    response = client.get(
        "/restapi/values",
        params={
            "provider": "dwd",
            "network": "mosmix",
            "station": "F660",
            "parameter": "ttt",
            "resolution": "small",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["quality"] is None


@pytest.mark.remote
def test_api_stations_missing_null():
    response = client.get(
        "/restapi/stations",
        params={
            "provider": "dwd",
            "network": "mosmix",
            "parameter": "ttt",
            "resolution": "small",
            "all": True,
        },
    )
    assert response.status_code == 200

    first = response.json()["data"][0]

    assert first["icao_id"] is None
    assert first["from_date"] is None
    assert first["to_date"] is None
    assert first["state"] is None
