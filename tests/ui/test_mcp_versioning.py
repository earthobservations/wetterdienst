# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The MCP endpoint is versioned like the REST API: `/mcp/v1` pinned, `/mcp` the alias of the current version (GH-3074).

Offline: a client of the `fastmcp` package talks to the REST app over ASGI, through its lifespan, and
the one tool it calls reads a stubbed station list.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import polars as pl
import pytest
from fastapi.testclient import TestClient

from wetterdienst.ui import restapi
from wetterdienst.ui.restapi import API_PREFIX, MCP_ALIAS_PREFIX, MCP_PREFIX

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from fastapi import FastAPI

pytest.importorskip("fastmcp")

HEADERS = {"Accept": "application/json, text/event-stream"}
MCP_PATHS = [MCP_PREFIX, MCP_ALIAS_PREFIX]


@asynccontextmanager
async def _no_lifespan(_app: object) -> AsyncIterator[None]:
    yield


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    """Give the REST app an MCP endpoint mounted by this test.

    The one mounted at import closes its client to the REST app as an earlier test's lifespan ends,
    so each test mounts its own, and the routes and the lifespan are the app's again afterwards.
    """
    routes = [route for route in restapi.app.router.routes if not getattr(route, "path", "").startswith("/mcp")]
    monkeypatch.setattr(restapi.app.router, "routes", routes)
    monkeypatch.setattr(restapi.app.router, "lifespan_context", _no_lifespan)
    assert restapi._mount_mcp(restapi.app) is True  # noqa: SLF001
    return restapi.app


@pytest.fixture
def stations(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub the station list of DWD observation, so that no list is downloaded."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    ids = ["01048", "01975"]
    rows = [
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": station_id,
            "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
            "end_timestamp": dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
            "latitude": latitude,
            "longitude": longitude,
            "elevation": 100.0,
            "name": name,
            "region": region,
        }
        for station_id, latitude, longitude, name, region in (
            ("01048", 51.1278, 13.7543, "Dresden-Klotzsche", "Sachsen"),
            ("01975", 53.6332, 9.9881, "Hamburg", "Hamburg"),
        )
    ]
    frame = pl.LazyFrame(rows)
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: frame)
    return ids


def test_the_constants_follow_the_api_version() -> None:
    """The MCP paths carry the version of the REST contract they mirror, and the alias is the path without it."""
    assert MCP_PREFIX == "/mcp/v1"
    assert MCP_ALIAS_PREFIX == "/mcp"
    assert API_PREFIX == "/api/v1"


def test_both_paths_are_routes_of_the_one_endpoint(app: FastAPI) -> None:
    """The alias is a second route to the pinned route's endpoint, so that they share one session manager."""
    routes = {route.path: route for route in app.router.routes if getattr(route, "path", "").startswith("/mcp")}
    assert set(routes) == set(MCP_PATHS)
    assert routes[MCP_PREFIX].endpoint is routes[MCP_ALIAS_PREFIX].endpoint
    assert routes[MCP_PREFIX].methods == routes[MCP_ALIAS_PREFIX].methods


def _call(
    app: FastAPI,
    paths: list[str],
    tool: str,
    arguments: dict[str, object],
) -> dict[str, tuple[list[str], dict[str, object]]]:
    """List the tools at each path and call one, with a client of `fastmcp` over ASGI, in one run of the app's lifespan.

    One run, as the lifespan ends the client the tools send their requests with.
    """
    import httpx2  # noqa: PLC0415
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.client.transports import StreamableHttpTransport  # noqa: PLC0415

    def factory(**kwargs: object) -> httpx2.AsyncClient:
        kwargs.pop("transport", None)
        return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), **kwargs)

    async def run() -> dict[str, tuple[list[str], dict[str, object]]]:
        answers = {}
        async with app.router.lifespan_context(app):
            for path in paths:
                transport = StreamableHttpTransport(f"http://testserver{path}", httpx_client_factory=factory)
                async with Client(transport) as client:
                    names = sorted(tool_.name for tool_ in await client.list_tools())
                    result = await client.call_tool(tool, arguments)
                    # a tool whose answer is an object comes back wrapped as `{"result": ...}`
                    answers[path] = (names, result.structured_content["result"])
        return answers

    return asyncio.run(run())


