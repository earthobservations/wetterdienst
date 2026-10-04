# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the REST API."""

import io
import json
import logging
import os
import pathlib
import zipfile
from collections.abc import Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, get_args

import pytest
from dirty_equals import IsApprox, IsNumber, IsStr
from starlette.testclient import TestClient

from wetterdienst import Settings, __version__
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE
from wetterdienst.ui import restapi
from wetterdienst.ui.core import StripesImageRequest, _FormatField, get_glossary
from wetterdienst.ui.restapi import REQUEST_EXAMPLES

if TYPE_CHECKING:
    from wetterdienst.model.result import ValuesResult

# the media type each image format is registered as, spelled out rather than read from the REST API's
# own table, which the tests would then only repeat (GH-2063)
_IMAGE_MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
}


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


@pytest.mark.remote
@pytest.mark.parametrize("url", REQUEST_EXAMPLES.values())
def test_index_examples(client: TestClient, url: str) -> None:
    """Test index examples.

    Every example URL fetches live provider data, so this is marked ``remote``.
    """
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


def test_version(client: TestClient) -> None:
    """Test that the version endpoint reports the version and whether MCP is served.

    `mcp_enabled` is what the app reads before offering an MCP client configuration: the endpoint
    is behind the optional `[mcp]` extra, so an instance without it must not be advertised as
    having one. The value tracks `_mount_mcp`, which is why this asserts agreement with the module
    flag rather than a fixed answer -- the test suite installs the extra, a bare install does not.
    """
    response = client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == __version__
    assert data["mcp_enabled"] is restapi.mcp_enabled


@pytest.mark.remote
def test_coverage(client: TestClient) -> None:
    """Test coverage."""
    response = client.get(
        "/api/coverage",
    )
    assert response.status_code == 200
    data = response.json()
    assert data.keys() == {
        "aemet",
        "chmi",
        "dmi",
        "dwd",
        "ea",
        "eaufrance",
        "eccc",
        "fmi",
        "geosphere",
        "imgw",
        "ipma",
        "knmi",
        "lhmt",
        "meteofrance",
        "meteoswiss",
        "metno",
        "metoffice",
        "noaa",
        "nws",
        "rmi",
        "smhi",
        "wsv",
    }
    dwd = data["dwd"]
    assert list(dwd.keys()) == [
        "observation",
        "mosmix",
        "dmo",
        "road",
        "swsmos",
        "poi",
        "phenology",
        "radar",
        "alerts",
        "derived",
    ]
    for network_info in dwd.values():
        assert network_info["auth"] is False
        assert network_info["configured"] is True
        assert network_info["valid"] is True
    # `road` requires a date range for value queries, other DWD networks don't
    assert dwd["observation"]["date_required"] is False
    assert dwd["road"]["date_required"] is True


def test_glossary(client: TestClient) -> None:
    """Test that the glossary reports what a parameter measures and its returned unit."""
    response = client.get("/api/glossary", params={"parameter": "radiation_global_intensity"})
    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "radiation_global_intensity",
            "unit_type": "power_per_area",
            "unit": "watt_per_square_meter",
            "unit_symbol": "W/m\u00b2",
            "description": "Global irradiance on a horizontal surface, reported as power rather than energy.",
        },
    ]


def test_glossary_all(client: TestClient) -> None:
    """Test that the unfiltered glossary covers the whole canonical vocabulary."""
    response = client.get("/api/glossary")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == len(PARAMETER_TABLE)
    # every entry says what it is and which unit it comes back in; that is the point of the endpoint
    assert all(entry["description"] for entry in entries)
    assert all(entry["unit"] for entry in entries)


def test_glossary_unit_type(client: TestClient) -> None:
    """Test that filtering by unit type returns only parameters of that quantity."""
    response = client.get("/api/glossary", params={"unit_type": "turbidity"})
    assert response.status_code == 200
    assert [entry["name"] for entry in response.json()] == ["turbidity"]


def test_glossary_unknown_unit_type(client: TestClient) -> None:
    """Test that an unknown unit type is rejected rather than answered with an empty list.

    `unit_type` is a closed vocabulary, so a typo is a caller error. Returning 200 and [] would be
    indistinguishable from a quantity that legitimately has no parameters, and the enum in the
    OpenAPI schema is also how an agent learns the valid values without downloading all 504 entries.
    """
    response = client.get("/api/glossary", params={"unit_type": "celsius"})
    assert response.status_code == 422


def test_glossary_limit(client: TestClient) -> None:
    """Test that limit bounds the response.

    The full vocabulary is a large payload for a tool-driving agent, and even a broad filter can be
    wide, so callers need a way to cap it explicitly. There is no default limit: silently truncating
    would be worse than a big answer.
    """
    response = client.get("/api/glossary", params={"limit": 3})
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_glossary_reports_unit_target_override() -> None:
    """Test that the reported unit follows ts_unit_targets rather than the built-in default.

    Reporting degree_celsius while a values request hands back Fahrenheit would make the glossary
    actively misleading, which is worse than it not existing.
    """
    entries = get_glossary(
        parameter="temperature_air_mean_2m",
        settings=Settings(ts_unit_targets={"temperature": "degree_fahrenheit"}),
    )
    assert entries
    assert {entry["unit"] for entry in entries if entry["unit_type"] == "temperature"} == {"degree_fahrenheit"}


def test_glossary_no_match(client: TestClient) -> None:
    """Test that a filter matching nothing is an empty list, not an error.

    The CLI exits 1 on the same query, following grep, but over HTTP a filter that matches nothing
    is a successful request with no results.
    """
    response = client.get("/api/glossary", params={"parameter": "not_a_parameter"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("network", ["alerts", "radar"])
def test_coverage_standalone_network_returns_404(client: TestClient, network: str) -> None:
    """Coverage for a metadata-less standalone network returns 404, not an uncaught 500."""
    response = client.get("/api/coverage", params={"provider": "dwd", "network": network})
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


def test_auth_no_auth_required(client: TestClient) -> None:
    """Providers without authentication always report configured=true and valid=true."""
    response = client.get("/api/auth", params={"provider": "dwd", "network": "observation"})
    assert response.status_code == 200
    data = response.json()
    assert data == {"provider": "dwd", "network": "observation", "auth": False, "configured": True, "valid": True}


def test_auth_unknown_provider(client: TestClient) -> None:
    """Unknown provider/network returns 404."""
    response = client.get("/api/auth", params={"provider": "nonexistent", "network": "fake"})
    assert response.status_code == 404


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
    assert "precipitation" in data["1_minute"]["datasets"]
    assert len(data["1_minute"]["datasets"]["precipitation"]["parameters"]) > 0
    parameters = [item["name"] for item in data["1_minute"]["datasets"]["precipitation"]["parameters"]]
    assert parameters == [
        "precipitation_amount",
        "precipitation_amount_droplet",
        "precipitation_amount_rocker",
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
    assert data["daily"]["datasets"].keys() == {"climate_summary"}
    assert data["monthly"]["datasets"].keys() == {"climate_summary"}
    assert data["annual"]["datasets"].keys() == {"climate_summary"}


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
        "start_date": "1980-09-01T00:00:00.000000+00:00",
        "end_date": IsStr,
        "latitude": 47.9736,
        "longitude": 8.5205,
        "elevation": 680.0,
        "name": "Donaueschingen (Landeplatz)",
        "region": "Baden-Württemberg",
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
        "start_date": "1910-01-01T00:00:00.000000+00:00",
        "end_date": IsStr,
        "latitude": 47.3984,
        "longitude": 10.2759,
        "elevation": 806.0,
        "name": "Oberstdorf",
        "region": "Bayern",
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
        "start_date": "1934-01-01T00:00:00.000000+00:00",
        "end_date": IsStr,
        "latitude": 51.1278,
        "longitude": 13.7543,
        "elevation": 228.0,
        "name": "Dresden-Klotzsche",
        "region": "Sachsen",
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
    assert response.headers["Content-Type"] == _IMAGE_MEDIA_TYPES[fmt]


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
        "timestamp": "1982-01-01T00:00:00.000000+00:00",
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
    assert response.status_code == 422
    assert response.json()["detail"] == [
        {
            "type": "missing_one_of",
            "loc": ["query"],
            "msg": (
                "Exactly one of all, station, name, (latitude and longitude), (left, bottom, right and top) or sql "
                "is required"
            ),
            "input": None,
            "ctx": {
                "one_of": [
                    ["all"],
                    ["station"],
                    ["name"],
                    ["latitude", "longitude"],
                    ["left", "bottom", "right", "top"],
                    ["sql"],
                ]
            },
        }
    ]


def test_history_no_station_selection(client: TestClient) -> None:
    """Test a history request with neither station nor all is refused by the model, as a 422."""
    response = client.get(
        "/api/history",
        params={"provider": "dwd", "network": "observation", "parameters": "daily/kl"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == [
        {
            "type": "missing_one_of",
            "loc": ["query"],
            "msg": "Exactly one of all or station is required",
            "input": None,
            "ctx": {"one_of": [["all"], ["station"]]},
        }
    ]


@pytest.mark.parametrize("endpoint", ["/api/stations", "/api/values"])
def test_two_station_selections_refused(client: TestClient, endpoint: str) -> None:
    """Test a request making two station selections is refused, not answered for the first.

    Given a station and a name, the REST API answered for the station and dropped the name without
    a word; only the CLI refused it, because only its option parser checked.
    """
    response = client.get(
        endpoint,
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "station": "01048",
            "name": "Hamburg-Fuhlsbüttel",
        },
    )
    assert response.status_code == 422
    # located at each query parameter involved, as FastAPI locates one parameter's error
    assert response.json()["detail"] == [
        {
            "type": "mutually_exclusive",
            "loc": ["query", "station"],
            "msg": "Cannot be combined with name",
            "input": ["01048"],
            "ctx": {"conflicts_with": ["name"]},
        },
        {
            "type": "mutually_exclusive",
            "loc": ["query", "name"],
            "msg": "Cannot be combined with station",
            "input": "Hamburg-Fuhlsbüttel",
            "ctx": {"conflicts_with": ["station"]},
        },
    ]


@pytest.mark.parametrize(
    ("endpoint", "lookup", "query"),
    [
        ("/api/stations", "get_stations", {"all": "true"}),
        ("/api/values", "get_values", {"station": "01048"}),
        ("/api/interpolate", "get_interpolate", {"station": "01048", "date": "2020-06-30"}),
        ("/api/summarize", "get_summarize", {"station": "01048", "date": "2020-06-30"}),
        ("/api/history", "get_stations", {"station": "01048"}),
    ],
)
def test_unreachable_selection_is_a_server_error(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    lookup: str,
    query: dict[str, str],
) -> None:
    """Test a lookup that finds no selection its model let through answers 500, not a caller's 4xx.

    get_stations, get_interpolate and get_summarize raise an AssertionError for it; each endpoint's
    catch-all answered it as a 400 or 404 that blamed the caller for our bug.
    """

    def unreachable(**_kwargs: object) -> None:
        msg = "StationsRequest selects no stations"
        raise AssertionError(msg)

    monkeypatch.setattr(restapi, lookup, unreachable)
    params = {"provider": "dwd", "network": "observation", "parameters": "daily/kl/temperature_air_mean_2m", **query}
    response = TestClient(restapi.app, raise_server_exceptions=False).get(endpoint, params=params)
    assert response.status_code == 500


def test_values_dwd_no_valid_parameters(client: TestClient) -> None:
    """Test that a parameter the provider does not have is answered with the request it was asked of."""
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/abc",
            "station": "00011",
        },
    )
    assert response.status_code == 400
    assert "No valid parameters could be parsed from" in response.text
    assert "DwdObservationRequest" in response.text


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
        "timestamp": "2020-01-25T00:00:00.000000+00:00",
        "resolution": "daily",
        "dataset": "climate_summary",
        "cloud_cover_total": 0.8625,
        "cloud_cover_total_quality": 10.0,
        "humidity_relative": 0.89,
        "humidity_relative_quality": 10.0,
        "precipitation_form": 0.0,
        "precipitation_form_quality": 10.0,
        "precipitation_amount": 0.0,
        "precipitation_amount_quality": 10.0,
        "pressure_air_site": 993.9,
        "pressure_air_site_quality": 10.0,
        "pressure_vapor": 4.6,
        "pressure_vapor_quality": 10.0,
        "snow_depth": 0,
        "snow_depth_quality": 10.0,
        "sunshine_duration": 0.0,
        "sunshine_duration_quality": 10.0,
        "temperature_air_max_2m": -0.6,
        "temperature_air_max_2m_quality": 10.0,
        "temperature_air_mean_2m": -2.2,
        "temperature_air_mean_2m_quality": 10.0,
        "temperature_air_min_0_05m": -6.6,
        "temperature_air_min_0_05m_quality": 10.0,
        "temperature_air_min_2m": -4.6,
        "temperature_air_min_2m_quality": 10.0,
        "wind_gust_max": 4.6,
        "wind_gust_max_quality": 10.0,
        "wind_speed": 1.9,
        "wind_speed_quality": 10.0,
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
        "timestamp": "2019-12-28T00:00:00.000000+00:00",
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
            "station_id": "4fde7164",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-10-31T00:00:00.000000+00:00",
            "value": 6.6422,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "4fde7164",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-11-01T00:00:00.000000+00:00",
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
            "station_id": "4fde7164",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-10-31T00:00:00.000000+00:00",
            "value": None,
            "distance_mean": None,
            "taken_station_ids": [],
        },
        {
            "station_id": "4fde7164",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-11-01T00:00:00.000000+00:00",
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
            "station_id": "4fde7164",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-10-31T00:00:00.000000+00:00",
            "value": 6.6422,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "4fde7164",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-11-01T00:00:00.000000+00:00",
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
            "station_id": "4fde7164",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-10-31T00:00:00.000000+00:00",
            "value": 43.9559,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "4fde7164",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-11-01T00:00:00.000000+00:00",
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
    assert response.headers["Content-Type"] == _IMAGE_MEDIA_TYPES[fmt]


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


def test_geo_settings_radii_reach_the_settings() -> None:
    """Test that the two radii given to an endpoint end up on the settings.

    The per-parameter dict is layered on top of them, so a request may widen a whole kind and still
    treat one parameter differently.
    """
    from wetterdienst.ui.core import InterpolationRequest  # noqa: PLC0415
    from wetterdienst.ui.restapi import _geo_settings  # noqa: PLC0415

    request = InterpolationRequest.model_validate(
        {
            "provider": "dwd",
            "network": "observation",
            "parameters": ["daily/kl/temperature_air_mean_2m"],
            "date": "1986-10-31",
            "station": "00071",
            "interpolation_station_distance_homogeneous": 60.0,
            "interpolation_station_distance": {"precipitation_amount": 25.0},
        },
    )
    settings = _geo_settings(request, request.model_fields_set, "interpolation")
    assert settings.ts_geo_station_distance["temperature_air_mean_2m"] == 60.0
    assert settings.ts_geo_station_distance["precipitation_amount"] == 25.0
    # the radius that was not given keeps its default rather than being reset
    assert settings.ts_geo_station_distance["snow_depth_new"] == 20.0


def test_interpolate_negative_radius_rejected(client: TestClient) -> None:
    """Test that a negative radius is rejected by the query parameter itself."""
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31",
            "interpolation_station_distance_homogeneous": -1,
        },
    )
    assert response.status_code == 422


