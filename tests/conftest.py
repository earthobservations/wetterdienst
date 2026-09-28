# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures for tests."""

import ipaddress
import os
import platform
import socket
import sys
import time
from collections.abc import Generator
from typing import Any

import fsspec.utils as _fsspec_utils
import pytest

from wetterdienst import Info, Settings
from wetterdienst.util.eccodes import bufr_is_available

IS_CI = bool(os.environ.get("CI"))
IS_LINUX = platform.system() == "Linux"
IS_LINUX_39 = IS_LINUX and sys.version_info[:2] == (3, 11)
IS_WINDOWS = platform.system() == "Windows"
IS_PYTHON_3_10 = sys.version_info[:2] == (3, 10)
IS_PYTHON_3_14 = sys.version_info[:2] == (3, 14)
BUFR_AVAILABLE = bufr_is_available()

info = Info()


def is_html_document(output: str) -> bool:
    """Say whether an HTML export is a whole document rather than a fragment.

    plotly 7 leads the document with a doctype where 6.x began straight at ``<html>``, and the
    plotly floor allows either.
    """
    return output.lstrip().lower().startswith(("<!doctype html>", "<html>"))


@pytest.fixture(autouse=True, scope="session")
def _worker_unique_cache_dir(tmp_path_factory: pytest.TempPathFactory, worker_id: str) -> None:
    """Give each pytest-xdist worker its own cache directory.

    Multiple workers writing to the same fsspec cache metadata file
    concurrently causes PermissionError (WinError 5) on Windows because
    os.replace() fails when the destination file is held open by another
    process. A per-worker directory eliminates that race entirely.

    The WD_CACHE_DIR env-var is honoured by pydantic-settings at
    Settings() instantiation time, so it takes effect for every Settings()
    created during the session.
    """
    cache = tmp_path_factory.mktemp(f"wd-cache-{worker_id}", numbered=False)
    os.environ["WD_CACHE_DIR"] = str(cache)
    yield
    del os.environ["WD_CACHE_DIR"]


@pytest.fixture(autouse=True, scope="session")
def _patch_windows_atomic_write() -> None:
    """Retry os.replace() inside fsspec on Windows to survive PermissionError.

    Tests that download hundreds of files concurrently (e.g. 1 536 files for
    the 1-minute precipitation dataset) schedule many async tasks in the same
    xdist worker.  All those tasks race to atomically update the single fsspec
    TTL-cache metadata file via os.replace().  On Windows, os.replace() raises
    PermissionError (WinError 5) when the destination is held open by another
    thread at the same instant.

    The fix proxies the ``os`` namespace visible inside ``fsspec.utils`` with
    a thin wrapper whose ``replace()`` retries with exponential back-off
    before re-raising.  The original binding is restored at session teardown.
    """
    if not IS_WINDOWS:
        yield
        return

    _orig_os = _fsspec_utils.os

    class _OsWithRetry:
        """Proxy around the ``os`` module that retries ``replace()`` on Windows."""

        def __getattr__(self, name: str) -> Any:  # noqa: ANN401
            return getattr(_orig_os, name)

        def replace(self, src: str, dst: str) -> None:
            delays = (0.05, 0.1, 0.2, 0.4)
            for delay in delays:
                try:
                    return _orig_os.replace(src, dst)
                except PermissionError:
                    time.sleep(delay)
            # final attempt — let it raise naturally
            return _orig_os.replace(src, dst)

    _fsspec_utils.os = _OsWithRetry()
    yield
    _fsspec_utils.os = _orig_os


def _is_local_address(address: object) -> bool:
    """Say whether a socket address points at this machine.

    Anything that is not an ``(host, port)`` tuple - a unix socket path, most notably - is local by
    definition. pytest-xdist talks to its workers over loopback, so loopback stays open.
    """
    if not isinstance(address, tuple) or not address:
        return True
    host = str(address[0])
    if host in {"", "localhost"} or host.endswith(".localhost"):
        return True
    try:
        parsed = ipaddress.ip_address(host)
    except ValueError:
        return False
    # a dual-stack socket reports a v4 peer as `::ffff:127.0.0.1`, and whether `is_loopback` looks
    # through that mapping has moved about between interpreters -- 3.12 answers False where 3.10,
    # 3.11, 3.13 and 3.14 answer True, and all five are in the CI matrix. Unwrapped here so the
    # answer is the same on all of them. The mapped address is asked the same question, so a mapped
    # `::ffff:8.8.8.8` stays refused
    parsed = getattr(parsed, "ipv4_mapped", None) or parsed
    return parsed.is_loopback or parsed.is_unspecified


