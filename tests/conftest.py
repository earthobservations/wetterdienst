# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures for tests."""

import ipaddress
import os
import platform
import socket
import sys
import time
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
    nothing. Deriving straight from `Exception` puts this outside every one of those handlers, so
    the missing marker is what the failure says.

    Not a `BaseException`, though that would also escape them: fsspec's `sync()` carries a result
    back from the loop thread through `except Exception`, and anything outside that is dropped for
    a `None` return rather than re-raised.
    """


def _guarded(original: Any) -> Any:  # noqa: ANN401
    """Wrap a socket connect method so that it refuses anything not on this machine."""

    def wrapper(self: socket.socket, address: object, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if not _is_local_address(address):
            msg = (
                f"network access blocked: {address}. A test that reaches the internet needs "
                f"@pytest.mark.remote, or has to be rewritten to work without the network."
            )
            raise NetworkAccessBlockedError(msg)
        return original(self, address, *args, **kwargs)

    return wrapper


@pytest.fixture(autouse=True)
def _block_network(request: pytest.FixtureRequest) -> None:
    """Refuse non-local socket connections for every test not marked ``remote``.

    ``-m "not remote"`` is documented as the offline selection, so nothing it selects may reach
    upstream. Without this guard an unmarked test that downloads something passes on a warm cache
    and fails on a cold one, which reads like a regression rather than a missing marker.

    The patching is done by hand rather than through ``monkeypatch``, because an autouse fixture
    requesting ``monkeypatch`` would pull it ahead of the module-level fixtures that expect to be
    torn down first.

    Two things it does not cover, both of which would let a connection through rather than refuse
    one wrongly: it is installed per test, so a connection opened at import time or by a
    session-scoped fixture is made before it is in place; and it patches `socket.connect`, which on
    Windows is not the path asyncio's `ProactorEventLoop` takes -- that connects through
    `_overlapped.ConnectEx`. Name resolution goes out either way. So this is what holds the suite
    to its own claim, not a sandbox.
    """
    if request.node.get_closest_marker("remote"):
        yield
        return
    socket.socket.connect = _guarded(_SOCKET_CONNECT)
    socket.socket.connect_ex = _guarded(_SOCKET_CONNECT_EX)
    try:
        yield
    finally:
        socket.socket.connect = _SOCKET_CONNECT
        socket.socket.connect_ex = _SOCKET_CONNECT_EX


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
