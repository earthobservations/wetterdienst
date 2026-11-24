# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The input schemas of the MCP tools lack the options that only the REST API needs (GH-4318).

The size and scale of a chart image, `pretty` and the formats of a chart (html, png, jpg, webp, svg, pdf) are of no use
to a model that reads JSON, and were in the schema of every session. The REST API, the command line and Python keep
them. A call that still sends one is answered or refused as `ui.mcp._refuse_unknown_arguments` says: `pretty`, `width`,
`height` and `scale` are let go (they change nothing of a data answer), and a chart format is refused where the call
would otherwise be answered with an image.

Offline: the REST app is stood in for by one that answers every route with a csv and records the request it got, so
that what is held is what the tool sends.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("fastmcp")

from fastapi import FastAPI, Request, Response
from fastmcp import Client

from tests.ui.test_mcp_formats import _calls
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import _CHART_FORMATS, _CHART_TOOLS, _REST_ONLY_ARGUMENTS, _TOOL_NAMES, build_mcp_server

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

#: the formats a tool answers: data
DATA_FORMATS = {"json", "geojson", "csv", "ndjson"}


def _tools() -> dict[str, Any]:
    async def listed() -> dict[str, Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return {tool.name: tool for tool in await client.list_tools()}

    return asyncio.run(listed())


def _route_of(name: str) -> dict[str, Any]:
    """Give the operation of the REST route a tool is generated from, as the REST app documents it."""
    path = f"/api/v1/{name.replace('_', '-')}"
    return restapi.app.openapi()["paths"][path]["get"]


def _query_parameters(name: str) -> dict[str, Any]:
    return {p["name"]: p for p in _route_of(name)["parameters"] if p["in"] == "query"}


def _stand_in() -> tuple[FastAPI, list[Mapping[str, str]]]:
    """Build a REST app with the routes of the real one that answers each with a csv, and the requests it got."""
    seen: list[Mapping[str, str]] = []
    app = FastAPI()
    app.openapi = restapi.app.openapi  # ty: ignore[invalid-assignment]

    @app.api_route("/{path:path}", methods=["GET"])
    def answer(path: str, request: Request) -> Response:  # noqa: ARG001
        seen.append(dict(request.query_params))
        return Response("a,b\n1,2\n", media_type="text/csv", headers={"X-Wetterdienst-License": "CC-BY-4.0"})

    return app, seen


#: the arguments a call of `values` needs, in csv, which the stand-in answers
_VALUES_CALL = {
    "provider": "dwd",
    "network": "observation",
    "parameters": "daily/climate_summary/temperature_air_mean_2m",
    "stations": "01048",
    "format": "csv",
}


def test_no_tool_takes_an_option_that_only_rest_needs() -> None:
    """The input schema of no tool has `pretty` or the size and scale of an image, nor offers a chart as a format."""
    tools = _tools()

    assert set(tools) == set(_TOOL_NAMES.values())
    for name, tool in tools.items():
        properties = tool.input_schema.get("properties", {})
        assert not _REST_ONLY_ARGUMENTS & set(properties), name
        if "format" in properties:
            formats = set(properties["format"]["enum"])
            assert formats <= DATA_FORMATS, name
            assert formats, name
            # the description does not offer what the tool no longer answers
            for word in ("chart", "png", "html", "svg", "pdf", "image"):
                assert word not in properties["format"]["description"].lower(), (name, word)


def test_the_tools_keep_every_other_option_of_their_route() -> None:
    """A tool is its route without the options above, and without the formats of a chart: nothing else is dropped."""
    for name, tool in _tools().items():
        route = _query_parameters(name)
        assert set(tool.input_schema.get("properties", {})) == set(route) - _REST_ONLY_ARGUMENTS, name
        if "format" in route:
            assert set(tool.input_schema["properties"]["format"]["enum"]) == set(
                route["format"]["schema"]["enum"]
            ) - set(_CHART_FORMATS), name
    # the box of the stations is no image margin
    values = _tools()["values"].input_schema["properties"]
    assert {"left", "right", "top", "bottom"} <= set(values)


def test_rest_keeps_the_options_and_the_charts_and_building_a_server_does_not_change_its_document() -> None:
    """The REST document has them still, after a server was built from it: the tools are made from a copy."""
    build_mcp_server(restapi.app)
    for name in ("stations", "values", "interpolate", "summarize"):
        route = _query_parameters(name)
        assert {"pretty", "width", "height", "scale"} <= set(route), name
        assert set(_CHART_FORMATS) <= set(route["format"]["schema"]["enum"]), name
        assert "chart" in route["format"]["schema"]["description"], name
    for name in ("coverage", "providers", "history", "alerts", "storm_cells", "kostra", "station_ids"):
        assert "pretty" in _query_parameters(name), name


def test_the_tools_that_the_refusal_points_to_rest_for_are_those_whose_route_draws_a_chart() -> None:
    """`_CHART_TOOLS` is held to the routes: a tool is told "charts are drawn by the REST API" where they are."""
    draws = {
        name
        for name in _TOOL_NAMES.values()
        if _CHART_FORMATS[0] in _query_parameters(name).get("format", {}).get("schema", {}).get("enum", ())
    }

    assert draws == _CHART_TOOLS


def test_a_dropped_option_is_let_go_and_never_sent_to_the_route() -> None:
    """A call with `pretty`, `width`, `height` and `scale` is answered as one without, and the route does not get them.

    A client that fills in every option with its default sends `pretty=false`; refusing it would break a call that
    works. For a data format they change nothing of the answer.
    """
    app, seen = _stand_in()
    options = {"pretty": True, "width": 800, "height": 600, "scale": 2.0}

    ((plain, _), (with_options, _)) = _calls(app, [("values", _VALUES_CALL), ("values", {**_VALUES_CALL, **options})])

    assert not plain.is_error, plain.content
    assert not with_options.is_error, with_options.content
    assert with_options.content[0].text == plain.content[0].text
    assert len(seen) == 2
    assert seen[0] == seen[1]
    assert not _REST_ONLY_ARGUMENTS & set(seen[1])
    assert seen[1]["format"] == "csv"


@pytest.mark.parametrize("fmt", _CHART_FORMATS)
def test_a_chart_format_is_refused_where_it_would_have_been_answered_with_an_image(fmt: str) -> None:
    """The error names the format, what the tool answers and that the REST API draws charts; nothing is requested."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("values", {**_VALUES_CALL, "format": fmt, "width": 100})])

    assert result.is_error
    text = result.content[0].text
    assert text == (
        f"format={fmt} is not offered by the tool values, which answers json, geojson, csv or ndjson. "
        f"Charts are drawn by the REST API: its route of values takes format={fmt}."
    )
    assert seen == []


def test_a_chart_format_of_a_tool_whose_route_never_drew_one_is_refused_without_a_pointer_to_rest() -> None:
    """`alerts` never offered a chart: the call is refused naming what it answers, and REST is not said to draw it."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("alerts", {"format": "png", "latitude": 54.3, "longitude": 10.1})])

    assert result.is_error
    assert result.content[0].text == "format=png is not offered by the tool alerts, which answers json, geojson or csv."
    assert seen == []


def test_a_format_that_is_no_chart_is_left_to_the_route() -> None:
    """A value that no route offers is the route's to refuse, as it was: the tool only refuses the charts."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("values", {**_VALUES_CALL, "format": "xml"})])

    assert not result.is_error  # the stand-in has no validation of its own
    assert seen[0]["format"] == "xml"


def test_an_argument_that_is_unknown_is_refused_with_the_dropped_ones_let_go() -> None:
    """`pretty` next to a name that is none is not what the error names: the tool is no more lenient for it."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("values", {**_VALUES_CALL, "pretty": True, "bogus": 1})])

    assert result.is_error
    assert result.content[0].text.startswith("bogus is not an argument of values, which takes ")
    assert "pretty" not in result.content[0].text
    assert seen == []


def test_a_tool_that_never_took_a_format_still_refuses_it() -> None:
    """`glossary` has no `format`: `format=png` is an argument it does not take, as it was."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("glossary", {"parameter": "temperature_air_mean_2m", "format": "png"})])

    assert result.is_error
    assert result.content[0].text.startswith("format is not an argument of glossary, which takes ")
    assert seen == []