def test_interpolate_unknown_station_distance_parameter(client: TestClient) -> None:
    """Test that a station distance for a name that is not a canonical parameter is a 400.

    It used to be accepted and never read, so the parameter the user meant kept its default radius.
    """
    response = client.get(
        "/api/interpolate",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31",
            "interpolation_station_distance": '{"temperature_air_mean": 10}',
        },
    )
    assert response.status_code == 400
    assert "not in the canonical parameters" in response.json()["detail"]


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
            "station_id": "96a83f47",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-10-31T00:00:00.000000+00:00",
            "value": 6.8275,
            "distance": 6.97,
            "taken_station_id": "00072",
        },
        {
            "station_id": "96a83f47",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-11-01T00:00:00.000000+00:00",
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
            "station_id": "96a83f47",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-10-31T00:00:00.000000+00:00",
            "value": 44.2895,
            "distance": 6.97,
            "taken_station_id": "00072",
        },
        {
            "station_id": "96a83f47",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": "1986-11-01T00:00:00.000000+00:00",
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
    assert response.headers["Content-Type"] == _IMAGE_MEDIA_TYPES[fmt]


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
            "parameters": "1_minute/precipitation/precipitation_amount",
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
        "elevation": 10.0,
        "name": "TROMSOE",
        "region": None,
    }


def test_get_stations_request_mosmix_issue_is_forwarded() -> None:
    """_get_stations_request must pass the `issue` kwarg to DwdMosmixRequest.

    Previously, isinstance(api, DwdMosmixRequest) was used where `api` is the
    *class* itself (not an instance), so the condition was always False and
    `issue` was silently dropped — DwdMosmixRequest always fell back to
    DwdForecastDate.LATEST regardless of what the caller sent.
    """
    import datetime as dt  # noqa: PLC0415

    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.provider.dwd.mosmix.api import DwdForecastDate  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.ui.core import ValuesRequest, _get_stations_request  # noqa: PLC0415

    api = Wetterdienst("dwd", "mosmix")
    settings = Settings()
    request = ValuesRequest(
        provider="dwd",
        network="mosmix",
        parameters=["hourly/large/ttt"],
        station=["10147"],
        issue="2026-06-27T09:00:00",
    )
    stations_request = _get_stations_request(api=api, request=request, date=None, settings=settings)

    # issue must be resolved to the specific datetime, not LATEST
    issue = stations_request.issue
    assert issue is not DwdForecastDate.LATEST
    assert isinstance(issue, dt.datetime)
    assert issue == dt.datetime(2026, 6, 27, 9, 0, 0, tzinfo=dt.timezone.utc)


def test_get_stations_request_mosmix_no_issue_defaults_to_latest() -> None:
    """When no issue is supplied the request must default to DwdForecastDate.LATEST."""
    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.provider.dwd.mosmix.api import DwdForecastDate  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.ui.core import ValuesRequest, _get_stations_request  # noqa: PLC0415

    api = Wetterdienst("dwd", "mosmix")
    settings = Settings()
    request = ValuesRequest(
        provider="dwd",
        network="mosmix",
        parameters=["hourly/large/ttt"],
        station=["10147"],
    )
    stations_request = _get_stations_request(api=api, request=request, date=None, settings=settings)

    assert stations_request.issue is DwdForecastDate.LATEST


def test_get_stations_request_date_required_dataset_does_not_raise_for_stations_request() -> None:
    """_get_stations_request must NOT raise StartDateEndDateError for StationsRequest.

    MetNo Frost marks its hourly, 10-minute, and 6-hour datasets as date_required=True.
    Previously the date-range check applied to StationsRequest too, so listing stations
    without a date range raised StartDateEndDateError and the Explorer showed no stations.
    """
    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.ui.core import StationsRequest, _get_stations_request  # noqa: PLC0415

    api = Wetterdienst("metno", "frost")
    settings = Settings(auth={"metno_frost": "fake-client-id"})
    request = StationsRequest(provider="metno", network="frost", parameters=["hourly/data"], all=True)

    # Must not raise StartDateEndDateError despite hourly/data having date_required=True
    stations_request = _get_stations_request(api=api, request=request, date=None, settings=settings)
    assert stations_request is not None


