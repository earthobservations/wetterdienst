# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The input schemas of the MCP tools lack the options that only the REST API needs (GH-4318, GH-4471).

The size and scale of a chart image, `pretty` and the formats of a chart (html, png, jpg, webp, svg, pdf) are of no use
to a model that reads JSON, and were in the schema of every session. The REST API, the command line and Python keep
them. A call that still sends one is answered or refused as `ui.mcp._refuse_unknown_arguments` says: `pretty` at any
value and `width`, `height` and `scale` as `null` (the default they had) are let go, by a tool whose route took them; a
`width`, `height` or `scale` with a value, and a `format` the tool does not offer, are refused, with every other
refusal of the call in the same error. `skip_empty`, `skip_threshold` and `skip_criteria` (`values`, GH-4471) are let
go as `null` or at their default and refused at any other value.

Offline: the REST app is stood in for by one that answers every route with a csv and records the request it got, so
that what is held is what the tool sends.
"""

from __future__ import annotations

import asyncio
import functools
import json
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("fastmcp")

from fastapi import FastAPI, Request, Response
from fastmcp import Client

from tests.ui.test_mcp_formats import _argument_for, _calls
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import (
    _CHART_FORMATS,
    _CHART_TOOLS,
    _REST_ONLY_ARGUMENTS,
    _TOOL_NAMES,
    _routes_of_tools,
    build_mcp_server,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

#: the formats a tool answers: data
DATA_FORMATS = {"json", "geojson", "csv", "ndjson"}


@functools.cache
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


def _required(tool: str) -> dict[str, Any]:
    """Give the arguments a call of the tool needs, from its input schema."""
    schema = _tools()[tool].input_schema
    return {name: _argument_for(schema["properties"][name]) for name in schema.get("required", ())}


#: the arguments a call of `values` needs, in csv, which the stand-in answers
_VALUES_CALL = {
    "provider": "dwd",
    "network": "observation",
    "parameters": "daily/climate_summary/temperature_air_mean_2m",
    "stations": "01048",
    "format": "csv",
}


def test_no_tool_takes_an_option_that_only_rest_needs() -> None:
    """The input schema of no tool has `pretty`, the size of an image or a skip option, nor offers a chart."""
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
    # the two listings offer all four formats of data
    for name in ("values", "stations"):
        assert set(tools[name].input_schema["properties"]["format"]["enum"]) == DATA_FORMATS, name


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
    for name in ("coverage", "providers", "history", "alerts", "storm_cells", "kostra", "station_ids", "statistics"):
        assert "pretty" in _query_parameters(name), name


def test_the_tools_that_the_refusal_points_to_rest_for_are_those_whose_route_draws_a_chart() -> None:
    """`_CHART_TOOLS` is held to the routes: a tool is told "charts are drawn by the REST API" where they are."""
    draws = {
        name
        for name in _TOOL_NAMES.values()
        if _CHART_FORMATS[0] in _query_parameters(name).get("format", {}).get("schema", {}).get("enum", ())
    }

    assert draws == _CHART_TOOLS


# --- the options a call may still send -------------------------------------------------------------------------------

#: the options of `_REST_ONLY_ARGUMENTS` each route has, as the tools were made before GH-4318 and as the REST API has
#: them still. A route that later gets an option of one of these names does not have it dropped from its tool without
#: a failing test: `test_the_names_are_dropped_where_the_table_says_and_mean_what_they_did` is it, until someone has
#: read what the option means
_OLD_OPTIONS_OF_TOOL: dict[str, set[str]] = {
    "stations": {"pretty", "width", "height", "scale"},
    "values": {"pretty", "width", "height", "scale", "skip_empty", "skip_threshold", "skip_criteria"},
    "interpolate": {"pretty", "width", "height", "scale"},
    "summarize": {"pretty", "width", "height", "scale"},
    "coverage": {"pretty"},
    "providers": {"pretty"},
    "station_ids": {"pretty"},
    "history": {"pretty"},
    "alerts": {"pretty"},
    "storm_cells": {"pretty"},
    "kostra": {"pretty"},
    "statistics": {"pretty"},
    "auth": set(),
    "glossary": set(),
    "issues": set(),
}

#: what the REST API says each of them is
_MEANING = {
    "pretty": "Pretty-print JSON/GeoJSON output.",
    "width": "Width of the rendered chart image in pixels.",
    "height": "Height of the rendered chart image in pixels.",
    "scale": "Scale factor of the rendered chart image.",
    "skip_empty": (
        "Skip stations whose coverage falls below `skip_threshold`. "
        "Default: the server's WD_TS_SKIP_EMPTY if set, else false."
    ),
    "skip_threshold": (
        "Coverage fraction below which a station is skipped (requires `skip_empty`). "
        "Default: the server's WD_TS_SKIP_THRESHOLD if set, else 0.95."
    ),
    "skip_criteria": (
        "Aggregation over the requested parameters' coverage: min, mean or max. "
        "Default: the server's WD_TS_SKIP_CRITERIA if set, else min."
    ),
}


def test_the_names_are_dropped_where_the_table_says_and_mean_what_they_did() -> None:
    """A name is dropped from the tools whose routes have it, and each means what the REST API says of it.

    The set of names is only a list to look for: an option that a later route names `height` (the height of a mast,
    say) is no image height, and must not be dropped from its tool and let go. It fails here instead.
    """
    assert set(_OLD_OPTIONS_OF_TOOL) == set(_TOOL_NAMES.values())
    for name, expected in _OLD_OPTIONS_OF_TOOL.items():
        route = _query_parameters(name)
        assert set(route) & _REST_ONLY_ARGUMENTS == expected, name
        for option in expected:
            assert route[option]["description"] == _MEANING[option], (name, option)
    routes = _routes_of_tools(restapi.app.openapi())
    assert {name: set(route.rest_only) for name, route in routes.items()} == _OLD_OPTIONS_OF_TOOL
    assert {name: route.path for name, route in routes.items()} == {
        name: f"/api/v1/{name.replace('_', '-')}" for name in _TOOL_NAMES.values()
    }


def test_the_old_schemas_had_no_default_for_the_size_options_but_null() -> None:
    """The three had no default: a client that fills in the old schema's defaults sends nothing, or `null`."""
    for name in ("stations", "values", "interpolate", "summarize"):
        route = _query_parameters(name)
        for option in ("width", "height", "scale"):
            schema = route[option]["schema"]
            assert "default" not in schema, (name, option)
            assert {"type": "null"} in schema["anyOf"], (name, option)
        assert route["pretty"]["schema"]["default"] is False, name


