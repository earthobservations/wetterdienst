# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What it means for the REST API to be ready, as `GET /ready` answers it (GH-3134).

`/health` says the process answers. It stays that: it reads nothing and cannot fail but by the process being gone, which
is what a restart is for. `/ready` says the server can serve a data request, which can stop being true while the process
is fine, and a restart is not the cure: the cure is the operator's, and a load balancer meanwhile sends the traffic
elsewhere. It checks what every data request needs of this server and nothing it needs of anyone else:

- **`settings`**: the `WD_*` and `WD_TS_*` settings build. They are checked as the server starts, and every request
  reads them again, so a `.env` that was edited into something invalid afterwards makes every data request a 500.
- **`cache`**: the library can cache and download. An unusable cache directory (a file, a volume nobody may write
  to) is no reason: the library caches in a temporary directory instead, warns once and goes on (`_fallback_cache_dir`
  of `util.network`, GH-2860), and the requests are served. What stops a download is that fallback failing as well, so
  `cache` fails where neither the cache directory nor the temporary directory can be written to (and the cache is not
  disabled). A full disk is not found out: that takes a write, which a probe that runs every few seconds should not
  make.

It asks no provider, so a provider that is down does not make the server not ready: those requests fail with the 5xx
that says so (`upstream-failed`, `upstream-unreachable`, `upstream-timeout`) and the rest are served. It needs no
credential and reads no file but the settings and the cache directory's metadata. It does not look at the load: a server
that works on as many requests as it allows answers those that count with a 503 (`server-busy`) and stays ready.
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

from wetterdienst.settings import Settings, check_settings
from wetterdienst.util.logging import get_one_line_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

log = get_one_line_logger(__name__)

#: whether the settings are being built by a probe, which writes nothing: building them logs a line (the cache they
#: are built with) for every request that does, and a probe every few seconds would write the same line each time
_QUIET: ContextVar[bool] = ContextVar("wetterdienst_readiness_quiet", default=False)


class _DropWhileQuiet(logging.Filter):
    """Drop what the settings log while a probe builds them, for that probe's thread or task alone."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: ARG002
        return not _QUIET.get()


logging.getLogger("wetterdienst.settings").addFilter(_DropWhileQuiet())


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """Build the settings without a line in the log."""
    token = _QUIET.set(True)
    try:
        yield
    finally:
        _QUIET.reset(token)


#: what is checked, in the order it is told
CHECKS = ("settings", "cache")

#: what the last probe that failed logged, so that a probe every few seconds does not write the same lines again
_logged: tuple[str, ...] = ()


def _report(lines: list[str]) -> None:
    """Log why the server is not ready, once for as long as the reasons stay the same."""
    global _logged  # noqa: PLW0603
    if tuple(lines) != _logged:
        for line in lines:
            log.warning(f"The server is not ready: {line}")
    _logged = tuple(lines)


def _settings_problems() -> list[str]:
    """Tell what is wrong with the settings, naming the variables as the start does, without their values."""
    try:
        with _quiet():
            return check_settings()
    except Exception as e:  # noqa: BLE001
        # told by its type alone, as the start does: its message may carry what it was given
        return [f"the settings could not be built: {type(e).__name__}"]


def _writable_or_makeable(directory: Path) -> bool:
    """Tell whether a directory can be written to, or made, which takes the nearest one that exists to be writable."""
    for candidate in (directory, *directory.parents):
        try:
            if candidate.exists():
                return candidate.is_dir() and os.access(candidate, os.W_OK | os.X_OK)
        except OSError:
            # an ancestor that cannot be searched: `exists` raises where the Python is older than 3.14
            return False
    return False


def _temporary_dir_writable() -> bool:
    """Tell whether the library's fallback can be made: a temporary directory, where a cache directory fails."""
    try:
        # `mkdtemp` makes the directory inside this one, and does not make this one
        return os.access(tempfile.gettempdir(), os.W_OK | os.X_OK)
    except OSError:
        # no directory for temporary files at all
        return False


def _cache_problem() -> str | None:
    """Tell what is wrong with the cache, given settings that build: nothing, unless the fallback fails too."""
    with _quiet():
        settings = Settings()
    if settings.cache_disable or _writable_or_makeable(Path(settings.cache_dir)) or _temporary_dir_writable():
        return None
    return "neither the cache directory nor the temporary directory is a directory the server can write to or make"


def failed_checks() -> list[str]:
    """Run the checks and name those that failed, none where the server is ready."""
    if problems := _settings_problems():
        # with settings that do not build there is no cache directory to look at
        _report([f"a setting is invalid: {problem}" for problem in problems])
        return ["settings"]
    if problem := _cache_problem():
        _report([problem])
        return ["cache"]
    _report([])
    return []
