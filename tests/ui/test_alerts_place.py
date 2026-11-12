# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The place of the alerts is asked for the same way in REST, MCP and on the command line (GH-4019).

A snapshot is every warning of Germany, over 100 KB, and more than an assistant can read. A place (a point, or a name or
warn cell id) keeps the warnings for it. The snapshot is a few real messages of DWD
(`tests/provider/dwd/alerts/stubs.py`) served in place of the download, so the request, the parser and the renderers
are the ones a live answer goes through.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.provider.dwd.alerts.stubs import (
    CAP_COMMUNITY_KIEL,
    CAP_COMMUNITY_NORDERNEY,
    CAP_COMMUNITY_SEA,
    serve_snapshot,
)
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

KIEL = {"latitude": 54.3233, "longitude": 10.1228}
MUNICH = {"latitude": 48.1351, "longitude": 11.5820}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Serve three warnings as the snapshot (Kiel's, Norderney's, a sea area's) and give the client of the REST app."""
    serve_snapshot(monkeypatch, CAP_COMMUNITY_KIEL, CAP_COMMUNITY_NORDERNEY, CAP_COMMUNITY_SEA)
    return TestClient(restapi.app)


def _names(response_json: dict) -> list[list[str]]:
    return [alert["area_names"] for alert in response_json["alerts"]]


def test_rest_without_a_place_is_every_warning(client: TestClient) -> None:
    """Nothing is filtered for a request that names no place, and nothing is told."""
    data = client.get("/api/alerts").json()
    assert len(data["alerts"]) == 3
    assert data["metadata"]["warnings"] == []


def test_rest_a_point_answers_the_warnings_that_contain_it(client: TestClient) -> None:
    """The point of Kiel is in the one warning that has Kiel's polygon."""
    response = client.get("/api/alerts", params=KIEL)
    assert response.status_code == 200
    data = response.json()
    (names,) = _names(data)
    assert "Stadt Kiel" in names
    assert data["metadata"]["counts"]["rows"] == 1
    assert data["metadata"]["warnings"] == []


def test_rest_a_name_answers_the_warnings_for_that_area(client: TestClient) -> None:
    """A name is matched as words of an area's name, in any case."""
    data = client.get("/api/alerts", params={"name": "norderney"}).json()
    (names,) = _names(data)
    assert "Stadt Norderney" in names


def test_rest_a_warn_cell_answers_the_warnings_for_that_area(client: TestClient) -> None:
    """A warn cell id is a name of digits."""
    data = client.get("/api/alerts", params={"name": "801002000"}).json()
    (names,) = _names(data)
    assert "Stadt Kiel" in names


def test_rest_a_warning_for_the_sea_is_found_by_its_name_and_not_by_a_point(client: TestClient) -> None:
    """The sea warning has no polygon: the name finds it, a point in its waters does not."""
    assert _names(client.get("/api/alerts", params={"name": "Ostfriesische Küste"}).json()) == [["Ostfriesische Küste"]]
    assert client.get("/api/alerts", params={"latitude": 53.9, "longitude": 7.0}).json()["alerts"] == []


def test_rest_a_place_without_a_warning_is_a_200_with_the_reason(client: TestClient) -> None:
    """Munich has no warning: an answer with no alerts, the `no-alerts-for-place` warning and a count of 0."""
    response = client.get("/api/alerts", params=MUNICH)
    assert response.status_code == 200
    data = response.json()
    assert data["alerts"] == []
    assert data["metadata"]["counts"]["rows"] == 0
    (warning,) = data["metadata"]["warnings"]
    assert warning["code"] == "no-alerts-for-place"
    assert "not an error" in warning["message"]
    assert "3 are for other places" in warning["message"]


@pytest.mark.parametrize(("fmt", "key"), [("json", "alerts"), ("geojson", "features")])
def test_rest_the_empty_answer_of_a_place_is_empty_in_each_json_format(client: TestClient, fmt: str, key: str) -> None:
    """JSON and GeoJSON have the reason in their `metadata` block."""
    data = client.get("/api/alerts", params={**MUNICH, "format": fmt}).json()
    assert data[key] == []
    assert [w["code"] for w in data["metadata"]["warnings"]] == ["no-alerts-for-place"]


def test_rest_the_empty_answer_of_a_place_in_csv_has_the_reason_in_a_header(client: TestClient) -> None:
    """CSV has no block: the header row alone is the body, and `X-Wetterdienst-Warnings` says why."""
    response = client.get("/api/alerts", params={**MUNICH, "format": "csv"})
    assert response.status_code == 200
    assert response.text.count("\n") == 1
    assert response.headers["x-wetterdienst-warnings"] == "no-alerts-for-place"
    assert response.headers["x-wetterdienst-rows"] == "0"


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
def test_rest_a_place_is_smaller_than_the_snapshot(client: TestClient, fmt: str) -> None:
    """What the filter is for: the warnings of one place are fewer than those of the snapshot."""
    everything = len(client.get("/api/alerts", params={"format": fmt}).text)
    kiel = len(client.get("/api/alerts", params={**KIEL, "format": fmt}).text)
    norderney = len(client.get("/api/alerts", params={"name": "Norderney", "format": fmt}).text)
    munich = len(client.get("/api/alerts", params={**MUNICH, "format": fmt}).text)
    assert munich < norderney < everything
    assert munich < kiel < everything


def test_rest_half_a_point_is_a_422_naming_the_missing_one(client: TestClient) -> None:
    """The REST API refuses a latitude without a longitude as it refuses the other rules over fields."""
    response = client.get("/api/alerts", params={"latitude": 54.3})
    assert response.status_code == 422
    assert response.json()["detail"] == "longitude: Field required with latitude"
    response = client.get("/api/alerts", params={"longitude": 10.1})
    assert response.status_code == 422
    assert response.json()["detail"] == "latitude: Field required with longitude"


@pytest.mark.parametrize(
    "params", [{"latitude": 91, "longitude": 10}, {"latitude": 54, "longitude": 181}, {"latitude": "x", "longitude": 1}]
)
def test_rest_a_point_off_the_earth_is_a_422(client: TestClient, params: dict) -> None:
    """The coordinates are bounded as those of `stations` are."""
    assert client.get("/api/alerts", params=params).status_code == 422


def test_rest_a_coordinate_of_zero_is_given(client: TestClient) -> None:
    """The equator is a latitude: `latitude=0` is a point and not a request without one."""
    response = client.get("/api/alerts", params={"latitude": 0, "longitude": 0})
    assert response.status_code == 200
    assert [w["code"] for w in response.json()["metadata"]["warnings"]] == ["no-alerts-for-place"]


def test_the_place_parameters_are_in_the_contract(client: TestClient) -> None:
    """The OpenAPI document, and so every MCP tool generated from it, has them, and they are optional."""
    schema = client.get("/openapi.json").json()
    parameters = {p["name"]: p for p in schema["paths"]["/api/v1/alerts"]["get"]["parameters"]}
    for name in ("latitude", "longitude", "name"):
        assert parameters[name]["required"] is False
    operation = schema["paths"]["/api/v1/alerts"]["get"]
    assert "latitude" in operation["description"]
    assert "no-alerts-for-place" in operation["description"]


def test_the_mcp_tool_takes_the_place() -> None:
    """`alerts` of the MCP server has the three parameters in its schema and says to pass them."""
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def read() -> object:
        tools = await build_mcp_server(restapi.app).list_tools()
        return next(tool for tool in tools if tool.name == "alerts")

    tool = asyncio.run(read())
    assert {"latitude", "longitude", "name"} <= set(tool.parameters["properties"])  # ty: ignore[unresolved-attribute]
    assert "pass" in tool.description  # ty: ignore[unresolved-attribute]


def test_cli_a_point(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--latitude` and `--longitude` keep the warnings that contain the point."""
    serve_snapshot(monkeypatch, CAP_COMMUNITY_KIEL, CAP_COMMUNITY_NORDERNEY, CAP_COMMUNITY_SEA)
    result = CliRunner().invoke(cli, ["alerts", "--latitude=54.3233", "--longitude=10.1228"])
    assert result.exit_code == 0, result.output
    (alert,) = json.loads(result.output)["alerts"]
    assert "Stadt Kiel" in alert["area_names"]


def test_cli_a_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--name` keeps the warnings with an area of that name."""
    serve_snapshot(monkeypatch, CAP_COMMUNITY_KIEL, CAP_COMMUNITY_NORDERNEY, CAP_COMMUNITY_SEA)
    result = CliRunner().invoke(cli, ["alerts", "--name=Norderney", "--format=csv"])
    assert result.exit_code == 0, result.output
    assert "Stadt Norderney" in result.output
    assert "Stadt Kiel" not in result.output


def test_cli_a_place_without_a_warning_says_so_in_its_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """The answer for Munich is an empty list and the warning that says why, exit 0."""
    serve_snapshot(monkeypatch, CAP_COMMUNITY_KIEL)
    result = CliRunner().invoke(cli, ["alerts", "--latitude=48.1351", "--longitude=11.582"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["alerts"] == []
    assert [w["code"] for w in data["metadata"]["warnings"]] == ["no-alerts-for-place"]


def test_cli_half_a_point_is_a_usage_error() -> None:
    """A latitude without a longitude is the command line's to fix: exit 2, naming both."""
    result = CliRunner().invoke(cli, ["alerts", "--latitude=54.3"])
    assert result.exit_code == 2
    assert "--latitude and --longitude" in result.output


def test_cli_a_point_off_the_earth_is_a_usage_error() -> None:
    """The latitude is bounded by click, as it is by the REST API."""
    result = CliRunner().invoke(cli, ["alerts", "--latitude=91", "--longitude=10"])
    assert result.exit_code == 2


@pytest.mark.parametrize("point", [["--latitude=nan", "--longitude=10"], ["--latitude=54", "--longitude=nan"]])
def test_cli_a_coordinate_that_is_not_a_number_is_blamed_on_the_point_and_not_the_timestamp(point: list[str]) -> None:
    """Click lets NaN through its range; it is no place on Earth, and the error names the point's options."""
    result = CliRunner().invoke(cli, ["alerts", *point])
    assert result.exit_code == 2
    assert "--latitude/--longitude" in result.output
    assert "--timestamp" not in result.output


def test_cli_help_names_the_place_options() -> None:
    """`alerts --help` lists them with an example."""
    output = CliRunner().invoke(cli, ["alerts", "--help"]).output
    for option in ("--latitude", "--longitude", "--name"):
        assert option in output


@pytest.mark.parametrize("params", [{}, KIEL, {"name": "Kiel"}, MUNICH])
def test_rest_the_date_of_the_data_is_that_of_the_whole_snapshot(client: TestClient, params: dict) -> None:
    """With a match, with none and without a place, `data_updated_at` is the newest `sent` of the snapshot (08:44)."""
    data = client.get("/api/alerts", params=params).json()
    assert data["metadata"]["data_updated_at"] == "2026-11-12T08:44:00.000000+00:00"
    csv = client.get("/api/alerts", params={**params, "format": "csv"})
    assert csv.headers["x-wetterdienst-data-updated-at"] == "2026-11-12T08:44:00.000000+00:00"


def _message(response_json: dict) -> str:
    (warning,) = response_json["metadata"]["warnings"]
    assert warning["code"] == "no-alerts-for-place"
    return warning["message"]


def test_rest_a_point_and_a_name_of_two_warnings_are_counted_each(client: TestClient) -> None:
    """The point of Kiel is in one warning and Norderney is in another: none has both, and the message counts each."""
    response = client.get("/api/alerts", params={**KIEL, "name": "Norderney"})
    assert response.status_code == 200
    data = response.json()
    assert data["alerts"] == []
    assert "1 warning contains the point and 1 warning lists the name, but none does both" in _message(data)


def test_rest_a_point_at_sea_is_told_of_the_warnings_without_a_polygon(client: TestClient) -> None:
    """53.9 N 7.0 E is in the North Sea, where the community product has a warning with no polygon."""
    data = client.get("/api/alerts", params={"latitude": 53.9, "longitude": 7.0}).json()
    assert data["alerts"] == []
    message = _message(data)
    assert "have no polygon (the sea)" in message
    assert "ask for them by name, or with granularity=district" in message


def test_rest_a_name_at_sea_finds_what_a_point_does_not(client: TestClient) -> None:
    """The name of the sea area is found, so no warning is told."""
    data = client.get("/api/alerts", params={"name": "Ostfriesische Küste"}).json()
    assert len(data["alerts"]) == 1
    assert data["metadata"]["warnings"] == []


@pytest.mark.parametrize("params", [MUNICH, {"name": "Munich"}, {**MUNICH, "name": "Munich"}])
def test_rest_a_place_in_an_empty_snapshot_is_a_true_all_clear(monkeypatch: pytest.MonkeyPatch, params: dict) -> None:
    """No warning is in force anywhere: told so, for a point, a name and both, and the header of a CSV has the code."""
    serve_snapshot(monkeypatch)
    api = TestClient(restapi.app)
    data = api.get("/api/alerts", params=params).json()
    assert _message(data).startswith("No warning is in force anywhere (the snapshot holds none)")
    assert "spelling" not in _message(data)
    csv = api.get("/api/alerts", params={**params, "format": "csv"})
    assert csv.headers["x-wetterdienst-warnings"] == "no-alerts-for-place"
