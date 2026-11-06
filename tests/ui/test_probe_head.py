# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`HEAD` on the two probes, `/health` and `/ready`, and on no other route (GH-3814).

Some uptime monitors and `wget --spider` probe with `HEAD` and read a 405 as the server being down. The two probes
answer it as their `GET` does, with the same status and headers and no body, through the same middleware: outside the
host check, the rate limit and the cap.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

import pytest
from starlette.testclient import TestClient

from tests.ui.test_operations import _VALUES, _async_client, _blocking_values, _until
from wetterdienst.ui import restapi

if TYPE_CHECKING:
    from pathlib import Path

_PROBES = ["/health", "/ready"]


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", _PROBES)
def test_a_probe_answers_head_as_its_get_does_without_a_body(client: TestClient, path: str) -> None:
    """The status and the headers of the `GET`, `Content-Length` and the `no-store` of `/ready` among them."""
    got = client.get(path)
    head = client.head(path)

    assert head.status_code == got.status_code == 200
    assert head.content == b""
    assert head.headers["content-type"] == got.headers["content-type"]
    assert head.headers["content-length"] == got.headers["content-length"] != "0"
    assert head.headers.get("cache-control") == got.headers.get("cache-control")
    assert head.headers["X-Request-ID"]
    assert head.headers["X-Content-Type-Options"] == "nosniff"
    if path == "/ready":
        assert head.headers["cache-control"] == "no-store"


def test_a_server_that_is_not_ready_answers_head_with_its_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 503 of `/ready` holds for `HEAD`: its status, `Retry-After` and `no-store`, and no body."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "a-secret-that-is-no-number")

    got = client.get("/ready", headers={"X-Request-ID": "ready-head-1"})
    head = client.head("/ready", headers={"X-Request-ID": "ready-head-1"})

    assert head.status_code == got.status_code == 503
    assert head.content == b""
    assert head.headers["Retry-After"] == got.headers["Retry-After"] == "30"
    assert head.headers["Cache-Control"] == "no-store"
    assert head.headers["content-type"].startswith("application/problem+json")
    assert head.headers["content-length"] == got.headers["content-length"]
    assert head.headers["X-Request-ID"] == "ready-head-1"
    # `/health` says the process is up whatever the settings are
    assert client.head("/health").status_code == 200


@pytest.mark.parametrize("path", _PROBES)
def test_a_probe_head_is_outside_the_host_check(client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    """A probe addresses the server by an address of its own: `HEAD` too, where any other route refuses the host."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "only.example.org")

    assert client.head(path, headers={"Host": "10.0.0.7:7890"}).status_code == 200
    assert client.get("/api/v1/version", headers={"Host": "10.0.0.7:7890"}).status_code == 400


def test_a_probe_head_is_not_counted_against_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the cap reached the `HEAD` of a probe is served, as its `GET` is, and a data request is refused."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "1")
    release, begun, _ended = _blocking_values(monkeypatch)

    async def run() -> tuple[Any, Any, Any, Any]:
        async with _async_client() as client:
            first = asyncio.ensure_future(client.get("/api/v1/values", params=_VALUES))
            await _until(lambda: len(begun) == 1 or first.done(), "handler of the request being served")
            busy = await client.get("/api/v1/values", params=_VALUES)
            health = await client.head("/health")
            ready = await client.head("/ready")
            release.set()
            await first
            return busy, health, ready, first

    try:
        busy, health, ready, _ = asyncio.run(run())
    finally:
        release.set()

    assert busy.status_code == 503
    assert (health.status_code, ready.status_code) == (200, 200)


@pytest.mark.parametrize("path", ["/", "/robots.txt", "/api/v1/version", "/api/v1/providers"])
def test_no_other_route_answers_head(client: TestClient, path: str) -> None:
    """Only the two probes: any other route is a 405 for `HEAD`, as it was."""
    assert client.head(path).status_code == 405


@pytest.mark.parametrize("path", _PROBES)
def test_the_document_shows_head_on_the_probes_and_nowhere_else(path: str) -> None:
    """A `head` operation beside the `get` of the probe, answered without a body, and on no other path."""
    document = restapi.app.openapi()
    paths = document["paths"]

    operation = paths[path]["head"]
    assert operation["tags"] == ["Server"]
    assert "content" not in operation["responses"]["200"]
    assert ("503" in operation["responses"]) == (path == "/ready")
    assert [name for name, item in paths.items() if "head" in item] == _PROBES


def test_head_adds_no_tool_to_mcp() -> None:
    """The probes are left out of the tools by their path, whatever the method."""
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def names() -> set[str]:
        async with Client(build_mcp_server(restapi.app)) as mcp:
            return {tool.name for tool in await mcp.list_tools()}

    tools = asyncio.run(names())

    assert not {name for name in tools if "health" in name or "ready" in name}
