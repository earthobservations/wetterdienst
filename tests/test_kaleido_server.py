# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the kaleido server the image tests share (GH-3250), driven with a fake `kaleido` module.

The lowest kaleido the `plotting` extra allows (1.0.0) has no `start_sync_server` and no `_global_server`, and the
lowest-versions job installs it: the fixture has to leave the image tests as they were there.
"""

from __future__ import annotations

import sys
import threading
from types import SimpleNamespace
from typing import Any

import pytest

from tests import conftest

# plotly keeps the `kaleido` it finds when it first imports this module for good: with a fake in `sys.modules` at that
# moment, every later image of the session would be drawn by the fake
pytest.importorskip("plotly.io._kaleido")


class _Server:
    """Stand in for kaleido's `GlobalKaleidoServer`: the thread it has, and the flag the fixture resets."""

    def __init__(self, *, alive: bool) -> None:
        self._thread = SimpleNamespace(is_alive=lambda: alive)
        self._initialized = True


def _kaleido(calls: list[str], **extra: Any) -> SimpleNamespace:  # noqa: ANN401
    """Give a fake `kaleido` module of a release with a server, which records what the fixture calls on it."""

    def calc_fig_sync(*_args: object, **_kwargs: object) -> str:
        return "drawn"

    def start_sync_server(**kwargs: object) -> None:
        calls.append("start")
        assert set(kwargs) == {"headers", "plotlyjs", "mathjax", "silence_warnings"}

    def stop_sync_server(**_kwargs: object) -> None:
        calls.append("stop")

    return SimpleNamespace(
        calc_fig_sync=calc_fig_sync,
        start_sync_server=start_sync_server,
        stop_sync_server=stop_sync_server,
        **extra,
    )


def _run_to_the_end(generator: Any) -> None:  # noqa: ANN401
    """Run a fixture generator through the tests (its yield) and its teardown."""
    assert next(generator) is None
    with pytest.raises(StopIteration):
        next(generator)


@pytest.fixture
def figures(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the warm-up figure, so that no Chrome is started, and record that it was asked for."""
    drawn: list[str] = []
    monkeypatch.setattr(conftest, "_draw_a_figure", lambda: drawn.append("figure"))
    return drawn


@pytest.mark.parametrize("missing", ["_global_server", "start_sync_server", "stop_sync_server", "calc_fig_sync"])
def test_a_kaleido_without_a_server_to_reach_is_left_alone(
    monkeypatch: pytest.MonkeyPatch, figures: list[str], missing: str
) -> None:
    """A release that lacks the server or a function of it starts nothing, and no test errors on it."""
    calls: list[str] = []
    fake = _kaleido(calls, _global_server=_Server(alive=True))
    delattr(fake, missing)
    monkeypatch.setitem(sys.modules, "kaleido", fake)

    _run_to_the_end(conftest._serve_kaleido())  # noqa: SLF001

    assert calls == []
    assert figures == []
    assert not hasattr(fake, missing)


def test_kaleido_1_0_0_is_left_alone(monkeypatch: pytest.MonkeyPatch, figures: list[str]) -> None:
    """The module of kaleido 1.0.0, which has `calc_fig_sync` and neither a server nor a way to start one."""
    fake = SimpleNamespace(calc_fig_sync=lambda *_a, **_k: "drawn", Kaleido=object)
    monkeypatch.setitem(sys.modules, "kaleido", fake)

    _run_to_the_end(conftest._serve_kaleido())  # noqa: SLF001

    assert figures == []


def test_a_kaleido_with_a_server_is_started_serialised_and_stopped(
    monkeypatch: pytest.MonkeyPatch, figures: list[str]
) -> None:
    """The server is started, a first figure is drawn, `calc_fig_sync` is wrapped for the tests and put back."""
    calls: list[str] = []
    fake = _kaleido(calls, _global_server=_Server(alive=True))
    original = fake.calc_fig_sync
    monkeypatch.setitem(sys.modules, "kaleido", fake)

    generator = conftest._serve_kaleido()  # noqa: SLF001
    assert next(generator) is None

    assert calls == ["start"]
    assert figures == ["figure", "figure"]  # the one-shot render, then the first one of the server
    assert fake.calc_fig_sync is not original
    assert fake.calc_fig_sync() == "drawn"

    with pytest.raises(StopIteration):
        next(generator)

    assert calls == ["start", "stop"]
    assert fake.calc_fig_sync is original


def test_a_server_whose_thread_died_fails_the_tests_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dead server never answers: the fixture fails with that said instead of waiting, and resets the server."""
    calls: list[str] = []
    server = _Server(alive=False)
    fake = _kaleido(calls, _global_server=server)
    original = fake.calc_fig_sync
    monkeypatch.setitem(sys.modules, "kaleido", fake)
    stuck = threading.Event()

    def draw() -> None:
        if calls:  # the render that waits on a server that is dead; the one before the start returns
            stuck.wait(30)

    monkeypatch.setattr(conftest, "_draw_a_figure", draw)

    try:
        with pytest.raises(pytest.fail.Exception, match="server thread is dead"):
            next(conftest._serve_kaleido())  # noqa: SLF001
    finally:
        stuck.set()

    assert fake.calc_fig_sync is original
    assert server._initialized is False  # noqa: SLF001
