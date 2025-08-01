# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the REST API."""

import json

import pytest
from dirty_equals import IsNumber, IsStr
from starlette.testclient import TestClient

from wetterdienst.ui.restapi import REQUEST_EXAMPLES


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    return TestClient(app)


def test_index(client: TestClient) -> None:
    """Test index."""
    response = client.get("/")
    assert response.status_code == 200
    assert "wetterdienst - open weather data for humans" in response.text


@pytest.mark.parametrize("url", REQUEST_EXAMPLES.values())
def test_index_examples(client: TestClient, url: str) -> None:
    """Test index examples."""
    response = client.get(url)
    assert response.status_code == 200


def test_robots(client: TestClient) -> None:
    """Test robots.txt."""
    response = client.get("/robots.txt")
    assert response.status_code == 200


def test_health(client: TestClient) -> None:
    """Test health."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}


@pytest.mark.remote
def test_coverage(client: TestClient) -> None:
    """Test coverage."""
    response = client.get(
        "/api/coverage",
    )
    assert response.status_code == 200
    data = response.json()
    assert data.keys() == {
        "dwd",
        "ea",
        "eaufrance",
        "eccc",
        "geosphere",
        "imgw",
        "noaa",
        "nws",
        "wsv",
    }
    networks = data["dwd"]
    assert networks == ["observation", "mosmix", "dmo", "road", "radar"]


@pytest.mark.remote
def test_coverage_dwd_observation(client: TestClient) -> None:
    """Test DWD observation."""
    response = client.get(
        "/api/coverage",
        params={
            "provider": "dwd",
            "network": "observation",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "1_minute" in data
    assert "precipitation" in data["1_minute"]
    assert len(data["1_minute"]["precipitation"]) > 0
    parameters = [item["name"] for item in data["1_minute"]["precipitation"]]
    assert parameters == [
        "precipitation_height",
        "precipitation_height_droplet",
        "precipitation_height_rocker",
        "precipitation_index",
    ]


@pytest.mark.remote
def test_coverage_dwd_observation_resolution_1_minute(client: TestClient) -> None:
    """Test resolution 1 minute."""
    response = client.get(
        "/api/coverage",
        params={
            "provider": "dwd",
            "network": "observation",
            "resolutions": "1_minute",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data.keys() == {"1_minute"}


@pytest.mark.remote
def test_coverage_dwd_observation_dataset_climate_summary(client: TestClient) -> None:
    """Test dataset climate_summary."""
    response = client.get(
        "/api/coverage",
        params={
            "provider": "dwd",
            "network": "observation",
            "datasets": "climate_summary",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data.keys() == {"daily", "monthly", "annual"}
    assert data["daily"].keys() == {"climate_summary"}
    assert data["monthly"].keys() == {"climate_summary"}
    assert data["annual"].keys() == {"climate_summary"}


@pytest.mark.remote
def test_coverage_wrong_only_provider_given(client: TestClient) -> None:
    """Test wrong request."""
    response = client.get(
        "/api/coverage",
        params={
            "provider": "dwd",
        },
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Either both or none of 'provider' and 'network' must be given. If none are given, all providers and "
        "networks are returned.",
    }


def test_stations_no_provider(client: TestClient) -> None:
    """Test no provider given."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "abc",
            "network": "abc",
            "parameters": "daily/kl",
            "periods": "recent",
            "all": "true",
        },
    )
    assert response.status_code == 404
    assert (
        "No API available for provider abc and network abc. "
        "Use /api/coverage to discover available providers and networks." in response.text
    )


def test_stations_no_network(client: TestClient) -> None:
    """Test no network given."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "abc",
            "parameters": "daily/kl",
            "periods": "recent",
            "all": "true",
        },
    )
    assert response.status_code == 404
    assert (
        "No API available for provider dwd and network abc. "
        "Use /api/coverage to discover available providers and networks."
    ) in response.text


def test_stations_wrong_format(client: TestClient) -> None:
    """Test wrong format."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "periods": "recent",
            "all": "true",
            "format": "abc",
        },
    )
    assert response.status_code == 422
    assert (
        response.json()["detail"][0]["msg"]
        == "Input should be 'json', 'geojson', 'csv', 'html', 'png', 'jpg', 'webp', 'svg' or 'pdf'"
    )


