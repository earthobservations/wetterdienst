# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""End the work of a request whose answer is gone (GH-4429).

A REST or MCP request that runs into the timeout is answered with a 504, but the handler that was reading the stations
runs in a thread, which cannot be cancelled: it used to go on to the last station, holding its place of the cap and
downloading. The server now sets a `Cancellation` around the work of a request (`ui.middleware`, `ui.streaming`), sets
it when the answer has timed out or the client has left, and the walk looks at it where it is cheap to: between stations
(`TimeseriesValues.query`, which `interpolate` and `summarize` walk too), before a file is downloaded
(`util.network.download_file` and `download_files`, so also between the files of one station and the listings of one
network) and between the rows of an interpolation. A thread that finds it set raises `WorkAbandoned`, which ends the
work and answers nothing: whoever set it has answered already.

- **A context variable, set by the server.** Nothing about a signature changes. The variable is copied into the thread
  that runs a handler and into the thread that produces a chunk of a stream (both run in a copy of the context of the
  request), but not into the threads that a pool starts of its own: `download_files` and the fetch-ahead take the
  `Cancellation` where they are made and look at it themselves. A concurrent request has a `Cancellation` of its own,
  and a request that the server does not time (Python, the CLI, the index) has none, where `check` does nothing.
- **A flag, not a time.** The server sets it at the moment it answers the 504 (or sees the client go), so that
  what the client is told and what the work does are one decision: a walk that read the clock itself could end with an
  exception before the middleware's timer fires, and the answer would be the 500 of that exception and not the 504.
- **`BaseException`**, as `asyncio.CancelledError` is: the many `except Exception` of providers, retries and
  fallbacks that turn a failure into a skipped file or a warning must not turn the end of the work into either.
- **Never in the middle of a file.** The checks are at the start of a step, never inside a download, a cache write or
  while the lock file of the cache is held, so a download in hand is finished and a cache is never left half written.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


class WorkAbandoned(BaseException):
    """The answer of the request this work was for is gone: stop, and do not answer."""


class Cancellation:
    """Whether the answer of a request is gone, and why: set once, by whoever answered or saw the client leave."""

    __slots__ = ("_reason",)

    def __init__(self) -> None:
        """Make one that has not been set."""
        self._reason: str | None = None

    def set(self, reason: str) -> None:
        """End the work, for `reason` (`timeout`, `client-left`, ...); the first reason stays."""
        if self._reason is None:
            self._reason = reason

    @property
    def reason(self) -> str | None:
        """Why the work ended, None while it has not."""
        return self._reason

    def is_set(self) -> bool:
        """Tell whether the work has been ended."""
        return self._reason is not None

    def check(self) -> None:
        """Raise `WorkAbandoned` if the work has been ended."""
        if self._reason is not None:
            raise WorkAbandoned(self._reason)


_CURRENT: contextvars.ContextVar[Cancellation | None] = contextvars.ContextVar(
    "wetterdienst_cancellation", default=None
)


def current() -> Cancellation | None:
    """Give the `Cancellation` of the request this runs for, None where there is none (Python, the CLI)."""
    return _CURRENT.get()


def check() -> None:
    """Raise `WorkAbandoned` if the request this runs for has had its work ended; with no request, do nothing."""
    cancellation = _CURRENT.get()
    if cancellation is not None:
        cancellation.check()


@contextmanager
def cancellable(cancellation: Cancellation) -> Iterator[Cancellation]:
    """Run what is started inside, and its threads that copy the context, under `cancellation`."""
    token = _CURRENT.set(cancellation)
    try:
        yield cancellation
    finally:
        _CURRENT.reset(token)