def test_get_stations_request_date_covers_the_span_it_names() -> None:
    """A `date` names a span, and the request window has to cover all of it.

    `date=2019-12` asked for December and got a window of one instant, the 1st at 00:00 -- one
    daily reading, and for anything hourly the one at midnight. An interval fared the same at its
    end: `2019-12/2020-01` stopped at the 1st of January rather than covering the month.
    """
    import datetime as dt  # noqa: PLC0415
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.ui.core import ValuesRequest, _get_stations_request  # noqa: PLC0415

    api = Wetterdienst("dwd", "observation")
    settings = Settings()

    def window(date: str) -> tuple[dt.datetime, dt.datetime]:
        request = ValuesRequest(
            provider="dwd",
            network="observation",
            parameters=["daily/kl"],
            station="00011",
        )
        stations_request = _get_stations_request(api=api, request=request, date=date, settings=settings)
        return stations_request.start_date, stations_request.end_date

    last_moment = dt.timedelta(microseconds=1)
    assert window("2019-12") == (
        dt.datetime(2019, 12, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")) - last_moment,
    )
    assert window("2019") == (
        dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")) - last_moment,
    )
    assert window("2019-12-28") == (
        dt.datetime(2019, 12, 28, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2019, 12, 29, tzinfo=ZoneInfo("UTC")) - last_moment,
    )
    assert window("2019-12/2020-01") == (
        dt.datetime(2019, 12, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")) - last_moment,
    )
    # a date carrying a time names one instant, so the window is that instant
    instant = dt.datetime(2019, 12, 28, 12, tzinfo=ZoneInfo("UTC"))
    assert window("2019-12-28T12:00:00") == (instant, instant)


def test_get_stations_request_passes_periods_to_every_provider() -> None:
    """The periods a caller asked for reach the request, whichever provider serves it.

    `periods` used to be a per-provider constructor argument, so `_get_stations_request` had to
    check for the field before passing it -- and MetnoFrostRequest, whose datasets are published
    under both historical and recent, had no way to hear the choice at all. It is a field of
    `TimeseriesRequest` now, validated against what the requested datasets publish.
    """
    from wetterdienst import Period, Wetterdienst  # noqa: PLC0415
    from wetterdienst.provider.metno.frost.api import MetnoFrostRequest  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.ui.core import StationsRequest, _get_stations_request  # noqa: PLC0415

    api = Wetterdienst("metno", "frost")
    settings = Settings(auth={"metno_frost": "fake-client-id"})
    request = StationsRequest(provider="metno", network="frost", parameters=["hourly/data"], periods="recent", all=True)

    stations_request = _get_stations_request(api=api, request=request, date=None, settings=settings)
    assert isinstance(stations_request, MetnoFrostRequest)
    assert stations_request.periods == {Period.RECENT}


def test_get_stations_request_periods_on_a_single_period_dataset() -> None:
    """An explicit period is answered even when the dataset publishes only one.

    `_get_stations_request` forwarded `periods` only when some requested dataset had more than one,
    so for `monthly/climate_correction_factor` -- released under `recent` alone -- a caller asking
    for `historical` was silently given every period the provider has instead of an error.
    """
    from wetterdienst import Period, Wetterdienst  # noqa: PLC0415
    from wetterdienst.exceptions import NoPeriodsFoundError  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.ui.core import StationsRequest, _get_stations_request  # noqa: PLC0415

    api = Wetterdienst("dwd", "derived")
    settings = Settings()
    request = StationsRequest(
        provider="dwd",
        network="derived",
        parameters=["monthly/climate_correction_factor"],
        periods="recent",
        all=True,
    )
    assert _get_stations_request(api=api, request=request, date=None, settings=settings).periods == {Period.RECENT}

    request = StationsRequest(
        provider="dwd",
        network="derived",
        parameters=["monthly/climate_correction_factor"],
        periods="historical",
        all=True,
    )
    with pytest.raises(NoPeriodsFoundError, match="Available periods: recent"):
        _get_stations_request(api=api, request=request, date=None, settings=settings)


@pytest.mark.parametrize("schema_name", ["_Station", "_OgcFeatureProperties"])
def test_stations_output_schemas_allow_null_region(schema_name: str) -> None:
    """The stations output schemas must type ``region`` as string-or-null (regression).

    MOSMIX/DMO stations have no region and serialise ``region`` as null. The MCP server validates every
    tool result against the output schema derived from these ``response_model`` types (via FastMCP).
    When the field (then ``state``) was typed ``str`` the schema required a string, so listing
    mosmix/dmo stations failed with "Output validation error: None is not of type 'string'". The
    field must be nullable.
    """
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    properties = app.openapi()["components"]["schemas"][schema_name]["properties"]
    # region is typed as string-or-null (anyOf includes a null branch)
    branches = properties["region"].get("anyOf", [properties["region"]])
    assert any(branch.get("type") == "null" for branch in branches), f"{schema_name}.region not nullable"
    assert any(branch.get("type") == "string" for branch in branches), f"{schema_name}.region not string"


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
        "timestamp": IsStr,
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
        "timestamp": IsStr,
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
        "timestamp": "2022-01-01T00:00:00.000000+00:00",
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
    assert response.headers["Content-Type"] == _IMAGE_MEDIA_TYPES[fmt]


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
    data = response.json()
    assert "metadata" in data
    assert "values" in data
    assert data["metadata"]["station"]["station_id"] == "01048"
    assert data["metadata"]["resolution"] == "annual"
    assert data["metadata"]["dataset"] == "climate_summary"
    assert data["metadata"]["parameter"] == "temperature_air_mean_2m"
    assert len(data["values"]) > 0
    assert all("timestamp" in v and "value" in v for v in data["values"])


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
    data = response.json()
    assert "metadata" in data
    assert "values" in data


@pytest.mark.remote
def test_stripes_values_csv_format(client: TestClient) -> None:
    """Test CSV format."""
    response = client.get(
        "/api/stripes/values",
        params={
            "kind": "temperature",
            "station": "01048",
            "format": "csv",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert b"timestamp,value" in response.content


@pytest.mark.parametrize(
    "fmt",
    sorted(
        {*get_args(get_args(_FormatField)[0]), *get_args(StripesImageRequest.model_fields["format"].annotation)}
        - {"json", "geojson", "csv", "html"},
    ),
)
def test_every_image_format_has_its_media_type(fmt: str) -> None:
    """Test each image format a request model allows is sent as its registered media type.

    A format added to a model without a media type would otherwise go out under a guessed one.
    """
    assert restapi._MEDIA_TYPES[fmt] == _IMAGE_MEDIA_TYPES[fmt]  # noqa: SLF001


@pytest.mark.parametrize(
    ("fmt", "media_type"),
    [
        ("png", "image/png"),
        ("jpg", "image/jpeg"),
        ("svg", "image/svg+xml"),
        ("pdf", "application/pdf"),
    ],
)
def test_stripes_image_is_sent_as_its_media_type(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
    media_type: str,
) -> None:
    """Test each stripes image format is sent as the media type registered for it (GH-2063).

    `image/{format}` gave `image/jpg`, `image/svg` and `image/pdf`, none of them registered.
    """

    class _Figure:
        def to_image(self, *_args: object, **_kwargs: object) -> bytes:
            return b"image"

    monkeypatch.setattr(restapi, "_plot_stripes", lambda _request: _Figure())
    response = client.get("/api/stripes/image", params={"kind": "temperature", "station": "01048", "format": fmt})
    assert response.status_code == 200
    assert response.headers["content-type"] == media_type


@pytest.mark.parametrize("endpoint", ["/api/stripes/values", "/api/stripes/image"])
@pytest.mark.parametrize(
    ("query", "detail"),
    [
        (
            {},
            [
                {
                    "type": "missing_one_of",
                    "loc": ["query"],
                    "msg": "Exactly one of station or name is required",
                    "input": None,
                    "ctx": {"one_of": [["station"], ["name"]]},
                },
            ],
        ),
        (
            {"station": "01048", "name": "Dresden-Klotzsche"},
            [
                {
                    "type": "mutually_exclusive",
                    "loc": ["query", "station"],
                    "msg": "Cannot be combined with name",
                    "input": "01048",
                    "ctx": {"conflicts_with": ["name"]},
                },
                {
                    "type": "mutually_exclusive",
                    "loc": ["query", "name"],
                    "msg": "Cannot be combined with station",
                    "input": "Dresden-Klotzsche",
                    "ctx": {"conflicts_with": ["station"]},
                },
            ],
        ),
        (
            {"station": "01048", "start_year": "2021", "end_year": "2020"},
            [
                {
                    "type": "greater_than_field",
                    "loc": ["query", "end_year"],
                    "msg": "Input should be greater than start_year (2021)",
                    "input": 2020,
                    "ctx": {"field": "start_year", "gt": 2021},
                },
            ],
        ),
        (
            {"name": "Dresden-Klotzsche", "name_threshold": "1.01"},
            [
                {
                    "type": "less_than_equal",
                    "loc": ["query", "name_threshold"],
                    "msg": "Input should be less than or equal to 1",
                    "input": "1.01",
                    "ctx": {"le": 1.0},
                },
            ],
        ),
    ],
)
def test_stripes_refused_as_the_other_endpoints_refuse(
    client: TestClient,
    endpoint: str,
    query: dict[str, str],
    detail: list[dict],
) -> None:
    """Test a stripes request is refused with FastAPI's 422, located at each parameter involved.

    Both endpoints checked these by hand and answered a string 400 --
    "Query arguments 'station' and 'name' are mutually exclusive" -- where the other endpoints answer
    the same rule with typed entries (GH-2060). Refused before anything is fetched.
    """
    response = client.get(endpoint, params={"kind": "temperature", **query})
    assert response.status_code == 422
    assert response.json()["detail"] == detail


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
    assert response.json()["detail"][0]["msg"] == "Input should be 'json' or 'csv'"


@pytest.mark.remote
def test_stripes_image_default(client: TestClient) -> None:
    """Test default parameters."""
    response = client.get(
        "/api/stripes/image",
        params={
            "kind": "temperature",
            "station": "01048",
        },
    )
    assert response.status_code == 200
    assert response.content


@pytest.mark.remote
def test_stripes_image_name(client: TestClient) -> None:
    """Test name parameter."""
    response = client.get(
        "/api/stripes/image",
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
def test_stripes_image_non_defaults(client: TestClient, params: dict) -> None:
    """Test non-default parameters."""
    response = client.get(
        "/api/stripes/image",
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
def test_stripes_image_unknown_name(client: TestClient) -> None:
    """Test unknown name value."""
    response = client.get(
        "/api/stripes/image",
        params={
            "kind": "temperature",
            "name": "foobar",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "No station with a name similar to 'foobar' found"}


@pytest.mark.remote
def test_stripes_image_unknown_format(client: TestClient) -> None:
    """Test wrong format value."""
    response = client.get(
        "/api/stripes/image",
        params={
            "kind": "temperature",
            "station": "01048",
            "format": "foobar",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Input should be 'png', 'jpg', 'svg' or 'pdf'"


@pytest.mark.remote
def test_stripes_image_wrong_dpi(client: TestClient) -> None:
    """Test wrong dpi value."""
    response = client.get(
        "/api/stripes/image",
        params={
            "kind": "temperature",
            "station": "01048",
            "dpi": 0,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Input should be greater than 0"


@pytest.mark.remote
def test_history_sections(client: TestClient) -> None:
    """Test sections keeps only the sections asked for, in the history's own order."""
    response = client.get(
        "/api/history",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/climate_summary",
            "station": "02564",
            "sections": "geography,name",
        },
    )
    assert response.status_code == 200
    assert [list(history) for history in response.json()["histories"]] == [
        ["station_id", "resolution", "dataset", "name", "geography"]
    ]


@pytest.mark.remote
def test_history_dwd_observation(client: TestClient) -> None:
    """Test dwd observation parameter."""
    response = client.get(
        "/api/history",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/climate_summary",
            "station": "02564",
            # with_metadata/with_stations now default to false; request them explicitly here
            "with_metadata": True,
            "with_stations": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data.keys() == {"metadata", "stations", "histories"}
    assert len(data["histories"]) == 1
    history = data["histories"][0]
    assert history.keys() == {
        "station_id",
        "resolution",
        "dataset",
        "name",
        "parameter",
        "device",
        "geography",
        "missing_data",
    }
    assert (history["station_id"], history["resolution"], history["dataset"]) == ("02564", "daily", "climate_summary")
    assert len(history["name"]) == 2
    assert history["name"].keys() == {"station", "operator"}
    assert history["name"]["station"][0] == {
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
        "start_date": "1927-02-01T00:00:00+00:00",
        "end_date": None,
    }
    assert history["name"]["operator"][0] == {
        "station_id": "02564",
        "operator_name": "Wetterdienst",
        "start_date": "1927-02-01T00:00:00+00:00",
        "end_date": "1951-01-16T00:00:00+00:00",
    }
    assert len(history["parameter"]) == 30
    assert history["parameter"][0] == {
        "data_source": "Winddaten (Stundenmittel, maximale Windspitze 00:00-23:59 "
        "MEZ) generiert aus analogen Registrierungen. Richtungsangaben "
        "in der 32-teiligen Windrose.",
        "description": "Tagesmittel der Windgeschwindigkeit m/s  Messnetz 3",
        "end_date": "1974-12-31T00:00:00+00:00",
        "extra_info": "arithm.Mittel aus mind. 21 Stundenwerten",
        "literature": "",
        "parameter": "FM",
        "special": "",
        "start_date": "1974-01-01T00:00:00+00:00",
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
        "unit": "m/sec",
    }
    assert len(history["device"]) == 49
    assert history["device"][0] == {
        "device_height": 31.0,
        "device_type": "Stationsbarometer",
        "end_date": "2009-11-17T00:00:00+00:00",
        "latitude": 54.38,
        "longitude": 10.14,
        "method": "Luftdruckmessung, konv.",
        "start_date": "1986-06-01T00:00:00+00:00",
        "station_elevation": 27.0,
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
    }
    assert len(history["geography"]) == 8
    assert history["geography"][0] == {
        "end_date": "1935-03-31T00:00:00+00:00",
        "latitude": 54.3767,
        "longitude": 10.1601,
        "start_date": "1927-02-01T00:00:00+00:00",
        "station_elevation": 4.0,
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
    }
    assert len(history["missing_data"]) == 2
    assert history["missing_data"].keys() == {"summary", "periods"}
    assert history["missing_data"]["summary"][0] == {
        "description": "Gesamt_Messzeitraum",
        "end_date": IsStr,
        "missing_count": IsApprox(147, delta=50),
        "parameter": "TMK",
        "start_date": "1974-01-01T00:00:00+00:00",
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
    }
    assert len(history["missing_data"]["periods"]) == IsApprox(398, delta=100)
    assert history["missing_data"]["periods"][0] == {
        "description": "",
        "end_date": "2007-03-12T00:00:00+00:00",
        "missing_count": 1,
        "parameter": "TMK",
        "start_date": "2007-03-12T00:00:00+00:00",
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
    }


@pytest.mark.remote
def test_issues_dwd_mosmix(client: TestClient) -> None:
    """Test /api/issues for DWD MOSMIX returns a non-empty sorted list of UTC ISO datetimes."""
    response = client.get(
        "/api/issues",
        params={"provider": "dwd", "network": "mosmix", "station": "10147"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data
    issues = data["issues"]
    assert len(issues) > 0
    assert issues == sorted(issues)
    assert all(issue.endswith("+00:00") for issue in issues)


@pytest.mark.remote
def test_issues_dwd_dmo(client: TestClient) -> None:
    """Test /api/issues for DWD DMO returns a non-empty sorted list of UTC ISO datetimes."""
    response = client.get(
        "/api/issues",
        params={"provider": "dwd", "network": "dmo", "station": "10147"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data
    issues = data["issues"]
    assert len(issues) > 0
    assert issues == sorted(issues)
    assert all(issue.endswith("+00:00") for issue in issues)


def test_issues_unsupported_provider(client: TestClient) -> None:
    """Test /api/issues returns 400 for providers that don't support issue listing."""
    response = client.get(
        "/api/issues",
        params={"provider": "dwd", "network": "observation", "station": "00011"},
    )
    assert response.status_code == 400
    assert "supported" in response.json()["detail"].lower()


def test_issues_unknown_provider(client: TestClient) -> None:
    """Test /api/issues returns 404 for unknown provider/network combinations."""
    response = client.get(
        "/api/issues",
        params={"provider": "unknown", "network": "unknown", "station": "00011"},
    )
    assert response.status_code == 404


@pytest.mark.remote
@pytest.mark.parametrize("granularity", ["community", "district"])
def test_alerts_default_json(client: TestClient, granularity: str) -> None:
    """Test /api/alerts returns a JSON alert collection."""
    response = client.get("/api/alerts", params={"granularity": granularity})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert "alerts" in data
    for alert in data["alerts"]:
        assert alert["alert_id"]


@pytest.mark.remote
def test_alerts_geojson(client: TestClient) -> None:
    """Test /api/alerts returns a GeoJSON FeatureCollection."""
    response = client.get("/api/alerts", params={"granularity": "district", "format": "geojson"})
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    for feature in data["features"]:
        assert feature["type"] == "Feature"
        if feature["geometry"] is not None:
            assert feature["geometry"]["type"] == "MultiPolygon"


@pytest.mark.remote
def test_alerts_csv(client: TestClient) -> None:
    """Test /api/alerts returns CSV."""
    response = client.get("/api/alerts", params={"format": "csv"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "alert_id" in response.text.splitlines()[0]


def test_alerts_invalid_granularity(client: TestClient) -> None:
    """Test /api/alerts rejects an unknown granularity."""
    response = client.get("/api/alerts", params={"granularity": "bogus"})
    assert response.status_code == 422


@pytest.mark.remote
def test_alerts_date_snapshot(client: TestClient) -> None:
    """Test /api/alerts accepts a historical date within the rolling window."""
    import datetime as dt  # noqa: PLC0415
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    target = dt.datetime.now(ZoneInfo("UTC")) - dt.timedelta(hours=6)
    response = client.get(
        "/api/alerts",
        params={"granularity": "district", "date": target.strftime("%Y-%m-%dT%H:%M:%S")},
    )
    assert response.status_code == 200
    assert "alerts" in response.json()


@pytest.mark.remote
def test_alerts_date_before_window(client: TestClient) -> None:
    """Test /api/alerts returns 400 for a date older than the rolling window."""
    response = client.get("/api/alerts", params={"date": "2000-01-01T00:00:00"})
    assert response.status_code == 400


def test_value_endpoints_default_to_compact_output() -> None:
    """with_metadata/with_stations default to false on the REST request models (compact output)."""
    from wetterdienst.ui.core import (  # noqa: PLC0415
        HistoryRequest,
        InterpolationRequest,
        StationsRequest,
        SummaryRequest,
        ValuesRequest,
    )

    for model in (StationsRequest, HistoryRequest, ValuesRequest, InterpolationRequest, SummaryRequest):
        assert model.model_fields["with_metadata"].default is False
        assert model.model_fields["with_stations"].default is False


def test_request_models_have_field_descriptions() -> None:
    """Every field of every REST request model carries a description (for OpenAPI + MCP)."""
    from wetterdienst.ui.core import (  # noqa: PLC0415
        HistoryRequest,
        InterpolationRequest,
        IssuesRequest,
        StationsRequest,
        SummaryRequest,
        ValuesRequest,
    )

    models = (
        StationsRequest,
        HistoryRequest,
        ValuesRequest,
        InterpolationRequest,
        SummaryRequest,
        IssuesRequest,
    )
    undescribed = {
        model.__name__: [name for name, info in model.model_fields.items() if not info.description] for model in models
    }
    undescribed = {model: fields for model, fields in undescribed.items() if fields}
    assert not undescribed, f"request-model fields missing descriptions: {undescribed}"


def test_mcp_endpoint_mounted() -> None:
    """The /mcp endpoint is mounted when the optional fastmcp extra is installed."""
    pytest.importorskip("fastmcp")
    from wetterdienst.ui import restapi  # noqa: PLC0415

    assert restapi.mcp_enabled is True
    paths = [getattr(route, "path", None) for route in restapi.app.routes]
    assert "/mcp" in paths


def test_mcp_index_link() -> None:
    """The index page advertises the MCP endpoint when it is enabled."""
    pytest.importorskip("fastmcp")
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415

    if not restapi.mcp_enabled:
        pytest.skip("fastmcp not installed")
    response = TestClient(restapi.app).get("/")
    assert "/mcp" in response.text


def test_mcp_initialize_handshake() -> None:
    """The /mcp endpoint speaks MCP: an initialize request returns an event-stream response."""
    pytest.importorskip("fastmcp")
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415

    if not restapi.mcp_enabled:
        pytest.skip("fastmcp not installed")
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    # the session manager runs in the app lifespan, so drive the client as a context manager
    with TestClient(restapi.app) as client:
        response = client.post("/mcp", json=body, headers={"Accept": "application/json, text/event-stream"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


def test_mcp_server_is_agent_friendly() -> None:
    """The MCP server exposes clean tool names, a workflow instructions block, and no noise tools."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    mcp = build_mcp_server(restapi.app)

    async def _introspect() -> tuple[set[str], str | None]:
        async with Client(mcp) as client:
            names = {tool.name for tool in await client.list_tools()}
            # client.instructions, not initialize_result: a FastMCP 4 discovery connection
            # negotiates a DiscoverResult and leaves initialize_result None
            return names, client.instructions

    tools, instructions = asyncio.run(_introspect())
    # data endpoints exposed under clean, agent-friendly names
    assert {"coverage", "glossary", "stations", "values", "alerts"} <= tools
    # the ugly auto-generated names are gone
    assert "values_api_values_get" not in tools
    # non-data/noise endpoints are excluded
    assert not tools & {"index", "health_health_get", "version_api_version_get", "auth_api_auth_get"}
    # a workflow instructions block is attached and describes the station -> values path
    assert instructions is not None
    assert "stations" in instructions
    assert "values" in instructions
    # interpolate/summarize are steered as opt-in, not the default for weather at a place
    assert "interpolate" in instructions
    assert "opt-in" in instructions or "explicitly" in instructions


def test_mcp_server_reports_the_wetterdienst_version() -> None:
    """The MCP server info carries wetterdienst's version, not FastMCP's.

    `FastMCP(version=...)` left unset reports the installed FastMCP release as the server's own
    version, so a client asking what it is talking to is told "Wetterdienst 4.0.3".
    """
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst import __version__  # noqa: PLC0415
    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    mcp = build_mcp_server(restapi.app)

    async def _server_info() -> object:
        async with Client(mcp) as client:
            return client.server_info

    server_info = asyncio.run(_server_info())
    assert server_info.name == "Wetterdienst"
    assert server_info.version == __version__


@pytest.mark.parametrize(
    ("schema_name", "nullable_numeric"),
    [
        ("_ValuesItemDict", ("value", "quality")),
        ("_InterpolatedValuesItemDict", ("value", "distance_mean")),
        ("_SummarizedValuesItemDict", ("value", "distance")),
    ],
)
def test_values_item_output_schemas_match_payload(schema_name: str, nullable_numeric: tuple[str, ...]) -> None:
    """The values/interpolate/summarize item schemas match what the endpoints serialise (regression).

    Guards the MCP output-schema drift behind #1776: every item carries `resolution` and `dataset`,
    and the numeric fields that go null when no station is in reach (e.g. an out-of-range
    interpolation point) must be typed nullable, or FastMCP output validation rejects the response.
    """
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    schema = app.openapi()["components"]["schemas"][schema_name]
    properties = schema["properties"]
    # resolution and dataset are always present in the serialised rows
    assert {"resolution", "dataset"} <= properties.keys()
    # nullable numeric fields are typed as number-or-null (anyOf includes a null branch)
    for field in nullable_numeric:
        branches = properties[field].get("anyOf", [properties[field]])
        assert any(branch.get("type") == "null" for branch in branches), f"{schema_name}.{field} not nullable"
        assert any(branch.get("type") == "number" for branch in branches), f"{schema_name}.{field} not numeric"


@pytest.mark.remote
def test_mcp_values_tool_returns_data() -> None:
    """The values MCP tool returns data instead of failing output-schema validation (regression)."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    mcp = build_mcp_server(restapi.app)

    async def _call() -> object:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "values",
                {
                    "provider": "dwd",
                    "network": "observation",
                    "parameters": "daily/climate_summary/temperature_air_mean_2m",
                    "station": "01975",
                    "periods": "recent",
                },
            )
            return result.data

    data = asyncio.run(_call())
    assert data is not None


@pytest.mark.remote
def test_mcp_interpolate_tool_returns_data() -> None:
    """The interpolate MCP tool passes output-schema validation, including null out-of-range rows.

    Interpolation of a point with no station in reach serialises null `value`/`distance_mean`; this
    exercises that the item schema types them nullable (regression for the interpolate/summarize
    counterpart of #1776).
    """
    pytest.importorskip("fastmcp")
    pytest.importorskip("utm")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    mcp = build_mcp_server(restapi.app)

    async def _call() -> object:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "interpolate",
                {
                    "provider": "dwd",
                    "network": "observation",
                    "parameters": "daily/climate_summary/temperature_air_mean_2m",
                    "station": "00071",
                    "date": "1986-10-31/1986-11-01",
                },
            )
            return result.data

    data = asyncio.run(_call())
    assert data is not None


@pytest.mark.parametrize(
    ("endpoint", "entry_point"),
    [
        ("/api/interpolate", "get_interpolate"),
        ("/api/summarize", "get_summarize"),
    ],
)
def test_geo_elevation_no_station_can_answer_is_a_400(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    entry_point: str,
) -> None:
    """A request understood and unanswerable as phrased is the caller's to fix, so it is a 400.

    Both endpoints used to answer every failure with a 404, which reads as "no such thing" for an
    elevation no station in reach can be placed against -- and the detail carried the reason to a
    caller who had no reason to read it.
    """
    from wetterdienst.exceptions import NoStationsWithElevationError  # noqa: PLC0415

    msg = "no station of known elevation is in reach, so there is no answer at 200.0 m for daily/climate_summary/tas"

    def unanswerable(**_kwargs: object) -> None:
        raise NoStationsWithElevationError(msg)

    monkeypatch.setattr(f"wetterdienst.ui.restapi.{entry_point}", unanswerable)
    response = client.get(
        endpoint,
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "00071",
            "date": "1986-10-31",
            "elevation": 200.0,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == msg


@pytest.mark.parametrize(
    ("endpoint", "entry_point", "params"),
    [
        (
            "/api/values",
            "get_values",
            {
                "provider": "dwd",
                "network": "road",
                "parameters": "15_minutes/data/temperature_air_mean_2m",
                "station": "A006",
                "date": "2024-01-01/2024-01-02",
            },
        ),
        (
            "/api/interpolate",
            "get_interpolate",
            {
                "provider": "dwd",
                "network": "road",
                "parameters": "15_minutes/data/temperature_air_mean_2m",
                "station": "A006",
                "date": "2024-01-01",
            },
        ),
        (
            "/api/summarize",
            "get_summarize",
            {
                "provider": "dwd",
                "network": "road",
                "parameters": "15_minutes/data/temperature_air_mean_2m",
                "station": "A006",
                "date": "2024-01-01",
            },
        ),
    ],
)
def test_a_reader_missing_on_the_server_is_a_501(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    endpoint: str,
    entry_point: str,
    params: dict[str, str],
) -> None:
    """A reader the deployment lacks is the server's lack, and it says so with the right status.

    The blanket handler turned it into a 400 -- the caller's fault -- carrying `pip install
    wetterdienst[bufr]`, which is an instruction for a machine the caller does not administer. The
    request was well formed; it is this instance that cannot serve it, which is a 501.

    Raised from a stubbed getter rather than by asking DWD for a road station: what is under test
    is the status and the body, and the real path downloads a station list on the way to the error.
    """
    from wetterdienst.exceptions import BufrReaderMissingError  # noqa: PLC0415

    msg = (
        "DWD road weather data is published as BUFR, which needs eccodes and pdbufr to read: "
        "`pip install wetterdienst[bufr]` installs both."
    )

    def refuse(**_kwargs: object) -> None:
        raise BufrReaderMissingError(msg)

    monkeypatch.setattr(f"wetterdienst.ui.restapi.{entry_point}", refuse)
    with caplog.at_level(logging.ERROR):
        response = client.get(endpoint, params=params)

    assert response.status_code == 501
    detail = response.json()["detail"]
    assert "eccodes and pdbufr" in detail
    # the install line is for whoever runs the instance, and reaches them through the log
    assert "pip install" not in detail
    assert "pip install wetterdienst[bufr]" in caplog.text


def test_values_a_value_error_from_the_values_is_a_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `ValueError` raised while collecting the values reaches the caller as a 500 with its message.

    `get_values` ended it with `sys.exit(1)`, a `SystemExit` the endpoint's `except Exception` does
    not catch, so the caller got a 500 with no message (GH-2218). It then answered a 400, which
    told the caller to rephrase a request that was fine; a failure that is not a refusal of the
    request is the server's (GH-2252).

    Stubbed at `get_stations` rather than provoked from a provider: what is under test is how the
    error travels, and a real one would need the network to arrive at.
    """
    msg = "can only call '.item()' if the dataframe has a single element"

    def fail() -> None:
        raise ValueError(msg)

    stations = SimpleNamespace(values=SimpleNamespace(all=fail))
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: stations)

    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "station": "01048",
            "date": "2020-06-30",
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == msg


def test_stations_schema_admits_null_core_columns_and_provider_columns(client: TestClient) -> None:
    """The station schema in /openapi.json admits the nulls and provider columns stations come with (GH-2226).

    `elevation` is null for every WSV and Eaufrance station, and `latitude`, `longitude` and `name`
    are null for the postcodes of dwd/derived climate_correction_factor; the schema typed them as a
    required number or string. Columns a provider adds (`gauge_zero`, `icao_id`, ...) were not part
    of the schema at all, so a client generated from it dropped them.
    """
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    # the endpoint's dict response carries its stations as `_Station` items
    assert schemas["_StationsDict"]["properties"]["stations"]["items"] == {"$ref": "#/components/schemas/_Station"}
    station = schemas["_Station"]
    nullable = {"latitude": "number", "longitude": "number", "elevation": "number", "name": "string"}
    for field, json_type in nullable.items():
        branches = station["properties"][field].get("anyOf", [station["properties"][field]])
        assert {branch.get("type") for branch in branches} == {json_type, "null"}, f"_Station.{field}"
    # provider station columns are admitted rather than declared one by one
    assert station["additionalProperties"] is True
    # the GeoJSON feature properties carry the same nullable name
    name = schemas["_OgcFeatureProperties"]["properties"]["name"]
    assert {branch.get("type") for branch in name.get("anyOf", [name])} == {"string", "null"}


@pytest.mark.remote
def test_mcp_stations_tool_wsv_null_elevation() -> None:
    """The stations MCP tool returns WSV stations, whose elevation is null (GH-2226).

    FastMCP validates a tool result against the output schema derived from the endpoint's
    `response_model`; with `elevation` typed as a number it failed with "None is not of type 'number'".
    """
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    mcp = build_mcp_server(restapi.app)

    async def _call() -> object:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "stations",
                {
                    "provider": "wsv",
                    "network": "pegel",
                    "parameters": "15_minutes/data/stage",
                    "station": "48900237",
                },
            )
            return result.structured_content

    data = asyncio.run(_call())
    (station,) = data["result"]["stations"]
    assert station["station_id"] == "48900237"
    assert station["elevation"] is None


def test_ogc_feature_properties_schema_allows_provider_station_columns() -> None:
    """The GeoJSON feature properties schema admits the station columns a provider adds.

    A feature carries the columns its provider declares beyond the core ones, such as WSV's
    `gauge_zero`, so the served schema must not read as a closed list of the core columns.
    """
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    assert app.openapi()["components"]["schemas"]["_OgcFeatureProperties"].get("additionalProperties") is True


@pytest.mark.parametrize(
    ("endpoint", "entry_point"),
    [("/api/interpolate", "get_interpolate"), ("/api/summarize", "get_summarize")],
)
def test_geo_a_failure_that_is_not_a_refusal_is_a_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    entry_point: str,
) -> None:
    """A failure on the server's side is a 500 with its message, not a 404 saying there is no such thing.

    The same failure answered 400 from `/api/values` and 404 from these, and neither is the
    caller's to fix (GH-2252).
    """
    msg = "can only call '.item()' if the dataframe has a single element"

    def fail(**_kwargs: object) -> None:
        raise ValueError(msg)

    monkeypatch.setattr(f"wetterdienst.ui.restapi.{entry_point}", fail)
    response = client.get(
        endpoint,
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl/temperature_air_mean_2m",
            "station": "01048",
            "date": "2020-06-30",
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == msg


_OBSERVATION = {"provider": "dwd", "network": "observation", "parameters": "daily/kl/temperature_air_mean_2m"}


def _year_10000_message() -> str:
    """Python's own words for a year past 9999, which 3.14 changed."""
    import datetime as dt  # noqa: PLC0415

    try:
        dt.datetime(9999, 1, 1, tzinfo=dt.timezone.utc).replace(year=10000)
    except ValueError as e:
        return str(e)
    msg = "a datetime held year 10000"
    raise AssertionError(msg)


@pytest.mark.parametrize(
    ("endpoint", "params", "status", "detail"),
    [
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "station": "01048", "date": "foo"},
            400,
            "date_string foo could not be parsed",
            id="values-unparseable-date",
        ),
        pytest.param(
            "/api/interpolate",
            {**_OBSERVATION, "station": "01048", "date": "foo"},
            404,
            "date_string foo could not be parsed",
            id="interpolate-unparseable-date",
        ),
        pytest.param(
            "/api/summarize",
            {**_OBSERVATION, "station": "01048", "date": "foo"},
            404,
            "date_string foo could not be parsed",
            id="summarize-unparseable-date",
        ),
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "station": "01048", "date": "2020/2021/2022"},
            400,
            "Invalid ISO 8601 time interval",
            id="values-three-part-interval",
        ),
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "parameters": "daily/abc", "station": "01048"},
            400,
            "No valid parameters could be parsed from ['daily/abc'] for DwdObservationRequest",
            id="values-unknown-parameter",
        ),
        pytest.param(
            "/api/interpolate",
            {**_OBSERVATION, "parameters": "daily/abc", "station": "01048", "date": "2020-06-30"},
            404,
            "No valid parameters could be parsed from ['daily/abc'] for DwdObservationRequest",
            id="interpolate-unknown-parameter",
        ),
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "station": "01048", "periods": "foo"},
            400,
            "foo could not be parsed from Period.",
            id="values-unknown-period",
        ),
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "station": "01048", "periods": "now"},
            400,
            "None of the periods now is published for the datasets requested from DwdObservationRequest. "
            "Available periods: historical, recent",
            id="values-unpublished-period",
        ),
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "left": 10, "bottom": 50, "right": 5, "top": 52},
            400,
            "bbox left border should be smaller then right",
            id="values-bbox-the-wrong-way-round",
        ),
        pytest.param(
            "/api/values",
            {"provider": "dwd", "network": "mosmix", "parameters": "hourly/small", "station": "10382", "issue": "foo"},
            400,
            "Invalid isoformat string: 'foo'",
            id="values-mosmix-unparseable-issue",
        ),
        pytest.param(
            "/api/interpolate",
            {
                "provider": "dwd",
                "network": "dmo",
                "parameters": "hourly/icon/temperature_air_mean_2m",
                "station": "10382",
                "issue": "foo",
                "date": "2026-10-01",
            },
            404,
            "Invalid isoformat string: 'foo'",
            id="interpolate-dmo-unparseable-issue",
        ),
        pytest.param(
            "/api/interpolate",
            {**_OBSERVATION, "latitude": 50.0, "longitude": 10.0, "date": ""},
            404,
            "start_date and end_date are required for interpolation",
            id="interpolate-empty-date",
        ),
        pytest.param(
            "/api/summarize",
            {**_OBSERVATION, "latitude": 50.0, "longitude": 10.0, "date": ""},
            404,
            "start_date and end_date are required for summarization",
            id="summarize-empty-date",
        ),
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "station": "01048", "date": "9999"},
            400,
            _year_10000_message(),
            id="values-date-past-the-last-year",
        ),
        pytest.param(
            "/api/interpolate",
            {**_OBSERVATION, "latitude": 50.0, "longitude": 10.0, "date": "9999-12-31"},
            404,
            "date value out of range",
            id="interpolate-date-past-the-last-day",
        ),
        pytest.param(
            "/api/interpolate",
            {**_OBSERVATION, "latitude": 85.0, "longitude": 10.0, "date": "2020-06-30"},
            404,
            "latitude out of range (must be between 80 deg S and 84 deg N)",
            id="interpolate-point-beyond-utm",
        ),
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "station": "01048", "date": "9999-12-31T23:00-05:00"},
            400,
            "date value out of range",
            id="values-instant-past-the-last-day-in-utc",
        ),
        pytest.param(
            "/api/values",
            {**_OBSERVATION, "station": "01048", "date": "9999-12-31T23:00Z"},
            400,
            "date value out of range",
            id="values-instant-past-the-last-day-in-the-providers-zone",
        ),
        pytest.param(
            "/api/values",
            {
                "provider": "dwd",
                "network": "dmo",
                "parameters": "hourly/icon/temperature_air_mean_2m",
                "station": "10382",
                "issue": "0001-01-01T00:00+01:00",
            },
            400,
            "date value out of range",
            id="values-dmo-issue-before-the-first-day-in-utc",
        ),
    ],
)
def test_a_refusal_of_the_request_keeps_its_4xx(
    client: TestClient,
    endpoint: str,
    params: dict[str, object],
    status: int,
    detail: str,
) -> None:
    """A request refused for what it asks is still the caller's to fix, and answers as it did (GH-2252).

    Each is refused before anything is downloaded, so these are real requests rather than stubs.
    The 404s from the geo endpoints are the status those answered with before; only failures that
    are not a refusal of the request moved, to a 500.
    """
    response = client.get(endpoint, params=params)

    assert response.status_code == status
    assert response.json()["detail"] == detail


def _raise_unit_target_refusal(**_kwargs: object) -> None:
    from wetterdienst.model.unit import UnitConverter  # noqa: PLC0415

    UnitConverter().update_targets({"temperature": "foo"})


def _raise_sql_refusal(**_kwargs: object) -> None:
    import polars as pl  # noqa: PLC0415

    from wetterdienst.io.export import ExportMixin  # noqa: PLC0415

    ExportMixin._filter_by_sql(pl.DataFrame({"value": [1.0]}), "foo = 1")  # noqa: SLF001


def _raise_station_not_found(**_kwargs: object) -> None:
    from wetterdienst.exceptions import StationNotFoundError  # noqa: PLC0415

    msg = "no station found for 99999"
    raise StationNotFoundError(msg)


@pytest.mark.parametrize(
    ("endpoint", "entry_point", "refuse", "status", "detail"),
    [
        pytest.param(
            "/api/values",
            None,
            _raise_unit_target_refusal,
            400,
            "Unit foo not supported for type temperature",
            id="values-unknown-unit-target",
        ),
        pytest.param(
            "/api/interpolate",
            "get_interpolate",
            _raise_unit_target_refusal,
            404,
            "Unit foo not supported for type temperature",
            id="interpolate-unknown-unit-target",
        ),
        pytest.param(
            "/api/values", None, _raise_sql_refusal, 400, 'Referenced column "foo" not found', id="values-sql"
        ),
        pytest.param(
            "/api/summarize",
            "get_summarize",
            _raise_sql_refusal,
            404,
            'Referenced column "foo" not found',
            id="summarize-sql",
        ),
        pytest.param(
            "/api/interpolate",
            "get_interpolate",
            _raise_station_not_found,
            404,
            "no station found for 99999",
            id="interpolate-unknown-station",
        ),
        pytest.param(
            "/api/summarize",
            "get_summarize",
            _raise_station_not_found,
            404,
            "no station found for 99999",
            id="summarize-unknown-station",
        ),
    ],
)
def test_a_refusal_raised_past_the_station_lookup_keeps_its_4xx(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    entry_point: str | None,
    refuse: object,
    status: int,
    detail: str,
) -> None:
    """A refusal raised once stations are known still answers as it did (GH-2252).

    The refusal is raised by the code that raises it on the real path -- the unit converter, the SQL
    filter -- from a stub at the point the network would otherwise be needed to reach it.
    """
    if entry_point is None:
        stations = SimpleNamespace(values=SimpleNamespace(all=refuse))
        monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: stations)
    else:
        monkeypatch.setattr(f"wetterdienst.ui.restapi.{entry_point}", refuse)

    response = client.get(endpoint, params={**_OBSERVATION, "station": "01048", "date": "2020-06-30"})

    assert response.status_code == status
    assert detail in response.json()["detail"]


def test_values_an_issue_the_source_does_not_list_keeps_its_400(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A forecast run asked for by an issue the listing does not hold is still a 400 (GH-2252)."""
    import polars as pl  # noqa: PLC0415

    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.dmo import api as dmo_api  # noqa: PLC0415

    monkeypatch.setattr(
        dmo_api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: ["https://example.com/kmz/ptp_gdmog_10382_078_1_210000.kmz"],
    )
    df_stations = pl.DataFrame(
        {"resolution": ["hourly"], "dataset": ["icon"], "station_id": ["10382"], "name": ["Berlin-Tegel"]},
    )
    stations = StationsResult(
        stations=DwdDmoRequest(parameters=["hourly/icon/temperature_air_mean_2m"], issue="2020-01-01T00:00"),
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.BY_STATION_ID,
    )
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: stations)

    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "dmo",
            "parameters": "hourly/icon/temperature_air_mean_2m",
            "station": "10382",
            "issue": "2020-01-01T00:00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Unable to find 2020-01-01 00:00:00 file within")


def test_the_refusal_types_keep_the_type_they_were_raised_as() -> None:
    """A library caller catching `ValueError` or `IndexError` still catches them (GH-2252).

    Two were raised as something narrower: a date past year 9999 as an `OverflowError`, which is not
    a `ValueError`, and a point beyond UTM as utm's `OutOfRangeError`, which is one.
    """
    from wetterdienst.exceptions import (  # noqa: PLC0415
        InvalidBoundingBoxError,
        InvalidEnumerationError,
        InvalidTimeIntervalError,
        IssueNotFoundError,
        LocationOutOfRangeError,
    )

    assert issubclass(LocationOutOfRangeError, ValueError)
    assert issubclass(InvalidBoundingBoxError, ValueError)
    assert issubclass(InvalidEnumerationError, ValueError)
    assert issubclass(InvalidTimeIntervalError, ValueError)
    assert issubclass(IssueNotFoundError, IndexError)


def test_values_a_duckdb_failure_that_is_not_about_the_statement_is_a_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DuckDB running out of memory is the server's failure, however the caller's SQL reads (GH-2252)."""
    import duckdb  # noqa: PLC0415

    msg = "Out of Memory Error: failed to allocate data of size 1.0 GiB"

    def fail() -> None:
        raise duckdb.OutOfMemoryException(msg)

    stations = SimpleNamespace(values=SimpleNamespace(all=fail))
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: stations)

    response = client.get("/api/values", params={**_OBSERVATION, "station": "01048", "date": "2020-06-30"})

    assert response.status_code == 500
    assert response.json()["detail"] == msg


@pytest.mark.parametrize("schema_name", ["_StationsOgcFeature", "_ValuesOgcFeature"])
def test_ogc_feature_schema_allows_a_null_geometry(schema_name: str) -> None:
    """The GeoJSON feature schemas admit a null geometry, which a station without a position gets."""
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    geometry = app.openapi()["components"]["schemas"][schema_name]["properties"]["geometry"]
    assert {"$ref": "#/components/schemas/_OgcFeatureGeometry"} in geometry["anyOf"]
    assert {"type": "null"} in geometry["anyOf"]


def test_ogc_feature_properties_schema_allows_a_null_dataset() -> None:
    """The GeoJSON feature properties admit a null dataset (GH-2274).

    A values feature of a resolution the wide shape merged several datasets into names none.
    """
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    dataset = app.openapi()["components"]["schemas"]["_OgcFeatureProperties"]["properties"]["dataset"]
    assert {branch.get("type") for branch in dataset.get("anyOf", [dataset])} == {"string", "null"}


def _values_result_of_shape(shape: str) -> "ValuesResult":
    """Build a values result of one station in two daily datasets, in the long or the wide shape.

    The wide row is the one `TimeseriesValues._widen_df` writes for two datasets of one resolution:
    one value and one quality column per parameter, prefixed with its dataset, and no dataset of
    its own.
    """
    import datetime as dt  # noqa: PLC0415

    import polars as pl  # noqa: PLC0415

    from wetterdienst.model.result import StationsFilter, StationsResult, ValuesResult  # noqa: PLC0415
    from wetterdienst.model.values import TimeseriesValues  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    station = {
        "resolution": "daily",
        "station_id": "01048",
        "start_date": None,
        "end_date": None,
        "latitude": 51.1,
        "longitude": 13.8,
        "elevation": 228.0,
        "name": "Dresden-Klotzsche",
        "region": "Sachsen",
    }
    df_stations = pl.DataFrame(
        [{**station, "dataset": "climate_summary"}, {**station, "dataset": "precipitation_more"}],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
        },
        orient="row",
    )
    stations = StationsResult(df=df_stations, df_all=df_stations, stations_filter=StationsFilter.ALL, stations=None)
    row = {"station_id": "01048", "resolution": "daily", "timestamp": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)}
    df_values = pl.DataFrame(
        [
            {
                **row,
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "value": 1.0,
                "quality": 10.0,
            },
            {
                **row,
                "dataset": "precipitation_more",
                "parameter": "precipitation_amount",
                "value": 2.0,
                "quality": None,
            },
        ],
        schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")},
        orient="row",
    )
    if shape == "wide":
        # widened by the method the values pipeline widens with, so the row is the one it writes
        request = DwdObservationRequest(
            parameters=[
                ("daily", "climate_summary", "temperature_air_mean_2m"),
                ("daily", "precipitation_more", "precipitation_amount"),
            ],
        )
        values = SimpleNamespace(sr=SimpleNamespace(parameters=request.parameters, settings=request.settings))
        df_values = TimeseriesValues._widen_df(values, df_values)  # noqa: SLF001
    df_values = TimeseriesValues._cast_metadata_to_enum(df_values)  # noqa: SLF001
    return ValuesResult(stations=stations, values=None, df=df_values)


