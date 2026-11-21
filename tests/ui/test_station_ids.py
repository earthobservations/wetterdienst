# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The search for a WMO, WIGOS or ICAO id on the REST API, as an MCP tool and on the command line (GH-4075).

The station lists are rows of the test's own (`tests/core/station_search_stubs.py`), so the route, the tool and the
command go through the real core function, the real declarations and the real renderers, and the three surfaces are
held to answer alike. What the core does with the ids is `tests/core/test_station_search.py`'s.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.core.station_search_stubs import KEYED, serve, station
from wetterdienst import exceptions
from wetterdienst.core.station_search import COLUMNS
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    from fastmcp.tools import ToolResult

#: Hamburg as three providers list it: the code at DWD's forecasts only, the number at all of them
HAMBURG = {
    "dwd/observation": [station("01975", "Hamburg-Fuhlsbüttel", wmo_id="10147")],
    "dwd/mosmix": [station("10147", "HAMBURG-FU.", wmo_id="10147", icao_id="EDDH")],
    "noaa/ghcn": [station("GM000010147", "HAMBURG FUHLSBUETTEL", wmo_id="10147")],
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Give the client of the REST app, which answers an unhandled exception with its 500, over the stub lists."""
    serve(monkeypatch, HAMBURG)
    return TestClient(restapi.app, raise_server_exceptions=False)


# --- REST ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api/v1", "/api"])
def test_rest_a_wmo_number_is_the_rows_and_the_block_under_both_prefixes(client: TestClient, prefix: str) -> None:
    """The stations of every network that lists the number, and the block that says where they come from."""
    response = client.get(f"{prefix}/station-ids", params={"wmo_id": "10147"})

    assert response.status_code == 200, response.text
    data = response.json()
    assert list(data) == ["metadata", "stations"]
    assert [(row["provider"], row["network"], row["station_id"]) for row in data["stations"]] == [
        ("dwd", "mosmix", "10147"),
        ("dwd", "observation", "01975"),
        ("noaa", "ghcn", "GM000010147"),
    ]
    assert list(data["stations"][0]) == COLUMNS
    assert {row["matched_by"] for row in data["stations"]} == {"wmo_id"}
    assert {row["match"] for row in data["stations"]} == {"direct"}


def test_rest_the_block_has_the_licence_of_each_provider_in_the_answer_and_every_network_asked(
    client: TestClient,
) -> None:
    """No one `provider`: a list of them, those with a station in the answer, and `searched` of every network."""
    metadata = client.get("/api/station-ids", params={"icao_id": "eddh"}).json()["metadata"]

    assert "provider" not in metadata
    assert [provider["provider"] for provider in metadata["providers"]] == ["dwd", "noaa"]
    dwd = metadata["providers"][0]
    assert dwd["license"]["spdx_id"] == "CC-BY-4.0"
    assert dwd["attribution"] == "Source: Deutscher Wetterdienst"
    assert metadata["request"] == {
        "wmo_id": [],
        "wigos_id": [],
        "icao_id": ["EDDH"],
        "also_searched": {"wmo_id": ["10147"], "wigos_id": ["0-20000-0-10147"]},
    }
    assert metadata["counts"] == {"stations": 3, "providers": 2, "networks_searched": 18, "networks_answered": 18}
    assert len(metadata["searched"]) == 18
    assert metadata["searched"][0] == {
        "provider": "aemet",
        "network": "observation",
        "resolution": "daily",
        "dataset": "data",
        "ids": ["wmo_id"],
        "status": "searched",
        "stations_with_ids": 0,
        "message": None,
    }
    assert metadata["warnings"] == []
    assert "selected from the station list each provider publishes" in metadata["processing_note"]
    assert metadata["api_version"] == "1"


def test_rest_csv_is_the_table_with_the_block_in_the_headers(client: TestClient) -> None:
    """The rows alone, and the providers' licences and credit lines, the note and the count in the headers."""
    response = client.get("/api/station-ids", params={"wmo_id": "10147", "format": "csv"})

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert list(rows[0]) == COLUMNS
    assert [row["station_id"] for row in rows] == ["10147", "01975", "GM000010147"]
    assert response.headers["X-Wetterdienst-Stations"] == "3"
    providers = unquote(response.headers["X-Wetterdienst-Provider"])
    assert providers.startswith("German Weather Service, National Oceanic")
    assert "CC-BY-4.0" in unquote(response.headers["X-Wetterdienst-License"])
    assert "Source: Deutscher Wetterdienst" in unquote(response.headers["X-Wetterdienst-Attribution"])
    assert 'rel="license"' in response.headers["Link"]
    assert "Processed by wetterdienst" in unquote(response.headers["X-Wetterdienst-Processing"])
    assert "X-Wetterdienst-Warnings" not in response.headers


def test_rest_pretty_indents(client: TestClient) -> None:
    """`pretty` is the 4 spaces of every other route."""
    compact = client.get("/api/station-ids", params={"wmo_id": "10147"}).text
    pretty = client.get("/api/station-ids", params={"wmo_id": "10147", "pretty": "true"}).text

    assert "\n" not in compact
    assert pretty.startswith('{\n    "metadata"')


def test_rest_a_list_of_ids_is_comma_separated_and_read_in_the_notation_of_the_column(client: TestClient) -> None:
    """`1001` is `01001`, `eddh` is `EDDH`, and each kind of id may be given beside another."""
    response = client.get("/api/station-ids", params={"wmo_id": "10147,1001", "icao_id": "eddh,edxx"})

    assert response.status_code == 200
    assert response.json()["metadata"]["request"]["wmo_id"] == ["10147", "01001"]
    assert response.json()["metadata"]["request"]["icao_id"] == ["EDDH", "EDXX"]


def test_rest_an_empty_answer_is_a_200(client: TestClient) -> None:
    """No listed station has the number: no rows, and every network is told as asked."""
    response = client.get("/api/station-ids", params={"wmo_id": "99999"})

    assert response.status_code == 200
    assert response.json()["stations"] == []
    assert response.json()["metadata"]["counts"]["stations"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"format": "json"},
        {"wmo_id": "abc"},
        {"wmo_id": "123456"},
        {"wigos_id": "10381"},
        {"icao_id": "EDD"},
        {"wmo_id": "10147", "format": "geojson"},
        {"wmo_id": "10147", "bogus": "x"},
        {"wmo_id": "10147", "provider": "dwd"},
    ],
)
def test_rest_a_request_that_is_not_one_is_refused_before_anything_is_read(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, params: dict[str, Any]
) -> None:
    """No id, an id that is none, a format the route has not, a parameter of another route: a 422 and no read."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        msg = "a refused request reached the search"
        raise AssertionError(msg)

    monkeypatch.setattr(restapi, "find_stations_by_id", refuse)

    response = client.get("/api/station-ids", params=params)

    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith("application/problem+json")


def test_rest_a_request_with_no_id_names_the_three(client: TestClient) -> None:
    """The problem says which parameters to give."""
    response = client.get("/api/station-ids")

    assert "`wmo_id`, `wigos_id` and `icao_id`" in response.text


def test_rest_a_network_that_fails_is_a_warning_in_the_block_and_the_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """The route answers with the others' rows (a 200), and says which network is missing and why."""
    serve(
        monkeypatch, {**HAMBURG, "dmi/observation": exceptions.NoInternetError("https://opendataapi.dmi.dk/ is down")}
    )
    client = TestClient(restapi.app, raise_server_exceptions=False)

    response = client.get("/api/station-ids", params={"wmo_id": "10147"})

    assert response.status_code == 200
    assert len(response.json()["stations"]) == 3
    warnings = response.json()["metadata"]["warnings"]
    assert [w["code"] for w in warnings] == ["network-failed"]
    assert "dmi/observation" in warnings[0]["message"]
    assert response.headers["X-Wetterdienst-Warnings"] == "network-failed"
    dmi = next(n for n in response.json()["metadata"]["searched"] if n["provider"] == "dmi")
    assert (dmi["status"], dmi["stations_with_ids"]) == ("failed", None)
    assert response.json()["metadata"]["counts"]["networks_answered"] == 17


