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
        "/api/dwd/observations/sites",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == "00011"
    assert response.json()["data"][0]["station_name"] == "Donaueschingen (Landeplatz)"


def test_dwd_stations_sql():

    response = client.get(
        "/api/dwd/observations/sites",
        params={
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "sql": "SELECT * FROM data WHERE lower(station_name) "
            "LIKE lower('%dresden%');",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["station_id"] == "01048"
    assert response.json()["data"][0]["station_name"] == "Dresden-Klotzsche"


def test_dwd_readings_success(dicts_are_same):

    response = client.get(
        "/api/dwd/observations/readings",
        params={
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
            "parameter_set": "climate_summary",
            "parameter": "wind_speed",
            "date": "1982-01-01T00:00:00.000Z",
            "value": 0.9,
            "quality": 10,
        },
    )


def test_dwd_readings_no_station():

    response = client.get(
        "/api/dwd/observations/readings",
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
        "/api/dwd/observations/readings",
        params={
            "station": "01048,4411",
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
        "/api/dwd/observations/readings",
        params={
            "station": "01048,4411",
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
        "/api/dwd/observations/readings",
        params={
            "station": "01048,4411",
            "parameter": "kl",
            "resolution": "daily",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Query arguments 'parameter', 'resolution' and 'period' are required"
    }


@pytest.mark.sql
def test_dwd_readings_sql(dicts_are_same):

    response = client.get(
        "/api/dwd/observations/readings",
        params={
            "station": "01048,4411",
            "parameter": "kl",
            "resolution": "daily",
            "period": "recent",
            "sql": "SELECT * FROM data "
            "WHERE parameter='temperature_air_max_200' AND value < 1.5",
        },
    )

    assert response.status_code == 200
    assert dicts_are_same(
        response.json()["data"][0],
        {
            "station_id": "01048",
            "parameter_set": "climate_summary",
            "parameter": "temperature_air_max_200",
            "date": "2019-12-28T00:00:00.000Z",
            "value": 1.3,
            "quality": 3,
        },
    )