@pytest.mark.parametrize("shape", ["long", "wide"])
@pytest.mark.parametrize(("fmt", "schema_name"), [("json", "_ValuesDict"), ("geojson", "_ValuesOgcFeatureCollection")])
def test_values_output_validates_against_the_served_schema(shape: str, fmt: str, schema_name: str) -> None:
    """Each values output validates against the schema /openapi.json serves for it (GH-2282).

    Every item was typed as a long JSON item, which a GeoJSON feature's values -- whose station
    the feature's properties carry -- and a wide row -- one column per parameter, and no dataset
    in a resolution several datasets were merged into -- do not match, so MCP output validation
    rejected them.
    """
    jsonschema = pytest.importorskip("jsonschema")
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    result = _values_result_of_shape(shape)
    payload = json.loads(result.to_json() if fmt == "json" else result.to_geojson())
    components = app.openapi()["components"]
    jsonschema.validate(payload, {"$ref": f"#/components/schemas/{schema_name}", "components": components})


@pytest.mark.parametrize("shape", ["long", "wide"])
@pytest.mark.parametrize("fmt", ["json", "geojson"])
def test_mcp_values_tool_passes_output_validation_in_each_shape_and_format(
    monkeypatch: pytest.MonkeyPatch,
    shape: str,
    fmt: str,
) -> None:
    """The values MCP tool's results pass its output validation in the wide shape and as GeoJSON (GH-2282).

    Stubbed at `get_stations` so that what is validated is the tool's response to a values result
    of the shape asked for, without the network.
    """
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    result = _values_result_of_shape(shape)
    stations = SimpleNamespace(values=SimpleNamespace(all=lambda: result))
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: stations)
    mcp = build_mcp_server(restapi.app)

    async def _call() -> object:
        async with Client(mcp) as client:
            response = await client.call_tool(
                "values",
                {
                    "provider": "dwd",
                    "network": "observation",
                    # the two datasets the stubbed result holds
                    "parameters": "daily/climate_summary/temperature_air_mean_2m,"
                    "daily/precipitation_more/precipitation_amount",
                    "station": "01048",
                    "format": fmt,
                    "shape": shape,
                },
            )
            return response.structured_content

    data = asyncio.run(_call())
    expected = json.loads(result.to_json() if fmt == "json" else result.to_geojson())
    assert data["result"] == expected