def test_rest_the_networks_that_need_a_key_are_named_and_no_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without credentials the three keyed networks are `not-configured`, and the answer is a 200."""
    serve(
        monkeypatch,
        {**HAMBURG, **{name: exceptions.CredentialMissingError(f"{name}: set WD_AUTH__X") for name in KEYED}},
    )
    client = TestClient(restapi.app, raise_server_exceptions=False)

    response = client.get("/api/station-ids", params={"wmo_id": "10147"})

    assert response.status_code == 200
    metadata = response.json()["metadata"]
    assert {w["code"] for w in metadata["warnings"]} == {"network-not-configured"}
    assert [n["network"] for n in metadata["searched"] if n["status"] == "not-configured"] == [
        name.split("/")[1] for name in KEYED
    ]
    assert metadata["counts"]["networks_answered"] == 15


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(exceptions.ProviderRateLimitError("https://x/", "rate limited", 7), 503, id="rate-limit"),
        pytest.param(exceptions.RequestError("a request that is none"), 400, id="request-error"),
        pytest.param(ValueError("a defect"), 500, id="plain-value-error"),
    ],
)
def test_rest_a_failure_of_the_search_is_answered_by_the_hierarchy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, error: BaseException, status: int
) -> None:
    """A 429 of a provider is the 503 with `Retry-After`, never a warning; the rest is the status of its place."""

    def raising(**_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(restapi, "find_stations_by_id", raising)

    response = client.get("/api/v1/station-ids", params={"wmo_id": "10147"})

    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    if status == 503:
        assert "Retry-After" in response.headers


def test_rest_the_route_is_described_in_the_openapi_document(client: TestClient) -> None:
    """The ids are optional parameters, and the description says what is found, how, and how long it takes."""
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/station-ids"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert operation["tags"] == ["Stations"]
    assert set(parameters) == {"wmo_id", "wigos_id", "icao_id", "format", "pretty"}
    assert not any(parameter["required"] for parameter in parameters.values())
    for text in ("0-20000-0-10381", "matched_by", "`match`", "about 9 s", "longer on a slow", "network-failed"):
        assert text in operation["description"]
    assert "/api/station-ids" not in schema["paths"]  # the alias is no part of the document


# --- the MCP tool ----------------------------------------------------------------------------------------------------


def _tool_call(arguments: dict[str, Any]) -> ToolResult:
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> ToolResult:
        async with Client(build_mcp_server(restapi.app)) as session:
            return await session.call_tool("station_ids", arguments, raise_on_error=False)

    return asyncio.run(call())


def test_the_mcp_tool_says_what_it_finds_and_what_it_costs() -> None:
    """The title and annotations, the three optional ids, and the cold latency in the description."""
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def read() -> Any:  # noqa: ANN401
        tools = await build_mcp_server(restapi.app).list_tools()
        return next(tool for tool in tools if tool.name == "station_ids")

    tool = asyncio.run(read())

    assert tool.title == "Find a station by WMO, WIGOS or ICAO id"
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.open_world_hint is True
    assert {"wmo_id", "wigos_id", "icao_id", "format", "pretty"} == set(tool.parameters["properties"])
    assert tool.parameters.get("required", []) == []
    assert "about 9 s" in tool.description
    assert "longer on a slow" in tool.description
    assert "Do not repeat it" in tool.description


def test_the_instructions_of_the_server_send_an_id_to_the_tool() -> None:
    """One line of the instructions says when to use `station_ids`."""
    from wetterdienst.ui.mcp import INSTRUCTIONS  # noqa: PLC0415

    line = next(line for line in INSTRUCTIONS.splitlines() if "`station_ids`" in line)
    assert "WMO, WIGOS or ICAO id" in line


def test_the_mcp_tool_answers_as_the_route_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rows and the block, as the route's JSON."""
    serve(monkeypatch, HAMBURG)

    result = _tool_call({"icao_id": "EDDH"})

    assert not result.is_error, result.content
    assert result.structured_content is not None
    data = result.structured_content.get("result", result.structured_content)
    assert [(row["station_id"], row["match"]) for row in data["stations"]] == [
        ("10147", "direct"),
        ("01975", "equivalent"),
        ("GM000010147", "equivalent"),
    ]
    assert data["metadata"]["providers"][0]["license"]["spdx_id"] == "CC-BY-4.0"


