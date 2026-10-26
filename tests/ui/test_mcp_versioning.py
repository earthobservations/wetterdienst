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


def _call_result(app: FastAPI, tool: str, arguments: dict[str, object]) -> object:
    """Call one tool through a real FastMCP client, preserving content and structured output for assertions."""
    import httpx2  # noqa: PLC0415
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.client.transports import StreamableHttpTransport  # noqa: PLC0415

    def factory(**kwargs: object) -> httpx2.AsyncClient:
        kwargs.pop("transport", None)
        return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), **kwargs)

    async def run() -> object:
        async with app.router.lifespan_context(app):
            transport = StreamableHttpTransport(f"http://testserver{MCP_PREFIX}", httpx_client_factory=factory)
            async with Client(transport) as client:
                return await client.call_tool(tool, arguments, raise_on_error=False)

    return asyncio.run(run())


@pytest.mark.parametrize(
    ("fmt", "body"),
    [
        ("csv", "station_id,value\n01048,1\n"),
        ("ndjson", '{"station_id":"01048","value":1}\n'),
        ("html", "<html>chart</html>"),
        ("svg", "<svg></svg>"),
        ("png", b"\x89PNG\r\n\x1a\n"),
        ("jpg", b"\xff\xd8\xff"),
        ("webp", b"RIFF\x00\x00\x00\x00WEBP"),
        ("pdf", b"%PDF-1.7"),
    ],
)
def test_values_formats_return_content_and_schema_valid_output(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, fmt: str, body: str | bytes
) -> None:
    """Non-JSON data and chart formats stay readable and satisfy their declared structured output schema."""
    import base64  # noqa: PLC0415

    monkeypatch.setattr(restapi, "_values", lambda **_kwargs: object())
    monkeypatch.setattr(restapi, "response_metadata", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(restapi, "response_headers", lambda _metadata: {})
    monkeypatch.setattr(restapi, "render", lambda *_args, **_kwargs: body)
    arguments = {
        "provider": "dwd",
        "network": "observation",
        "parameters": "daily/kl",
        "stations": "01048",
        "format": fmt,
    }

    result = _call_result(app, "values", arguments)

    assert not result.is_error  # type: ignore[attr-defined]
    if fmt in {"csv", "ndjson", "html", "svg"}:
        assert result.structured_content["result"] == body  # type: ignore[attr-defined,index]
        assert result.content[0].text == body  # type: ignore[attr-defined,index]
    elif fmt in {"png", "jpg", "webp"}:
        image = result.content[0]  # type: ignore[attr-defined,index]
        assert image.type == "image"
        assert image.mime_type == {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[fmt]
        assert base64.b64decode(image.data) == body
        assert result.structured_content == {"result": f"{fmt.upper()} chart image attached."}  # type: ignore[attr-defined]
    else:
        assert result.structured_content["result"].startswith("data:application/pdf;base64,")  # type: ignore[attr-defined,index]
        assert result.content[0].text.startswith("PDF chart as a base64 data URI:")  # type: ignore[attr-defined,index]


def test_stripes_image_returns_an_image_block_without_an_output_schema(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The binary climate-stripes tool exposes its PNG as native MCP image content, too."""
    import base64  # noqa: PLC0415

    image_bytes = b"\x89PNG\r\n\x1a\nstripe"

    class Figure:
        def to_image(self, *_args: object, **_kwargs: object) -> bytes:
            return image_bytes

    monkeypatch.setattr(restapi, "_plot_stripes", lambda _request: Figure())
    monkeypatch.setattr(restapi, "require_kaleido", lambda: None)

    result = _call_result(app, "stripes_image", {"kind": "temperature", "station": "01048"})

    assert not result.is_error  # type: ignore[attr-defined]
    image = result.content[0]  # type: ignore[attr-defined,index]
    assert image.type == "image"
    assert image.mime_type == "image/png"
    assert base64.b64decode(image.data) == image_bytes


@pytest.mark.usefixtures("stations")
def test_mcp_values_row_refusal_uses_single_answer_limit_without_streaming_advice(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MCP renders CSV/NDJSON in one bounded answer; only REST streaming refusals recommend those formats."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1")
    arguments = {
        "provider": "dwd",
        "network": "observation",
        "parameters": "daily/kl",
        "stations": "01048",
        "timestamp": "2020-01-01/2020-01-31",
        "format": "csv",
    }

    result = _call_result(app, "values", arguments)

    assert result.is_error  # type: ignore[attr-defined]
    refusal = " ".join(block.text for block in result.content if getattr(block, "type", None) == "text")  # type: ignore[attr-defined]
    assert "more than the 1 this server sends as one answer" in refusal
    assert "format=ndjson" not in refusal
    assert "format=csv" not in refusal

    rest_arguments = {**arguments, "format": "json"}
    response = TestClient(app).get("/api/v1/values", params=rest_arguments)
    assert response.status_code == 400
    rest_detail = response.json()["detail"]
    assert "format=ndjson" in rest_detail
    assert "format=csv" in rest_detail


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
def test_the_endpoint_is_stateless_at_either_path(app: FastAPI, path: str) -> None:
    """No session is created, and a list of the tools and a call work without an `initialize` (GH-3088)."""
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
    }
    call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "glossary", "arguments": {"limit": 1}},
    }
    with TestClient(app) as client:
        response = client.post(path, json=initialize, headers=HEADERS)
        assert response.status_code == 200
        assert "mcp-session-id" not in response.headers
        for given in (HEADERS, {**HEADERS, "mcp-session-id": "left-over-from-a-server-that-kept-one"}):
            listed = client.post(path, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=given)
            assert listed.status_code == 200
            assert "stations" in listed.text
            called = client.post(path, json=call, headers=given)
            assert called.status_code == 200
            assert "clearance_height" in called.text
        # there is no session to end, or a stream of the server's messages to open
        assert client.delete(path, headers={**HEADERS, "mcp-session-id": "x"}).status_code == 405
        assert client.get(path, headers={"Accept": "text/event-stream"}).status_code == 405


def _sdk_client_run(app: FastAPI, connections: int) -> list[tuple[list[str], str]]:
    """Connect `connections` times with the client of the official `mcp` package, which `fastmcp` builds on.

    Each connection: the handshake, the list of the tools and a call of one, ending the session on closing as the
    client does. In one run of the app's lifespan, as it ends the client the tools send their requests with.
    """
    import httpx2  # noqa: PLC0415
    from mcp import ClientSession  # noqa: PLC0415
    from mcp.client.streamable_http import streamable_http_client  # noqa: PLC0415

    async def one() -> tuple[list[str], str]:
        http_client = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), headers={"Accept": "application/json, text/event-stream"}
        )
        async with (
            http_client,
            streamable_http_client(f"http://testserver{MCP_PREFIX}", http_client=http_client) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            names = [tool.name for tool in (await session.list_tools()).tools]
            result = await session.call_tool(
                "stations", {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True}
            )
            return names, result.content[0].text  # ty: ignore[unresolved-attribute]

    async def run() -> list[tuple[list[str], str]]:
        async with app.router.lifespan_context(app):
            return [await one() for _ in range(connections)]

    return asyncio.run(run())


@pytest.mark.usefixtures("stations")
def test_the_official_sdk_client_works_against_the_stateless_endpoint(app: FastAPI) -> None:
    """The client of the `mcp` package: a handshake, a tool list and a call, no session, and none kept (GH-3088)."""
    answers = _sdk_client_run(app, connections=3)

    for names, text in answers:
        assert {"coverage", "stations", "values"} <= set(names)
        assert "01048" in text
        assert "01975" in text
    manager = next(
        route.endpoint.session_manager for route in app.router.routes if getattr(route, "path", "") == MCP_PREFIX
    )
    assert manager.stateless is True
    assert not manager._server_instances  # noqa: SLF001


_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
}


@pytest.mark.parametrize("path", MCP_PATHS)
def test_the_origin_of_a_page_is_checked_against_the_allowed_hosts(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """A page of another origin cannot use the endpoint; a client without an `Origin` and a local page can (GH-3087)."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
    local = {**HEADERS, "Host": "localhost:7890"}
    with TestClient(app) as client:
        refused = client.post(path, json=_INITIALIZE, headers={**local, "Origin": "https://evil.example"})
        assert refused.status_code == 400
        assert refused.json()["type"] == "urn:wetterdienst:problem:origin-not-allowed"
        # a null origin (a sandboxed page) is no listed host either
        assert client.post(path, json=_INITIALIZE, headers={**local, "Origin": "null"}).status_code == 400
        # a rebinding page: its name in `Host`, and its own origin
        rebound = client.post(
            path, json=_INITIALIZE, headers={**HEADERS, "Host": "evil.example", "Origin": "http://evil.example"}
        )
        assert rebound.json()["type"] == "urn:wetterdienst:problem:host-not-allowed"
        # the app on localhost, another port, and a client that sends none
        for origin in ({"Origin": "http://localhost:4000"}, {"Origin": "http://[::1]:4000"}, {}):
            assert client.post(path, json=_INITIALIZE, headers={**local, **origin}).status_code == 200, origin


def test_the_origin_is_not_checked_where_any_host_is_allowed(app: FastAPI) -> None:
    """By default, as before: a server behind a proxy takes the `Origin` of the page that its clients come from."""
    with TestClient(app) as client:
        response = client.post(MCP_PREFIX, json=_INITIALIZE, headers={**HEADERS, "Origin": "https://evil.example"})
    assert response.status_code == 200


@pytest.mark.usefixtures("stations")
def test_the_tools_work_when_the_hosts_are_restricted(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool's request to the REST app is made in process, with a `Host` of its own, and is not refused for it."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "testserver")
    arguments = {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True}

    names, answer = _call(app, [MCP_PREFIX], "stations", arguments)[MCP_PREFIX]

    assert "stations" in names
    assert [station["station_id"] for station in answer["stations"]] == ["01048", "01975"]


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