def _pydantic_writes_extra_items() -> bool:
    """Tell whether pydantic writes a TypedDict's `extra_items` into its schema, which it does from 2.12.

    An older one leaves the wide row's columns undeclared, which JSON Schema admits all the same.
    """
    import pydantic  # noqa: PLC0415

    major, minor = (int(part) for part in pydantic.VERSION.split(".")[:2])
    return (major, minor) >= (2, 12)


_NEEDS_EXTRA_ITEMS = pytest.mark.skipif(
    not _pydantic_writes_extra_items(),
    reason="pydantic writes a TypedDict's extra_items into its schema from 2.12 on",
)


@_NEEDS_EXTRA_ITEMS
@pytest.mark.parametrize("schema_name", ["_ValuesWideItemDict", "_ValuesWideOgcItemDict"])
def test_values_wide_row_schemas_type_the_parameter_columns(schema_name: str) -> None:
    """The wide row schemas type the columns beyond the declared ones as nullable numbers (GH-2282).

    A wide row has a value and a quality column per parameter asked for, which differ per request,
    so a client generated from the schema must not read the declared keys as a closed list.
    """
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    extra = app.openapi()["components"]["schemas"][schema_name]["additionalProperties"]
    assert {branch.get("type") for branch in extra.get("anyOf", [extra])} == {"number", "null"}


