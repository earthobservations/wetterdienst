# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every format an MCP tool advertises comes back as a valid answer, and the row limit names what helps (GH-3464).

The tools are the routes of the REST API run in process. FastMCP reads a route's answer as JSON: a text body (csv,
ndjson, html, svg) it passed on without structured content, which the output schema of the tool refuses ("has an
output schema but did not return structured content"), and a binary one (png, jpg, webp, pdf) it failed to decode. And
the refusal of a row limit told an assistant to use `format=ndjson` or `format=csv`, which it could not.

Offline: the selection of the stations and the reader are stood in for, as in `test_operations.py`.

Building a server and opening a session is most of what a call costs, so a test makes all of its calls in one session.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
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
from wetterdienst.ui.mcp import _mark_tool_requests, _report_of, _sentence_of, build_mcp_server

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

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


def _calls(
    app: FastAPI, calls: Sequence[tuple[str, Mapping[str, Any]]]
) -> list[tuple[ToolResult, dict[str, Any] | None]]:
    """Make the calls on one server built from `app`, in one session; give each result with its tool's output schema."""

    async def call() -> list[tuple[ToolResult, dict[str, Any] | None]]:
        async with Client(build_mcp_server(app)) as client:
            schemas = {tool.name: tool.output_schema for tool in await client.list_tools()}
            return [
                (await client.call_tool(tool, dict(arguments), raise_on_error=False), schemas[tool])
                for tool, arguments in calls
            ]

    return asyncio.run(call())


def _call(app: FastAPI, tool: str, arguments: Mapping[str, Any]) -> tuple[ToolResult, dict[str, Any] | None]:
    """Call a tool of the server built from `app`; give the result and the output schema the tool declares."""
    return _calls(app, [(tool, arguments)])[0]


def _every_format(tool: str, arguments: Mapping[str, Any]) -> tuple[dict[str, ToolResult], dict[str, Any] | None]:
    """Call a tool of the real app in each format its input schema offers, in one session.

    Gives the results by format and the output schema of the tool.
    """

    async def call() -> tuple[dict[str, ToolResult], dict[str, Any] | None]:
        async with Client(build_mcp_server(restapi.app)) as client:
            listed = next(t for t in await client.list_tools() if t.name == tool)
            formats = listed.input_schema["properties"]["format"]["enum"]
            answers = {
                fmt: await client.call_tool(tool, {**arguments, "format": fmt}, raise_on_error=False) for fmt in formats
            }
            return answers, listed.output_schema

    return asyncio.run(call())


def _warn_then_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Have the reader raise a warning of the response before it gives its values."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415
    from wetterdienst.util.response_warnings import warn_response  # noqa: PLC0415

    def query(_reader: object) -> Any:  # noqa: ANN401
        warn_response(restapi.log, "station-skipped", "station 00002 is skipped")
        yield _values_result_of_shape("long")

    monkeypatch.setattr(DwdObservationRequest._values, "query", query)  # noqa: SLF001


@pytest.mark.parametrize("tool", ["values", "stations"])
def test_a_tool_that_advertises_a_format_answers_in_it(tool: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each format of `values` and `stations` is an answer without an error whose structured content fits the schema.

    And it says whose data it is: the licence and the attribution, which REST sends in headers for the formats that
    have no body for the `metadata` block, and, for `values`, the warning the reader raised.
    """
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])
    arguments = {**_VALUES, "parameters": "daily/climate_summary/temperature_air_mean_2m"}
    if tool == "stations":
        arguments = {key: value for key, value in arguments.items() if key != "stations"} | {"all": True}
    else:
        _warn_then_answer(monkeypatch)

    answers, schema = _every_format(tool, arguments)

    # the point of the test: it holds the tool to everything it offers, not to a list kept here
    assert {"json", "csv", "ndjson", "html", "png"} <= set(answers)
    for fmt, result in answers.items():
        assert not result.is_error, (fmt, result.content)
        assert isinstance(result.content[0], _BLOCK_OF_FORMAT[fmt]), fmt
        assert result.structured_content is not None, fmt
        jsonschema.validate(result.structured_content, schema)
        told = json.dumps(result.structured_content)
        assert "CC-BY-4.0" in told, fmt
        if tool == "values":
            assert "station-skipped" in told, fmt
        if fmt not in ("json", "geojson"):
            assert "Attribution: " in told, fmt
            assert result.meta["wetterdienst"]["license"] == "CC-BY-4.0", fmt
            # the `Link` header of the answer is carried, and the sentence names the terms
            assert result.meta["wetterdienst"]["license_url"] == "https://creativecommons.org/licenses/by/4.0/", fmt
            assert "(https://creativecommons.org/licenses/by/4.0/)" in told, fmt
            if tool == "values":
                assert result.meta["wetterdienst"]["warnings"] == ["station-skipped"], fmt


def test_each_kind_of_body_arrives_as_its_own_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """Text is the content of the result as the REST API sends it, and not repeated in the structured content.

    An image is image content of its media type, a pdf an embedded resource, and a json answer stays structured.
    """
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])

    (csv, _), (ndjson, _), (png, _), (pdf, _), (json_, _) = _calls(
        restapi.app, [("values", {**_VALUES, "format": fmt}) for fmt in ("csv", "ndjson", "png", "pdf", "json")]
    )

    assert csv.content[0].text.splitlines()[0].startswith("station_id,resolution,")
    assert csv.content[0].text.splitlines()[1].startswith("01048,daily,")
    sent = f"The answer is text/csv ({len(csv.content[0].text.encode()):,} bytes), sent as text content of this result."
    assert csv.structured_content["result"].startswith(sent)
    lines = ndjson.content[0].text.splitlines()
    assert '"metadata"' in lines[0]
    assert lines[-1].startswith('{"end"')
    assert png.content[0].mime_type == "image/png"
    assert base64.b64decode(png.content[0].data).startswith(b"\x89PNG")
    size = len(base64.b64decode(png.content[0].data))
    sent = f"The answer is image/png ({size:,} bytes), sent as image content of this result."
    assert png.structured_content["result"].startswith(sent)
    assert pdf.content[0].resource.mime_type == "application/pdf"
    assert base64.b64decode(pdf.content[0].resource.blob).startswith(b"%PDF")
    assert json_.structured_content["result"]["values"][0]["station_id"] == "01048"


@pytest.mark.parametrize(("fmt", "block"), [("png", ImageContent), ("svg", TextContent), ("pdf", EmbeddedResource)])
def test_the_stripes_image_tool_reports_the_licence_the_attribution_and_the_warnings(
    fmt: str, block: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The image has no `metadata` block, so the headers of the route are what a tool reports them from (GH-3581)."""
    from tests.ui.test_restapi import _stub_stripes_station  # noqa: PLC0415
    from wetterdienst.ui import core  # noqa: PLC0415
    from wetterdienst.util.response_warnings import warn_response  # noqa: PLC0415

    _stub_stripes_station(monkeypatch, "temperature", [1.0, 2.0])
    read = core._get_stripes_data  # noqa: SLF001

    def read_and_warn(request: object) -> object:
        warn_response(restapi.log, "station-skipped", "station 00002 is skipped")
        return read(request)

    class _Figure:
        def to_image(self, *_args: object, **_kwargs: object) -> bytes:
            return b"<svg xmlns='http://www.w3.org/2000/svg'/>" if fmt == "svg" else b"\x89PNG\r\n\x1a\n"

    monkeypatch.setattr(restapi, "_get_stripes_data", read_and_warn)
    monkeypatch.setattr(restapi, "_draw_stripes", lambda _data, _request: _Figure())

    result, schema = _call(restapi.app, "stripes_image", {"kind": "temperature", "station": "01048", "format": fmt})

    assert not result.is_error, result.content
    assert isinstance(result.content[0], block)
    report = result.meta["wetterdienst"]
    assert report["license"] == "CC-BY-4.0"
    assert report["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert "Deutscher Wetterdienst" in report["attribution"]
    assert report["warnings"] == ["station-skipped"]
    if schema is not None:
        sentence = result.structured_content["result"]
        assert "Licence: CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/)." in sentence
        assert "Attribution: " in sentence
        assert sentence.endswith("Warnings: station-skipped.")


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


def _app_with_answers() -> FastAPI:
    """Build a REST app with the route of the stripes image, which declares no output schema.

    It answers what `format` names, to try the transport on each kind of answer.
    """
    app = FastAPI()
    answers = {
        "svg": lambda: Response(b"<svg xmlns='http://www.w3.org/2000/svg'/>", media_type="image/svg+xml"),
        "png": lambda: Response(b"\x89PNG\r\n\x1a\n\x00\xff", media_type="image/png"),
        "plain_4xx": lambda: Response(b"nope", status_code=400, media_type="text/plain"),
        "no_content_type": lambda: Response(b'{"a": 1}'),
        "geo_json": lambda: Response(b'{"type": "FeatureCollection"}', media_type="application/geo+json"),
        "latin1": lambda: Response(b"caf\xe9", headers={"content-type": "text/csv; charset=latin-1"}),
        "broken_utf8": lambda: Response(b"a\xffb", media_type="text/csv"),
        "unknown_charset": lambda: Response(b"abc", headers={"content-type": "text/csv; charset=nonsense"}),
    }

    @app.get("/api/stripes/image", response_class=Response)
    def stripes_image(format: str) -> Response:  # noqa: A002
        return answers[format]()

    return app


def test_the_transport_carries_what_is_not_json_and_leaves_the_rest_alone() -> None:
    """Without an output schema the body is the content alone; a failure, JSON and a body of no type are as they were.

    A text body is decoded with the charset of its media type, and none that is invalid or unknown is an error.
    """
    names = ["svg", "png", "plain_4xx", "no_content_type", "geo_json", "latin1", "broken_utf8", "unknown_charset"]

    answers = _calls(_app_with_answers(), [("stripes_image", {"format": name}) for name in names])
    (svg, schema), (png, _), (refused, _), (typeless, _), (geo, _), (latin1, _), (broken, _), (unknown, _) = answers

    assert schema is None
    assert not svg.is_error
    assert svg.content[0].text.startswith("<svg")
    assert svg.structured_content is None
    assert not png.is_error
    assert base64.b64decode(png.content[0].data).startswith(b"\x89PNG")
    # a 400 in text is the tool's error, with the text of the answer and not the envelope
    assert refused.is_error
    assert "400" in refused.content[0].text
    assert "nope" in refused.content[0].text
    assert "x-wetterdienst-body" not in refused.content[0].text
    # nothing says it is not JSON, so FastMCP reads it as it always did
    assert not typeless.is_error
    assert typeless.structured_content == {"a": 1}
    # `application/geo+json` is JSON, not a binary body
    assert not geo.is_error
    assert geo.structured_content == {"type": "FeatureCollection"}
    for result, text in ((latin1, "caf\xe9"), (broken, "a�b"), (unknown, "abc")):
        assert not result.is_error
        assert result.content[0].text == text


def _headers(attribution: str, link: str) -> dict[str, str]:
    """Write the headers of an answer as `response_headers` does: text percent-encoded, the names in lower case."""
    from wetterdienst.ui.response_metadata import _header_text  # noqa: PLC0415

    return {
        "x-wetterdienst-license": _header_text("Licence Ouverte v2.0 (Etalab) é"),
        "link": link,
        "x-wetterdienst-attribution": _header_text(attribution),
        "x-wetterdienst-warnings": "station-skipped, parameter-without-rows",
    }


def test_the_report_and_the_sentence_read_what_the_headers_write() -> None:
    """The licence with its URL (the first Link, a deprecation's after it), the attribution and the warnings."""
    link = (
        '<https://www.etalab.gouv.fr/licence>; rel="license", '
        '<https://wetterdienst.eobs.org/api/v1/values>; rel="successor-version"'
    )

    report = _report_of(_headers("© Météo-France", link))

    assert report == {
        "license": "Licence Ouverte v2.0 (Etalab) é",
        "license_url": "https://www.etalab.gouv.fr/licence",
        "attribution": "© Météo-France",
        "warnings": ["station-skipped", "parameter-without-rows"],
    }
    assert _sentence_of("text/csv", 1234, "text content", report) == (
        "The answer is text/csv (1,234 bytes), sent as text content of this result. "
        "Licence: Licence Ouverte v2.0 (Etalab) é (https://www.etalab.gouv.fr/licence). "
        "Attribution: © Météo-France. Warnings: station-skipped, parameter-without-rows."
    )


def test_an_attribution_that_ends_in_a_period_does_not_get_a_second() -> None:
    """IMGW's attribution ends in a period, which the sentence's own is not added to."""
    report = _report_of(_headers("Source: IMGW-PIB.", '<https://example.org/licence>; rel="license"'))

    assert "Attribution: Source: IMGW-PIB. Warnings" in _sentence_of("text/csv", 1, "text content", report)


def test_an_answer_without_a_licence_or_warnings_has_a_plain_sentence() -> None:
    """A report that is empty adds nothing to the sentence."""
    assert _report_of({}) == {}
    assert _sentence_of("image/png", 3, "image content", {}) == (
        "The answer is image/png (3 bytes), sent as image content of this result."
    )


def test_the_tool_wrapper_sets_plotly_to_the_cdn_for_its_request_only() -> None:
    """The handler sees the CDN, and the caller's context has the default again once the request is done."""
    import httpx2  # noqa: PLC0415

    from wetterdienst.io.export import HTML_PLOTLYJS  # noqa: PLC0415

    app = FastAPI()
    seen: list[bool | str] = []

    @app.get("/page")
    def page() -> dict[str, str]:
        seen.append(HTML_PLOTLYJS.get())
        return {}

    async def request() -> bool | str:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=_mark_tool_requests(app)), base_url="http://t"
        ) as client:
            await client.get("/page")
        return HTML_PLOTLYJS.get()

    after = asyncio.run(request())

    assert seen == ["cdn"]
    assert after is True


def test_an_html_chart_through_a_tool_does_not_carry_plotly_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plotly.js is 4.8 MB inline; a tool's page loads it from the CDN, and the REST page is as it was."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    _stub_stream(monkeypatch, [_values_result_of_shape("long")])

    result, _ = _call(restapi.app, "values", {**_VALUES, "format": "html"})
    rest = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/v1/values", params={**_VALUES, "format": "html"}
    )

    assert len(result.content[0].text) < 100_000
    assert "cdn.plot.ly" in result.content[0].text
    assert len(rest.text) > 1_000_000


