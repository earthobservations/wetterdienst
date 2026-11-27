# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The text of a tool error is the REST API's `detail` as it is, with FastMCP's frame around it (GH-4384).

FastMCP writes the body of a failed upstream call into the tool error: `HTTP error <status>: <phrase> - <body>`.
From 4.1.5 it reads the body as JSON where it can and writes it with `json.dumps`, so a REST answer that is a JSON
string came out in quotes, with a line break as a backslash and an n. The REST app answers a tool's request with
`text/plain` instead, which FastMCP appends as it is. A model reads prose, not JSON.

Offline: the routes are made to fail by what their reader raises.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("fastmcp")

import httpx2
from fastapi import FastAPI, HTTPException, Response
from fastmcp import Client
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from wetterdienst import exceptions
from wetterdienst.ui import limits as limits_module
from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import _TOOL_NAMES, _TOOL_REQUEST_SCOPE_KEY, build_mcp_server
from wetterdienst.ui.problems import PROBLEM_MEDIA_TYPE, problem_response

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

_LIMITS = limits_module.Limits(
    max_stations=10, max_rows=100_000, max_stream_rows=1_000_000, max_groups=1, timeout=1, max_concurrent=0
)


def _limit_of_stations() -> Exception:
    try:
        limits_module.check_station_count(120, _LIMITS)
    except Exception as error:  # noqa: BLE001
        return error
    raise AssertionError


def _limit_of_rows() -> Exception:
    try:
        limits_module.check_rows(5_000_000, _LIMITS, streamed=False)
    except Exception as error:  # noqa: BLE001
        return error
    raise AssertionError


def _raising(error: Exception) -> Callable[..., None]:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise error

    return fail


async def _text_of_error(app: FastAPI, tool: str, arguments: dict[str, Any]) -> str:
    async with Client(build_mcp_server(app)) as client:
        with pytest.raises(ToolError) as error:
            await client.call_tool(tool, arguments)
    return str(error.value)


def _tool_error(tool: str, arguments: dict[str, Any], app: FastAPI | None = None) -> str:
    return asyncio.run(_text_of_error(app or restapi.app, tool, arguments))


def _frame(tool: str, status: int, detail: str) -> str:
    return f"Error calling tool '{tool}': HTTP error {status}: {httpx2.codes.get_reason_phrase(status)} - {detail}"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(exceptions.RequestError("plain request problem"), 400, id="400"),
        pytest.param(HTTPException(403, "no access here"), 403, id="403"),
        pytest.param(exceptions.NotFoundError("Station 99999 does not exist"), 404, id="404"),
        pytest.param(exceptions.MissingDependencyError("needs `radar`"), 501, id="501"),
        pytest.param(exceptions.UpstreamError("the provider answered garbage"), 502, id="502"),
        pytest.param(exceptions.NoInternetError("no connection to https://example.org"), 503, id="503"),
        pytest.param(
            exceptions.RequestError('say "hi"\nsecond line \\ back\\slash\ttab'), 400, id="quotes-and-escapes"
        ),
        pytest.param(exceptions.NotFoundError("Düsseldorf – Köln ☃"), 404, id="non-ascii"),  # noqa: RUF001
    ],
)
def test_a_tool_error_is_the_detail_of_the_rest_answer_in_the_frame_of_fastmcp(
    monkeypatch: pytest.MonkeyPatch, error: Exception, status: int
) -> None:
    """What follows `HTTP error <status>: <phrase> - ` is the `detail` the REST API answers, byte for byte."""
    monkeypatch.setattr("wetterdienst.ui.restapi.get_glossary", _raising(error))

    rest = TestClient(restapi.app, raise_server_exceptions=False).get("/api/v1/glossary")
    assert rest.status_code == status
    detail = rest.json()["detail"]

    message = _tool_error("glossary", {})

    assert message == _frame("glossary", status, detail)
    # not a JSON string: no quote around it, no escape in it
    assert not message.endswith('"')
    assert "\\n" not in message


def test_a_500_of_a_tool_ends_with_the_request_id_of_the_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The REST problem carries `request_id` and the tool's text has no field: the text ends with it (GH-4469)."""
    monkeypatch.setattr("wetterdienst.ui.restapi.get_glossary", _raising(RuntimeError("/srv/secret/path")))
    rest = TestClient(restapi.app, raise_server_exceptions=False).get("/api/v1/glossary")
    assert rest.status_code == 500
    sentence = rest.json()["detail"]
    assert sentence == "Internal server error (RuntimeError). The cause is in the server log."

    message = _tool_error("glossary", {})

    found = re.fullmatch(_frame("glossary", 500, re.escape(sentence) + r" Request id: ([0-9a-f]{32})"), message)
    assert found, message
    # the id is the one the log names, so an operator finds the traceback by it
    assert f"Request {found.group(1)} failed with a 500" in caplog.text
    assert "/srv/secret" not in message


