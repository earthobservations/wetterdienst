# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every format an MCP tool advertises comes back as a valid answer, and the row limit names what helps (GH-3464).

The tools are the routes of the REST API run in process. FastMCP reads a route's answer as JSON: a text body (csv,
ndjson, html, svg) it passed on without structured content, which the output schema of the tool refuses ("has an
output schema but did not return structured content"), and a binary one (png, jpg, webp, pdf) it failed to decode. And
the refusal of a row limit told an assistant to use `format=ndjson` or `format=csv`, which it could not.

Offline: the selection of the stations and the reader are stood in for, as in `test_operations.py`.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("fastmcp")
pytest.importorskip("jsonschema")

import jsonschema
from fastapi import FastAPI, Response
from fastmcp import Client
from mcp_types import EmbeddedResource, ImageContent, TextContent

from tests.ui.test_operations import _VALUES, _no_ambient_settings, _selection_of  # noqa: F401
from tests.ui.test_restapi import _stub_stream, _values_result_of_shape
from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import build_mcp_server

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastmcp.tools import ToolResult

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

#: what each format of a chart or a listing comes back as through a tool
_BLOCK_OF_FORMAT: dict[str, type] = {
    "json": TextContent,
    "geojson": TextContent,
    "csv": TextContent,
    "ndjson": TextContent,
    "html": TextContent,
    "svg": TextContent,
    "png": ImageContent,
    "jpg": ImageContent,
    "webp": ImageContent,
    "pdf": EmbeddedResource,
}


def _call(app: FastAPI, tool: str, arguments: Mapping[str, Any]) -> tuple[ToolResult, dict[str, Any] | None]:
    """Call a tool of the server built from `app`; give the result and the output schema the tool declares."""

    async def call() -> tuple[ToolResult, dict[str, Any] | None]:
        async with Client(build_mcp_server(app)) as client:
            schema = next(t for t in await client.list_tools() if t.name == tool).output_schema
            return await client.call_tool(tool, dict(arguments), raise_on_error=False), schema

    return asyncio.run(call())


def _advertised(tool: str) -> list[str]:
    """Give the formats the input schema of a tool offers."""

    async def listed() -> list[str]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return next(t for t in await client.list_tools() if t.name == tool).input_schema["properties"]["format"][
                "enum"
            ]

    return asyncio.run(listed())


@pytest.mark.parametrize("tool", ["values", "stations"])
def test_a_tool_that_advertises_a_format_answers_in_it(tool: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each format of `values` and `stations` is an answer without an error whose structured content fits the schema."""
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])
    arguments = {**_VALUES, "parameters": "daily/climate_summary/temperature_air_mean_2m"}
    if tool == "stations":
        arguments = {key: value for key, value in arguments.items() if key != "stations"} | {"all": True}
    formats = _advertised(tool)
    # the point of the test: it holds the tool to everything it offers, not to a list kept here
    assert {"json", "csv", "ndjson", "html", "png"} <= set(formats)

    for fmt in formats:
        result, schema = _call(restapi.app, tool, {**arguments, "format": fmt})

        assert not result.is_error, (fmt, result.content)
        assert isinstance(result.content[0], _BLOCK_OF_FORMAT[fmt]), fmt
        assert result.structured_content is not None, fmt
        jsonschema.validate(result.structured_content, schema)


def test_csv_and_ndjson_are_text_content_as_the_rest_api_answers_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """The body is the content of the result, not repeated in the structured content that describes it."""
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])

    csv, _ = _call(restapi.app, "values", {**_VALUES, "format": "csv"})
    ndjson, _ = _call(restapi.app, "values", {**_VALUES, "format": "ndjson"})

    assert csv.content[0].text.splitlines()[0].startswith("station_id,resolution,")
    assert csv.content[0].text.splitlines()[1].startswith("01048,daily,")
    assert csv.structured_content == {
        "result": f"The answer is text/csv ({len(csv.content[0].text):,} bytes), sent as text content of this result."
    }
    lines = ndjson.content[0].text.splitlines()
    assert '"metadata"' in lines[0]
    assert lines[-1].startswith('{"end"')


def test_an_image_is_image_content_and_a_pdf_an_embedded_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bytes of a chart arrive as base64 of the right media type."""
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])

    png, _ = _call(restapi.app, "values", {**_VALUES, "format": "png"})
    pdf, _ = _call(restapi.app, "values", {**_VALUES, "format": "pdf"})

    assert png.content[0].mimeType == "image/png"
    assert base64.b64decode(png.content[0].data).startswith(b"\x89PNG")
    assert pdf.content[0].resource.mimeType == "application/pdf"
    assert base64.b64decode(pdf.content[0].resource.blob).startswith(b"%PDF")