_SOCKET_CONNECT = socket.socket.connect
_SOCKET_CONNECT_EX = socket.socket.connect_ex


class NetworkAccessBlockedError(Exception):
    """Raised in place of a connection an unmarked test tried to open.

    Deliberately not an `OSError`. The library treats being offline as a condition to degrade on
    rather than report: aiohttp turns any `OSError` from a connect into `ClientConnectorError`,
    `list_remote_files_fsspec` answers that with `[]`, and `download_file` answers it with a `File`
    carrying `NoInternetError` that `raise_if_exception` logs at debug. A guard that raised
    `OSError` was therefore swallowed by all three: the test either failed as
    `FileNotFoundError: url ... does not have a list of files`, which reads like an upstream
    restructure, or -- where an empty listing is a legitimate answer -- passed while testing
    nothing. Deriving straight from `Exception` puts this outside those three, so the missing
    marker is what the failure says.

    Not a `BaseException`, which would escape more: fsspec's `sync()` carries a result back from
    the loop thread through `except Exception`, and anything outside that is dropped for a `None`
    return rather than re-raised.

    Being an `Exception` does leave it catchable by the handful of call sites that degrade on a
    bare `except Exception` -- `provider/dwd/dmo/api.py` and `Wetterdienst.discover`'s `is_valid`
    among them. `_block_network` therefore also fails the test at teardown for a refusal that
    never reached it, so swallowing one postpones the failure rather than avoiding it.
    """


#: What the guard refused during the current test, and whether the test said it meant to provoke
#: one. Read at teardown, because a refusal a caller swallowed has to fail the test all the same.
_GUARD_STATE: dict[str, Any] = {"refused": [], "expected": False}