@pytest.mark.remote
def test_stations_dwd_basic(client: TestClient) -> None:
    """Test basic request."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "periods": "recent",
            "all": "true",
        },
    )
    assert response.status_code == 200
    item = response.json()["stations"][0]
    assert item == {
        "resolution": "daily",
        "dataset": "climate_summary",
        "station_id": "00011",
        "start_date": "1980-09-01T00:00:00+00:00",
        "end_date": IsStr,
        "latitude": 47.9736,
        "longitude": 8.5205,
        "height": 680.0,
        "name": "Donaueschingen (Landeplatz)",
        "state": "Baden-Württemberg",
    }


@pytest.mark.remote
def test_stations_dwd_geo(client: TestClient) -> None:
    """Test geojson format."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "periods": "recent",
            "latitude": "45.54",
            "longitude": "10.10",
            "rank": 5,
        },
    )
    assert response.status_code == 200
    item = response.json()["stations"][0]
    assert item == {
        "resolution": "daily",
        "dataset": "climate_summary",
        "station_id": "03730",
        "start_date": "1910-01-01T00:00:00+00:00",
        "end_date": IsStr,
        "latitude": 47.3984,
        "longitude": 10.2759,
        "height": 806.0,
        "name": "Oberstdorf",
        "state": "Bayern",
        "distance": 207.0831,
    }


@pytest.mark.remote
def test_stations_dwd_sql(client: TestClient) -> None:
    """Test SQL query."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "periods": "recent",
            "sql": "lower(name) LIKE '%dresden%';",
        },
    )
    assert response.status_code == 200
    item = response.json()["stations"][0]
    assert item == {
        "resolution": "daily",
        "dataset": "climate_summary",
        "station_id": "01048",
        "start_date": "1934-01-01T00:00:00+00:00",
        "end_date": IsStr,
        "latitude": 51.1278,
        "longitude": 13.7543,
        "height": 228.0,
        "name": "Dresden-Klotzsche",
        "state": "Sachsen",
    }


@pytest.mark.xfail
@pytest.mark.remote
@pytest.mark.parametrize(
    "fmt",
    [
        "png",
        "jpg",
        "webp",
        "svg",
    ],
)
def test_stations_dwd_obs_image(client: TestClient, fmt: str) -> None:
    """Test image formats."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "all": "true",
            "format": fmt,
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == f"image/{fmt}"


@pytest.mark.remote
def test_stations_dwd_obs_image_html(client: TestClient) -> None:
    """Test HTML format."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "all": "true",
            "format": "html",
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"


@pytest.mark.remote
def test_stations_dwd_obs_image_pdf(client: TestClient) -> None:
    """Test PDF format."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "all": "true",
            "format": "pdf",
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "application/pdf"


@pytest.mark.xfail
@pytest.mark.remote
def test_stations_dwd_obs_image_png_custom_settings(client: TestClient) -> None:
    """Test custom settings."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "all": "true",
            "format": "png",
            "width": 1000,
            "height": 1000,
            "scale": 2,
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "image/png"


@pytest.mark.remote
def test_stations_dwd_obs_image_png_wrong_settings(client: TestClient) -> None:
    """Test wrong settings."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "all": "true",
            "format": "png",
            "width": 0,
            "height": 0,
            "scale": 0,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Input should be greater than 0"


@pytest.mark.remote
def test_values_dwd_success(client: TestClient) -> None:
    """Test values."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "01359",
            "parameters": "daily/kl/wind_gust_max",
            "periods": "historical",
            "date": "1982-01-01",
        },
    )
    assert response.status_code == 200
    item = response.json()["values"][0]
    assert item == {
        "station_id": "01359",
        "resolution": "daily",
        "dataset": "climate_summary",
        "parameter": "wind_gust_max",
        "date": "1982-01-01T00:00:00+00:00",
        "value": 4.2,
        "quality": 10.0,
    }


def test_values_dwd_no_station(client: TestClient) -> None:
    """Test no station given."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "periods": "recent",
        },
    )
    assert response.status_code == 400
    assert (
        "'Give one of the parameters: all (boolean), station (string), "
        "name (string), latitude (float), longitude (float) and rank (integer), "
        "latitude (float), longitude (float) and distance (float), "
        "left (float), bottom (float), right (float), top (float)'" in response.text
    )


