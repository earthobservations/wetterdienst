# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the watchdog that fails an offline test which does not end (GH-3723)."""

from __future__ import annotations

import signal
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from tests import conftest

_ROOT = Path(__file__).parent.parent

needs_itimer = pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs setitimer (not on Windows)")


@needs_itimer
def test_a_test_that_spins_is_failed_with_the_stacks_of_the_threads() -> None:
    """A busy loop is interrupted, and the error says where each thread was."""
    started = threading.Event()
    stop = threading.Event()
    waiting = threading.Thread(target=lambda: (started.set(), stop.wait(30)), name="stays-waiting", daemon=True)
    waiting.start()
    started.wait(5)

    def spin() -> None:
        with conftest._fail_if_hung(0.3):  # noqa: SLF001
            while True:
                pass

    try:
        with pytest.raises(conftest.HungTestError, match=r"did not end within 0\.3 seconds") as raised:
            spin()
    finally:
        stop.set()

    assert "Thread 'stays-waiting'" in str(raised.value)
    assert "Thread 'MainThread'" in str(raised.value)


@needs_itimer
def test_a_test_that_blocks_is_failed_too() -> None:
    """A wait that never returns, the join of a thread that does not end, is interrupted as well."""
    never = threading.Event()

    def block() -> None:
        with conftest._fail_if_hung(0.3):  # noqa: SLF001
            never.wait(30)

    with pytest.raises(conftest.HungTestError):
        block()


@needs_itimer
def test_a_test_that_ends_leaves_the_timer_and_the_handler_it_found() -> None:
    """After the test the alarm is the one that was running (the fixture's own), and the handler the one before."""
    previous = signal.signal(signal.SIGALRM, signal.SIG_IGN)
    before = signal.getitimer(signal.ITIMER_REAL)
    try:
        with conftest._fail_if_hung(30):  # noqa: SLF001
            pass
        after = signal.getitimer(signal.ITIMER_REAL)
        assert (after[0] > 0) == (before[0] > 0)
        assert after[0] <= before[0] or before[0] == 0
        assert signal.getsignal(signal.SIGALRM) is signal.SIG_IGN
    finally:
        signal.signal(signal.SIGALRM, previous)


def test_the_stderr_of_the_process_is_kept_for_the_stacks() -> None:
    """The stacks of a hang are written to the stderr from before the capture of a test, a file of its own."""
    assert conftest._REAL_STDERR is not None  # noqa: SLF001
    assert conftest._REAL_STDERR.fileno() > 2  # noqa: SLF001


def test_without_a_timer_the_process_is_ended_with_the_stacks() -> None:
    """Where `setitimer` is missing (Windows), the process ends at the time, which xdist reports as a crash."""
    script = textwrap.dedent(
        """
        import signal, threading
        if hasattr(signal, "setitimer"):
            del signal.setitimer
        from tests import conftest

        with conftest._fail_if_hung(1):
            threading.Event().wait(60)
        """
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode != 0
    assert "Timeout (0:00:01)!" in result.stderr