def test_a_json_answer_is_still_the_structured_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON and GeoJSON are not touched: the structured content is the answer."""
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])

    result, _ = _call(restapi.app, "values", {**_VALUES, "format": "json"})

    assert result.structured_content["result"]["values"][0]["station_id"] == "01048"


def test_every_tool_with_a_format_that_is_no_json_admits_a_string_for_it() -> None:
    """The structured content of such an answer is a sentence, which the output schema of the tool has to admit.

    The tools of the other routes (`interpolate`, `summarize`, `alerts`, the stripes) are checked by their schema:
    their routes have the `str` of csv in the response model, as `values` has.
    """

    async def tools() -> list[Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return await client.list_tools()

    checked = []
    for tool in asyncio.run(tools()):
        formats = set(tool.input_schema.get("properties", {}).get("format", {}).get("enum", ()))
        if not formats - {"json", "geojson"}:
            continue
        checked.append(tool.name)
        if tool.output_schema is not None:
            jsonschema.validate({"result": "a sentence"}, tool.output_schema)
    assert {"values", "stations", "interpolate", "summarize", "alerts", "stripes_values", "stripes_image"} <= set(
        checked
    )


def _app_with_stripes_image() -> FastAPI:
    """Build a REST app with the route of the stripes image, which declares no output schema."""
    app = FastAPI()
    media = {"svg": "image/svg+xml", "png": "image/png"}
    body = {"svg": b"<svg xmlns='http://www.w3.org/2000/svg'/>", "png": b"\x89PNG\r\n\x1a\n\x00\xff"}

    @app.get("/api/stripes/image", response_class=Response)
    def stripes_image(format: str = "png") -> Response:  # noqa: A002
        return Response(body[format], media_type=media[format])

    return app


def test_a_tool_without_an_output_schema_answers_the_body_as_content_alone() -> None:
    """The stripes image has no output schema: its svg is text and its png an image, with no structured content."""
    app = _app_with_stripes_image()

    svg, schema = _call(app, "stripes_image", {"format": "svg"})
    png, _ = _call(app, "stripes_image", {"format": "png"})

    assert schema is None
    assert not svg.is_error
    assert svg.content[0].text.startswith("<svg")
    assert not png.is_error
    assert base64.b64decode(png.content[0].data).startswith(b"\x89PNG")


# --- the refusal of a row limit -----------------------------------------------------------------------------------


def _over_the_row_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    record = _selection_of(1, start=dt.datetime(1950, 1, 1, tzinfo=dt.UTC), end=dt.datetime(2020, 1, 1, tzinfo=dt.UTC))
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=record)


def test_the_refusal_through_a_tool_names_the_ways_that_work_through_a_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool is told a shorter window, fewer parameters or fewer stations, and not to stream."""
    _over_the_row_limit(monkeypatch)

    result, _ = _call(restapi.app, "values", _VALUES)

    assert result.is_error
    text = result.content[0].text
    assert "more than the 1,000 this server sends as one answer" in text
    assert "Ask for a shorter `timestamp` window, fewer `parameters` or fewer stations." in text
    for streaming in ("ndjson", "csv", "stream"):
        assert streaming not in text


@pytest.mark.parametrize("fmt", ["csv", "ndjson"])
def test_a_tool_is_held_to_the_rows_limit_in_every_format(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """A tool answers one body: csv and ndjson over `rows` are refused though they are under `stream_rows` (GH-3464)."""
    _over_the_row_limit(monkeypatch)

    result, _ = _call(restapi.app, "values", {**_VALUES, "format": fmt})

    assert result.is_error
    text = result.content[0].text
    assert "more than the 1,000 this server sends as one answer" in text
    assert "Ask for a shorter `timestamp` window, fewer `parameters` or fewer stations." in text
    for streaming in ("ndjson", "csv", "stream"):
        assert streaming not in text


@pytest.mark.parametrize("fmt", ["csv", "ndjson"])
def test_a_stream_over_http_is_held_to_stream_rows_still(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """REST keeps streaming csv and ndjson up to `stream_rows`."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    _over_the_row_limit(monkeypatch)

    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/v1/values", params={**_VALUES, "format": fmt}
    )

    assert response.status_code == 200


def test_the_timeout_through_a_tool_does_not_advise_a_stream() -> None:
    """The 504 text names a stream for REST and not for a tool."""
    from wetterdienst.ui.middleware import timeout_detail  # noqa: PLC0415

    assert "format=ndjson or csv" in timeout_detail(30)
    tool = timeout_detail(30, tool=True)
    assert "a shorter `timestamp` window, fewer stations or parameters." in tool
    assert "ndjson" not in tool
    assert "csv" not in tool


def test_the_refusal_over_http_still_advises_the_stream_and_keeps_its_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    """REST and CLI keep their advice, and the problem keeps `limit`, `maximum` and `requested`."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    _over_the_row_limit(monkeypatch)

    response = TestClient(restapi.app, raise_server_exceptions=False).get("/api/v1/values", params=_VALUES)

    body = response.json()
    assert (body["limit"], body["maximum"]) == ("rows", 1000)
    assert body["requested"] > 1000
    assert "or use `format=ndjson` or `format=csv`" in body["detail"]