@pytest.mark.remote
@pytest.mark.sql
def test_values_dwd_sql_tabular(client: TestClient) -> None:
    """Test tabular format."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "01048,4411",
            "parameters": "daily/kl",
            "periods": "historical",
            "date": "2020/2021",
            "sql_values": "temperature_air_max_2m < 2.0",
            "shape": "wide",
        },
    )
    assert response.status_code == 200
    data = response.json()["values"]
    assert len(data) >= 8
    item = data[0]
    assert item == {
        "station_id": "01048",
        "date": "2020-01-25T00:00:00+00:00",
        "resolution": "daily",
        "dataset": "climate_summary",
        "cloud_cover_total": 0.8625,
        "qn_cloud_cover_total": 10.0,
        "humidity": 0.89,
        "qn_humidity": 10.0,
        "precipitation_form": 0.0,
        "qn_precipitation_form": 10.0,
        "precipitation_height": 0.0,
        "qn_precipitation_height": 10.0,
        "pressure_air_site": 993.9,
        "qn_pressure_air_site": 10.0,
        "pressure_vapor": 4.6,
        "qn_pressure_vapor": 10.0,
        "snow_depth": 0,
        "qn_snow_depth": 10.0,
        "sunshine_duration": 0.0,
        "qn_sunshine_duration": 10.0,
        "temperature_air_max_2m": -0.6,
        "qn_temperature_air_max_2m": 10.0,
        "temperature_air_mean_2m": -2.2,
        "qn_temperature_air_mean_2m": 10.0,
        "temperature_air_min_0_05m": -6.6,
        "qn_temperature_air_min_0_05m": 10.0,
        "temperature_air_min_2m": -4.6,
        "qn_temperature_air_min_2m": 10.0,
        "wind_gust_max": 4.6,
        "qn_wind_gust_max": 10.0,
        "wind_speed": 1.9,
        "qn_wind_speed": 10.0,
    }


@pytest.mark.remote
@pytest.mark.sql
def test_values_dwd_sql_long(client: TestClient) -> None:
    """Test long format."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "01048,4411",
            "parameters": "daily/kl",
            "date": "2019-12-01/2019-12-31",
            "sql_values": "parameter='temperature_air_max_2m' AND value < 1.5",
        },
    )
    assert response.status_code == 200
    item = response.json()["values"][0]
    assert item == {
        "station_id": "01048",
        "resolution": "daily",
        "dataset": "climate_summary",
        "parameter": "temperature_air_max_2m",
        "date": "2019-12-28T00:00:00+00:00",
        "value": 1.3,
        "quality": 10.0,
    }


@pytest.mark.remote
def test_interpolate_dwd(client: TestClient) -> None:
    """Test interpolation."""
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
        },
    )
    assert response.status_code == 200
    assert response.json()["values"] == [
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 6.37,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 8.7,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
def test_interpolate_dwd_lower_interpolation_distance(client: TestClient) -> None:
    """Test interpolation with lower distance."""
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "interpolation_station_distance": '{"temperature_air_mean_2m": 10.0}',
        },
    )
    assert response.status_code == 200
    assert response.json()["values"] == [
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": None,
            "distance_mean": None,
            "taken_station_ids": [],
        },
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 8.7,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
def test_interpolate_dwd_dont_use_nearby_station(client: TestClient) -> None:
    """Test not using nearby stations."""
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "use_nearby_station_distance": 0,
        },
    )
    assert response.status_code == 200
    assert response.json()["values"] == [
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 6.37,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 8.7,
            "distance_mean": 11.33,
            "taken_station_ids": ["00071", "00072", "02074", "02638"],
        },
    ]


@pytest.mark.remote
def test_interpolate_dwd_custom_unit(client: TestClient) -> None:
    """Test custom unit targets."""
    unit_targets = {
        "temperature": "degree_fahrenheit",
    }
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "unit_targets": json.dumps(unit_targets),
        },
    )
    assert response.status_code == 200
    assert response.json()["values"] == [
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 43.47,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 47.66,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
@pytest.mark.parametrize(
    "fmt",
    [
        "png",
        "jpg",
        "webp",
        "svg",
    ],
)
def test_interpolate_dwd_image(client: TestClient, fmt: str) -> None:
    """Test image formats."""
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "format": fmt,
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == f"image/{fmt}"


@pytest.mark.remote
def test_interpolate_dwd_image_html(client: TestClient) -> None:
    """Test HTML format."""
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "format": "html",
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"


@pytest.mark.remote
def test_interpolate_dwd_image_pdf(client: TestClient) -> None:
    """Test PDF format."""
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "format": "pdf",
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "application/pdf"


@pytest.mark.remote
def test_summarize_dwd(client: TestClient) -> None:
    """Test summarize."""
    response = client.get(
        "/api/summarize",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/climate_summary/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
        },
    )
    assert response.status_code == 200
    assert response.json()["values"] == [
        {
            "station_id": "a87291a8",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 6.6,
            "distance": 6.97,
            "taken_station_id": "00072",
        },
        {
            "station_id": "a87291a8",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 8.7,
            "distance": 0.0,
            "taken_station_id": "00071",
        },
    ]