#: valid arguments for each tool, which reach the route's own reader (a 422 of the route would come before it)
_ARGUMENTS: dict[str, dict[str, Any]] = {
    "alerts": {},
    "auth": {"provider": "dwd", "network": "observation"},
    "coverage": {"provider": "dwd", "network": "observation"},
    "glossary": {},
    "history": {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True},
    "interpolate": {
        "provider": "dwd",
        "network": "observation",
        "parameters": "daily/kl/temperature_air_mean_2m",
        "latitude": 50.0,
        "longitude": 8.0,
        "timestamp": "2020-01-01",
    },
    "issues": {"provider": "dwd", "network": "observation", "station": "00011"},
    "kostra": {"latitude": 52.0, "longitude": 13.0},
    "providers": {},
    "station_ids": {"wmo_id": "10381"},
    "stations": {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": True},
    "statistics": {
        "provider": "dwd",
        "network": "observation",
        "parameters": "daily/kl/temperature_air_mean_2m",
        "stations": "00011",
        "aggregate": "mean",
    },
    "storm_cells": {},
    "summarize": {
        "provider": "dwd",
        "network": "observation",
        "parameters": "daily/kl/temperature_air_mean_2m",
        "latitude": 50.0,
        "longitude": 8.0,
        "timestamp": "2020-01-01",
    },
    "values": {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "stations": "00011"},
}


def test_every_tool_has_arguments_here() -> None:
    """The per-tool tests below cover every tool there is."""
    assert set(_ARGUMENTS) == set(_TOOL_NAMES.values())


async def _calls_of_every_tool(app: FastAPI) -> dict[str, tuple[str, list[str]]]:
    """Call each tool on `app`: its error text and the formats its own schema offers (none: it has no `format`)."""
    answers = {}
    async with Client(build_mcp_server(app)) as client:
        offered = {
            tool.name: tool.input_schema.get("properties", {}).get("format", {}).get("enum", [])
            for tool in await client.list_tools()
        }
        for tool, arguments in _ARGUMENTS.items():
            try:
                await client.call_tool(tool, arguments)
            except ToolError as error:
                answers[tool] = (str(error), offered[tool])
            else:
                pytest.fail(f"{tool} did not fail")
    return answers


def test_the_502_of_every_tool_names_the_formats_of_that_tool() -> None:
    """`interpolate` and `summarize` have no ndjson, `station_ids` only json and csv: each says what it answers."""
    stand_in = FastAPI()
    stand_in.openapi = restapi.app.openapi  # ty: ignore[invalid-assignment]

    @stand_in.api_route("/{path:path}", methods=["GET"])
    def answer(path: str) -> Response:  # noqa: ARG001
        return Response(b"x", media_type="image/png")

    answers = asyncio.run(_calls_of_every_tool(stand_in))

    assert set(answers) == set(_TOOL_NAMES.values())
    for tool, (message, formats) in answers.items():
        names = formats or ["json"]
        said = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} or {names[-1]}"
        assert message == _frame(
            tool, 502, f"The REST API answered image/png, which a tool does not carry: {tool} answers {said}."
        )
    assert answers["interpolate"][0].endswith("interpolate answers json, geojson or csv.")
    assert answers["summarize"][0].endswith("summarize answers json, geojson or csv.")
    assert answers["values"][0].endswith("values answers json, geojson, csv, ndjson or compact.")
    assert answers["glossary"][0].endswith("glossary answers json.")
    assert "ndjson" not in answers["interpolate"][0] + answers["summarize"][0] + answers["station_ids"][0]


