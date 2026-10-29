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
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, NotRequired

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence


class ResponseWarning(TypedDict):
    """One thing an answer is missing, told by a `code` that stays and a `message` that may improve."""

    code: str
    message: str
    #: what the warning is about, where it is about one parameter: `resolution/dataset/parameter`, or
    #: `resolution/dataset` for a whole dataset (`parameter-without-rows`)
    parameter: NotRequired[str]
    #: the stations the warning is about, as many as it lists (`parameter-without-rows`, `file-skipped`)
    stations: NotRequired[list[str]]


#: the code of the warning that counts the readings the source wrote a marker for, and its message
MISSING_VALUE_MARKER = "missing-value-marker"
MISSING_VALUE_MARKER_MESSAGE = (
    "{count} readings of the source were a marker for a missing value, or a number no sensor can have produced, "
    "and are null; with drop_nulls they are not in the answer, without it the text the source wrote is the `raw:` "
    "token of their quality_flags."
)

#: the code of the warning that names a requested parameter the source holds no values for, at any station asked about
PARAMETER_WITHOUT_ROWS = "parameter-without-rows"

#: the code of the warning that names the stations whose file the provider let go (`note_skipped_download`), so that a
#: partial answer can be told from a whole one
FILE_SKIPPED = "file-skipped"

#: the parameters a warning names while a walk collects one station (`collecting`), which the response warnings of
#: the request cannot tell where nothing is recorded (the library as a library)
_NAMED: ContextVar[set[str] | None] = ContextVar("wetterdienst_named_parameters", default=None)
_RECORDED: ContextVar[list[ResponseWarning] | None] = ContextVar("wetterdienst_response_warnings", default=None)
#: the warnings that count something across the whole request, by code: the count and the message, where `{count}` is
#: the number
_COUNTED: ContextVar[dict[str, list[Any]] | None] = ContextVar("wetterdienst_counted_warnings", default=None)


#: what a provider tells when it lets a file of the station being collected go (`note_skipped_download`): set by the
#: walk of the values around the collection of one station, and `None` outside it
_SKIPPING: ContextVar[Callable[[bool], None] | None] = ContextVar("wetterdienst_skipping", default=None)


@contextmanager
def collecting(note: Callable[[bool], None], named: set[str] | None = None) -> Iterator[None]:
    """Have `note` told what a provider lets go while the block runs, which is the collection of one station.

    The `parameter` of every warning raised meanwhile is added to `named`, for a walk that must not say again what
    another warning has said of a parameter (`parameter-without-rows` after `parameter-ended`): the warnings of the
    request are not kept outside a response, but the log lines are written all the same, and would repeat. Both are
    the block's alone, so that walks that overlap (interleaved, or one in the other's collection) keep to their own.
    """
    skipping = _SKIPPING.set(note)
    watching = _NAMED.set(named)
    try:
        yield
    finally:
        _NAMED.reset(watching)
        _SKIPPING.reset(skipping)


def note_skipped_download(*, whole_request: bool = False) -> None:
    """Tell that the provider let a file go and answers without it: a station's readings may be missing for that.

    For the places where a provider gives up on a file it expected to be there and goes on with the others: a
    download that failed for good (a refusal, a file withdrawn since the listing, a timestamp not published), a body
    that is an error in the guise of an answer (a maintenance page, an exception report), a file that would not
    parse, or a reader that returns for want of a window without asking the source at all. Not for an answer that
    says there is nothing (a 404 for a station that does not report the parameter,
    Frost's 412), nor for a download that failed and was made again with success. The station being collected is then
    no evidence that the source holds nothing, and `parameter-without-rows` does not count it (`whole_request` for a
    file that every station of the request is read from). Nothing happens outside the collection of a station.

    What is told is the other side of that: once the walk is over, `file-skipped` names the stations whose file was
    let go (`ParameterRows.warn`), one warning for the request. A provider that lets a file go without calling this
    says nothing.
    """
    note = _SKIPPING.get()
    if note is not None:
        note(whole_request)


def begin_response() -> None:
    """Start recording the warnings of the request being served, forgetting those of an earlier one.

    Whatever served the request before is forgotten too: the lists belong to the context the request runs
    in, which is a thread of the server for each request and the process for the command line.
    """
    _RECORDED.set([])
    _COUNTED.set({})


def count_response_warning(code: str, count: int, message: str) -> None:
    """Add `count` to the warning `code` of the request being served, whose `message` has `{count}` for the total.

    For what happens many times in a request, once for each station: the answer tells it once, with the sum.
    Nothing is recorded outside a request.
    """
    counted = _COUNTED.get()
    if counted is None or count <= 0:
        return
    entry = counted.setdefault(code, [0, message])
    entry[0] += count


def warn_response(
    log: logging.Logger,
    code: str,
    message: str,
    *,
    level: int = logging.WARNING,
    parameter: str | None = None,
    stations: Sequence[str] | None = None,
) -> None:
    """Log `message` as `log` does at `level`, and record it under `code` for the answer of the request being served.

    A warning about one `parameter` and its `stations` carries them as members beside the code and the message.
    A warning recorded twice, as an estimate asks the same stations for each parameter, is told once.
    """
    log.log(level, message)
    named = _NAMED.get()
    # not the warning of this very code, which is raised after a walk, and must not silence another one
    if named is not None and parameter is not None and code != PARAMETER_WITHOUT_ROWS:
        named.add(parameter)
    recorded = _RECORDED.get()
    warning: ResponseWarning = {"code": code, "message": message}
    if parameter is not None:
        warning["parameter"] = parameter
    if stations is not None:
        warning["stations"] = list(stations)
    if recorded is not None and warning not in recorded:
        recorded.append(warning)


def recorded_warnings() -> list[ResponseWarning]:
    """Give the warnings recorded since `begin_response`, in the order they were raised, the counted ones last."""
    counted = [
        ResponseWarning(code=code, message=message.format(count=count))
        for code, (count, message) in (_COUNTED.get() or {}).items()
    ]
    return [*(_RECORDED.get() or []), *counted]
