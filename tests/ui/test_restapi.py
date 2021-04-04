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


def test_dwd_stations_basic():

    response = client.get(
        "/api/dwd/observation/stations",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == "00011"
    assert response.json()["data"][0]["name"] == "Donaueschingen (Landeplatz)"
    assert response.json()["data"][0]["latitude"] == 47.9737
    assert response.json()["data"][0]["longitude"] == 8.5205


def test_dwd_stations_geo():

    response = client.get(
        "/api/dwd/observation/stations",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "latitude": 45.54,
            "longitude": 10.10,
            "number_nearby": 5,
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == "03730"
    assert response.json()["data"][0]["station_name"] == "Oberstdorf"
    assert response.json()["data"][0]["latitude"] == 47.3984
    assert response.json()["data"][0]["longitude"] == 10.2759


def test_dwd_stations_sql():

    response = client.get(
        "/api/dwd/observation/stations",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "sql": "SELECT * FROM data WHERE lower(name) " "LIKE lower('%dresden%');",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == "01048"
    assert response.json()["data"][0]["name"] == "Dresden-Klotzsche"


def test_dwd_readings_success(dicts_are_same):

    response = client.get(
        "/api/dwd/observation/values",
        params={
            "stations": "01359",
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
            "date": "1982-01-01T00:00:00.000Z",
            "value": 4.2,
            "quality": 10,
        },
    )


def test_dwd_readings_no_station():

    response = client.get(
        "/api/dwd/observation/values",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Query argument 'stations' is required"}


def test_dwd_readings_no_parameter():

    response = client.get(
        "/api/dwd/observation/values",
        params={
            "stations": "01048,4411",
            "resolution": "daily",
            "period": "recent",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Query arguments 'parameter', 'resolution' and 'period' are required"
    }


def test_dwd_readings_no_resolution():

    response = client.get(
        "/api/dwd/observation/values",
        params={
            "stations": "01048,4411",
            "parameter": "kl",
            "period": "recent",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Query arguments 'parameter', 'resolution' and 'period' are required"
    }


def test_dwd_readings_no_period():

    response = client.get(
        "/api/dwd/observation/values",
        params={
            "stations": "01048,4411",
            "parameter": "kl",
            "resolution": "daily",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Query arguments 'parameter', 'resolution' and 'period' are required"
    }


@pytest.mark.sql
def test_dwd_values_sql_tabular(dicts_are_same):

    response = client.get(
        "/api/dwd/observation/values",
        params={
            "stations": "01048,4411",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "date": "2019/2022",
            "sql": "SELECT * FROM data WHERE temperature_air_max_200 < 2.0",
            "tidy": False,
        },
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert len(data) >= 49
    assert dicts_are_same(
        data[0],
        {
            "station_id": "01048",
            "date": "2019-12-28T00:00:00.000Z",
            "qn_3": 10.0,
            "qn_4": 3,
            "cloud_cover_total": 7.4,
            "humidity": 82.54,
            "precipitation_form": 7,
            "precipitation_height": 0.4,
            "pressure_air": 1011.49,
            "pressure_vapor": 5.2,
            "snow_depth": 0,
            "sunshine_duration": 0.0,
            "temperature_air_200": 0.4,
            "temperature_air_max_200": 1.3,
            "temperature_air_min_005": -1.0,
            "temperature_air_min_200": -0.7,
            "wind_gust_max": 7.7,
            "wind_speed": 3.1,
        },
    )


@pytest.mark.sql
@pytest.mark.xfail(
    reason="The data types of the `value` column in tidy data "
    "frames is currently not homogenous",
    strict=True,
)
def test_dwd_values_sql_tidy(dicts_are_same):

    response = client.get(
        "/api/dwd/observation/values",
        params={
            "stations": "01048,4411",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "date": "2019/2022",
            "sql": "SELECT * FROM data "
            "WHERE parameter='temperature_air_max_200' AND value < 1.5",
        },
    )
    assert response.status_code == 200
    assert dicts_are_same(
        response.json()["data"][0],
        {
            "station_id": "01048",
            "dataset": "climate_summary",
            "parameter": "temperature_air_max_200",
            "date": "2019-12-28T00:00:00.000Z",
            "value": 1.3,
            "quality": 3,
        },
    )