def test_the_500_of_every_tool_names_its_request_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each tool's route fails in the server's own code (a defect), and the text of every tool ends with the id."""
    monkeypatch.setattr("wetterdienst.ui.restapi.begin_response", _raising(RuntimeError("/srv/secret/path")))
    monkeypatch.setattr("wetterdienst.ui.restapi.get_glossary", _raising(RuntimeError("/srv/secret/path")))
    monkeypatch.setattr("wetterdienst.ui.restapi.get_auth", _raising(RuntimeError("/srv/secret/path")))
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.observation.api.DwdObservationRequest.discover",
        classmethod(lambda _cls, **_kwargs: _raising(RuntimeError("/srv/secret/path"))()),
    )

    answers = asyncio.run(_calls_of_every_tool(restapi.app))

    ids = set()
    for tool, (message, _formats) in answers.items():
        found = re.fullmatch(
            _frame(
                tool,
                500,
                re.escape("Internal server error (RuntimeError). The cause is in the server log.")
                + r" Request id: ([0-9a-f]{32})",
            ),
            message,
        )
        assert found, (tool, message)
        ids.add(found.group(1))
    # an id of its own for each call
    assert len(ids) == len(answers)


@pytest.mark.parametrize(
    "make",
    [pytest.param(_limit_of_stations, id="stations"), pytest.param(_limit_of_rows, id="rows")],
)
def test_a_limit_a_tool_exceeds_is_told_in_the_text_of_the_tool(monkeypatch: pytest.MonkeyPatch, make: Any) -> None:  # noqa: ANN401
    """A 400 `limit-exceeded` has its own text for a tool (`tool_detail`, where it has one), in no quotes."""
    error = make()
    monkeypatch.setattr("wetterdienst.ui.restapi.get_glossary", _raising(error))

    expected = error.tool_detail or error.detail

    assert _tool_error("glossary", {}) == _frame("glossary", 400, expected)


def test_a_validation_error_of_several_entries_is_one_line_each() -> None:
    """The lines of a 422 are separated by line breaks in the text, and not by their escape."""
    rest = TestClient(restapi.app).get("/api/v1/glossary", params={"unit_type": "nonsense", "limit": 0})
    assert rest.status_code == 422
    detail = rest.json()["detail"]
    assert len(detail.splitlines()) == 2

    message = _tool_error("glossary", {"unit_type": "nonsense", "limit": 0})

    assert message == _frame("glossary", 422, detail)
    assert len(message.splitlines()) == 2
    assert not any(token in message for token in ('"unit_type', "\\n", "{'", "[{"))


def test_a_422_with_one_entry_is_the_sentence_of_pydantic() -> None:
    """One entry of pydantic is one line, with no quote around it."""
    assert _tool_error("glossary", {"limit": 0}) == _frame(
        "glossary", 422, "limit: Input should be greater than or equal to 1"
    )


def test_a_tool_refused_before_its_route_is_unframed_and_unchanged() -> None:
    """The refusals of the middleware are `ToolError`s of ours, which FastMCP passes on as they are."""
    assert (
        _tool_error("glossary", {"foo": 1})
        == "foo is not an argument of glossary, which takes limit, parameter and unit_type"
    )
    assert _tool_error("no_such_tool", {}) == "Unknown tool: 'no_such_tool'"
    # the text of a refused chart format is held where charts are (`test_restapi_plotting.py`)


@pytest.mark.parametrize("media_type", ["image/png", "application/pdf", "text/html", "image/svg+xml"])
def test_an_answer_the_tool_does_not_carry_is_told_in_plain_words(media_type: str) -> None:
    """The 502 of the transport is text too: its sentence reaches the model without quotes."""
    stand_in = FastAPI()
    stand_in.openapi = restapi.app.openapi  # ty: ignore[invalid-assignment]

    @stand_in.api_route("/{path:path}", methods=["GET"])
    def answer(path: str) -> Response:  # noqa: ARG001
        return Response(b"x", media_type=media_type)

    message = _tool_error(
        "values", {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "format": "csv"}, stand_in
    )

    assert message == _frame(
        "values",
        502,
        f"The REST API answered {media_type}, which a tool does not carry: "
        "values answers json, geojson, csv, ndjson or compact.",
    )


def test_the_rest_app_answers_a_tool_request_with_text_and_any_other_with_the_problem() -> None:
    """The one place the difference is made: `problem_response` for the scope of a tool's request."""
    detail = 'a "quoted"\nsentence'
    tool = problem_response({"type": "http", _TOOL_REQUEST_SCOPE_KEY: True}, 400, detail)
    other = problem_response({"type": "http"}, 400, detail)

    assert tool.media_type == "text/plain"
    assert tool.body == detail.encode()
    assert other.media_type == PROBLEM_MEDIA_TYPE
    assert b'"detail"' in other.body


def test_only_the_text_of_a_500_to_a_tool_has_the_request_id_in_it() -> None:
    """The problem of any other request has it in `request_id` and the header; a tool's other failures need none."""
    scope = {"type": "http", "state": {"request_id": "abc123"}}
    tool = problem_response({**scope, _TOOL_REQUEST_SCOPE_KEY: True}, 500, "Internal server error (X).")
    assert tool.body == b"Internal server error (X). Request id: abc123"
    other = problem_response(scope, 500, "Internal server error (X).")
    assert b"Request id" not in other.body
    assert b'"request_id":"abc123"' in other.body.replace(b" ", b"")
    for status in (400, 404, 502, 503):
        assert problem_response({**scope, _TOOL_REQUEST_SCOPE_KEY: True}, status, "text").body == b"text"
