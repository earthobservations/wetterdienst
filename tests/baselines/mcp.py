# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The MCP tools of the last release: the baseline of their names and arguments (GH-3131).

The tools are generated from the REST routes (`wetterdienst.ui.mcp`): each takes the query parameters of its route as
arguments, under the name `_TOOL_NAMES` gives it. A client of an agent writes `values(provider=..., stations=...)`,
so the names of the tools and of their arguments, with the types, the enum members, the defaults and the bounds,
are what it relies on. `tests/baselines/mcp.baseline.json` is the input schema of every tool **as it was released**
(without the titles and descriptions, which describe more than they promise). The rule is that the server must still
offer all the baseline offered, and must not ask more of a call, as `tests/ui/openapi_diff.py` words it for the
parameters of a route, which this shares:

- a tool or an argument that is gone, a changed type, an enum member that is gone breaks;
- an argument that becomes required, a changed default, a tighter bound or a new pattern breaks;
- a new tool, an optional argument, an enum member and a looser bound pass.

The input schemas depend on the versions of FastAPI, pydantic and FastMCP, as the OpenAPI document does, and are
compared where those are the locked ones.

Refresh with `uv run poe mcp:baseline`, in the release commit only (see `tests/baselines/common.py`).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from tests.baselines.common import DIRECTORY, RELEASE, read, write
from tests.ui.openapi_diff import schema_breaks
from tests.ui.openapi_snapshot import _clean_environment

BASELINE = DIRECTORY / "mcp.baseline.json"
#: the packages whose version shapes the input schemas
SHAPED_BY = ("fastapi", "pydantic", "fastmcp")

#: what an approved break says: the finding as `breaking_changes` words it, then why it is no break of a client
_DEBUG_REMOVED = (
    "a request set the log level of the whole server process, for every other caller; it is refused with a hint "
    "to the operator's own setting (GH-3336)"
)
ACCEPTED_BREAKS: dict[str, str] = {
    f"tool {tool}: argument debug was removed": _DEBUG_REMOVED
    for tool in (
        "alerts",
        "auth",
        "coverage",
        "glossary",
        "history",
        "interpolate",
        "issues",
        "providers",
        "stations",
        "stripes_image",
        "stripes_stations",
        "stripes_values",
        "summarize",
        "values",
    )
}

#: the keys of a schema that describe it for a reader and promise nothing
_PROSE = frozenset({"description", "title", "examples", "example"})
#: the keys whose value maps names to schemas, where `description` may be a name
_NAMED = frozenset({"properties", "$defs", "definitions", "patternProperties"})


def _prune(node: Any) -> Any:  # noqa: ANN401
    """Leave out the prose of a schema, down to its members."""
    if isinstance(node, list):
        return [_prune(item) for item in node]
    if not isinstance(node, dict):
        return node
    return {
        key: ({name: _prune(sub) for name, sub in value.items()} if key in _NAMED else _prune(value))
        for key, value in node.items()
        if key not in _PROSE
    }


def build_surface() -> dict[str, Any]:
    """Describe the tools of the server as it is built from the REST app, with no `WD_*` variable set."""
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def list_tools() -> dict[str, Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return {tool.name: _prune(tool.input_schema) for tool in await client.list_tools()}

    with _clean_environment():
        kept = restapi.app.openapi_schema
        restapi.app.openapi_schema = None
        try:
            tools = asyncio.run(list_tools())
        finally:
            restapi.app.openapi_schema = kept
    # through JSON, as it is served
    return {"tools": json.loads(json.dumps(dict(sorted(tools.items()))))}


def read_baseline() -> dict[str, Any]:
    """Read the committed baseline."""
    return read(BASELINE)


def write_baseline() -> None:
    """Write the tools as the baseline of the version in `pyproject.toml`."""
    write(BASELINE, build_surface())


def breaking_changes(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Name each tool or argument that `baseline` offers and `current` does not, or asks more of a call for."""
    found = []
    for tool, old in baseline["tools"].items():
        new = current["tools"].get(tool)
        if new is None:
            found.append(f"tool {tool} was removed")
            continue
        found += _arguments(tool, old, new)
    return sorted(found)


def _arguments(tool: str, old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    found = []
    for name, old_schema in old.get("properties", {}).items():
        where = f"tool {tool}: argument {name}"
        if name not in new.get("properties", {}):
            found.append(f"{where} was removed")
            continue
        if name in new.get("required", []) and name not in old.get("required", []):
            found.append(f"{where} became required")
        # the schemas refer to the `$defs` of their own tool
        found += schema_breaks(
            {"$defs": old.get("$defs", {})},
            {"$defs": new.get("$defs", {})},
            where,
            old_schema,
            new["properties"][name],
        )
    found += [
        f"tool {tool}: argument {name} was added and is required"
        for name in new.get("required", [])
        if name not in old.get("properties", {})
    ]
    return found


__all__ = ["ACCEPTED_BREAKS", "BASELINE", "RELEASE", "SHAPED_BY", "breaking_changes", "build_surface"]

if __name__ == "__main__":
    write_baseline()