@_NEEDS_EXTRA_ITEMS
@pytest.mark.parametrize(
    ("fmt", "schema_name"),
    [("json", "_ValuesWideItemDict"), ("geojson", "_ValuesWideOgcItemDict")],
)
def test_values_long_row_does_not_pass_for_a_wide_one(fmt: str, schema_name: str) -> None:
    """A long row fails the wide row schema, so the served union still checks a long row (GH-2282).

    Were the wide row's columns untyped, every long row would match it too, and a long row missing
    its `value` or `quality` would pass the union through the wide branch.
    """
    jsonschema = pytest.importorskip("jsonschema")
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    result = _values_result_of_shape("long")
    if fmt == "json":
        item = result.to_dict()["values"][0]
    else:
        item = result.to_ogc_feature_collection()["data"]["features"][0]["values"][0]
    schema = {"$ref": f"#/components/schemas/{schema_name}", "components": app.openapi()["components"]}
    with pytest.raises(jsonschema.ValidationError, match="'temperature_air_mean_2m' is not valid"):
        jsonschema.validate(item, schema)


@pytest.mark.parametrize(
    ("endpoint", "params", "detail"),
    [
        pytest.param(
            "/api/stations",
            {**_OBSERVATION, "parameters": "daily/abc", "all": "true"},
            "No valid parameters could be parsed from ['daily/abc'] for DwdObservationRequest",
            id="stations-unknown-parameter",
        ),
        pytest.param(
            "/api/stations",
            {**_OBSERVATION, "periods": "foo", "all": "true"},
            "foo could not be parsed from Period.",
            id="stations-unknown-period",
        ),
        pytest.param(
            "/api/stations",
            {**_OBSERVATION, "periods": "now", "all": "true"},
            "None of the periods now is published for the datasets requested from DwdObservationRequest. "
            "Available periods: historical, recent",
            id="stations-unpublished-period",
        ),
        pytest.param(
            "/api/stations",
            {**_OBSERVATION, "left": 10, "bottom": 50, "right": 5, "top": 52},
            "bbox left border should be smaller then right",
            id="stations-bbox-the-wrong-way-round",
        ),
        pytest.param(
            "/api/stations",
            {"provider": "dwd", "network": "mosmix", "parameters": "hourly/small", "station": "10382", "issue": "foo"},
            "Invalid isoformat string: 'foo'",
            id="stations-mosmix-unparseable-issue",
        ),
        pytest.param(
            "/api/stations",
            {
                "provider": "dwd",
                "network": "dmo",
                "parameters": "hourly/icon",
                "station": "10382",
                "issue": "0001-01-01T00:00+01:00",
            },
            "date value out of range",
            id="stations-dmo-issue-before-the-first-day-in-utc",
        ),
        pytest.param(
            "/api/history",
            {**_OBSERVATION, "parameters": "daily/abc", "station": "01048"},
            "No valid parameters could be parsed from ['daily/abc'] for DwdObservationRequest",
            id="history-unknown-parameter",
        ),
        pytest.param(
            "/api/history",
            {"provider": "eccc", "network": "observation", "parameters": "hourly/data", "all": "true"},
            "Start and end date required for single period datasets",
            id="history-dataset-listed-only-for-a-date",
        ),
        pytest.param(
            "/api/issues",
            {"provider": "dwd", "network": "mosmix", "station": "10382", "lead_time": "long"},
            "lead_time applies to DWD DMO only (got DwdMosmixRequest)",
            id="issues-mosmix-with-a-lead-time",
        ),
    ],
)
def test_a_refusal_of_the_lookup_keeps_its_400(
    client: TestClient,
    endpoint: str,
    params: dict[str, object],
    detail: str,
) -> None:
    """A request the station lookup or the issue listing refuses is still the caller's 400 (GH-2276).

    Each is refused before anything is downloaded, so these are real requests rather than stubs.
    """
    response = client.get(endpoint, params=params)

    assert response.status_code == 400
    assert response.json()["detail"] == detail


def test_stations_a_sql_refusal_keeps_its_400(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `sql` naming a column the stations do not have is still the caller's 400 (GH-2276)."""
    monkeypatch.setattr("wetterdienst.ui.restapi.get_stations", _raise_sql_refusal)

    response = client.get("/api/stations", params={**_OBSERVATION, "sql": "foo = 1"})

    assert response.status_code == 400
    assert 'Referenced column "foo" not found' in response.json()["detail"]


def _stub_stripes(monkeypatch: pytest.MonkeyPatch, stations: list[dict], values: dict[int, float | None]) -> None:
    """Have the temperature stripes read `stations` and these yearly `values` instead of DWD's."""
    import datetime as dt  # noqa: PLC0415

    import polars as pl  # noqa: PLC0415

    from wetterdienst.ui import core  # noqa: PLC0415

    frame = pl.DataFrame(
        {
            # `dt.timezone.utc` rather than `dt.UTC`, which Python 3.10 does not have
            "timestamp": [dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc) for year in values],
            "value": list(values.values()),
        },
        schema={"timestamp": pl.Datetime(time_zone="UTC"), "value": pl.Float64},
    )
    result = SimpleNamespace(
        to_dict=lambda: {"stations": stations},
        values=SimpleNamespace(all=lambda: SimpleNamespace(df=frame)),
    )
    request = SimpleNamespace(filter_by_station_id=lambda _station: result)
    monkeypatch.setitem(core.CLIMATE_STRIPES_CONFIG["temperature"], "request", lambda _period: request)


@pytest.mark.parametrize("endpoint", ["/api/stripes/values", "/api/stripes/image"])
@pytest.mark.parametrize(
    ("stations", "values", "detail"),
    [
        pytest.param([], {}, "No station with a station_id similar to '99999' found", id="unknown-station"),
        pytest.param(
            [{"station_id": "99999", "name": "Somewhere"}],
            {2000: 1.0},
            "At least two years with data are required to create climate stripes; station 99999 has data "
            "from 2000 to 2000",
            id="one-year-with-data",
        ),
    ],
)
def test_stripes_a_refusal_keeps_its_400(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    stations: list[dict],
    values: dict[int, float | None],
    detail: str,
) -> None:
    """A station the stripes do not know, or one with too little data, is still the caller's 400 (GH-2276)."""
    _stub_stripes(monkeypatch, stations, values)

    response = client.get(endpoint, params={"kind": "temperature", "station": "99999"})

    assert response.status_code == 400
    assert response.json()["detail"] == detail


_UNEXPECTED = "can only call '.item()' if the dataframe has a single element"


def _fail(*_args: object, **_kwargs: object) -> None:
    raise ValueError(_UNEXPECTED)


class _HistoryFails:
    """A stations result whose history fails at the step named, as a source that cannot be read would."""

    def __init__(self, step: str, fail: Callable[[], None] = _fail) -> None:
        self.step, self.fail = step, fail

    @property
    def history(self) -> SimpleNamespace:
        if self.step == "history":
            self.fail()
        return SimpleNamespace(query=self.fail)


@pytest.mark.parametrize(
    ("endpoint", "entry_point", "stub", "params"),
    [
        pytest.param("/api/stations", "get_stations", _fail, {**_OBSERVATION, "all": "true"}, id="stations"),
        pytest.param("/api/history", "get_stations", _fail, {**_OBSERVATION, "station": "01048"}, id="history-lookup"),
        pytest.param(
            "/api/history",
            "get_stations",
            lambda **_kwargs: _HistoryFails("history"),
            {**_OBSERVATION, "station": "01048"},
            id="history-provider",
        ),
        pytest.param(
            "/api/history",
            "get_stations",
            lambda **_kwargs: _HistoryFails("query"),
            {**_OBSERVATION, "station": "01048"},
            id="history-query",
        ),
        pytest.param(
            "/api/issues",
            "get_issues",
            _fail,
            {"provider": "dwd", "network": "mosmix", "station": "10382"},
            id="issues",
        ),
        pytest.param(
            "/api/stripes/stations", "_get_stripes_stations", _fail, {"kind": "temperature"}, id="stripes-stations"
        ),
        pytest.param(
            "/api/stripes/values",
            "_get_stripes_data",
            _fail,
            {"kind": "temperature", "station": "01048"},
            id="stripes-values",
        ),
        pytest.param(
            "/api/stripes/image",
            "_plot_stripes",
            _fail,
            {"kind": "temperature", "station": "01048"},
            id="stripes-image",
        ),
    ],
)
def test_a_failure_of_the_lookup_that_is_not_a_refusal_is_a_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    entry_point: str,
    stub: object,
    params: dict[str, object],
) -> None:
    """A failure on the server's side is a 500 with its message, as from `/api/values` (GH-2276).

    These answered it with a 400, which told the caller to rephrase a request that was fine.
    """
    monkeypatch.setattr(f"wetterdienst.ui.restapi.{entry_point}", stub)

    response = client.get(endpoint, params=params)

    assert response.status_code == 500
    assert response.json()["detail"] == _UNEXPECTED


def _fail_as_a_refusal(*_args: object, **_kwargs: object) -> None:
    from wetterdienst.exceptions import InvalidEnumerationError  # noqa: PLC0415

    raise InvalidEnumerationError(_UNEXPECTED)


@pytest.mark.parametrize(
    ("endpoint", "entry_point", "stub", "params"),
    [
        pytest.param(
            "/api/stripes/stations",
            "_get_stripes_stations",
            _fail_as_a_refusal,
            {"kind": "temperature"},
            id="stripes-stations",
        ),
        pytest.param(
            "/api/history",
            "get_stations",
            lambda **_kwargs: _HistoryFails("history", _fail_as_a_refusal),
            {**_OBSERVATION, "station": "01048"},
            id="history-provider",
        ),
        pytest.param(
            "/api/history",
            "get_stations",
            lambda **_kwargs: _HistoryFails("query", _fail_as_a_refusal),
            {**_OBSERVATION, "station": "01048"},
            id="history-query",
        ),
    ],
)
def test_a_failure_where_the_caller_has_no_input_is_a_500_whatever_its_type(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    entry_point: str,
    stub: object,
    params: dict[str, object],
) -> None:
    """A refusal's type raised where nothing of the caller's reaches is the source's, and a 500 (GH-2276).

    The station list of the stripes takes no input the signature has not checked, and a history is
    read once its stations are known, so an `InvalidEnumerationError` there comes from the data.
    """
    monkeypatch.setattr(f"wetterdienst.ui.restapi.{entry_point}", stub)

    response = client.get(endpoint, params=params)

    assert response.status_code == 500
    assert response.json()["detail"] == _UNEXPECTED


def test_stripes_an_index_error_building_the_station_is_not_an_unknown_station(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An `IndexError` from building the stations is a 500, not "No station ... found" (GH-2276)."""
    from wetterdienst.ui import core  # noqa: PLC0415

    def to_dict() -> None:
        msg = "list index out of range"
        raise IndexError(msg)

    request = SimpleNamespace(filter_by_station_id=lambda _station: SimpleNamespace(to_dict=to_dict))
    monkeypatch.setitem(core.CLIMATE_STRIPES_CONFIG["temperature"], "request", lambda _period: request)

    response = client.get("/api/stripes/values", params={"kind": "temperature", "station": "01048"})

    assert response.status_code == 500
    assert response.json()["detail"] == "list index out of range"


def test_values_a_unit_target_for_an_unknown_quantity_is_a_400(client: TestClient) -> None:
    """A unit target for a quantity the converter does not know is the caller's 400 (GH-2272).

    `/api/values` built its settings outside any handler, so the validator's refusal reached the
    caller as a bare 500 "Internal Server Error". Refused before anything is downloaded.
    """
    response = client.get(
        "/api/values",
        params={**_OBSERVATION, "station": "01048", "unit_targets": json.dumps({"foo": "bar"})},
    )

    assert response.status_code == 400
    assert "Invalid unit targets: quantities not supported: foo." in response.json()["detail"]


def test_values_a_setting_the_server_environment_got_wrong_is_not_the_callers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """A malformed `WD_*` setting is the server's 500, without its value, not the caller's 400 (GH-2272).

    A malformed process variable stops the server from starting, as importing it builds `Settings`
    once. The `.env` file is read again for every `Settings` built, so one written while the server
    runs reaches the settings `/api/values` builds per request.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    (tmp_path / ".env").write_text("WD_CACHE_DISABLE=not-a-bool\n")
    monkeypatch.chdir(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/values", params={**_OBSERVATION, "station": "01048"})

    # Starlette's own answer to an exception nothing handled, so the settings are what failed: a
    # request that got past them would fail on the network and answer with a detail of its own
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        pytest.param("/api/alerts", {}, id="alerts"),
        pytest.param("/api/stations", {**_OBSERVATION, "station": "01048"}, id="stations"),
        pytest.param("/api/history", {**_OBSERVATION, "station": "01048"}, id="history"),
        pytest.param("/api/issues", {"provider": "dwd", "network": "mosmix", "station": "10147"}, id="issues"),
        pytest.param("/api/interpolate", {**_OBSERVATION, "station": "01048", "date": "2020-06-30"}, id="interpolate"),
        pytest.param("/api/summarize", {**_OBSERVATION, "station": "01048", "date": "2020-06-30"}, id="summarize"),
        pytest.param(
            "/api/interpolate",
            {
                **_OBSERVATION,
                "station": "01048",
                "date": "2020-06-30",
                "interpolation_station_distance": '{"temperature_air_mean": 10}',
            },
            id="interpolate-beside-a-refusal",
        ),
    ],
)
def test_a_setting_the_server_environment_got_wrong_is_not_the_callers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    endpoint: str,
    params: dict[str, str],
) -> None:
    """A malformed `WD_*` setting is the server's 500, without its value, not the caller's 400 (GH-2297).

    Read from `.env` for every `Settings` built, as for `/api/values`. The geo endpoints answered it
    as a 400, and alerts too, its `ValidationError` being a `ValueError`; the station, history and
    issue lookups as a 500 carrying the value. A refusal of the caller's beside it does not make it
    theirs.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    (tmp_path / ".env").write_text("WD_CACHE_DISABLE=not-a-bool\n")
    monkeypatch.chdir(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(endpoint, params=params)

    # Starlette's own answer to an exception nothing handled, so the settings are what failed
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


@pytest.mark.parametrize("endpoint", ["/api/interpolate", "/api/summarize"])
def test_geo_a_unit_target_for_an_unknown_quantity_is_a_400(client: TestClient, endpoint: str) -> None:
    """A unit target for a quantity the converter does not know stays the caller's 400 (GH-2297)."""
    response = client.get(
        endpoint,
        params={**_OBSERVATION, "station": "01048", "date": "2020-06-30", "unit_targets": json.dumps({"foo": "bar"})},
    )

    assert response.status_code == 400
    assert "Invalid unit targets: quantities not supported: foo." in response.json()["detail"]


