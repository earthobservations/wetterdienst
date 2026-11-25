# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `_meta` of an MCP request is validated, the python name of a field beside its alias included (GH-4378).

Before pydantic 2.14.2, validating a `TypedDict` that has aliased fields and takes extra items let a key given
under the field's python name replace the value validated under its alias (GHSA-3r8g-cqwr-jr29). `mcp_types`
validates `_meta` so (`RequestParamsMeta`, whose `progress_token` has the alias `progressToken` from the alias
generator of its models), so a client could put an object where the token is a string or an integer. Nothing in
wetterdienst reads the value: the one consumer is fastmcp's `Context.report_progress`, which no tool calls.

Offline: the request goes to the REST app over ASGI, and a middleware records the `_meta` the server was handed.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from wetterdienst.ui import mcp as mcp_module
from wetterdienst.ui import restapi
from wetterdienst.ui.restapi import MCP_ALIAS_PREFIX, MCP_PREFIX

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from typing import Any

    from fastapi import FastAPI
    from fastmcp.server.middleware import CallNext, MiddlewareContext
    from fastmcp.tools import ToolResult

pytest.importorskip("fastmcp")

HEADERS = {"Accept": "application/json, text/event-stream"}


@asynccontextmanager
async def _no_lifespan(_app: object) -> AsyncIterator[None]:
    yield


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any] | None]:
    """Record the `_meta` of each tool call the mounted MCP endpoint receives, as the server holds it."""
    recorded: list[dict[str, Any] | None] = []

    def recorder() -> object:
        from fastmcp.server.middleware import Middleware  # noqa: PLC0415

        class Record(Middleware):
            async def on_call_tool(
                self, context: MiddlewareContext[Any], call_next: CallNext[Any, ToolResult]
            ) -> ToolResult:
                request_context = context.fastmcp_context.request_context
                meta = request_context._srctx.meta  # noqa: SLF001
                recorded.append(None if meta is None else dict(meta))
                return await call_next(context)

        return Record()

    monkeypatch.setattr(mcp_module, "_require_a_network_for_coverage", recorder)
    return recorded


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, seen: list[dict[str, Any] | None]) -> Iterator[FastAPI]:  # noqa: ARG001
    """Give the REST app an MCP endpoint of this test (see `test_mcp_versioning`), built after the recorder is in."""
    routes = [route for route in restapi.app.router.routes if not getattr(route, "path", "").startswith("/mcp")]
    monkeypatch.setattr(restapi.app.router, "routes", routes)
    monkeypatch.setattr(restapi.app.router, "lifespan_context", _no_lifespan)
    assert restapi._mount_mcp(restapi.app) is True  # noqa: SLF001
    return restapi.app


def _call_glossary(client: TestClient, path: str, meta: dict[str, Any]) -> str:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "glossary", "arguments": {"limit": 1}, "_meta": meta},
    }
    response = client.post(path, json=request, headers=HEADERS)
    assert response.status_code == 200
    return response.text


@pytest.mark.parametrize("path", [MCP_PREFIX, MCP_ALIAS_PREFIX])
def test_a_progress_token_given_under_its_python_name_does_not_replace_the_validated_one(
    app: FastAPI, seen: list[dict[str, Any] | None], path: str
) -> None:
    """The token under its alias is validated and kept; the same field under its python name is not taken instead."""
    with TestClient(app) as client:
        _call_glossary(client, path, {"progressToken": 7, "progress_token": {"smuggled": "object"}})

    assert seen == [{"progress_token": 7}]


@pytest.mark.parametrize("path", [MCP_PREFIX, MCP_ALIAS_PREFIX])
def test_a_progress_token_that_is_no_token_is_refused_under_either_name(
    app: FastAPI, seen: list[dict[str, Any] | None], path: str
) -> None:
    """A token that is neither a string nor an integer is an invalid request, whichever name carries it."""
    with TestClient(app) as client:
        for meta in ({"progressToken": {"not": "a token"}}, {"progress_token": {"not": "a token"}}):
            answer = _call_glossary(client, path, meta)
            assert "validation error" in answer.lower() or "invalid" in answer.lower()

    assert seen == []
