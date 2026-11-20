# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The KOSTRA-DWD-2020 statistics of `dwd/kostra` on the REST API, as an MCP tool and on the command line (GH-4072).

The tables are the real rows of DWD (`tests/provider/dwd/kostra/stubs.py`) served in place of the download, so the
request, the reader and the renderers are the ones a live answer goes through, and the three surfaces are held to
answer alike.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.provider.dwd.kostra.stubs import BERLIN, MUNICH, NORTH_SEA, serve
from wetterdienst import exceptions
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    from fastmcp.tools import ToolResult

#: the 60 minute rain of Berlin once in 100 years, as DWD's table has it
BERLIN_60_100 = {"depth_mm": 48.9, "intensity_l_s_ha": 135.8, "uncertainty_percent": 25.0}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Give the client of the REST app, which answers an unhandled exception with its 500, over the stub tables."""
    serve(monkeypatch)
    return TestClient(restapi.app, raise_server_exceptions=False)


def _point(point: tuple[float, float] = BERLIN, **more: Any) -> dict[str, Any]:  # noqa: ANN401
    return {"latitude": point[0], "longitude": point[1], **more}


# --- REST ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api/v1", "/api"])
def test_rest_a_duration_and_a_return_period_is_one_value_under_both_prefixes(client: TestClient, prefix: str) -> None:
    """The value of DWD's table for the cell, the cell and the edition, and the block with the licence."""
    response = client.get(f"{prefix}/kostra", params=_point(duration=60, return_period=100))

    assert response.status_code == 200
    data = response.json()
    assert list(data) == ["metadata", "edition", "cell", "values"]
    assert data["edition"] == "KOSTRA-DWD-2020"
    assert data["cell"] == {
        "index_rc": "105190",
        "row": 105,
        "column": 190,
        "latitude": 52.512909,
        "longitude": 13.411289,
    }
    assert data["values"] == [{"duration_minutes": 60, "return_period_years": 100, **BERLIN_60_100}]