def test_an_option_that_means_nothing_is_let_go_and_never_sent_to_the_route() -> None:
    """`pretty` at any value and the size options as `null` are answered as a call without, and are not sent.

    A client that fills in every option with its default sends `pretty=false` and, for the three that had none,
    `null`; refusing them would break a call that works. For a data format they change nothing of the answer.
    """
    app, seen = _stand_in()
    nulls = {"width": None, "height": None, "scale": None}
    calls = [
        ("values", _VALUES_CALL),
        ("values", {**_VALUES_CALL, "pretty": True, **nulls}),
        ("values", {**_VALUES_CALL, "pretty": False}),
        ("values", {**_VALUES_CALL, "pretty": "maybe"}),
    ]

    answers = _calls(app, calls)

    for result, _ in answers:
        assert not result.is_error, result.content
        assert result.content[0].text == answers[0][0].content[0].text
    assert len(seen) == len(calls)
    assert all(request == seen[0] for request in seen)
    assert not _REST_ONLY_ARGUMENTS & set(seen[0])
    assert seen[0]["format"] == "csv"


def _matrix() -> list[tuple[str, str, bool]]:
    """Give each tool with each of the four names, and whether the route of the tool had it."""
    return [
        (tool, option, option in _OLD_OPTIONS_OF_TOOL[tool])
        for tool in _TOOL_NAMES.values()
        for option in sorted(_REST_ONLY_ARGUMENTS)
    ]


