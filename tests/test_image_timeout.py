# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An image that Kaleido does not draw in time is an `ImageTimeoutError`, and its browser is closed (GH-3723).

Kaleido bounds the drawing of an image and nothing around it: a Chrome that never starts, a page that is never ready
and a browser that does not close each held the caller for ever. `render_image` puts a clock on the whole of it.

Offline, with a `kaleido` that is a script of what the browser does (it answers, it is stuck on its start, on the
drawing, or on its close) and a time of a third of a second, so that no test waits for a hang; the one test that
starts a real Chrome is told so.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.conftest import IS_WINDOWS
from tests.ui.test_restapi import _stub_stripes_station
from wetterdienst.exceptions import ImageTimeoutError
from wetterdienst.io import export
from wetterdienst.io.export import IMAGE_TIMEOUT, render_image
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

go = pytest.importorskip("plotly.graph_objects")
pytest.importorskip("kaleido")

#: a time short enough for a test to wait for, long enough for a script of a browser to finish
_SHORT = 0.3


class _ChromeNotFoundError(Exception):
    """Stand in for kaleido's error of a machine without Chrome."""


def _fake_kaleido(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stuck: tuple[str, ...] = (),
    error: BaseException | None = None,
    server: object | None = None,
) -> list[Any]:
    """Put a `kaleido` that is a script into the imports, and give the list of what was done to its browser.

    `stuck` names the steps that never end: `open`, `draw` and `close`. `error` is raised by the drawing.
    """
    events: list[Any] = []

    class Kaleido:
        def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
            events.append(("init", kwargs))

        async def open(self) -> None:
            events.append("open")
            if "open" in stuck:
                await asyncio.Event().wait()

        async def calc_fig(self, fig: object, opts: dict[str, Any] | None = None, topojson: object = None) -> bytes:  # noqa: ARG002
            events.append(("draw", opts))
            if "draw" in stuck:
                await asyncio.Event().wait()
            if error is not None:
                raise error
            return b"image"

        async def close(self) -> None:
            events.append("close")
            if "close" in stuck:
                await asyncio.Event().wait()

    kaleido = types.ModuleType("kaleido")
    kaleido.Kaleido = Kaleido  # ty: ignore[unresolved-attribute]
    if server is not None:
        kaleido._global_server = server  # ty: ignore[unresolved-attribute]  # noqa: SLF001
    errors = types.ModuleType("kaleido.errors")
    errors.ChromeNotFoundError = _ChromeNotFoundError  # ty: ignore[unresolved-attribute]
    monkeypatch.setitem(sys.modules, "kaleido", kaleido)
    monkeypatch.setitem(sys.modules, "kaleido.errors", errors)
    monkeypatch.setattr(export, "_CLOSE_GRACE", _SHORT)
    return events


@pytest.fixture
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