# --- an answer that fails is a tool error, not a short answer ------------------------------------------------------


def test_a_failure_while_collecting_is_a_tool_error_not_a_partial_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool's body is built before the response begins, so a station that fails fails the call.

    A stream answered 200 and was cut: through a tool that was a successful, complete-looking answer.
    """
    record = _selection_of(2)
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], error=RuntimeError("boom"), stations_df=record)

    answers = _calls(
        restapi.app, [("values", {**_VALUES, "stations": "00000,00001", "format": fmt}) for fmt in ("csv", "ndjson")]
    )

    assert all(result.is_error for result, _ in answers)


def test_a_timeout_while_collecting_is_a_tool_error_that_names_no_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request that outlasts the timeout is a 504 through a tool in csv too, without the advice to stream."""
    import time  # noqa: PLC0415

    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    _stub_stream(monkeypatch, [_values_result_of_shape("long")])
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")

    def slow(_reader: object) -> Any:  # noqa: ANN401
        time.sleep(1.5)
        yield _values_result_of_shape("long")

    monkeypatch.setattr(DwdObservationRequest._values, "query", slow)  # noqa: SLF001

    answers = _calls(restapi.app, [("values", {**_VALUES, "format": fmt}) for fmt in ("csv", "ndjson")])

    for result, _ in answers:
        assert result.is_error
        text = result.content[0].text
        assert "request timeout of 0.3 seconds" in text
        for streaming in ("ndjson", "csv", "stream"):
            assert streaming not in text