def test_an_option_is_let_go_only_by_a_tool_whose_route_took_it() -> None:
    """`pretty` is let go by the tools that took it and refused by `glossary`, `auth` and `issues`, as on main.

    The option is given a value that means nothing (`pretty=true`, `null` for the others). A tool that lets it go
    reaches the route without it; any other refuses it as an argument it does not take. So a set applied to every tool,
    or to the tools that draw a chart only, fails here.
    """
    app, seen = _stand_in()
    matrix = _matrix()
    calls = [{**_required(tool), option: True if option == "pretty" else None} for tool, option, _ in matrix]

    async def call() -> list[tuple[int, str]]:
        """Give for each call how many requests the route had got by then, and what the tool refused with."""
        outcomes = []
        async with Client(build_mcp_server(app)) as client:
            for (tool, _option, _took), arguments in zip(matrix, calls, strict=True):
                refusal = ""
                try:
                    result = await client.call_tool(tool, arguments, raise_on_error=False)
                    refusal = result.content[0].text if result.is_error else ""
                except RuntimeError:
                    # the stand-in's csv is no answer a tool of another format admits: the route was reached
                    pass
                outcomes.append((len(seen), refusal))
        return outcomes

    outcomes = asyncio.run(call())

    before = 0
    for (tool, option, took), (count, refusal) in zip(matrix, outcomes, strict=True):
        if took:
            assert count == before + 1, (tool, option, refusal)
            assert option not in seen[before], (tool, option)
        else:
            assert count == before, (tool, option)
            assert refusal.startswith(f"{option} is not an argument of {tool}, which takes "), (tool, option, refusal)
        before = count


_SIZE_MEANING = {"width": "width in pixels", "height": "height in pixels", "scale": "scale factor"}


@pytest.mark.parametrize(
    ("tool", "option", "value"),
    [
        ("values", "width", 800),
        ("values", "scale", 2.0),
        ("stations", "height", 600),
        ("interpolate", "width", 1),
        ("summarize", "scale", 0),
        ("values", "height", ""),
    ],
)
def test_a_size_option_with_a_value_is_refused_naming_the_route_that_takes_it(
    tool: str,
    option: str,
    value: Any,  # noqa: ANN401
) -> None:
    """A value is no default: it may mean something else to the model, so the call fails and nothing is requested."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [(tool, {**_required(tool), option: value})])

    assert result.is_error
    assert result.content[0].text == (
        f"{option} is not an argument of {tool}: it was the {_SIZE_MEANING[option]} of a chart image, "
        f"and the tool answers data only. Charts are drawn by the REST API: /api/v1/{tool} takes {option}."
    )
    assert seen == []


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_a_height_is_refused_naming_elevation_where_the_tool_takes_it(tool: str) -> None:
    """A model that sends `height=800` to a point tool may mean the elevation: it is told so, not let go.

    Let go, it was silently ignored: the answer was that of the elevation of the stations (2.47 °C against 6.15 °C
    in a live check of `interpolate`).
    """
    app, seen = _stand_in()

    ((point, _), (values, _)) = _calls(
        app, [(tool, {**_required(tool), "height": 800}), ("values", {**_VALUES_CALL, "height": 800})]
    )

    assert point.is_error
    assert point.content[0].text.endswith(" The height of the point above sea level is the argument elevation.")
    assert "elevation" in _tools()[tool].input_schema["properties"]
    assert values.is_error
    assert "elevation" not in values.content[0].text
    assert seen == []


# --- the formats a tool does not offer -------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", _CHART_FORMATS)
def test_a_chart_format_is_refused_where_it_would_have_been_answered_with_an_image(fmt: str) -> None:
    """The error names the format, what the tool answers and the REST route that draws charts; nothing is requested."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("values", {**_VALUES_CALL, "format": fmt})])

    assert result.is_error
    assert result.content[0].text == (
        f"format={fmt} is not offered by the tool values, which answers json, geojson, csv or ndjson. "
        f"Charts are drawn by the REST API: /api/v1/values takes format={fmt}."
    )
    assert seen == []