_ALERTS_LISTING = [
    {
        "name": (
            "https://opendata.dwd.de/weather/alerts/cap/COMMUNEUNION_DWD_STAT/"
            f"Z_CAP_C_EDZW_{timestamp}_PVW_STATUS_PREMIUMDWD_COMMUNEUNION_EN.zip"
        ),
        "type": "file",
    }
    for timestamp in ("20260726100000", "20260726110000")
]


def _alerts_snapshot(content: object) -> Callable[..., object]:
    """Stand in for the snapshot download, answering with `content`: a body, or the failure."""
    from wetterdienst.util.network import File  # noqa: PLC0415

    return lambda *_args, **_kwargs: File(url="http://x", content=content, status=200)


def _alerts_zip(cap: bytes) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("alert.xml", cap)
    buffer.seek(0)
    return buffer


def test_alerts_a_date_before_the_window_is_the_callers(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A date before DWD's rolling window is the caller's 400 (GH-2294)."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.alerts.api.list_remote_directory_fsspec",
        lambda *_args, **_kwargs: _ALERTS_LISTING,
    )

    response = client.get("/api/alerts", params={"date": "2026-07-01T00:00:00"})

    assert response.status_code == 400
    assert "rolling ~48-hour window" in response.json()["detail"]


def test_alerts_a_date_that_does_not_parse_is_the_callers(client: TestClient) -> None:
    """A date that does not parse is the caller's 400, refused before anything is listed (GH-2294)."""
    response = client.get("/api/alerts", params={"date": "yesterday"})

    assert response.status_code == 400
    assert "yesterday" in response.json()["detail"]


@pytest.mark.parametrize(
    ("listing", "download", "detail"),
    [
        pytest.param(
            None,
            _alerts_snapshot(FileNotFoundError("404")),
            "could not download weather alerts snapshot",
            id="download",
        ),
        pytest.param(
            None,
            _alerts_snapshot(io.BytesIO(b"<html>error</html>")),
            "not a valid zip archive",
            id="not-a-zip",
        ),
        pytest.param(
            None,
            # a `ValueError`, as the request's date refusal is, but from DWD's own timestamp
            _alerts_snapshot(_alerts_zip(b"<alert><sent>not-a-time</sent></alert>")),
            "Invalid isoformat string: 'not-a-time'",
            id="cap-timestamp",
        ),
        pytest.param(
            None,
            # an `OverflowError`, as the request's own date can raise, but from DWD's timestamp
            _alerts_snapshot(_alerts_zip(b"<alert><sent>0001-01-01T00:00:00+01:00</sent></alert>")),
            "date value out of range",
            id="cap-timestamp-overflow",
        ),
        pytest.param([], None, "no weather-alerts snapshot listed at", id="empty-listing"),
    ],
)
def test_alerts_a_feed_that_cannot_be_read_is_a_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    listing: list[dict[str, str]] | None,
    download: Callable[..., object] | None,
    detail: str,
) -> None:
    """A CAP feed that does not list, download or read is the server's 500, not the caller's 400 (GH-2294)."""
    params = {}
    if listing is not None:
        monkeypatch.setattr(
            "wetterdienst.provider.dwd.alerts.api.list_remote_directory_fsspec",
            lambda *_args, **_kwargs: listing,
        )
        params["date"] = "2026-07-26T10:30:00"
    if download is not None:
        monkeypatch.setattr("wetterdienst.provider.dwd.alerts.api.download_file", download)

    response = client.get("/api/alerts", params=params)

    assert response.status_code == 500
    assert detail in response.json()["detail"]


def test_alerts_a_date_an_offset_carries_out_of_range_is_the_callers(client: TestClient) -> None:
    """A date its offset carries past what a datetime holds is the caller's 400, not a bare 500 (GH-2294)."""
    response = client.get("/api/alerts", params={"date": "0001-01-01T00:00:00+01:00"})

    assert response.status_code == 400
    assert response.json()["detail"] == "date value out of range"


@pytest.mark.parametrize(
    "setting",
    [
        pytest.param('WD_TS_UNIT_TARGETS={"foo": "bar"}', id="unit-targets"),
        pytest.param("WD_TS_GEO_STATION_DISTANCE__nonsense=5", id="station-distance"),
    ],
)
@pytest.mark.parametrize("endpoint", ["/api/interpolate", "/api/summarize"])
def test_geo_a_dict_setting_the_server_got_wrong_is_not_the_callers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    endpoint: str,
    setting: str,
) -> None:
    """A malformed dict-valued `WD_*` setting is the server's bare 500, though the request gives that field (GH-2297).

    pydantic-settings merges the dict the environment sets into the one the request gives, so the
    error is located at a field the request supplied.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    (tmp_path / ".env").write_text(f"{setting}\n")
    monkeypatch.chdir(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(endpoint, params={**_OBSERVATION, "station": "01048", "date": "2020-06-30"})

    assert response.status_code == 500
    assert response.text == "Internal Server Error"


_DAYS = ["1990-01-01", "1990-01-02", "1990-01-03"]


@pytest.fixture
def stubbed_values(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> Callable[..., dict]:
    """Answer `/api/values` offline for two stations and three parameters of two daily datasets.

    Each dataset comes back newest timestamp first, and its parameters interleaved within a
    timestamp, so the order a response comes in is the one `TimeseriesValues.query` sorts it into,
    not the order the source wrote.
    """
    from tests.model.test_values import _stub_dwd_daily  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415

    _stub_dwd_daily(
        station_ids=["00002", "00001"],
        data_year_by_station={"00002": 1990, "00001": 1990},
        monkeypatch=monkeypatch,
        datasets=["climate_summary", "precipitation_more"],
    )
    collect = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001
    monkeypatch.setattr(
        DwdObservationValues,
        "_collect_station_parameter_or_dataset",
        lambda self, station_id, parameter_or_dataset: collect(self, station_id, parameter_or_dataset).reverse(),
    )

    def get(**params: str) -> dict:
        response = client.get(
            "/api/values",
            params={
                "provider": "dwd",
                "network": "observation",
                "parameters": "daily/kl/temperature_air_mean_2m,daily/kl/precipitation_amount,"
                "daily/more_precip/snow_depth",
                "station": "00002,00001",
                **params,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    return get


def _station_runs(items: list[dict]) -> list[str]:
    """Name the station of each run of consecutive items, so a station split in two shows twice."""
    from itertools import groupby  # noqa: PLC0415

    return [station_id for station_id, _ in groupby(item["station_id"] for item in items)]


def test_values_long_order_is_the_one_the_description_states(stubbed_values: Callable[..., dict]) -> None:
    """Long items come grouped by station, then dataset and parameter, in timestamp order (GH-2295).

    The endpoint's docstring, which is also the MCP `values` tool description, tells a model a
    parameter's latest timestamp is the last item of its group. It used to say the array was sorted
    by timestamp, which a response with two parameters is not. Which station comes first is not
    stated, and not asserted either; the stub is daily only, so the resolution level goes unvaried.
    """
    values = stubbed_values()["values"]

    assert sorted(_station_runs(values)) == ["00001", "00002"]
    for station_id in ["00001", "00002"]:
        assert [
            (item["dataset"], item["parameter"], item["timestamp"][:10])
            for item in values
            if item["station_id"] == station_id
        ] == [
            (dataset, parameter, day)
            for dataset, parameter in [
                ("climate_summary", "precipitation_amount"),
                ("climate_summary", "temperature_air_mean_2m"),
                ("precipitation_more", "snow_depth"),
            ]
            for day in _DAYS
        ]


def test_values_wide_items_are_the_ones_the_description_states(stubbed_values: Callable[..., dict]) -> None:
    """A wide item is one timestamp with a key per parameter, named by its dataset here (GH-2295)."""
    wide = stubbed_values(shape="wide")["values"]

    # one item per timestamp of a station
    assert sorted((item["station_id"], item["timestamp"][:10]) for item in wide) == [
        (station_id, day) for station_id in ["00001", "00002"] for day in _DAYS
    ]
    # the request names two datasets, so every parameter key carries its dataset's name, and no
    # item has a `parameter` key
    parameters = [
        "climate_summary_precipitation_amount",
        "climate_summary_temperature_air_mean_2m",
        "precipitation_more_snow_depth",
    ]
    for item in wide:
        assert item.keys() == {
            "station_id",
            "resolution",
            "dataset",
            "timestamp",
            *parameters,
            *(f"{parameter}_quality" for parameter in parameters),
        }
        # both datasets are daily, so they share the row and no one dataset names it
        assert item["dataset"] is None


def test_values_geojson_items_are_the_ones_the_description_states(stubbed_values: Callable[..., dict]) -> None:
    """A GeoJSON feature holds one station's items of one dataset, in long order, without `station_id` (GH-2295)."""
    long = stubbed_values()["values"]
    features = stubbed_values(format="geojson")["data"]["features"]

    # one feature per station and dataset here, each item of the long array in exactly one of them
    assert len(features) == 4
    assert sum(len(feature["values"]) for feature in features) == len(long)
    for feature in features:
        station_id, dataset = feature["properties"]["id"], feature["properties"]["dataset"]
        assert feature["values"] == [
            {key: value for key, value in item.items() if key != "station_id"}
            for item in long
            if item["station_id"] == station_id and item["dataset"] == dataset
        ]


@pytest.mark.parametrize("endpoint", ["/api/stations", "/api/values"])
def test_swsmos_issue_reaches_the_request(client: TestClient, endpoint: str) -> None:
    """The issue asked of dwd/swsmos is read, so one that is no date is the caller's 400 (GH-2299).

    It was dropped on the way to the request, which then read the latest run whatever was asked.
    """
    response = client.get(
        endpoint,
        params={"provider": "dwd", "network": "swsmos", "parameters": "hourly/data", "station": "A006", "issue": "foo"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid isoformat string: 'foo'"


@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        pytest.param("/api/values", {**_OBSERVATION, "station": "01048"}, id="values"),
        pytest.param("/api/interpolate", {**_OBSERVATION, "station": "01048", "date": "2020-06-30"}, id="interpolate"),
        pytest.param("/api/summarize", {**_OBSERVATION, "station": "01048", "date": "2020-06-30"}, id="summarize"),
    ],
)
def test_a_unit_target_for_an_unknown_unit_is_a_400(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    endpoint: str,
    params: dict[str, str],
) -> None:
    """A unit the converter has none of for a known quantity is the caller's 400 (GH-2306).

    It passed the settings and was refused only once the stations had been fetched. Refused before
    anything is downloaded.
    """
    monkeypatch.delenv("WD_TS_UNIT_TARGETS", raising=False)
    response = client.get(endpoint, params={**params, "unit_targets": json.dumps({"temperature": "furlong"})})

    assert response.status_code == 400
    assert "Invalid unit targets: Unit furlong not supported for type temperature." in response.json()["detail"]