def test_rest_the_block_names_the_licence_the_date_of_the_data_and_what_the_values_are(client: TestClient) -> None:
    """CC BY 4.0 and DWD's credit line, when DWD wrote the files, and that these are statistics of a cell."""
    metadata = client.get("/api/kostra", params=_point(duration=60)).json()["metadata"]

    assert metadata["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert metadata["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert metadata["provider"]["copyright"] == "© Deutscher Wetterdienst (DWD), KOSTRA-DWD-2020"
    assert metadata["data_updated_at"] == "2022-12-12T17:12:06.000000+00:00"
    assert "statistics of the 5 km grid cell" in metadata["processing_note"]
    assert metadata["counts"] == {"stations": 0, "rows": 9}
    assert metadata["request"] == {
        "provider": "dwd",
        "network": "kostra",
        "parameters": [],
        "periods": [],
        "start": None,
        "end": None,
        "stations": None,
    }
    assert metadata["warnings"] == []


def test_rest_without_a_duration_is_the_whole_table(client: TestClient) -> None:
    """22 durations and 9 return periods: 198 rows, the cell once."""
    data = client.get("/api/kostra", params=_point(MUNICH)).json()

    assert len(data["values"]) == 198
    assert data["cell"]["index_rc"] == "203167"
    assert data["metadata"]["counts"]["rows"] == 198


def test_rest_csv_is_the_table_with_the_block_in_the_headers(client: TestClient) -> None:
    """The rows alone: the licence and the credit line, the date and the note are in the headers."""
    response = client.get("/api/kostra", params=_point(duration=60, format="csv"))

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert [row["return_period_years"] for row in rows] == ["1", "2", "3", "5", "10", "20", "30", "50", "100"]
    assert rows[-1]["depth_mm"] == "48.9"
    assert response.headers["x-wetterdienst-license"] == "CC-BY-4.0"
    assert "Deutscher" in response.headers["x-wetterdienst-attribution"]
    assert "statistics" in response.headers["x-wetterdienst-processing"]
    assert response.headers["x-wetterdienst-rows"] == "9"
    assert response.headers["x-wetterdienst-data-updated-at"] == "2022-12-12T17:12:06.000000+00:00"


def test_rest_pretty_indents(client: TestClient) -> None:
    """Four spaces, as the other routes."""
    assert "\n    " in client.get("/api/kostra", params=_point(duration=60, pretty="true")).text
    assert "\n" not in client.get("/api/kostra", params=_point(duration=60)).text.rstrip("\n")


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"latitude": 52.5},
        {"longitude": 13.4},
        {"latitude": 91, "longitude": 13.4},
        {"latitude": 52.5, "longitude": 181},
        {"latitude": 52.5, "longitude": 13.4, "duration": 61},
        {"latitude": 52.5, "longitude": 13.4, "duration": 0},
        {"latitude": 52.5, "longitude": 13.4, "return_period": 4},
        {"latitude": 52.5, "longitude": 13.4, "format": "geojson"},
        {"latitude": 52.5, "longitude": 13.4, "bogus": "x"},
    ],
)
def test_rest_a_request_that_is_not_one_is_refused_before_anything_is_read(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, params: dict[str, Any]
) -> None:
    """No point, half a point, a point off the globe, a duration or return period DWD has none of, a bad format."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        msg = "a refused request reached the request"
        raise AssertionError(msg)

    monkeypatch.setattr("wetterdienst.provider.dwd.kostra.DwdKostraRequest", refuse)

    assert client.get("/api/kostra", params=params).status_code == 422


def test_rest_a_duration_the_table_has_none_of_names_the_ones_it_has(client: TestClient) -> None:
    """The problem says which durations there are."""
    response = client.get("/api/kostra", params=_point(duration=61))

    assert "5, 10, 15, 20, 30, 45, 60" in response.text


@pytest.mark.parametrize("point", [(40.0, 0.0), (60.0, 10.0), NORTH_SEA])
def test_rest_a_point_outside_the_area_of_the_values_is_a_400_and_no_empty_table(
    client: TestClient, point: tuple[float, float]
) -> None:
    """Off the grid, or in a cell DWD writes its missing values for (the North Sea): the caller's to move."""
    response = client.get("/api/kostra", params=_point(point, duration=60))

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "KOSTRA-DWD-2020" in response.json()["detail"]
    assert "values" not in response.json()


def test_rest_the_route_is_described_in_the_openapi_document(client: TestClient) -> None:
    """The point is required, the rest is not, and the description says to pass a duration."""
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/kostra"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert operation["tags"] == ["Heavy rainfall"]
    assert parameters["latitude"]["required"] is True
    assert parameters["longitude"]["required"] is True
    for name in ("duration", "return_period", "format", "pretty"):
        assert parameters[name]["required"] is False
    for text in ("``duration``", "depth_mm", "intensity_l_s_ha", "uncertainty_percent", "not measurements"):
        assert text in operation["description"]
    assert "/api/kostra" not in schema["paths"]  # the alias is no part of the document


