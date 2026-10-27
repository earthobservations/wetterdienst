# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The title and the annotations of every MCP tool (GH-3482).

The Claude connectors directory requires a `title` and the hints `readOnlyHint` and `destructiveHint` of every tool,
and other clients use the hints to skip a confirmation for a read-only call. The tools are generated from the REST
routes, which every one is a GET that only reads, so the hints are the same for all of them but `openWorldHint`
(whether the tool reaches a service outside wetterdienst).

FastMCP logs and swallows an exception in the function that sets them, so a broken function or a new endpoint
without a title would leave the tool bare and nothing would fail: these tests hold the listed tools to having them.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("fastmcp")

from fastmcp import Client

from wetterdienst.ui import mcp as mcp_module
from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import _TOOL_NAMES, _TOOL_TITLES, build_mcp_server

if TYPE_CHECKING:
    from collections.abc import Mapping

#: the tools that answer from wetterdienst's own metadata and never reach a provider
OFFLINE_TOOLS = frozenset({"coverage", "glossary", "providers"})
HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


def _list_tools() -> list[Any]:
    async def listed() -> list[Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return await client.list_tools()

    return asyncio.run(listed())


def _default_title(name: str) -> str:
    """Derive the title FastMCP gives a tool that has none, which is no title of ours."""
    return name.replace("_", " ").replace("-", " ").title()


def problems(tools: list[Any]) -> list[str]:
    """Name what is missing or wrong in the title and the annotations of the tools, as a list for one assert."""
    found = []
    for tool in tools:
        name = tool.name
        annotations = tool.annotations
        if not tool.title or tool.title == _default_title(name):
            found.append(f"{name} has no title of its own ({tool.title!r})")
        if annotations is None:
            found.append(f"{name} has no annotations")
            continue
        # as a client reads them: by the names on the wire, which the attributes of newer MCP SDKs no longer have
        wire = annotations.model_dump(by_alias=True)
        if wire.get("title") != tool.title:
            found.append(f"{name} has the annotation title {wire.get('title')!r}, not {tool.title!r}")
        expected = {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": name not in OFFLINE_TOOLS,
        }
        for hint in HINTS:
            if wire.get(hint) is None:
                found.append(f"{name} has no {hint}")
            elif wire[hint] != expected[hint]:
                found.append(f"{name} has {hint}={wire[hint]!r}, not {expected[hint]!r}")
    return found


def test_every_tool_has_a_title_and_the_annotations() -> None:
    """Whatever tool the server lists has a title and all four hints, with the values of a read-only tool."""
    tools = _list_tools()

    assert len(tools) >= len(_TOOL_NAMES)
    assert problems(tools) == []


def test_the_titles_are_of_the_tools_there_are() -> None:
    """Each tool has an entry and each entry a tool: a renamed or removed tool leaves no stale title behind."""
    assert {tool.name for tool in _list_tools()} == set(_TOOL_TITLES) == set(_TOOL_NAMES.values())


def test_the_titles_are_distinct_and_read_as_names() -> None:
    """A title tells the tools apart in a client's list."""
    titles = [title for title, _ in _TOOL_TITLES.values()]

    assert len(set(titles)) == len(titles)
    assert all(title[:1].isupper() and not title.endswith(".") for title in titles)


def test_only_the_metadata_tools_are_closed_world() -> None:
    """A tool is closed-world only where it never makes a request to a provider."""
    closed = {name for name, (_, open_world) in _TOOL_TITLES.items() if not open_world}

    assert closed == OFFLINE_TOOLS


def test_every_endpoint_the_tools_come_from_only_reads() -> None:
    """`readOnlyHint=True` and `destructiveHint=False` hold only while every route is a GET."""
    methods = {
        method
        for operations in restapi.app.openapi()["paths"].values()
        for method in operations
        if method != "parameters"
    }

    assert methods == {"get"}


@pytest.fixture
def without_titles(monkeypatch: pytest.MonkeyPatch) -> Mapping[str, tuple[str, bool]]:
    """Drop the entry of `values` from the table, as a new endpoint without a title would find it."""
    without = {name: entry for name, entry in _TOOL_TITLES.items() if name != "values"}
    monkeypatch.setattr(mcp_module, "_TOOL_TITLES", without)
    return without


def test_a_tool_without_a_title_is_caught(without_titles: Mapping[str, tuple[str, bool]]) -> None:  # noqa: ARG001
    """FastMCP swallows the function's error, so the tool is listed bare: the check names it."""
    found = problems(_list_tools())

    assert any(line.startswith("values has no annotations") for line in found), found
    assert any(line.startswith("values has no title of its own") for line in found), found


def test_a_broken_function_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """A function that raises for every tool leaves all of them without annotations, and the check says so."""

    def broken(*_args: object) -> None:
        msg = "broken"
        raise RuntimeError(msg)

    monkeypatch.setattr(mcp_module, "_annotate_tool", broken)

    found = problems(_list_tools())

    assert {line.split()[0] for line in found if "has no annotations" in line} == set(_TOOL_NAMES.values())