# --- the refusal of a row limit -----------------------------------------------------------------------------------


def _over_the_row_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    record = _selection_of(1, start=dt.datetime(1950, 1, 1, tzinfo=dt.UTC), end=dt.datetime(2020, 1, 1, tzinfo=dt.UTC))
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=record)


def test_a_tool_is_held_to_the_rows_limit_in_every_format_and_told_what_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool answers one body: json, csv and ndjson over `rows` are refused, csv and ndjson being under `stream_rows`.

    It is told a shorter window, fewer parameters or fewer stations, and not to stream (GH-3464).
    """
    _over_the_row_limit(monkeypatch)

    answers = _calls(restapi.app, [("values", {**_VALUES, "format": fmt}) for fmt in ("json", "csv", "ndjson")])

    for result, _ in answers:
        assert result.is_error
        text = result.content[0].text
        assert "more than the 1,000 this server sends as one answer" in text
        assert "Ask for a shorter `timestamp` window, fewer `parameters` or fewer stations." in text
        for streaming in ("ndjson", "csv", "stream"):
            assert streaming not in text


def test_the_stations_tool_is_held_to_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """A listing through a tool is one body too: over `rows` it is refused in csv and ndjson, saying what works."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "10")
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=_selection_of(30))
    arguments = {key: value for key, value in _VALUES.items() if key != "stations"} | {"all": True}

    answers = _calls(restapi.app, [("stations", {**arguments, "format": fmt}) for fmt in ("csv", "ndjson")])

    for result, _ in answers:
        assert result.is_error
        assert "more than the 10 this server sends as one answer" in result.content[0].text
        for word in ("ndjson", "csv", "stream"):
            assert word not in result.content[0].text


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