#: Whether the refusal is what ended the test itself. Set from the report hook below, because a
#: fixture's teardown cannot see how the call phase went, and the teardown check would otherwise
#: report a second time -- saying a caller swallowed it -- on the run where it plainly did not.
_REFUSAL_ENDED_TEST = pytest.StashKey[bool]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Note whether the guard's refusal is what ended this phase.

    Setup as well as the call: a fixture that downloads something is an ordinary thing to write,
    and the refusal reaches the runner from there just as plainly. Accumulated rather than
    assigned, so the later phase does not answer for the earlier one. A refusal raised in another
    fixture's *teardown* is still reported twice -- that report is made after `_block_network` has
    already run its check, so there is nothing for the check to read.

    Only where the phase actually failed, so the stash does not claim a refusal was reported when
    `xfail` turned it into a green xfail instead. That does not rescue the `xfail` case -- see the
    fixture below -- it only keeps this from saying something untrue about it.
    """
    report = yield
    if call.when in {"setup", "call"}:
        ended = (
            call.excinfo is not None
            and isinstance(call.excinfo.value, NetworkAccessBlockedError)
            and report.outcome == "failed"
        )
        item.stash[_REFUSAL_ENDED_TEST] = item.stash.get(_REFUSAL_ENDED_TEST, default=False) or ended
    return report


def _guarded(original: Any) -> Any:  # noqa: ANN401
    """Wrap a socket connect method so that it refuses anything not on this machine."""

    def wrapper(self: socket.socket, address: object, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if not _is_local_address(address):
            msg = (
                f"network access blocked: {address}. A test that reaches the internet needs "
                f"@pytest.mark.remote, or has to be rewritten to work without the network."
            )
            _GUARD_STATE["refused"].append(address)
            raise NetworkAccessBlockedError(msg)
        return original(self, address, *args, **kwargs)

    return wrapper


@pytest.fixture
def blocked_network() -> list[object]:
    """Say that this test provokes the guard on purpose, and hand it what was refused.

    Without it a refusal fails the test at teardown even where nothing propagated, which is the
    point of the teardown check. Requested after the autouse fixture has armed it, so the flag is
    set between that fixture's setup and its teardown.
    """
    _GUARD_STATE["expected"] = True
    return _GUARD_STATE["refused"]


@pytest.fixture(autouse=True)
def _block_network(request: pytest.FixtureRequest) -> None:
    """Refuse non-local socket connections for every test not marked ``remote``.

    ``-m "not remote"`` is documented as the offline selection, so nothing it selects may reach
    upstream. Without this guard an unmarked test that downloads something passes on a warm cache
    and fails on a cold one, which reads like a regression rather than a missing marker.

    The patching is done by hand rather than through ``monkeypatch``, because an autouse fixture
    requesting ``monkeypatch`` would pull it ahead of the module-level fixtures that expect to be
    torn down first.

    Three things it does not cover, all of which would let a connection through rather than refuse
    one wrongly. It is installed per test, so a connection opened at import time or by a
    session-scoped fixture is made before it is in place. It patches `socket.connect`, which on
    Windows is not the path asyncio's `ProactorEventLoop` takes -- that connects through
    `_overlapped.ConnectEx`. And it only sees a connection being opened: fsspec keeps one
    filesystem instance per key, and with it one aiohttp session and its keep-alive pool, for the
    life of the worker, so an unmarked test asking for a url a `remote` test has just fetched can
    be served over a connection that is already up. Name resolution goes out regardless.

    And a fourth, which is pytest rather than this guard: a non-strict `@pytest.mark.xfail` absorbs
    everything a test can report, the teardown check below included -- a bare `pytest.fail()` in a
    fixture's teardown comes back as a second xfail and the run stays green. So a test that is both
    unmarked and `xfail` can reach upstream and say nothing, and no check made per test can change
    that. `test_benchmarks` was the one in the tree; it is marked now.

    So this holds the suite to its own claim; it is not a sandbox.
    """
    if request.node.get_closest_marker("remote"):
        yield
        return
    # cleared rather than rebound, so a reference `blocked_network` handed out stays the live one
    _GUARD_STATE["refused"].clear()
    _GUARD_STATE["expected"] = False
    socket.socket.connect = _guarded(_SOCKET_CONNECT)
    socket.socket.connect_ex = _guarded(_SOCKET_CONNECT_EX)
    try:
        yield
    finally:
        socket.socket.connect = _SOCKET_CONNECT
        socket.socket.connect_ex = _SOCKET_CONNECT_EX
        refused = list(_GUARD_STATE["refused"])
        reported = request.node.stash.get(_REFUSAL_ENDED_TEST, default=False)
        if refused and not _GUARD_STATE["expected"] and not reported:
            # the test ended on something other than the refusal, so something between the socket
            # and the test caught it -- `list_remote_files_fsspec` and `download_file` no longer
            # do, but several providers degrade on a bare `except Exception`. Said here, because a
            # refusal nobody reported is the vacuous pass this guard exists to stop
            pytest.fail(
                f"network access blocked: {refused}. A test that reaches the internet needs "
                f"@pytest.mark.remote, or has to be rewritten to work without the network. The "
                f"refusal did not reach the test, so something on the way caught it.",
            )


@pytest.fixture
def default_settings() -> Settings:
    """Provide default settings."""
    return Settings()


@pytest.fixture
def settings_drop_nulls_false() -> Settings:
    """Provide no drop nulls settings."""
    return Settings(ts_drop_nulls=False)


@pytest.fixture
def settings_convert_units_false() -> Settings:
    """Provide no unit conversion settings."""
    return Settings(ts_convert_units=False)


# True settings
@pytest.fixture
def settings_skip_empty_true() -> Settings:
    """Provide skip empty settings."""
    return Settings(ts_skip_empty=True)


# False settings
@pytest.fixture
def settings_humanize_false_drop_nulls_false() -> Settings:
    """Provide no humanize and no drop nulls settings."""
    return Settings(ts_humanize=False, ts_drop_nulls=False)


@pytest.fixture
def settings_humanize_false_convert_units_false() -> Settings:
    """Provide no humanize and no unit conversion settings."""
    return Settings(ts_humanize=False, ts_convert_units=False)


@pytest.fixture
def settings_humanize_false_convert_units_false_wide_shape() -> Settings:
    """Provide wide shape, no humanize and no unit conversion settings."""
    return Settings(ts_shape="wide", ts_humanize=False, ts_convert_units=False)


@pytest.fixture
def settings_humanize_false_wide_shape() -> Settings:
    """Provide wide shape and no humanize settings."""
    return Settings(ts_shape="wide", ts_humanize=False)


@pytest.fixture
def settings_convert_units_false_wide_shape() -> Settings:
    """Provide wide shape and no unit conversion settings."""
    return Settings(ts_shape="wide", ts_convert_units=False)


@pytest.fixture
def settings_wide_shape() -> Settings:
    """Provide wide shape settings."""
    return Settings(ts_shape="wide")


@pytest.fixture
def metadata() -> dict:
    """Provide metadata."""
    return {
        "producer": {
            "doi": "10.5281/zenodo.3960624",
            "name": "wetterdienst",
            "version": info.version,
            "repository": "https://github.com/earthobservations/wetterdienst",
            "documentation": "https://wetterdienst.readthedocs.io",
        },
        "provider": {
            "copyright": "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
            "country": "Germany",
            "name_english": "German Weather Service",
            "name_local": "Deutscher Wetterdienst",
            "url": "https://opendata.dwd.de/climate_environment/CDC/",
        },
    }