class _Raising:
    """Stand in for the request, raising `error` where the tables are read."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def __call__(self, **_kwargs: object) -> _Raising:
        return self

    def query(self) -> None:
        raise self.error


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(exceptions.LocationOutOfRangeError("no values"), 400, id="no-values"),
        pytest.param(exceptions.MetaFileFormatError("not a table"), 502, id="format"),
        pytest.param(exceptions.DownloadError("https://opendata.dwd.de/x.zip", "404"), 502, id="download"),
        pytest.param(exceptions.NoInternetError("No internet"), 503, id="no-internet"),
        pytest.param(exceptions.ProviderRateLimitError("https://x/", "rate limited", 7), 503, id="rate-limit"),
        pytest.param(ValueError("a defect"), 500, id="plain-value-error"),
    ],
)
def test_rest_a_failure_is_answered_by_the_hierarchy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, error: BaseException, status: int
) -> None:
    """Every failure is a problem of the status of its place in the hierarchy."""
    monkeypatch.setattr("wetterdienst.provider.dwd.kostra.DwdKostraRequest", _Raising(error))

    response = client.get("/api/v1/kostra", params=_point(duration=60))

    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")


# --- the MCP tool ----------------------------------------------------------------------------------------------------


def _tool_call(arguments: dict[str, Any]) -> ToolResult:
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> ToolResult:
        async with Client(build_mcp_server(restapi.app)) as session:
            return await session.call_tool("kostra", arguments, raise_on_error=False)

    return asyncio.run(call())


def test_the_mcp_tool_takes_the_point_and_says_to_pass_a_duration() -> None:
    """The schema of `kostra` requires the point, and the description asks for the one duration."""
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def read() -> Any:  # noqa: ANN401
        tools = await build_mcp_server(restapi.app).list_tools()
        return next(tool for tool in tools if tool.name == "kostra")

    tool = asyncio.run(read())

    assert set(tool.parameters["required"]) == {"latitude", "longitude"}
    assert {"duration", "return_period", "format", "pretty"} <= set(tool.parameters["properties"])
    assert tool.title == "Get heavy-rainfall statistics for a point"
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.open_world_hint is True
    assert "``duration``" in tool.description


def test_the_mcp_tool_answers_as_the_route_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """The value of a point, the cell, and the block with the licence."""
    serve(monkeypatch)

    result = _tool_call({**_point(), "duration": 60, "return_period": 100})

    assert not result.is_error, result.content
    assert result.structured_content is not None
    data = result.structured_content["result"]
    assert data["values"] == [{"duration_minutes": 60, "return_period_years": 100, **BERLIN_60_100}]
    assert data["cell"]["index_rc"] == "105190"
    assert data["metadata"]["provider"]["license"]["spdx_id"] == "CC-BY-4.0"


def test_the_mcp_tool_refuses_a_point_outside_the_area(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal is the tool's error, with the reason."""
    serve(monkeypatch)

    result = _tool_call({**_point(NORTH_SEA), "duration": 60})

    assert result.is_error
    assert "KOSTRA-DWD-2020" in json.dumps([block.model_dump() for block in result.content])


# --- the command line ------------------------------------------------------------------------------------------------


def _invoke(*args: str) -> Any:  # noqa: ANN401
    return CliRunner().invoke(cli, ["kostra", *args])


def test_cli_a_value_is_the_answer_of_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """The JSON the route answers: the block, the edition, the cell and the value."""
    serve(monkeypatch)

    result = _invoke("--latitude=52.52", "--longitude=13.40", "--duration=60", "--return-period=100")

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["values"] == [{"duration_minutes": 60, "return_period_years": 100, **BERLIN_60_100}]
    assert data["cell"]["index_rc"] == "105190"
    assert data["metadata"]["provider"]["license"]["spdx_id"] == "CC-BY-4.0"


def test_cli_csv_is_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rows alone."""
    serve(monkeypatch)

    result = _invoke("--latitude=52.52", "--longitude=13.40", "--duration=60", "--format=csv")

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert result.exit_code == 0, result.output
    assert len(rows) == 9
    assert rows[-1]["depth_mm"] == "48.9"


def test_cli_a_point_outside_the_area_is_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit 2 and the reason, as a refusal of any command is, and nothing on stdout."""
    serve(monkeypatch)

    result = _invoke(f"--latitude={NORTH_SEA[0]}", f"--longitude={NORTH_SEA[1]}", "--duration=60")

    assert result.exit_code == 2
    assert "no KOSTRA-DWD-2020 values" in result.output
    assert result.stdout == ""


@pytest.mark.parametrize(
    "args",
    [
        ["--latitude=52.52"],
        ["--longitude=13.4"],
        ["--latitude=52.52", "--longitude=13.4", "--duration=61"],
        ["--latitude=52.52", "--longitude=13.4", "--return-period=4"],
        ["--latitude=95", "--longitude=13.4"],
        ["--latitude=52.52", "--longitude=13.4", "--format=geojson"],
    ],
)
def test_cli_a_request_that_is_not_one_is_a_usage_error(args: list[str]) -> None:
    """A missing coordinate, a duration or return period DWD has none of, or a format: refused before the lookup."""
    result = _invoke(*args)

    assert result.exit_code == 2
