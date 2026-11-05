# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The other languages of a `mul` alert are in every answer: REST, MCP and the command line (GH-3801).

The snapshot is a real `mul` message (`tests/provider/dwd/alerts/stubs.py`) served in place of the download, so the
request, the parser and the renderer are the ones a live answer goes through.
"""

from __future__ import annotations

import asyncio
import io
import json
from typing import TYPE_CHECKING

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.provider.dwd.alerts.stubs import CAP_MUL, CAP_MUL_LANGUAGES, serve_snapshot
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

_FURTHER = CAP_MUL_LANGUAGES[1:]


def _languages(translations: list[dict]) -> list[str]:
    return [translation["language"] for translation in translations]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Serve the `mul` message as the snapshot and give the client of the REST app."""
    serve_snapshot(monkeypatch, CAP_MUL)
    return TestClient(restapi.app)


def test_rest_json_has_the_translations_of_an_alert(client: TestClient) -> None:
    """`format=json` answers the first language in the fields of the alert and the seven others in `translations`."""
    response = client.get("/api/alerts", params={"language": "mul"})
    assert response.status_code == 200
    (alert,) = response.json()["alerts"]
    assert alert["language"] == "de-DE"
    assert alert["event"] == "NEBEL"
    assert _languages(alert["translations"]) == _FURTHER
    assert alert["translations"][0]["event"] == "fog"
    assert alert["translations"][4]["event"] == "Туман"
    # the same four texts and the language, in each
    assert {tuple(translation) for translation in alert["translations"]} == {
        ("language", "event", "headline", "description", "instruction")
    }


def test_rest_geojson_has_the_translations_in_the_properties_of_a_feature(client: TestClient) -> None:
    """`format=geojson` puts them in the `properties` of the feature, which keeps its polygon as `geometry`."""
    response = client.get("/api/alerts", params={"language": "mul", "format": "geojson"})
    assert response.status_code == 200
    (feature,) = response.json()["features"]
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert _languages(feature["properties"]["translations"]) == _FURTHER


def test_rest_csv_is_one_row_with_the_translations_as_json_text(client: TestClient) -> None:
    """`format=csv` is still a row for the alert, with its other languages as JSON text in one field."""
    response = client.get("/api/alerts", params={"language": "mul", "format": "csv"})
    assert response.status_code == 200
    frame = pl.read_csv(io.StringIO(response.text), infer_schema=False)
    assert frame.height == 1
    assert _languages(json.loads(frame["translations"][0])) == _FURTHER


def test_rest_answer_of_one_language_has_empty_translations(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `en` product has one block: `translations` is `[]` and nothing else is added."""
    from tests.provider.dwd.alerts.test_parser import CAP_XML  # noqa: PLC0415

    serve_snapshot(monkeypatch, CAP_XML)
    (alert,) = TestClient(restapi.app).get("/api/alerts", params={"language": "en"}).json()["alerts"]
    assert alert["translations"] == []


def test_the_language_parameter_says_what_mul_answers_with(client: TestClient) -> None:
    """The description of `language`, in the OpenAPI document and so in the MCP tool, no longer says it is not read."""
    schema = client.get("/openapi.json").json()
    parameters = schema["paths"]["/api/v1/alerts"]["get"]["parameters"]
    description = next(p for p in parameters if p["name"] == "language")["description"]
    assert "translations" in description
    assert "only the first is read" not in description


def test_mcp_alerts_tool_has_the_translations(client: TestClient) -> None:  # noqa: ARG001
    """The `alerts` tool answers what the route does, structured content included, so it is valid for its schema."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> object:
        async with Client(build_mcp_server(restapi.app)) as mcp:
            tool = next(tool for tool in await mcp.list_tools() if tool.name == "alerts")
            result = await mcp.call_tool("alerts", {"language": "mul"})
            return tool, result

    tool, result = asyncio.run(call())
    (alert,) = result.structured_content["result"]["alerts"]
    assert _languages(alert["translations"]) == _FURTHER
    assert "translations" in tool.input_schema["properties"]["language"]["description"]


def test_cli_prints_and_writes_the_translations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`wetterdienst alerts --language=mul` prints them, and `--target` writes them to a JSON, GeoJSON or CSV file."""
    serve_snapshot(monkeypatch, CAP_MUL)
    run = CliRunner().invoke(cli, ["alerts", "--language=mul"])
    assert run.exit_code == 0, run.output
    (alert,) = json.loads(run.output)["alerts"]
    assert _languages(alert["translations"]) == _FURTHER

    for name in ("alerts.json", "alerts.geojson", "alerts.csv"):
        run = CliRunner().invoke(cli, ["alerts", "--language=mul", f"--target={tmp_path / name}"])
        assert run.exit_code == 0, run.output
    assert _languages(
        json.loads((tmp_path / "alerts.json").read_text(encoding="utf-8"))["alerts"][0]["translations"]
    ) == (_FURTHER)
    feature = json.loads((tmp_path / "alerts.geojson").read_text(encoding="utf-8"))["features"][0]
    assert _languages(feature["properties"]["translations"]) == _FURTHER
    row = pl.read_csv(tmp_path / "alerts.csv", infer_schema=False)
    assert row.height == 1
    assert _languages(json.loads(row["translations"][0])) == _FURTHER
