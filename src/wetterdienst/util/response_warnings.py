# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What an answer is missing but did not fail on, told to the caller with the answer (GH-2561).

A request can be answered in part: an id that no station has is left out, a period the datasets do not
publish is skipped, a station with too few readings is dropped. Each was a line in the server's log, which a
caller of the REST API cannot read. `warn_response` writes the line as before and, where the answer is being
built for a caller (`begin_response`), also records it, so that the `warnings` of the answer's metadata name it
by a stable `code`.

The record is per request: a context variable, which the thread of a REST handler (FastAPI copies the context
into it) and a command of the command line each start empty. Outside a request, which is every use of the
library as a library, nothing is recorded and the call is a log line.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

from typing_extensions import TypedDict


class ResponseWarning(TypedDict):
    """One thing an answer is missing, told by a `code` that stays and a `message` that may improve."""

    code: str
    message: str


_RECORDED: ContextVar[list[ResponseWarning] | None] = ContextVar("wetterdienst_response_warnings", default=None)


def begin_response() -> None:
    """Start recording the warnings of the request being served, forgetting those of an earlier one."""
    _RECORDED.set([])


def warn_response(log: logging.Logger, code: str, message: str, *, level: int = logging.WARNING) -> None:
    """Log `message` as `log` does at `level`, and record it under `code` for the answer of the request being served.

    A warning recorded twice, as an estimate asks the same stations for each parameter, is told once.
    """
    log.log(level, message)
    recorded = _RECORDED.get()
    warning: ResponseWarning = {"code": code, "message": message}
    if recorded is not None and warning not in recorded:
        recorded.append(warning)


def recorded_warnings() -> list[ResponseWarning]:
    """Give the warnings recorded since `begin_response`, in the order they were raised."""
    return list(_RECORDED.get() or [])
