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
import contextlib
import logging
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from collections.abc import Iterator

go = pytest.importorskip("plotly.graph_objects")
pytest.importorskip("kaleido")
# plotly keeps the `kaleido` it finds when it first imports this module for good: with a fake in `sys.modules` at that
# moment, every later image of the session would be drawn by the fake (see `test_kaleido_server`)
pytest.importorskip("plotly.io._kaleido")

#: a time short enough for a test to wait for, long enough for a script of a browser to finish
_SHORT = 0.3


class _ChromeNotFoundError(Exception):
    """Stand in for kaleido's error of a machine without Chrome."""


def _fake_kaleido(  # noqa: C901
    monkeypatch: pytest.MonkeyPatch,
    *,
    stuck: tuple[str, ...] = (),
    error: BaseException | None = None,
    server: object | None = None,
    process: subprocess.Popen[bytes] | None = None,
) -> list[Any]:
    """Put a `kaleido` that is a script into the imports, and give the list of what was done to its browser.

    `stuck` names the steps that never end: `open`, `draw` and `close`. `error` is raised by the drawing. `process` is
    the browser's process, which the script's close does not end.
    """
    events: list[Any] = []

    class Kaleido:
        def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
            events.append(("init", kwargs))
            if process is not None:
                self.subprocess = process

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
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    events.append("close cancelled")
                    raise

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
    assert events[-2:] == ["close", "close cancelled"]


def test_an_image_is_drawn_with_the_options_it_is_given_and_the_browser_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What is not named is what plotly takes; what plotly gives Kaleido (the OpenStreetMap header) is given."""
    from plotly.io import defaults  # noqa: PLC0415

    events = _fake_kaleido(monkeypatch)

    assert render_image(go.Figure(), "svg", width=300, scale=2.0, timeout=5) == b"image"

    assert [event if isinstance(event, str) else event[0] for event in events] == ["init", "open", "draw", "close"]
    headers = getattr(defaults, "headers", None)  # plotly before 6.8 has none
    assert events[0][1] == {"n": 1, "timeout": 5, **({"headers": headers} if headers else {})}
    assert events[2][1] == {"format": "svg", "width": 300, "height": 500, "scale": 2.0}


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
    assert raised.value.timeout is None
    assert "the limit is" not in str(raised.value)  # it was not the limit that ran out
    assert events[-1] == "close"


def test_a_browser_that_ends_under_the_drawing_is_an_error_and_no_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Choreographer cancels what waited on a browser that died: `CancelledError` is no `Exception`, this is."""
    events = _fake_kaleido(monkeypatch, error=asyncio.CancelledError())

    with pytest.raises(RuntimeError, match="ended before it was done"):
        render_image(go.Figure(), "png", timeout=5)

    assert events[-1] == "close"


def test_a_caller_with_a_running_loop_is_served(monkeypatch: pytest.MonkeyPatch) -> None:
    """A notebook has a loop running in its thread: the render does not start one there, or fail for it."""
    _fake_kaleido(monkeypatch)

    async def call() -> bytes:
        return render_image(go.Figure(), "png", timeout=5)

    assert asyncio.run(call()) == b"image"


#: a browser in a session of its own, as choreographer starts one, that ignores the request to terminate and has a
#: child, as Chrome has: it prints the pid of the child
_BROWSER = (
    "import signal, subprocess, sys, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "print(child.pid, flush=True)\n"
    "time.sleep(60)\n"
)


@contextlib.contextmanager
def _a_browser_with_a_child() -> Iterator[tuple[subprocess.Popen[str], int]]:
    """Start a stand-in for the browser, and make sure nothing of it outlives the test."""
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", _BROWSER], start_new_session=True, stdout=subprocess.PIPE, text=True
    )
    assert process.stdout is not None
    child = int(process.stdout.readline())
    try:
        yield process, child
    finally:
        for pid in (child, process.pid):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGKILL)
        process.wait()


def _is_gone(pid: int) -> bool:
    """Tell whether a process has ended, given a moment for its parent, or init, to reap it."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


@pytest.mark.skipif(IS_WINDOWS, reason="a process group is a POSIX thing")
@pytest.mark.parametrize("stuck", [("draw", "close"), ("draw",)], ids=["close-never-answers", "close-answers-late"])
def test_a_browser_that_is_still_there_after_the_close_is_killed_with_its_group(
    monkeypatch: pytest.MonkeyPatch, stuck: tuple[str, ...]
) -> None:
    """A close that was given up on, or that returned with the browser alive, is not the end: the group is killed.

    The child is the proof that it is the group: killing the browser's process alone leaves it running.
    """
    with _a_browser_with_a_child() as (process, child):
        _fake_kaleido(monkeypatch, stuck=stuck, process=process)  # ty: ignore[invalid-argument-type]
        with pytest.raises(ImageTimeoutError):
            render_image(go.Figure(), "png", timeout=_SHORT)

        assert process.poll() is not None
        assert _is_gone(child)


@pytest.mark.skipif(IS_WINDOWS, reason="a process group is a POSIX thing")
def test_a_clock_that_runs_out_while_the_process_is_being_started_still_kills_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Browser.open` keeps the `Popen` of a thread that starts the process: a cancel before that loses the process.

    The window is a fraction of a second, and a limit of a few milliseconds finds it every time (on a slow runner
    50 ms did): the process was started after the close, and nothing held it to kill.
    """
    started: list[subprocess.Popen[bytes]] = []

    def start() -> subprocess.Popen[bytes]:
        time.sleep(0.4)  # the thread of choreographer that starts the wrapper of the browser
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
        started.append(process)
        return process

    class Kaleido:
        def __init__(self, **_kwargs: Any) -> None:  # noqa: ANN401
            pass

        async def open(self) -> None:
            self.subprocess = await asyncio.get_running_loop().run_in_executor(None, start)  # as choreographer does
            await asyncio.Event().wait()  # the page is never ready

        async def close(self) -> None:
            if hasattr(self, "subprocess"):  # choreographer: "No _close(), already is closed" where it has none
                await asyncio.Event().wait()

    _fake_kaleido(monkeypatch)
    monkeypatch.setattr(sys.modules["kaleido"], "Kaleido", Kaleido)
    try:
        with pytest.raises(ImageTimeoutError):
            render_image(go.Figure(), "png", timeout=0.05)
        deadline = time.monotonic() + 3
        while not started and time.monotonic() < deadline:
            time.sleep(0.05)

        assert started, "the process was never started"
        assert started[0].poll() is not None
        assert _is_gone(started[0].pid) is True
    finally:
        for process in started:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


