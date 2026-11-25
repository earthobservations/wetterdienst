# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An object for an argument that is no object is refused, and no query parameter reaches a route but its own (GH-4453).

FastMCP sends an object as one query parameter for each of its keys (`ui.mcp._send_objects_as_json` turns the
arguments that are objects into their JSON text for that reason). Given for an argument that is no object,
`values(shape={"format": "png"})` was requested as `...&format=png`, which the refusal of a chart format (it reads the
argument `format`) never saw: the tool answered an image past the refusal and past the budget. Any key of the object
was a query parameter that the tool does not declare. Such an object is refused, naming the argument; `format` has its
own refusal, and the arguments that are objects (`limits`, `unit_targets`, the station distances) are as they were.

And the transport of the tools carries the answers that are data only: a 2xx that is not csv, ndjson or JSON is an
error of the tool, as it reaches no client (defence in depth, where the refusal of the arguments is the guard).

Offline: the REST app is stood in for by one that answers every route with a csv and records the query it got.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("fastmcp")

from fastapi import FastAPI, Response
from fastmcp import Client

from tests.ui.test_mcp_formats import _calls
from tests.ui.test_mcp_slim_schemas import _required, _stand_in, _tools
from tests.ui.test_operations import _VALUES, _no_ambient_settings  # noqa: F401
from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import _REST_ONLY_ARGUMENTS, _object_arguments, build_mcp_server

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

#: what is given in place of a value: an object, a list of them, one nested, an empty one
_OBJECTS: dict[str, Any] = {
    "object": {"format": "png"},
    "object-with-two-keys": {"format": "png", "zzz": "1"},
    "list-of-objects": [{"format": "png"}],
    "nested": {"a": {"format": "png"}},
    "list-of-lists": [[{"format": "png"}]],
    "empty": {},
}

_CHART_OBJECTS = [{"format": fmt} for fmt in ("png", "jpg", "webp", "pdf", "svg", "html")]


def _arguments_of(tool: str) -> list[str]:
    """Name each argument a call of the tool can give: those of its schema, and the options REST alone takes."""
    return sorted(set(_tools()[tool].input_schema["properties"]) | _REST_ONLY_ARGUMENTS)


def _make_calls(
    calls: Sequence[tuple[str, Mapping[str, Any]]],
) -> tuple[list[Any], list[Mapping[str, str]], list[int]]:
    """Make the calls on a server built from the stand-in, in one session; give the results, the queries, the counts.

    The count of a call is how many requests it sent the route.
    """
    app, seen = _stand_in()
    counts: list[int] = []

    async def call() -> list[Any]:
        results = []
        async with Client(build_mcp_server(app)) as client:
            for tool, arguments in calls:
                before = len(seen)
                try:
                    results.append(await client.call_tool(tool, dict(arguments), raise_on_error=False))
                except RuntimeError as error:
                    # the stand-in's csv is no answer of the tool's schema, which the client holds the result to
                    assert "Invalid structured content" in str(error), error  # noqa: PT017
                    results.append(None)
                counts.append(len(seen) - before)
        return results

    return asyncio.run(call()), seen, counts


def test_no_query_parameter_reaches_a_route_but_those_the_tool_declares() -> None:
    """Every argument of every tool, given as each kind of object: what the route gets is its own query.

    1,620 calls with the tools of today: the object is refused by the tool where the argument is no object, and sent as
    the JSON text of the argument where it is one. A key of an object is never a query parameter.
    """
    cases = [
        (tool, name, {**_required(tool), name: value})
        for tool in _tools()
        for name in _arguments_of(tool)
        if name != "format"
        for value in _OBJECTS.values()
    ]

    results, seen, counts = _make_calls([(tool, arguments) for tool, _, arguments in cases])

    assert len(cases) > 1_000
    position = 0
    for (tool, name, arguments), result, count in zip(cases, results, counts, strict=True):
        schema = _tools()[tool].input_schema
        queries = seen[position : position + count]
        position += count
        assert all(set(query) <= set(schema["properties"]) for query in queries), (tool, arguments, queries)
        if name not in _object_arguments(schema):
            assert result is not None
            assert result.is_error, (tool, arguments)
            assert count == 0, (tool, arguments)
            assert name in result.content[0].text, (tool, arguments)