@pytest.mark.remote
def test_summarize_dwd_custom_unit(client: TestClient) -> None:
    """Test custom unit."""
    unit_targets = {
        "temperature": "degree_fahrenheit",
    }
    response = client.get(
        "/api/summarize",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/climate_summary/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "unit_targets": json.dumps(unit_targets),
        },
    )
    assert response.status_code == 200
    assert response.json()["values"] == [
        {
            "station_id": "a87291a8",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 43.88,
            "distance": 6.97,
            "taken_station_id": "00072",
        },
        {
            "station_id": "a87291a8",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 47.66,
            "distance": 0.0,
            "taken_station_id": "00071",
        },
    ]


@pytest.mark.remote
@pytest.mark.parametrize(
    "fmt",
    [
        "png",
        "jpg",
        "webp",
        "svg",
    ],
)
def test_summarize_dwd_image(client: TestClient, fmt: str) -> None:
    """Test image formats."""
    response = client.get(
        "/api/summarize",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/climate_summary/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "format": fmt,
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == f"image/{fmt}"


@pytest.mark.remote
def test_summarize_dwd_image_html(client: TestClient) -> None:
    """Test HTML format."""
    response = client.get(
        "/api/summarize",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/climate_summary/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "format": "html",
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"


@pytest.mark.remote
def test_summarize_dwd_image_pdf(client: TestClient) -> None:
    """Test PDF format."""
    response = client.get(
        "/api/summarize",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/climate_summary/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31/1986-11-01",
            "format": "pdf",
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "application/pdf"


@pytest.mark.remote
def test_values_missing_null(client: TestClient) -> None:
    """Test missing values."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "mosmix",
            "station": "F660",
            "parameters": "hourly/small/ttt",
        },
    )
    assert response.status_code == 200
    assert response.json()["values"][0]["quality"] is None


@pytest.mark.remote
def test_values_missing_empty(client: TestClient) -> None:
    """Test missing values."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "00011",
            "parameters": "1_minute/precipitation/precipitation_height",
            "periods": "recent",
        },
    )
    assert response.status_code == 200
    assert not response.json()["values"]


@pytest.mark.remote
def test_stations_missing_null(client: TestClient) -> None:
    """Test missing values."""
    response = client.get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "mosmix",
            "parameters": "hourly/small/ttt",
            "all": True,
        },
    )
    assert response.status_code == 200
    item = response.json()["stations"][2]
    assert item == {
        "resolution": "hourly",
        "dataset": "small",
        "station_id": "01025",
        "icao_id": None,
        "start_date": None,
        "end_date": None,
        "latitude": 69.68,
        "longitude": 18.92,
        "height": 10.0,
        "name": "TROMSOE",
        "state": None,
    }


@pytest.mark.remote
def test_values_dwd_mosmix(client: TestClient) -> None:
    """Test MOSMIX."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "mosmix",
            "parameters": "hourly/small/ttt",
            "station": "01025",
        },
    )
    assert response.status_code == 200
    first = response.json()["values"][0]
    assert first == {
        "station_id": "01025",
        "resolution": "hourly",
        "dataset": "small",
        "parameter": "temperature_air_mean_2m",
        "date": IsStr,
        "value": IsNumber,
        "quality": None,
    }


@pytest.mark.remote
def test_values_dwd_dmo_lead_time_long(client: TestClient) -> None:
    """Test lead time long."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "dmo",
            "parameters": "hourly/icon/ttt",
            "station": "01025",
            "lead_time": "long",
        },
    )
    assert response.status_code == 200
    first = response.json()["values"][0]
    assert first == {
        "station_id": "01025",
        "resolution": "hourly",
        "dataset": "icon",
        "parameter": "temperature_air_mean_2m",
        "date": IsStr,
        "value": IsNumber,
        "quality": None,
    }


@pytest.mark.remote
def test_values_dwd_observation_climate_summary_custom_units(client: TestClient) -> None:
    """Test custom units."""
    unit_targets = {
        "temperature": "degree_fahrenheit",
    }
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "1048",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "date": "2022-01-01",
            "unit_targets": json.dumps(unit_targets),
        },
    )
    assert response.status_code == 200
    first = response.json()["values"][0]
    assert first == {
        "station_id": "01048",
        "resolution": "daily",
        "dataset": "climate_summary",
        "parameter": "temperature_air_mean_2m",
        "date": "2022-01-01T00:00:00+00:00",
        "value": 52.52,
        "quality": 10.0,
    }