# --- the render --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("step", ["open", "draw"])
def test_a_browser_stuck_on_its_start_or_its_drawing_is_an_error_and_is_closed(
    monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    """The caller is not held for ever: `ImageTimeoutError` after the time, and the browser is closed after it."""
    events = _fake_kaleido(monkeypatch, stuck=(step,))

    started = time.monotonic()
    with pytest.raises(ImageTimeoutError) as raised:
        render_image(go.Figure(), "png", timeout=_SHORT)

    assert time.monotonic() - started < 10
    assert raised.value.timeout == _SHORT
    assert isinstance(raised.value, TimeoutError)
    assert events[-1] == "close"
    assert "open" in events


def test_a_browser_that_does_not_close_does_not_hold_the_error_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """A browser stuck on its start also does not answer the request to close: it gets a grace, and no more."""
    events = _fake_kaleido(monkeypatch, stuck=("open", "close"))

    started = time.monotonic()
    with pytest.raises(ImageTimeoutError):
        render_image(go.Figure(), "png", timeout=_SHORT)

    assert time.monotonic() - started < 10
    assert events[-1] == "close"


def test_an_image_is_drawn_with_the_options_it_is_given_and_the_browser_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What is not named is left to Kaleido; what plotly would give it (the OpenStreetMap header) is given."""
    from plotly.io import defaults  # noqa: PLC0415

    events = _fake_kaleido(monkeypatch)

    assert render_image(go.Figure(), "svg", width=300, scale=2.0, timeout=5) == b"image"

    assert [event if isinstance(event, str) else event[0] for event in events] == ["init", "open", "draw", "close"]
    assert events[0][1] == {"n": 1, "timeout": 5, "headers": defaults.headers}
    assert events[2][1] == {"format": "svg", "width": 300, "scale": 2.0}


def test_the_time_is_the_default_one_where_none_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """`IMAGE_TIMEOUT` is what a surface gets, and the one place that says it."""
    events = _fake_kaleido(monkeypatch)
    monkeypatch.setattr(export, "IMAGE_TIMEOUT", 7.5)

    render_image(go.Figure(), "png")

    assert events[0][1]["timeout"] == 7.5
    assert IMAGE_TIMEOUT == 120.0


def test_an_error_of_the_drawing_comes_through_and_the_browser_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A drawing that fails is not a timeout: the caller gets what Kaleido raised, with the browser closed."""
    events = _fake_kaleido(monkeypatch, error=RuntimeError("Map error."))

    with pytest.raises(RuntimeError, match="Map error"):
        render_image(go.Figure(), "png", timeout=5)

    assert events[-1] == "close"


def test_a_wait_of_the_browsers_own_that_runs_out_is_the_same_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kaleido's render time, and choreographer's 30 s for a page, raise `TimeoutError`: told as this error."""
    events = _fake_kaleido(monkeypatch, error=TimeoutError())

    with pytest.raises(ImageTimeoutError) as raised:
        render_image(go.Figure(), "png", timeout=5)

    assert isinstance(raised.value.__cause__, TimeoutError)
    assert events[-1] == "close"


def test_a_caller_with_a_running_loop_is_served(monkeypatch: pytest.MonkeyPatch) -> None:
    """A notebook has a loop running in its thread: the render does not start one there, or fail for it."""
    _fake_kaleido(monkeypatch)

    async def call() -> bytes:
        return render_image(go.Figure(), "png", timeout=5)

    assert asyncio.run(call()) == b"image"


def test_a_server_the_caller_started_draws_the_image_as_plotly_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """`kaleido.start_sync_server` is the caller's: one browser for many images, reached by `Figure.to_image`."""
    events = _fake_kaleido(monkeypatch, server=types.SimpleNamespace(is_running=lambda: True))
    monkeypatch.setattr(
        go.Figure,
        "to_image",
        lambda _fig, **kwargs: events.append(("to_image", kwargs)) or b"from the server",
    )

    assert render_image(go.Figure(), "png", width=300, timeout=5) == b"from the server"

    assert events == [("to_image", {"format": "png", "width": 300, "height": None, "scale": None})]


def test_a_machine_without_chrome_is_the_runtime_error_plotly_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kaleido's `ChromeNotFoundError` says what to install, as plotly's `RuntimeError` did."""
    _fake_kaleido(monkeypatch)

    def no_chrome(**_kwargs: object) -> None:
        msg = "Kaleido v1 and later requires Chrome to be installed."
        raise _ChromeNotFoundError(msg)

    monkeypatch.setattr(sys.modules["kaleido"], "Kaleido", no_chrome)

    with pytest.raises(RuntimeError, match="requires Chrome"):
        render_image(go.Figure(), "png", timeout=5)


# --- the surfaces ------------------------------------------------------------------------------------------------


@pytest.mark.usefixtures("_no_ambient_settings")
def test_the_rest_api_answers_a_stuck_image_with_a_504_and_closes_the_browser(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """`/api/stripes/image` was held by a browser that never answered; now it is a 504 problem to retry."""
    events = _fake_kaleido(monkeypatch, stuck=("open",))
    monkeypatch.setattr(export, "IMAGE_TIMEOUT", _SHORT)
    _stub_stripes_station(monkeypatch, "temperature", [1.0, 2.0])
    client = TestClient(restapi.app, raise_server_exceptions=False)

    with caplog.at_level(logging.WARNING):
        response = client.get("/api/stripes/image", params={"kind": "temperature", "station": "01048"})

    assert response.status_code == 504, response.text
    problem = response.json()
    assert problem["type"] == "urn:wetterdienst:problem:image-timeout"
    assert problem["status"] == 504
    assert problem["detail"] == "The image was not rendered in time. The request was valid; try again later."
    assert response.headers["Retry-After"] == "30"
    assert events[-1] == "close"
    # the limit is the server's: it is in the log, not in the body
    assert "limit is 0.3 seconds" in caplog.text
    assert "0.3" not in response.text


def test_the_command_line_tells_a_stuck_image_in_one_line_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Exit 1, as for every failure that is not the request's to rephrase, and no traceback."""
    events = _fake_kaleido(monkeypatch, stuck=("draw",))
    monkeypatch.setattr(export, "IMAGE_TIMEOUT", _SHORT)
    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", lambda _request: go.Figure())

    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(cli, ["stripes", "image", "--kind=temperature", "--station=01048"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert [record.getMessage() for record in errors] == [str(ImageTimeoutError(_SHORT))]
    assert all(record.exc_info is None for record in errors)
    assert events[-1] == "close"


def test_the_docs_state_the_time_an_image_has() -> None:
    """The seconds the docs and the problem table name are `IMAGE_TIMEOUT`, which they were written from."""
    docs = Path(__file__).parents[1] / "docs" / "usage"
    seconds = f"{IMAGE_TIMEOUT:g} seconds"
    assert seconds in (docs / "restapi.md").read_text(encoding="utf-8")
    assert seconds in (docs / "troubleshooting.md").read_text(encoding="utf-8")
    assert re.search(rf"IMAGE_TIMEOUT.*\({IMAGE_TIMEOUT:g}\)", (docs / "python-api.md").read_text(encoding="utf-8"))


# --- a real browser ----------------------------------------------------------------------------------------------


def _children() -> set[str]:
    """List the processes this one started and that are still there."""
    listed = subprocess.run(["pgrep", "-P", str(os.getpid())], capture_output=True, text=True, check=False)  # noqa: S603, S607
    return set(listed.stdout.split())


@pytest.mark.skipif(IS_WINDOWS or shutil.which("pgrep") is None, reason="the processes are listed with `pgrep`")
def test_a_real_browser_that_is_not_up_in_time_is_closed_with_its_processes() -> None:
    """The one test with a real Chrome: 50 ms is less than it needs to start, and none of it is left behind."""
    before = _children()  # what an earlier test left, such as the resource tracker of `multiprocessing`
    try:
        with pytest.raises(ImageTimeoutError):
            render_image(go.Figure(), "png", timeout=0.05)
    except RuntimeError as e:
        pytest.skip(f"no Chrome to start: {e}")

    # a process that was told to end is gone within moments, not at once
    deadline = time.monotonic() + 10
    while _children() - before and time.monotonic() < deadline:
        time.sleep(0.2)
    assert _children() - before == set()