@pytest.mark.parametrize("given", _CHART_OBJECTS, ids=lambda given: given["format"])
@pytest.mark.parametrize(
    ("tool", "name"), [("values", "shape"), ("values", "humanize"), ("stations", "name"), ("interpolate", "latitude")]
)
def test_a_chart_format_in_an_object_is_refused_where_the_route_would_have_drawn_it(
    tool: str, name: str, given: dict[str, str]
) -> None:
    """The route is not asked, and the error names the argument. The real app, so an answer would be the chart."""
    arguments = {**(_VALUES if tool == "values" else _required(tool)), name: given}
    ((result, _),) = _calls(restapi.app, [(tool, arguments)])

    assert result.is_error
    assert f"{name} is not an object argument of {tool}" in result.content[0].text
    assert len(result.content[0].text) < 1_000


def test_an_object_is_refused_in_the_list_of_the_refusals_of_the_call() -> None:
    """One error holds each refusal of a call: the object, the format, and an argument the tool does not take."""
    arguments = {**_required("values"), "shape": {"format": "png"}, "format": "pdf", "nonsense": 1}
    ((result, _),) = _calls(restapi.app, [("values", arguments)])

    text = result.content[0].text
    assert result.is_error
    assert "shape is not an object argument of values" in text
    assert "format=pdf is not offered by the tool values" in text
    assert "nonsense is not an argument of values" in text


def test_the_arguments_that_are_objects_are_sent_as_their_json_and_are_not_refused() -> None:
    """`limits` takes an object, as it did: the route gets one query parameter, the JSON text, and no key of it."""
    arguments = {**_VALUES, "format": "csv", "limits": {"temperature_air_mean_2m": [-50, 50]}}
    app, seen = _stand_in()

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(app)) as client:
            return await client.call_tool("values", arguments, raise_on_error=False)

    result = asyncio.run(call())

    assert not result.is_error, result.content
    assert json.loads(seen[0]["limits"]) == {"temperature_air_mean_2m": [-50, 50]}
    assert "temperature_air_mean_2m" not in seen[0]


def test_a_value_that_is_no_object_is_let_through_as_it_was() -> None:
    """A list for an argument that takes one, and a plain value, are no objects: the route is asked."""
    arguments = {**_VALUES, "parameters": ["daily/climate_summary/temperature_air_mean_2m"], "format": "csv"}
    ((result, _),) = _calls(restapi.app, [("coverage", {"provider": "dwd", "network": "observation"})])
    assert not result.is_error or "object" not in result.content[0].text

    app, seen = _stand_in()

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(app)) as client:
            return await client.call_tool("values", arguments, raise_on_error=False)

    result = asyncio.run(call())
    assert not result.is_error, result.content
    assert len(seen) == 1


@pytest.mark.parametrize(
    ("media_type", "body"),
    [
        ("image/png", b"\x89PNG\r\n\x1a\n\x00\xff"),
        ("image/jpeg", b"\xff\xd8\xff"),
        ("image/webp", b"RIFF\x00\x00\x00\x00WEBP"),
        ("application/pdf", b"%PDF-1.4\n\xff"),
        ("image/svg+xml", b"<svg xmlns='http://www.w3.org/2000/svg'/>"),
        ("text/html", b"<html></html>"),
        ("application/octet-stream", b"\x00\x01"),
        ("text/plain", b"plain"),
    ],
)
def test_an_answer_that_is_not_data_is_an_error_of_the_tool_whatever_reached_it(media_type: str, body: bytes) -> None:
    """A 2xx that is not csv, ndjson or JSON is no answer a tool carries: an error, and its body is not read.

    Before, a text body was decoded as text and an image or pdf made an image content or an embedded resource, which
    no client was meant to get from a tool.
    """
    stand_in = FastAPI()
    stand_in.openapi = restapi.app.openapi  # ty: ignore[invalid-assignment]

    @stand_in.api_route("/{path:path}", methods=["GET"])
    def answer(path: str) -> Response:  # noqa: ARG001
        return Response(body, media_type=media_type)

    ((result, _),) = _calls(stand_in, [("values", {**_VALUES, "format": "csv"})])

    assert result.is_error
    text = result.content[0].text
    assert media_type in text
    assert "502" in text
    assert len(text) < 500