@pytest.mark.parametrize("path", MCP_PATHS)
def test_a_client_lists_the_tools_and_calls_one_at_either_path(app: FastAPI, stations: list[str], path: str) -> None:
    """A real MCP client, at `/mcp/v1` and at `/mcp`: the handshake, the tool list and a tool call."""
    arguments = {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True}

    names, answer = _call(app, [path], "stations", arguments)[path]

    assert {"coverage", "stations", "values"} <= set(names)
    assert [station["station_id"] for station in answer["stations"]] == stations


@pytest.mark.usefixtures("stations")
def test_the_tool_surface_is_the_same_at_both_paths(app: FastAPI) -> None:
    """The tools, their arguments and the answer of one are alike at the pinned path and at the alias."""
    arguments = {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True}

    answers = _call(app, MCP_PATHS, "stations", arguments)
    pinned, alias = answers[MCP_PREFIX], answers[MCP_ALIAS_PREFIX]

    assert pinned[0] == alias[0]
    assert [station["station_id"] for station in pinned[1]["stations"]] == ["01048", "01975"]
    pinned[1]["metadata"].pop("retrieved_at")
    alias[1]["metadata"].pop("retrieved_at")
    assert pinned[1] == alias[1]


@pytest.mark.parametrize("path", MCP_PATHS)
def test_the_session_of_a_streamable_http_client_is_kept_at_either_path(app: FastAPI, path: str) -> None:
    """The first request opens a session whose id the next ones carry; the end of it is a DELETE, at the same path."""
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
    }
    with TestClient(app) as client:
        response = client.post(path, json=initialize, headers=HEADERS)
        assert response.status_code == 200
        session = {**HEADERS, "mcp-session-id": response.headers["mcp-session-id"]}
        client.post(path, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=session)
        listed = client.post(path, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=session)
        assert listed.status_code == 200
        assert "stations" in listed.text
        assert client.delete(path, headers=session).status_code == 200
        # the session is gone
        assert (
            client.post(path, json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, headers=session).status_code
            == 404
        )


def test_the_version_reports_where_the_endpoint_is() -> None:
    """`/api/version` and `/api/v1/version` say which path to configure and which one follows the current version."""
    with TestClient(restapi.app) as client:
        for prefix in ("/api", API_PREFIX):
            body = client.get(f"{prefix}/version").json()
            assert body["mcp_enabled"] is True
            assert body["mcp_path"] == "/mcp/v1"
            assert body["mcp_alias_path"] == "/mcp"


def test_the_version_reports_no_path_without_the_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """An instance without the `[mcp]` extra reports `null` for both paths, and `mcp_enabled` false."""
    monkeypatch.setattr(restapi, "mcp_enabled", False)
    body = TestClient(restapi.app).get("/api/v1/version").json()
    assert (body["mcp_enabled"], body["mcp_path"], body["mcp_alias_path"]) == (False, None, None)


def test_the_index_page_lists_the_pinned_path() -> None:
    """The index page names `/mcp/v1` as the endpoint, and `/mcp` as the alias that follows the current version."""
    text = TestClient(restapi.app).get("/").text
    assert "<code>/mcp/v1</code>" in text
    assert "<code>/mcp</code> follows the current version" in text


@pytest.mark.parametrize("path", MCP_PATHS)
@pytest.mark.parametrize("document", ["oauth-authorization-server", "oauth-protected-resource"])
def test_the_oauth_discovery_of_either_path_is_a_404(path: str, document: str) -> None:
    """A client that derives the discovery document from the endpoint's URL concludes "no auth" at either path."""
    client = TestClient(restapi.app)
    assert client.get(f"/.well-known/{document}{path}").status_code == 404
    assert client.get(f"/.well-known/{document}").status_code == 404


def test_the_mcp_paths_are_no_rest_routes() -> None:
    """The OpenAPI document lists no MCP path, so the endpoint is no tool of itself."""
    assert not [path for path in restapi.app.openapi()["paths"] if path.startswith(("/mcp", "/.well-known"))]