def test_a_chart_format_of_a_tool_whose_route_never_drew_one_is_refused_without_a_pointer_to_rest() -> None:
    """`alerts` never offered a chart: the call is refused naming what it answers, and REST is not said to draw it."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("alerts", {"format": "png", "latitude": 54.3, "longitude": 10.1})])

    assert result.is_error
    assert result.content[0].text == "format=png is not offered by the tool alerts, which answers json, geojson or csv."
    assert seen == []


@pytest.mark.parametrize(
    ("tool", "fmt", "chart"),
    [
        ("values", "xml", None),
        ("values", "PNG", "png"),
        ("values", "jpeg", None),
        ("values", " png", "png"),
        ("values", "Svg ", "svg"),
        ("values", "", None),
        ("interpolate", "ndjson", None),
        ("summarize", "ndjson", None),
        ("stations", "PDF", "pdf"),
    ],
)
def test_a_format_the_tool_does_not_offer_is_refused_by_the_tool_not_left_to_the_route(
    tool: str, fmt: str, chart: str | None
) -> None:
    """Any `format` outside the list of the tool is its refusal, which lists what the tool answers.

    The route's 422 lists html, png, jpg, webp, svg and pdf as valid, which they are not for a tool, and offers ndjson
    to `interpolate`, which does not answer it. Only a chart format, compared without case and whitespace, is pointed
    to the REST API.
    """
    app, seen = _stand_in()
    offered = _tools()[tool].input_schema["properties"]["format"]["enum"]
    answers = f"{', '.join(offered[:-1])} or {offered[-1]}"

    ((result, _),) = _calls(app, [(tool, {**_required(tool), "format": fmt})])

    assert result.is_error
    expected = f"format={fmt} is not offered by the tool {tool}, which answers {answers}."
    if chart is not None:
        expected += f" Charts are drawn by the REST API: /api/v1/{tool} takes format={chart}."
    assert result.content[0].text == expected
    assert "422" not in result.content[0].text
    assert seen == []


@pytest.mark.parametrize(
    ("given", "refused"),
    [(["png"], ["png"]), (["json", "png"], ["png"]), (["csv", "xml", "svg"], ["xml", "svg"])],
)
def test_each_element_of_a_format_given_as_a_list_is_checked(given: list[str], refused: list[str]) -> None:
    """A list reaches the route as one `format` for each element, so a chart in it would have been answered."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("values", {**_VALUES_CALL, "format": given})])

    assert result.is_error
    text = result.content[0].text
    for fmt in refused:
        assert f"format={fmt} is not offered by the tool values" in text
    assert text.count("is not offered") == len(refused)
    assert seen == []