@pytest.mark.remote
@pytest.mark.parametrize(
    "fmt",
    [
        "png",
        "jpg",
        "webp",
        "svg",
    ],
)
def test_values_dwd_observation_climate_summary_image(client: TestClient, fmt: str) -> None:
    """Test image format."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "1048",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "date": "2022-01-01",
            "format": fmt,
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == f"image/{fmt}"


@pytest.mark.remote
def test_values_dwd_observation_climate_summary_image_html(client: TestClient) -> None:
    """Test HTML format."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "1048",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "date": "2022-01-01",
            "format": "html",
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"


@pytest.mark.remote
def test_values_dwd_observation_climate_summary_image_pdf(client: TestClient) -> None:
    """Test PDF format."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "1048",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "date": "2022-01-01",
            "format": "pdf",
        },
    )
    assert response.status_code == 200
    assert response.content
    assert response.headers["Content-Type"] == "application/pdf"


@pytest.mark.remote
def test_stripes_stations_default(client: TestClient) -> None:
    """Test default parameters."""
    response = client.get(
        "/api/stripes/stations",
        params={
            "kind": "temperature",
        },
    )
    assert response.status_code == 200
    assert response.content
    data = response.json()
    assert len(data["stations"]) >= 500


@pytest.mark.remote
def test_stripes_stations_active_false(client: TestClient) -> None:
    """Test active=False parameter."""
    response = client.get(
        "/api/stripes/stations",
        params={
            "kind": "temperature",
            "active": False,
        },
    )
    assert response.status_code == 200
    assert response.content
    data = response.json()
    assert len(data["stations"]) >= 1100


@pytest.mark.remote
def test_stripes_values_default(client: TestClient) -> None:
    """Test default parameters."""
    response = client.get(
        "/api/stripes/values",
        params={
            "kind": "temperature",
            "station": "01048",
        },
    )
    assert response.status_code == 200
    assert response.content


@pytest.mark.remote
def test_stripes_values_name(client: TestClient) -> None:
    """Test name parameter."""
    response = client.get(
        "/api/stripes/values",
        params={
            "kind": "temperature",
            "name": "Dresden-Klotzsche",
        },
    )
    assert response.status_code == 200
    assert response.content


@pytest.mark.remote
@pytest.mark.parametrize(
    "params",
    [
        {"show_title": "true"},
        {"show_years": "true"},
        {"show_data_availability": "true"},
        {"show_title": "false"},
        {"show_years": "false"},
        {"show_data_availability": "false"},
    ],
)
def test_stripes_values_non_defaults(client: TestClient, params: dict) -> None:
    """Test non-default parameters."""
    response = client.get(
        "/api/stripes/values",
        params=params
        | {
            "kind": "temperature",
            "station": "01048",
            "show_title": "true",
            "show_years": "true",
            "show_data_availability": "true",
        },
    )
    assert response.status_code == 200
    assert response.content


@pytest.mark.remote
def test_stripes_values_start_year_ge_end_year(client: TestClient) -> None:
    """Test start_year greater or equal to end_year."""
    response = client.get(
        "/api/stripes/values",
        params={
            "kind": "temperature",
            "station": "01048",
            "start_year": "2021",
            "end_year": "2020",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Query argument 'start_year' must be less than 'end_year'"}


@pytest.mark.remote
def test_stripes_values_wrong_name_threshold(client: TestClient) -> None:
    """Test wrong name_threshold value."""
    response = client.get(
        "/api/stripes/values",
        params={
            "kind": "temperature",
            "name": "Dresden-Klotzsche",
            "name_threshold": 1.01,
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Query argument 'name_threshold' must be between 0.0 and 1.0"}


@pytest.mark.remote
def test_stripes_values_unknown_name(client: TestClient) -> None:
    """Test unknown name value."""
    response = client.get(
        "/api/stripes/values",
        params={
            "kind": "temperature",
            "name": "foobar",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "No station with a name similar to 'foobar' found"}


@pytest.mark.remote
def test_stripes_values_unknown_format(client: TestClient) -> None:
    """Test wrong format value."""
    response = client.get(
        "/api/stripes/values",
        params={
            "kind": "temperature",
            "station": "01048",
            "format": "foobar",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Input should be 'png', 'jpg', 'svg' or 'pdf'"


@pytest.mark.remote
def test_stripes_values_wrong_dpi(client: TestClient) -> None:
    """Test wrong dpi value."""
    response = client.get(
        "/api/stripes/values",
        params={
            "kind": "temperature",
            "station": "01048",
            "dpi": 0,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Input should be greater than 0"