@pytest.mark.parametrize(
    "unit_targets",
    [
        pytest.param(None, id="none-given"),
        pytest.param({"temperature": "degree_fahrenheit"}, id="a-valid-one-given"),
        pytest.param({"bar": "baz"}, id="beside-a-refusal"),
    ],
)
def test_values_a_unit_target_the_server_environment_got_wrong_is_not_the_callers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    unit_targets: dict[str, str] | None,
) -> None:
    """A malformed `WD_TS_UNIT_TARGETS` is the server's 500, without its value, not the caller's 400 (GH-2312).

    pydantic-settings merges the dict the environment sets into the one the request gives, so it
    failed at `ts_unit_targets`, where a refusal of the caller's fails, and came back as their 400
    reading the server's value back.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    (tmp_path / ".env").write_text('WD_TS_UNIT_TARGETS={"foo": "bar"}\n')
    monkeypatch.chdir(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    params = {**_OBSERVATION, "station": "01048"}
    if unit_targets is not None:
        params["unit_targets"] = json.dumps(unit_targets)

    response = client.get("/api/values", params=params)

    # Starlette's own answer to an exception nothing handled, so the settings are what failed
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        pytest.param("/api/stripes/stations", {"kind": "temperature"}, id="stripes-stations"),
        pytest.param("/api/stripes/values", {"kind": "temperature", "station": "01048"}, id="stripes-values"),
        pytest.param("/api/stripes/image", {"kind": "temperature", "station": "01048"}, id="stripes-image"),
    ],
)
def test_stripes_a_setting_the_server_environment_got_wrong_is_not_the_callers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    endpoint: str,
    params: dict[str, str],
) -> None:
    """A malformed `WD_*` setting is the server's bare 500, without its value (GH-2312).

    The stripes build their provider request, and with it its settings, inside a catch-all, which
    answered the `ValidationError` with a 500 carrying the configured value.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    (tmp_path / ".env").write_text("WD_CACHE_DISABLE=not-a-bool\n")
    monkeypatch.chdir(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(endpoint, params=params)

    # Starlette's own answer to an exception nothing handled, so the settings are what failed
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


@pytest.fixture
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings.

    The cache directory the test session gives each worker is kept.
    """
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


_FETCH_OF_ENDPOINT = {
    "/api/values": "get_values",
    "/api/interpolate": "get_interpolate",
    "/api/summarize": "get_summarize",
}


def _settings_of(monkeypatch: pytest.MonkeyPatch, endpoint: str, params: dict[str, str]) -> Settings:
    """Answer a request up to its fetch, and return the settings it would fetch with."""
    taken: list[Settings] = []

    def take(*, settings: Settings, **_kwargs: object) -> None:
        taken.append(settings)
        raise RuntimeError

    monkeypatch.setattr(restapi, _FETCH_OF_ENDPOINT[endpoint], take)
    client = TestClient(restapi.app, raise_server_exceptions=False)
    response = client.get(endpoint, params=params)
    assert response.status_code == 500, response.text
    (settings,) = taken
    return settings


@pytest.mark.usefixtures("_no_ambient_settings")
def test_values_leaves_a_setting_the_request_does_not_give_to_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The server's WD_TS_* variables set what a request to `/api/values` leaves out (GH-2325).

    Every setting was passed from the request model, whose defaults FastAPI fills in, and an init
    argument outranks the environment. A field the request gives, at its default value too, still
    outranks the server's.
    """
    env = {
        "WD_TS_SHAPE": "wide",
        "WD_TS_HUMANIZE": "false",
        "WD_TS_CONVERT_UNITS": "false",
        "WD_TS_UNIT_TARGETS": '{"temperature": "degree_fahrenheit"}',
        "WD_TS_SKIP_EMPTY": "true",
        "WD_TS_SKIP_CRITERIA": "max",
        "WD_TS_SKIP_THRESHOLD": "0.5",
        "WD_TS_DROP_NULLS": "false",
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    params = {**_OBSERVATION, "station": "01048"}

    settings = _settings_of(monkeypatch, "/api/values", params)
    assert settings.ts_shape == "wide"
    assert settings.ts_humanize is False
    assert settings.ts_convert_units is False
    assert settings.ts_unit_targets == {"temperature": "degree_fahrenheit"}
    assert settings.ts_skip_empty is True
    assert settings.ts_skip_criteria == "max"
    assert settings.ts_skip_threshold == 0.5
    assert settings.ts_drop_nulls is False

    settings = _settings_of(
        monkeypatch,
        "/api/values",
        {
            **params,
            "shape": "long",
            "humanize": "true",
            "convert_units": "true",
            "skip_empty": "false",
            "skip_criteria": "min",
            "skip_threshold": "0.95",
            "drop_nulls": "true",
        },
    )
    assert settings.ts_shape == "long"
    assert settings.ts_humanize is True
    assert settings.ts_convert_units is True
    assert settings.ts_skip_empty is False
    assert settings.ts_skip_criteria == "min"
    assert settings.ts_skip_threshold == 0.95
    assert settings.ts_drop_nulls is True


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(("endpoint", "kind"), [("/api/interpolate", "interpolation"), ("/api/summarize", "summary")])
def test_geo_leaves_a_setting_the_request_does_not_give_to_the_server(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    kind: str,
) -> None:
    """The server's WD_TS_* variables set what a request to an estimating endpoint leaves out (GH-2325).

    A field the request gives, at its default value too, still outranks the server's.
    """
    env = {
        "WD_TS_HUMANIZE": "false",
        "WD_TS_CONVERT_UNITS": "false",
        "WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS": "60",
        "WD_TS_GEO_STATION_DISTANCE_HETEROGENEOUS": "15",
        "WD_TS_GEO_USE_NEARBY_STATION_DISTANCE": "0",
        "WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS": "0.5",
        "WD_TS_GEO_NUM_ADDITIONAL_STATIONS": "5",
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    params = {**_OBSERVATION, "station": "01048", "date": "2020-06-30"}

    settings = _settings_of(monkeypatch, endpoint, params)
    assert settings.ts_humanize is False
    assert settings.ts_convert_units is False
    assert settings.ts_geo_station_distance_homogeneous == 60
    assert settings.ts_geo_station_distance_heterogeneous == 15
    assert settings.ts_geo_use_nearby_station_distance == 0
    assert settings.ts_geo_min_gain_of_value_pairs == 0.5
    assert settings.ts_geo_num_additional_stations == 5

    settings = _settings_of(
        monkeypatch,
        endpoint,
        {
            **params,
            "humanize": "true",
            "convert_units": "true",
            f"{kind}_station_distance_homogeneous": "40",
            f"{kind}_station_distance_heterogeneous": "20",
            "use_nearby_station_distance": "1",
            "min_gain_of_value_pairs": "0.1",
            "num_additional_stations": "3",
        },
    )
    assert settings.ts_humanize is True
    assert settings.ts_convert_units is True
    assert settings.ts_geo_station_distance_homogeneous == 40
    assert settings.ts_geo_station_distance_heterogeneous == 20
    assert settings.ts_geo_use_nearby_station_distance == 1
    assert settings.ts_geo_min_gain_of_value_pairs == 0.1
    assert settings.ts_geo_num_additional_stations == 3


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("endpoint", "params", "detail"),
    [
        pytest.param(
            "/api/values",
            {"station": "01048", "unit_targets": '{"foo": "bar"}'},
            "Invalid value for 'unit_targets': Invalid unit targets: quantities not supported: foo. ",
            id="values-unit-targets",
        ),
        pytest.param(
            "/api/summarize",
            {"station": "01048", "date": "2020-06-30", "unit_targets": '{"foo": "bar"}'},
            "Invalid value for 'unit_targets': Invalid unit targets: quantities not supported: foo. ",
            id="summarize-unit-targets",
        ),
        pytest.param(
            "/api/interpolate",
            {
                "station": "01048",
                "date": "2020-06-30",
                "interpolation_station_distance": '{"temperature_air_mean": 10}',
            },
            "Invalid value for 'interpolation_station_distance': Invalid parameters in ts_geo_station_distance: "
            "['temperature_air_mean'] not in the canonical parameters (got {\"temperature_air_mean\": 10.0})",
            id="interpolate-station-distance",
        ),
    ],
)
def test_a_refused_setting_quotes_the_request_not_the_server(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    endpoint: str,
    params: dict[str, str],
    detail: str,
) -> None:
    """A refused dict field is told by its field with what the request gave, not the server's entries (GH-2329).

    pydantic-settings merges a dict the server's environment sets into the one the request gives,
    and the 400 was the whole `ValidationError`, quoting the merged dict.
    """
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", '{"temperature": "degree_fahrenheit"}')
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE__precipitation_amount", "25")

    response = client.get(endpoint, params={**_OBSERVATION, **params})

    assert response.status_code == 400
    refusal = response.json()["detail"]
    assert refusal.startswith(detail)
    for servers in ("degree_fahrenheit", "precipitation_amount", "25"):
        assert servers not in refusal
    assert "input_value" not in refusal
    assert "Value error, " not in refusal


def _start_lifespan(caplog: pytest.LogCaptureFixture) -> bool:
    """Start the app's lifespan as uvicorn does, shut it down again, and say whether it started."""
    import asyncio  # noqa: PLC0415

    from uvicorn.config import Config  # noqa: PLC0415
    from uvicorn.lifespan.on import LifespanOn  # noqa: PLC0415

    # uvicorn's default lifespan mode, which `wetterdienst restapi` runs with; no log config, so
    # that uvicorn's records reach caplog
    config = Config(restapi.app, lifespan="auto", log_config=None)
    config.load()
    lifespan = LifespanOn(config)

    async def run() -> bool:
        await lifespan.startup()
        started = not lifespan.should_exit
        if started:
            await lifespan.shutdown()
        return started

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        return asyncio.run(run())


@pytest.fixture
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    import os  # noqa: PLC0415

    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("_no_ambient_settings")
def test_restapi_refuses_to_start_with_a_malformed_setting(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A malformed `WD_*` setting stops the server before it serves, told by its variable (GH-2335).

    It used to stop the import with pydantic's traceback, as a side effect of building `Info`, and a
    `.env` that broke after that gave a bare 500 per request. The log now has the variable and what
    is wrong with it, without the value and without a traceback.
    """
    (tmp_path / ".env").write_text("WD_CACHE_DISABLE=secret-ish\n")

    assert not _start_lifespan(caplog)

    assert "WD_CACHE_DISABLE is invalid: Input should be a valid boolean" in caplog.text
    assert "Application startup failed. Exiting." in caplog.text
    assert "secret-ish" not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.usefixtures("_no_ambient_settings")
def test_restapi_starts_with_valid_settings(caplog: pytest.LogCaptureFixture) -> None:
    """Valid settings pass the startup check, on to the app's own lifespan (GH-2335)."""
    assert _start_lifespan(caplog)
    assert "Application startup complete." in caplog.text


def test_restapi_imports_with_a_malformed_setting(tmp_path: pathlib.Path) -> None:
    """The REST API's module imports with a malformed `WD_*` setting, for its startup to refuse (GH-2335).

    Its `Info` read the settings on import, so the import failed with pydantic's traceback first.
    """
    import os  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    result = subprocess.run(
        [sys.executable, "-c", "import wetterdienst.ui.restapi"],
        cwd=tmp_path,
        env={**os.environ, "WD_CACHE_DISABLE": "secret-ish"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.usefixtures("_no_ambient_settings")
def test_restapi_refuses_to_start_when_the_settings_fail_otherwise(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A settings build failing other than by a validation error is refused too (GH-2335).

    A validator's `TypeError` (GH-2353) escaped the check, and uvicorn, by default in lifespan mode
    `auto`, took it for a lifespan the app does not support, and served. It is told by its type,
    as its message is not pydantic's and may carry what the validator was given.
    """

    def fail() -> list[str]:
        msg = "secret-ish"
        raise TypeError(msg)

    monkeypatch.setattr(restapi, "check_settings", fail)

    assert not _start_lifespan(caplog)

    assert "the settings could not be built: TypeError" in caplog.text
    assert "secret-ish" not in caplog.text
    assert "Application startup failed. Exiting." in caplog.text


@pytest.mark.parametrize("threshold", [0, 5])
def test_values_refuses_a_skip_threshold_outside_zero_to_one(client: TestClient, threshold: float) -> None:
    """A skip_threshold outside (0, 1] is a 422, as the CLI option and the setting refuse it (GH-2334).

    0 used to be taken, and skipped nothing.
    """
    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "periods": "recent",
            "station": "01048",
            "skip_empty": "true",
            "skip_threshold": threshold,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "skip_threshold"]


def test_values_skip_threshold_bounds_are_in_the_schema_the_mcp_tools_take() -> None:
    """The MCP tools are generated from the OpenAPI schema, so the bounds reach them there (GH-2334)."""
    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    parameters = app.openapi()["paths"]["/api/values"]["get"]["parameters"]
    (schema,) = (parameter["schema"] for parameter in parameters if parameter["name"] == "skip_threshold")
    assert schema["exclusiveMinimum"] == 0
    assert schema["maximum"] == 1


def test_issues_dwd_swsmos(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test /api/issues lists the dwd/swsmos runs rather than refusing the network (GH-2319)."""
    from wetterdienst.provider.dwd.swsmos import api  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [f"{api._BASE_URL}/swsmos_20261004060000_opendata.csv.bz2"],  # noqa: SLF001
    )

    response = client.get("/api/issues", params={"provider": "dwd", "network": "swsmos", "station": "A006"})

    assert response.status_code == 200
    assert response.json() == {"issues": ["2026-10-04T06:00:00+00:00"]}


def test_values_dwd_swsmos_issue_not_held_is_the_callers(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test /api/values answers an swsmos issue DWD does not hold with a 400, not an empty 200 (GH-2324)."""
    import bz2  # noqa: PLC0415

    from wetterdienst.provider.dwd.swsmos import api  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    catalogue = bz2.compress(
        b"Kennung;Name;Streckentyp;Streckenbelag;Breite;Laenge;Hoehe;Flughafen;Inaktiv\n"
        b"A006;Station A006;A;B;54,889156;8,908735;2,0;;\n",
    )
    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [f"{api._BASE_URL}/swsmos_20261004060000_opendata.csv.bz2"],  # noqa: SLF001
    )
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: (
            File(url=kwargs["url"], content=io.BytesIO(catalogue), status=200)
            if kwargs["url"] == api._CATALOG_URL  # noqa: SLF001
            else File(url=kwargs["url"], content=FileNotFoundError(kwargs["url"]), status=404)
        ),
    )

    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "swsmos",
            "parameters": "hourly/data",
            "station": "A006",
            "issue": "2020-01-01T00:00",
        },
    )

    assert response.status_code == 400
    assert "swsmos_20200101000000_opendata.csv.bz2" in response.json()["detail"]


@pytest.mark.parametrize(("network", "station"), [("mosmix", "10147"), ("swsmos", "A006")])
@pytest.mark.parametrize(("option", "value"), [("dataset", "icon"), ("lead_time", "long")])
def test_issues_refuses_the_dmo_options_for_mosmix_and_swsmos(
    client: TestClient, network: str, station: str, option: str, value: str
) -> None:
    """/api/issues refuses a DMO-only option for MOSMIX and SWSMOS, as its description says (GH-2347)."""
    response = client.get(
        "/api/issues",
        params={"provider": "dwd", "network": network, "station": station, option: value},
    )
    assert response.status_code == 400
    assert response.json()["detail"].startswith(f"{option} applies to DWD DMO only")


def test_mcp_issues_tool_describes_the_dmo_options_as_refused() -> None:
    """The MCP issues tool says a DMO-only option is refused for MOSMIX and SWSMOS, and names its default (GH-2347).

    It said "ignored", copied from the data endpoints' lead time, which other networks do ignore, so
    a caller or a model that trusted it passed the option to MOSMIX and was refused.
    """
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415
    import inspect  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import DwdDmoRequest  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def _schemas() -> dict[str, dict]:
        async with Client(build_mcp_server(restapi.app)) as mcp_client:
            return {tool.name: tool.input_schema["properties"] for tool in await mcp_client.list_tools()}

    schemas = asyncio.run(_schemas())
    defaults = inspect.signature(DwdDmoRequest.available_issues).parameters
    for name in ("dataset", "lead_time"):
        description = schemas["issues"][name]["description"]
        assert description.endswith("; DMO only, refused for MOSMIX and SWSMOS."), name
        # an enum member for lead_time (SHORT = 78), named in a request by its lowercased name
        assert f", default '{getattr(defaults[name].default, 'name', defaults[name].default).lower()}';" in description
    # the data endpoints keep the shared description: there a lead time outside DMO is ignored
    assert schemas["values"]["lead_time"]["description"].endswith("; ignored for other networks.")