def test_a_list_of_formats_the_tool_offers_is_left_to_the_route() -> None:
    """Every element offered: the tool refuses nothing (what the route makes of a list is its own)."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("values", {**_VALUES_CALL, "format": ["csv"]})])

    assert not result.is_error, result.content
    assert seen[0]["format"] == "csv"


def test_the_refusals_of_a_call_are_one_error() -> None:
    """A format, a size, a renamed name and an unknown one are told together, not the first and then the next."""
    app, seen = _stand_in()
    arguments = {**_VALUES_CALL, "format": "png", "width": 100, "bogus": 1, "date": "2020"}

    ((result, _),) = _calls(app, [("values", arguments)])

    assert result.is_error
    parts = result.content[0].text.split("; ")
    assert parts[0].startswith("format=png is not offered by the tool values")
    assert parts[1].startswith("width is not an argument of values: it was the width in pixels")
    assert any(part.startswith("date ") for part in parts)
    assert any(part.startswith("bogus is not an argument of values, which takes ") for part in parts)
    assert len(parts) == 4
    assert seen == []


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


# --- the options that leave a station out (GH-4471) ------------------------------------------------------------------

_SKIP_OPTIONS = ("skip_empty", "skip_threshold", "skip_criteria")
#: the default each had, which a call may still send
_SKIP_DEFAULTS = {"skip_empty": False, "skip_threshold": 0.95, "skip_criteria": "min"}


def test_no_tool_schema_instruction_or_description_names_a_skip_option() -> None:
    """The three options are in the input schema of no tool, and no text the server hands a client names them."""
    server = build_mcp_server(restapi.app)

    for name, tool in _tools().items():
        assert not set(_SKIP_OPTIONS) & set(tool.input_schema.get("properties", {})), name
        for option in _SKIP_OPTIONS:
            assert option not in json.dumps(tool.input_schema), (name, option)
            assert option not in (tool.description or ""), (name, option)
    for option in _SKIP_OPTIONS:
        assert option not in (server.instructions or ""), option


def test_only_values_had_the_skip_options_and_rest_still_takes_them_with_the_defaults_the_tool_lets_go() -> None:
    """One route has them: the REST API documents them still, with the defaults a client may send."""
    holders = {name for name in _TOOL_NAMES.values() if set(_SKIP_OPTIONS) & set(_query_parameters(name))}
    assert holders == {"values"}
    route = _query_parameters("values")
    assert {name: route[name]["schema"]["default"] for name in _SKIP_OPTIONS} == _SKIP_DEFAULTS


def test_a_skip_option_at_its_default_or_null_is_answered_as_a_call_without_and_is_not_sent() -> None:
    """A client that fills in the old schema's defaults is not refused for it, and the route never sees them."""
    app, seen = _stand_in()
    calls = [
        ("values", _VALUES_CALL),
        ("values", {**_VALUES_CALL, **_SKIP_DEFAULTS}),
        ("values", {**_VALUES_CALL, "skip_empty": None, "skip_threshold": None, "skip_criteria": None}),
        ("values", {**_VALUES_CALL, "skip_empty": False}),
        ("values", {**_VALUES_CALL, "skip_empty": "false", "skip_threshold": "0.95", "skip_criteria": "min"}),
    ]

    answers = _calls(app, calls)

    for result, _ in answers:
        assert not result.is_error, result.content
        assert result.content[0].text == answers[0][0].content[0].text
    assert len(seen) == len(calls)
    assert all(request == seen[0] for request in seen)
    assert not set(_SKIP_OPTIONS) & set(seen[0])


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("skip_empty", True),
        ("skip_empty", 0),
        ("skip_empty", "true"),
        ("skip_empty", "maybe"),
        ("skip_threshold", "0.5"),
        ("skip_threshold", "x"),
        ("skip_threshold", 0.5),
        ("skip_threshold", 1),
        ("skip_criteria", "mean"),
        ("skip_criteria", "max"),
        ("skip_criteria", ""),
    ],
)
def test_a_skip_option_with_another_value_is_refused_saying_how_to_get_the_same(
    option: str,
    value: Any,  # noqa: ANN401
) -> None:
    """The call is a tool error that names the option, what to do instead and the route; nothing is requested."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [("values", {**_VALUES_CALL, option: value})])

    assert result.is_error
    text = result.content[0].text
    assert text.startswith(f"{option} is not an argument of values: it was ")
    assert "the tool answers every station it is asked for" in text
    assert "Leave the stations without rows in `values` out of the answer yourself" in text
    assert text.endswith(f"or call the REST API: /api/v1/values takes {option}.")
    assert text.count("is not an argument") == 1
    assert seen == []


def test_every_skip_option_with_a_value_is_told_in_one_error() -> None:
    """The three are named together, with the other refusals of the call, not one after the next."""
    app, seen = _stand_in()
    arguments = {**_VALUES_CALL, "skip_empty": True, "skip_threshold": 0.5, "skip_criteria": "max", "bogus": 1}

    ((result, _),) = _calls(app, [("values", arguments)])

    assert result.is_error
    parts = result.content[0].text.split("; ")
    assert [part.split(" ")[0] for part in parts[:3]] == ["skip_criteria", "skip_empty", "skip_threshold"]
    assert parts[3].startswith("bogus is not an argument of values, which takes ")
    assert seen == []


@pytest.mark.parametrize("tool", ["interpolate", "summarize", "stations"])
def test_a_tool_whose_route_never_took_a_skip_option_refuses_it_as_unknown(tool: str) -> None:
    """`interpolate` never had them: `skip_empty` is an argument it does not take, as before."""
    app, seen = _stand_in()

    ((result, _),) = _calls(app, [(tool, {**_required(tool), "skip_empty": True})])

    assert result.is_error
    assert result.content[0].text.startswith(f"skip_empty is not an argument of {tool}, which takes ")
    assert seen == []


def test_rest_still_takes_the_skip_options() -> None:
    """The REST route reads them: `skip_threshold=2` is its 422, which only a route that takes the option says."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    response = TestClient(restapi.app).get(
        "/api/v1/values",
        params={**_VALUES_CALL, "format": "json", "skip_threshold": 2},
    )

    assert response.status_code == 422
    assert "skip_threshold" in response.text


def test_the_command_line_still_takes_the_skip_options() -> None:
    """`wetterdienst values --help` lists them."""
    from click.testing import CliRunner  # noqa: PLC0415

    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    help_text = CliRunner().invoke(cli, ["values", "--help"]).output

    for option in ("--skip-empty", "--skip-threshold", "--skip-criteria"):
        assert option in help_text


def test_python_still_takes_the_skip_options() -> None:
    """`Options` holds them."""
    from wetterdienst import Options  # noqa: PLC0415

    options = Options(skip_empty=True, skip_threshold=0.5, skip_criteria="max")

    assert (options.skip_empty, options.skip_threshold, options.skip_criteria) == (True, 0.5, "max")
