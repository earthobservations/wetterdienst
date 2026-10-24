# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a caller sends stays on one line of the server log, however it is written (GH-3336)."""

from __future__ import annotations

import importlib
import logging

import pytest
from starlette.testclient import TestClient

from wetterdienst.ui.restapi import app
from wetterdienst.util.logging import escape_control_characters, get_one_line_logger

#: a value that ends its line and begins another that reads as a record of the server's own
_FORGED = "x\n2026-10-23 12:00:00,000 [wetterdienst.ui.restapi                 ] ERROR  : FORGED LINE"

_VALUES = {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "stations": "00011"}


def _fail() -> None:
    msg = "boom"
    raise RuntimeError(msg)


@pytest.mark.parametrize(
    ("text", "escaped"),
    [
        ("plain text, kept as it is", "plain text, kept as it is"),
        ("a\nb", "a\\nb"),
        ("a\r\nb", "a\\r\\nb"),
        ("a\tb", "a\\tb"),
        ("\x1b[31mred", "\\x1b[31mred"),
        ("a\x85b", "a\\x85b"),
        ("a\u2028b\u2029c", "a\\u2028b\\u2029c"),
        ("back\\slash and ümlaut", "back\\slash and ümlaut"),
    ],
)
def test_control_characters_are_written_as_escapes(text: str, escaped: str) -> None:
    """A newline, a carriage return, an escape and the Unicode line separators are shown, not obeyed."""
    assert escape_control_characters(text) == escaped
    assert "\n" not in escaped


def test_a_logger_keeps_a_message_on_one_line(caplog: pytest.LogCaptureFixture) -> None:
    """The message is escaped after its arguments are put in, and a traceback keeps its own lines."""
    log = get_one_line_logger("wetterdienst.test_log_lines")
    assert get_one_line_logger("wetterdienst.test_log_lines") is log
    assert len(log.filters) == 1, "asked for twice, the filter is added once"
    with caplog.at_level(logging.INFO, logger=log.name):
        log.info("Refused %s: %s", "a\nb", _FORGED)
        try:
            _fail()
        except RuntimeError:
            log.exception("Failed\nonce")

    first, second = caplog.records
    assert first.getMessage() == f"Refused a\\nb: {escape_control_characters(_FORGED)}"
    assert second.getMessage() == "Failed\\nonce"
    assert "RuntimeError: boom" in caplog.text


@pytest.mark.parametrize(
    "module",
    ["restapi", "core", "middleware", "problems", "providers", "streaming"],
)
def test_the_loggers_of_the_server_keep_a_message_on_one_line(module: str) -> None:
    """Every module of the server that answers a caller has the filter, so a line added later is held to it too."""
    log = importlib.import_module(f"wetterdienst.ui.{module}").log
    assert any(type(item).__name__ == "_EscapeControlCharacters" for item in log.filters)


def test_a_name_that_matches_no_station_is_logged_on_one_line(caplog: pytest.LogCaptureFixture) -> None:
    """The request logs the `name` of a search that found nothing, which the REST API takes from the caller."""
    from wetterdienst.model import request  # noqa: PLC0415

    with caplog.at_level(logging.INFO, logger=request.log.name):
        request.log.info(f"No weather stations were found for name {_FORGED}")

    assert "\n" not in caplog.records[0].getMessage()


@pytest.fixture
def client() -> TestClient:
    """Give a client of the app."""
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/values", {**_VALUES, "timestamp": _FORGED}),
        ("/api/values", {**_VALUES, "parameters": f"daily/kl/{_FORGED}"}),
        ("/api/coverage", {"provider": "dwd", "network": "observation", "datasets": _FORGED}),
    ],
)
def test_a_refused_value_does_not_add_a_line_to_the_log(
    client: TestClient, caplog: pytest.LogCaptureFixture, path: str, params: dict[str, str]
) -> None:
    """The refusal is logged with the value the caller sent in it, on the one line of the refusal."""
    with caplog.at_level(logging.INFO):
        response = client.get(path, params=params)

    assert response.status_code in {400, 404}
    ours = [record for record in caplog.records if record.name.startswith("wetterdienst.ui")]
    assert ours, "the refusal is logged"
    for record in ours:
        assert "\n" not in record.getMessage()
    assert not [line for line in caplog.text.splitlines() if line.startswith("2026-10-23 12:00:00,000")]
    assert "x\\n2026-10-23" in caplog.text, "the value is in the log, with its newline written out"