@pytest.mark.skipif(IS_WINDOWS, reason="a process group is a POSIX thing")
@pytest.mark.parametrize("error", [PermissionError("zombie"), OSError("no"), subprocess.TimeoutExpired("taskkill", 6)])
def test_a_kill_that_fails_does_not_replace_the_image(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """On macOS `killpg` on a zombie leader raises `PermissionError`: the image that was drawn is still the result."""

    def failing(_pid: int, _signal: int) -> None:
        raise error

    with _a_browser_with_a_child() as (process, _child):
        _fake_kaleido(monkeypatch, process=process)  # ty: ignore[invalid-argument-type]
        monkeypatch.setattr(os, "killpg", failing)

        assert render_image(go.Figure(), "png", timeout=5) == b"image"


@pytest.mark.skipif(IS_WINDOWS, reason="a process group is a POSIX thing")
def test_a_kill_that_fails_does_not_replace_the_timeout_nor_skip_the_cancelling_of_the_close(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The timeout stands, and the close that was given up on is cancelled all the same."""

    def failing(_pid: int, _signal: int) -> None:
        msg = "zombie"
        raise PermissionError(msg)

    with _a_browser_with_a_child() as (process, _child):
        events = _fake_kaleido(monkeypatch, stuck=("draw", "close"), process=process)  # ty: ignore[invalid-argument-type]
        monkeypatch.setattr(os, "killpg", failing)

        with caplog.at_level(logging.WARNING), pytest.raises(ImageTimeoutError):
            render_image(go.Figure(), "png", timeout=_SHORT)

    assert "close cancelled" in events
    assert "could not be killed" in caplog.text


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


def _a_server_is_running() -> bool:
    """Tell whether the session's Chrome of `_kaleido_server` is up in this process, which `render_image` then uses."""
    import kaleido  # noqa: PLC0415

    server = getattr(kaleido, "_global_server", None)
    return server is not None and server.is_running()


@pytest.mark.skipif(IS_WINDOWS or shutil.which("pgrep") is None, reason="the processes are listed with `pgrep`")
def test_a_real_browser_that_is_not_up_in_time_is_closed_with_its_processes() -> None:
    """The one test with a real Chrome: 50 ms is less than it needs to start, and none of it is left behind."""
    if _a_server_is_running():
        pytest.skip("the Chrome of a kaleido server is up in this process, and an image is drawn by it")
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


# --- the image is what plotly draws ------------------------------------------------------------------------------


def _png_size(image: bytes) -> tuple[int, int]:
    """Read the width and the height out of the header of a PNG."""
    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", image[16:24])  # ty: ignore[invalid-return-type]


@pytest.mark.parametrize(
    ("defaults", "layout", "template", "arguments", "size"),
    [
        pytest.param({}, {}, {}, {}, (700, 500), id="plotly-defaults"),
        pytest.param({"default_width": 1000, "default_height": 400}, {}, {}, {}, (1000, 400), id="default-size"),
        pytest.param({"default_scale": 2}, {}, {}, {}, (1400, 1000), id="default-scale"),
        pytest.param({}, {"width": 640, "height": 320}, {}, {}, (640, 320), id="layout-size"),
        pytest.param({}, {}, {"width": 500, "height": 300}, {}, (500, 300), id="template-size"),
        pytest.param(
            {"default_width": 1000},
            {"height": 260},
            {},
            {"width": 420, "scale": 1.5},
            (630, 390),
            id="arguments",
        ),
    ],
)
def test_an_image_has_the_size_plotly_gives_it(
    monkeypatch: pytest.MonkeyPatch,
    defaults: dict[str, float],
    layout: dict[str, int],
    template: dict[str, int],
    arguments: dict[str, float],
    size: tuple[int, int],
) -> None:
    """The argument, the layout of the figure, its template and `plotly.io.defaults`, in that order: as `to_image`.

    Read off the pixels of the PNG, and `to_image` is held to the same size: plotly 6.3.1, the floor, is the first
    release that honours the size of the figure's layout and template (6.2.0 and 6.3.0 take the argument or their
    default, GH-3829), so on every version the extra allows both draw it alike.
    """
    from plotly.io import defaults as plotly_defaults  # noqa: PLC0415

    if _a_server_is_running():
        pytest.skip("the Chrome of a kaleido server is up in this process, and both are drawn by it")
    for name, value in defaults.items():
        monkeypatch.setattr(plotly_defaults, name, value)
    figure = go.Figure(layout={**layout, "template": {"layout": template}})

    ours = render_image(figure, "png", **arguments)  # ty: ignore[invalid-argument-type]

    assert _png_size(ours) == size
    assert _png_size(figure.to_image(format="png", **arguments)) == size