def test_the_mcp_tool_refuses_a_call_with_no_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal is the tool's error, with the reason."""
    serve(monkeypatch, HAMBURG)

    result = _tool_call({})

    assert result.is_error
    assert "wmo_id" in json.dumps([block.model_dump() for block in result.content])


# --- the command line ------------------------------------------------------------------------------------------------


def _invoke(*args: str) -> Any:  # noqa: ANN401
    return CliRunner().invoke(cli, ["station-ids", *args])


def test_cli_the_answer_is_the_one_of_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """The JSON the route answers: the block and the stations."""
    serve(monkeypatch, HAMBURG)

    result = _invoke("--icao-id=EDDH")

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert list(data) == ["metadata", "stations"]
    assert [row["station_id"] for row in data["stations"]] == ["10147", "01975", "GM000010147"]
    assert data["metadata"]["request"]["also_searched"]["wmo_id"] == ["10147"]
    assert data["metadata"]["providers"][1]["provider"] == "noaa"


def test_cli_csv_is_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rows alone."""
    serve(monkeypatch, HAMBURG)

    result = _invoke("--wmo-id=10147", "--format=csv")

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert result.exit_code == 0, result.output
    assert list(rows[0]) == COLUMNS
    assert [row["station_id"] for row in rows] == ["10147", "01975", "GM000010147"]


def test_cli_a_network_that_fails_is_a_warning_and_the_exit_code_is_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """Told on stderr and in the block, as every partial answer is."""
    serve(
        monkeypatch, {**HAMBURG, "dmi/observation": exceptions.NoInternetError("https://opendataapi.dmi.dk/ is down")}
    )

    result = _invoke("--wmo-id=10147")

    assert result.exit_code == 0, result.output
    assert [w["code"] for w in json.loads(result.stdout)["metadata"]["warnings"]] == ["network-failed"]


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--format=csv"],
        ["--wmo-id=abc"],
        ["--wigos-id=10381"],
        ["--icao-id=EDD"],
        ["--wmo-id=10147", "--format=geojson"],
    ],
)
def test_cli_a_request_that_is_not_one_is_a_usage_error(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    """No id, an id that is none, a format the command has not: exit 2, refused before any list is read."""
    asked = serve(monkeypatch, HAMBURG)

    result = _invoke(*args)

    assert result.exit_code == 2, result.output
    assert asked == []


def test_cli_a_rate_limit_is_an_error_and_no_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider's 429 is never a warning: exit 1 and nothing on stdout."""
    serve(monkeypatch, {**HAMBURG, "noaa/ghcn": exceptions.ProviderRateLimitError("https://x/", "rate limited", 7)})

    result = _invoke("--wmo-id=10147")

    assert result.exit_code == 1
    assert result.stdout == ""
