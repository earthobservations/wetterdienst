# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The text of an option costs time in proportion to its length, not to the square of it (GH-4412).

One GET with 30,000 spaces in `having` kept the event loop 2.4 s: a regular expression with nested quantifiers ran over
the raw text before its length was looked at. Every option of `statistics` is given texts of a megabyte that a scanner
could be slow on, in Python, on REST and in the tool, and a fuzz measures the time against the length.

The bounds are wide, as a busy runner stalls for a second on its own: the scan they are there for took 2.4 s for 30,000
characters, and so most of an hour for a megabyte.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any
from urllib.parse import urlencode

import pytest

from tests.ui.row_options_stub import TMIN, serve
from wetterdienst.model.group_statistics import parse_statistics
from wetterdienst.ui.restapi import app

OPTIONS = ("aggregate", "by", "filter", "having", "sort", "year_start", "max_missing", "first", "per", "max_rows")
MEGABYTE = 1_000_000

# seconds
PYTHON_BOUND = 1.0
REST_BOUND = 5.0
TOOL_BOUND = 10.0

#: texts a scanner may be slow on, by length
SHAPES = {
    "spaces": lambda n: " " * n,
    "letters": lambda n: "a" * n,
    "digits": lambda n: "1" * n,
    "commas": lambda n: "," * n,
    "minus": lambda n: "-" * n,
    "pipes": lambda n: "value=1" + "|1" * (n // 2),
    "conditions": lambda n: "count>1," * (n // 8),
    "complete then spaces": lambda n: "complete=" + " " * n,
    "complete spaces then x": lambda n: "complete=" + " " * n + "x",
    "complete value spaces then x": lambda n: "complete=1" + " " * n + "x",
    "spaces then x": lambda n: " " * n + "x",
    "complete spaces equals": lambda n: "complete" + " " * n + "=",
    "complete bang spaces": lambda n: "complete" + "!" * n,
    "complete in words": lambda n: "complete=" + "|".join(["true"] * (n // 5)),
    "a name": lambda n: "a" * n + "<0",
}
_VOCABULARY = (" ", "complete", "=", "!=", "|", ",", "1", "a", "value", "<", "-", "e", ".", "mean", "year", "true")


def _call(option: str, text: str) -> float:
    start = time.perf_counter()
    try:
        if option == "aggregate":
            parse_statistics(text)
        else:
            parse_statistics("count", **{option: text})  # ty: ignore[invalid-argument-type]
    except ValueError:
        pass
    return time.perf_counter() - start


@pytest.mark.parametrize("option", OPTIONS)
def test_a_megabyte_of_any_shape_is_read_or_refused_in_time(option: str) -> None:
    """Python: every shape, in every option, is refused (or read) within the bound."""
    slow = {}
    # 30,000 characters is the text of the request that held the event loop 2.4 s, a megabyte the one nobody should send
    for length in (30_000, MEGABYTE):
        for name, make in SHAPES.items():
            spent = min(_call(option, make(length)) for _ in range(2))
            if spent > PYTHON_BOUND:
                slow[f"{name} x {length:,}"] = round(spent * 1000)
    assert not slow, f"{option}: milliseconds {slow}"


@pytest.mark.parametrize("option", OPTIONS)
def test_the_time_grows_with_the_length_and_not_with_its_square(option: str) -> None:
    """Fuzz: random strings of the grammar's words: ten times the text, under 30 times the time."""
    generator = random.Random(4412)  # noqa: S311
    worst = 0.0
    for _ in range(6):
        words = [generator.choice(_VOCABULARY) for _ in range(40)]
        small = "".join(generator.choice(words) for _ in range(4_000))
        big = small * 10
        floor = max(_call(option, small), 0.02)
        ratio = _call(option, big) / floor
        worst = max(worst, ratio)
    for make in SHAPES.values():
        floor = max(_call(option, make(20_000)), 0.02)
        worst = max(worst, _call(option, make(200_000)) / floor)
    assert worst < 30, f"{option}: ten times the text took {worst:.0f} times as long"


def _query(option: str, text: str) -> str:
    base = {
        "provider": "dwd",
        "network": "observation",
        "parameters": TMIN,
        "timestamp": "2018/2020",
        "all": "true",
        "aggregate": "count",
        "by": "year",
    }
    # the text is sent as it is, with the signs of the grammar unescaped: what the server unquotes is the text and not
    # the three times as long escape of it, whose cost is the framework's
    return urlencode({**base, option: text}, safe=",|=<>!-.:/")


async def _get(query: str) -> tuple[int, float]:
    status: list[int] = []
    sent = False

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if sent:
            await asyncio.sleep(3600)
        sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            status.append(message["status"])

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/api/v1/statistics",
        "raw_path": b"/api/v1/statistics",
        "root_path": "",
        "scheme": "http",
        "query_string": query.encode(),
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
    }
    start = time.perf_counter()
    await app(scope, receive, send)
    return status[0], time.perf_counter() - start


@pytest.mark.parametrize("option", OPTIONS)
def test_rest_refuses_a_megabyte_in_every_option_without_holding_the_loop(
    monkeypatch: pytest.MonkeyPatch, option: str
) -> None:
    """REST: a megabyte in an option is a 4xx within the bound, not the minutes a scan of it takes."""
    serve(monkeypatch, count=2)
    slow = {}
    for name, make in SHAPES.items():
        status, spent = asyncio.run(_get(_query(option, make(MEGABYTE))))
        assert status in (200, 400, 422), (option, name, status)
        if status != 200 and spent > REST_BOUND:
            slow[name] = round(spent * 1000)
    assert not slow, f"{option}: milliseconds for a megabyte {slow}"


@pytest.mark.parametrize("option", OPTIONS)
def test_the_tool_refuses_a_megabyte_in_every_option_in_time(monkeypatch: pytest.MonkeyPatch, option: str) -> None:
    """The tool: the same, through the MCP client."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    serve(monkeypatch, count=2)
    base = {"provider": "dwd", "network": "observation", "parameters": TMIN, "all": True, "aggregate": "count"}

    async def run() -> dict[str, float]:
        slow = {}
        async with Client(build_mcp_server(app)) as client:
            for name, make in SHAPES.items():
                arguments: dict[str, Any] = {**base, "by": "year", option: make(MEGABYTE)}
                start = time.perf_counter()
                result = await client.call_tool("statistics", arguments, raise_on_error=False)
                spent = time.perf_counter() - start
                if result.is_error and spent > TOOL_BOUND:
                    slow[name] = round(spent * 1000)
        return slow

    slow = asyncio.run(run())
    assert not slow, f"{option}: milliseconds for a megabyte {slow}"
