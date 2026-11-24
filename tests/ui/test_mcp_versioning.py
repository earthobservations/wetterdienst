# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The MCP endpoint is versioned like the REST API: `/mcp/v1` pinned, `/mcp` the alias of the current version (GH-3074).

Offline: a client of the `fastmcp` package talks to the REST app over ASGI, through its lifespan, and
the one tool it calls reads a stubbed station list.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import polars as pl
import pytest
from fastapi.testclient import TestClient

from wetterdienst.ui import restapi
from wetterdienst.ui.restapi import API_PREFIX, MCP_ALIAS_PREFIX, MCP_PREFIX

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from typing import Any

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
def test_the_endpoint_is_stateless_at_either_path(app: FastAPI, path: str) -> None:
    """No session is kept, and a list of the tools and a call work without an `initialize` (GH-3088, GH-4341)."""
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
        for given in (HEADERS, {**HEADERS, "mcp-session-id": "left-over-from-a-server-that-kept-one"}):
            listed = client.post(path, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=given)
            assert listed.status_code == 200
            assert "mcp-session-id" not in listed.headers
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


_SESSION_ID = re.compile(r"[\x21-\x7e]+")
_TOOLS_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
_TOOL_CALL = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {"name": "glossary", "arguments": {"limit": 1}},
}


@pytest.mark.parametrize("path", MCP_PATHS)
def test_initialize_answers_with_a_fresh_session_id_at_either_path(app: FastAPI, path: str) -> None:
    """`initialize` carries an `Mcp-Session-Id` of visible ASCII, a new one each time (GH-4341)."""
    with TestClient(app) as client:
        ids = [client.post(path, json=_INITIALIZE, headers=HEADERS).headers.get("mcp-session-id") for _ in range(3)]

    assert all(session_id and _SESSION_ID.fullmatch(session_id) for session_id in ids)
    assert len(set(ids)) == 3


@pytest.mark.parametrize("path", MCP_PATHS)
def test_initialize_is_answered_by_the_endpoint_and_a_refusal_gets_no_id(app: FastAPI, path: str) -> None:
    """The body is replayed as sent: the answer is the endpoint's own, with the id added; a refused one has none."""
    with TestClient(app) as client:
        response = client.post(path, json=_INITIALIZE, headers=HEADERS)
        # a batch is refused by the endpoint (400), so no session is announced for it
        batch = client.post(path, json=[_INITIALIZE], headers=HEADERS)

    assert response.status_code == 200
    assert "protocolVersion" in response.text
    assert "Wetterdienst" in response.text
    assert response.headers["mcp-session-id"]
    assert batch.status_code == 400
    assert "mcp-session-id" not in batch.headers


@pytest.mark.parametrize("path", MCP_PATHS)
def test_a_request_that_is_no_initialize_gets_no_id(app: FastAPI, path: str) -> None:
    """A list, a call, a notification and a body that is no JSON are served as they were, with no id (GH-4341)."""
    notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    with TestClient(app) as client:
        for body in (_TOOLS_LIST, _TOOL_CALL, notification):
            response = client.post(path, json=body, headers=HEADERS)
            assert response.status_code in (200, 202), body
            assert "mcp-session-id" not in response.headers, body
        garbage = client.post(path, content=b"not json", headers=HEADERS)
        assert "mcp-session-id" not in garbage.headers
        assert garbage.status_code == 400


@pytest.mark.parametrize("path", MCP_PATHS)
def test_the_id_is_neither_stored_nor_checked(app: FastAPI, path: str) -> None:
    """The id of an `initialize`, another, and none, are served alike, and nothing is kept (GH-4341, GH-3088)."""
    with TestClient(app) as client:
        issued = client.post(path, json=_INITIALIZE, headers=HEADERS).headers["mcp-session-id"]
        for given in (
            HEADERS,
            {**HEADERS, "mcp-session-id": issued},
            {**HEADERS, "mcp-session-id": "never-issued"},
        ):
            listed = client.post(path, json=_TOOLS_LIST, headers=given)
            assert listed.status_code == 200
            assert "stations" in listed.text
            called = client.post(path, json=_TOOL_CALL, headers=given)
            assert called.status_code == 200
            assert "clearance_height" in called.text
            assert "mcp-session-id" not in called.headers
        # a second initialize that carries the id is a new one, not the continuation of a session
        again = client.post(path, json=_INITIALIZE, headers={**HEADERS, "mcp-session-id": issued})
        assert again.status_code == 200
        assert again.headers["mcp-session-id"] != issued
        assert client.delete(path, headers={**HEADERS, "mcp-session-id": issued}).status_code == 405
        manager = next(
            route.endpoint.session_manager for route in app.router.routes if getattr(route, "path", "") == path
        )
        assert manager.stateless is True
        assert not manager._server_instances  # noqa: SLF001


