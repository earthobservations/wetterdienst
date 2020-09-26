import pytest

from wetterdienst.service import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "Wetterdienst - Open weather data for humans" in response.text


def test_robots():
    response = client.get("/robots.txt")
    assert response.status_code == 200


def test_dwd_stations():

    response = client.get(
        "/api/dwd/stations",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == 1
    assert response.json()["data"][0]["station_name"] == "Aach"


def test_dwd_stations_sql():

    response = client.get(
        "/api/dwd/stations",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "sql": "SELECT * FROM data WHERE lower(station_name) "
            "LIKE lower('%dresden%');",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == 1047
    assert response.json()["data"][0]["station_name"] == "Dresden (Mitte)"


def test_dwd_readings_success(dicts_are_same):

    response = client.get(
        "/api/dwd/readings",
        params={
            "station": "1048,4411",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "date": "2020-08-01",
        },
    )

    assert response.status_code == 200
    assert dicts_are_same(
        response.json()["data"][0],
        {
            "station_id": 1048,
            "parameter": "climate_summary",
            "element": "wind_gust_max",
            "date": "2020-08-01T00:00:00.000Z",
            "value": 11.5,
            "quality": 1,
        },
    )


def test_dwd_readings_no_station():

    response = client.get(
        "/api/dwd/readings",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Query argument 'station' is required"}


def test_dwd_readings_no_parameter():

    response = client.get(
        "/api/dwd/readings",
        params={
            "station": "1048,4411",
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
        "/api/dwd/readings",
        params={
            "station": "1048,4411",
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
        "/api/dwd/readings",
        params={
            "station": "1048,4411",
            "parameter": "kl",
            "resolution": "daily",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Query arguments 'parameter', 'resolution' and 'period' are required"
    }


@pytest.mark.xfail
@pytest.mark.sql
def test_dwd_readings_sql(dicts_are_same):

    response = client.get(
        "/api/dwd/readings",
        params={
            "station": "1048,4411",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "sql": "SELECT * FROM data "
            "WHERE element='temperature_air_max_200' AND value < 1.5",
        },
    )

    assert response.status_code == 200
    assert dicts_are_same(
        response.json()["data"][0],
        {
            "station_id": 1048,
            "parameter": "climate_summary",
            "element": "temperature_air_max_200",
            "date": "2019-12-28T00:00:00.000Z",
            "value": 1.3,
            "quality": None,
        },
    )