@pytest.mark.usefixtures("stations")
def test_the_official_sdk_client_takes_the_id_and_ends_without_an_error(app: FastAPI) -> None:
    """The `mcp` client keeps the id, sends it on, and its `DELETE` on closing and its `GET` are answered 405 (GH-4341).

    What the client does with the id, observed: it sends it with every later request; on closing it sends a `DELETE`,
    and a 405 is logged by the SDK at debug level as "Server does not allow session termination"; and after the
    `initialized` notification it opens a `GET` stream, which a stateless server refuses with 405, and which it tries
    twice (a second after the first) before giving up, silently. No call fails.
    """
    import httpx2  # noqa: PLC0415
    from mcp import ClientSession  # noqa: PLC0415
    from mcp.client.streamable_http import streamable_http_client  # noqa: PLC0415

    seen: list[tuple[str, int, str | None, str | None]] = []

    async def record(response: httpx2.Response) -> None:
        request = response.request
        seen.append(
            (
                request.method,
                response.status_code,
                request.headers.get("mcp-session-id"),
                response.headers.get("mcp-session-id"),
            )
        )

    async def run() -> tuple[list[str], str]:
        http_client = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            headers=HEADERS,
            event_hooks={"response": [record]},
        )
        async with (
            app.router.lifespan_context(app),
            http_client,
            streamable_http_client(f"http://testserver{MCP_PREFIX}", http_client=http_client) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            names = [tool.name for tool in (await session.list_tools()).tools]
            result = await session.call_tool(
                "stations", {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True}
            )
            text = result.content[0].text  # ty: ignore[unresolved-attribute]
        return names, text

    names, text = asyncio.run(run())

    assert {"coverage", "stations", "values"} <= set(names)
    assert "01048" in text
    posts = [entry for entry in seen if entry[0] == "POST"]
    assert posts[0][2] is None
    issued = posts[0][3]
    assert issued
    assert all(sent == issued and status in (200, 202) for _, status, sent, _ in posts[1:])
    assert [entry[1] for entry in seen if entry[0] == "DELETE"] == [405]
    gets = [entry[1] for entry in seen if entry[0] == "GET"]
    assert gets
    assert set(gets) == {405}


_MIB = 1024 * 1024


def _post_in_chunks(
    app: FastAPI, path: str, chunks: list[bytes], *, declare: int | str | None = None
) -> tuple[int, dict[str, str], bytes, int]:
    """POST `chunks` to the app as one request, as an ASGI server delivers a body: one message for each chunk.

    Answers the status, the headers and the body of the response, and how many times the app called `receive`: a
    wrapper that reads a body it was not to read shows in that count. `declare` is the `Content-Length` to send, none
    for a chunked body.

    The client stays connected until the answer is complete (GH-4398): the SDK streams its answer as SSE and listens
    for `http.disconnect` meanwhile, and a disconnect that comes on a timer cuts an answer that a loaded machine has
    not written yet (a 200 with no body). So the disconnect is the answer of `receive` once the last message of the
    response was sent, which a client that has read it all does, and not before.
    """
    calls = 0
    pending = list(chunks)
    answered = asyncio.Event()

    async def receive() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if pending:
            return {"type": "http.request", "body": pending.pop(0), "more_body": bool(pending)}
        await answered.wait()
        return {"type": "http.disconnect"}

    started: dict[str, Any] = {}
    body = bytearray()

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            started.update(message)
        else:
            body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                answered.set()

    headers = [
        (b"host", b"testserver"),
        (b"accept", HEADERS["Accept"].encode()),
        (b"content-type", b"application/json"),
    ]
    if declare is not None:
        headers.append((b"content-length", str(declare).encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    async def run() -> None:
        async with app.router.lifespan_context(app):
            # a bound that fails the test where it would hang: the answer is never given up on for want of time
            await asyncio.wait_for(app(scope, receive, send), timeout=60)

    asyncio.run(run())
    assert answered.is_set(), "the app returned before the last message of its response was sent"
    response_headers = {name.decode().lower(): value.decode() for name, value in started["headers"]}
    return started["status"], response_headers, bytes(body), calls


@pytest.mark.parametrize("path", MCP_PATHS)
def test_a_chunked_initialize_gets_the_id_and_reaches_the_sdk_whole(app: FastAPI, path: str) -> None:
    """An `initialize` in several chunks, with no `Content-Length`: it gets the id, and the SDK reads all of it."""
    raw = json.dumps(_INITIALIZE).encode()
    chunks = [raw[i : i + 20] for i in range(0, len(raw), 20)]
    assert len(chunks) > 3

    status, headers, body, _ = _post_in_chunks(app, path, chunks)

    assert status == 200
    assert headers["mcp-session-id"]
    # the SDK read the whole body: it answers for the protocol version it was sent
    assert b"protocolVersion" in body
    assert b'"id":1' in body


@pytest.mark.parametrize("path", MCP_PATHS)
def test_a_body_that_declares_more_than_the_limit_is_refused_without_being_read(app: FastAPI, path: str) -> None:
    """A declared `Content-Length` over the SDK's 4 MiB is a 413 before any of the body is read (GH-4341)."""
    chunks = [b"x" * _MIB] * 8

    status, headers, _, calls = _post_in_chunks(app, path, chunks, declare=8 * _MIB)

    assert status == 413
    assert "mcp-session-id" not in headers
    assert calls == 0


@pytest.mark.parametrize("path", MCP_PATHS)
def test_an_oversized_chunked_body_is_cut_by_the_sdk_not_read_by_the_wrapper(app: FastAPI, path: str) -> None:
    """A chunked body of 64 MiB with no `Content-Length` is a 413 after the SDK's 4 MiB, not after all of it."""
    chunks = [b"x" * _MIB] * 64

    status, headers, _, calls = _post_in_chunks(app, path, chunks)

    assert status == 413
    assert "mcp-session-id" not in headers
    # 4 MiB and the chunk that goes past it, and one read of the wrapper's before; not the 64 chunks
    assert calls <= 8


@pytest.mark.parametrize("path", MCP_PATHS)
def test_an_initialize_padded_past_the_cap_is_served_as_before_with_no_id(app: FastAPI, path: str) -> None:
    """A body past what the wrapper inspects is not read for a method: the endpoint answers it, with no id."""
    padded = json.dumps({**_INITIALIZE, "padding": "x" * (128 * 1024)}).encode()
    # 20 KiB chunks: three are within the cap and held when the fourth goes past it, and the SDK must get all of them
    chunks = [padded[i : i + 20 * 1024] for i in range(0, len(padded), 20 * 1024)]
    assert len(chunks) > 4

    status, headers, body, _ = _post_in_chunks(app, path, chunks)

    assert status == 200
    assert "mcp-session-id" not in headers
    assert b"protocolVersion" in body


@pytest.mark.parametrize("size", [0, 128 * 1024])
def test_a_slow_answer_reaches_the_client_whole(app: FastAPI, monkeypatch: pytest.MonkeyPatch, size: int) -> None:
    """An answer the machine is slow to write is still read whole, below the cap and past it (GH-4398).

    The test driver once disconnected on a timer, which cut the SSE answer of a loaded runner into a 200 with no body;
    the server was not at fault, and a client that stays connected got the answer every time.
    """
    from mcp.server.streamable_http import StreamableHTTPServerTransport  # noqa: PLC0415

    write = StreamableHTTPServerTransport._run_sse_writer  # noqa: SLF001

    async def slowly(self: StreamableHTTPServerTransport, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        await asyncio.sleep(1)
        await write(self, *args, **kwargs)

    monkeypatch.setattr(StreamableHTTPServerTransport, "_run_sse_writer", slowly)
    padded = json.dumps({**_INITIALIZE, "padding": "x" * size}).encode()
    chunks = [padded[i : i + 20 * 1024] for i in range(0, len(padded), 20 * 1024)]

    status, headers, body, _ = _post_in_chunks(app, MCP_PREFIX, chunks)

    assert status == 200
    assert ("mcp-session-id" in headers) is (size == 0)
    assert b"protocolVersion" in body
    assert b'"id":1' in body


async def _feed(messages: list[dict[str, Any]], *, then: dict[str, Any] | None = None) -> Any:  # noqa: ANN401
    """Run the reader of the start of a body over `messages`, and answer what it gives and how many it asked for."""
    from wetterdienst.ui import mcp  # noqa: PLC0415

    asked = 0

    async def receive() -> dict[str, Any]:
        nonlocal asked
        asked += 1
        # a point to cancel at, as a server's `receive` has: an endless stream must end in the timeout, not hang the run
        await asyncio.sleep(0)
        if messages:
            return messages.pop(0)
        return then or {"type": "http.disconnect"}

    replay, body = await mcp._read_start_of_body(receive)  # noqa: SLF001
    return list(replay), body, asked


def test_a_body_of_one_byte_messages_is_held_as_one_message() -> None:
    """A body that comes one byte at a time is a single message and a buffer, not a message for each byte."""
    body = b'{"jsonrpc":"2.0","id":1,"method":"initialize"}'
    messages = [
        {"type": "http.request", "body": body[i : i + 1], "more_body": i < len(body) - 1} for i in range(len(body))
    ]

    replay, read, asked = asyncio.run(_feed(messages))

    assert read == body
    assert replay == [{"type": "http.request", "body": body, "more_body": False}]
    assert asked == len(body)


def test_the_messages_of_a_body_up_to_the_cap_are_held_as_one() -> None:
    """65535 messages of a byte are still one message held, and the one that goes past the cap is kept as it came."""
    cap = 64 * 1024
    messages = [{"type": "http.request", "body": b"x", "more_body": True} for _ in range(cap)]
    crossing = {"type": "http.request", "body": b"y", "more_body": True}

    replay, read, _ = asyncio.run(_feed([*messages, crossing]))

    assert read is None
    assert len(replay) == 2
    assert replay[0] == {"type": "http.request", "body": b"x" * cap, "more_body": True}
    assert replay[1] is crossing


def test_the_messages_after_the_body_are_kept_for_the_endpoint() -> None:
    """A disconnect that ends the body is replayed after it."""
    disconnect = {"type": "http.disconnect"}

    replay, read, _ = asyncio.run(_feed([{"type": "http.request", "body": b"ab", "more_body": True}], then=disconnect))

    assert read == b"ab"
    assert replay == [{"type": "http.request", "body": b"ab", "more_body": True}, disconnect]


def test_empty_messages_that_end_are_waited_for() -> None:
    """A few messages with no bytes, then the body: it is all read, and the empty ones are not replayed."""
    body = b'{"jsonrpc":"2.0","id":1,"method":"initialize"}'
    messages = [{"type": "http.request", "body": b"", "more_body": True}] * 10
    messages.append({"type": "http.request", "body": body, "more_body": False})

    replay, read, _ = asyncio.run(_feed(messages))

    assert read == body
    assert replay == [{"type": "http.request", "body": body, "more_body": False}]


def test_an_endless_stream_of_empty_messages_is_given_up_on() -> None:
    """A server that sends `more_body` and nothing else without end does not hold the wrapper: it hands over."""
    empty = {"type": "http.request", "body": b"", "more_body": True}

    async def run() -> Any:  # noqa: ANN401
        return await asyncio.wait_for(_feed([], then=empty), timeout=5)

    replay, read, asked = asyncio.run(run())

    assert read is None
    assert replay == [{"type": "http.request", "body": b"", "more_body": True}]
    assert asked < 200


@pytest.mark.parametrize("path", MCP_PATHS)
def test_empty_messages_before_an_initialize_are_served_with_the_id(app: FastAPI, path: str) -> None:
    """Through the app: empty messages, then the body, and the SDK reads the `initialize` all the same."""
    raw = json.dumps(_INITIALIZE).encode()

    status, headers, body, _ = _post_in_chunks(app, path, [b"", b"", raw[:30], b"", raw[30:]])

    assert status == 200
    assert headers["mcp-session-id"]
    assert b"protocolVersion" in body


@pytest.mark.parametrize("path", MCP_PATHS)
def test_a_content_length_of_thousands_of_digits_is_no_number_and_no_error(app: FastAPI, path: str) -> None:
    """A `Content-Length` of leading zeros, longer than `int` takes from a string, is served as one with none."""
    raw = json.dumps(_INITIALIZE).encode()

    status, headers, body, _ = _post_in_chunks(app, path, [raw], declare="0" * 5000 + str(len(raw)))

    assert status == 200
    assert headers["mcp-session-id"]
    assert b"protocolVersion" in body


@pytest.mark.parametrize("path", MCP_PATHS)
def test_a_deeply_nested_body_is_a_400_not_a_500(app: FastAPI, path: str) -> None:
    """A body nested deeper than a parser takes is the SDK's parse error (400), as it was before the id (GH-4341)."""
    # deep enough for the C scanner of `json` too, whose limit is far above the interpreter's recursion limit
    nested = b"[" * 30000 + b"]" * 30000
    raw = b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":' + nested + b"}"
    assert len(raw) < 64 * 1024

    status, headers, _, _ = _post_in_chunks(app, path, [raw])

    assert status == 400
    assert "mcp-session-id" not in headers


@pytest.mark.parametrize("path", MCP_PATHS)
def test_a_notification_named_initialize_gets_no_id(app: FastAPI, path: str) -> None:
    """The id answers a request: a message named `initialize` that has no `id` is a notification (GH-4341)."""
    notification = {key: value for key, value in _INITIALIZE.items() if key != "id"}

    with TestClient(app) as client:
        response = client.post(path, json=notification, headers=HEADERS)

    assert "mcp-session-id" not in response.headers
