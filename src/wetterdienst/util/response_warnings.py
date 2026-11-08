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
from enum import Enum
from typing import TYPE_CHECKING, Any, NotRequired

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence
    from datetime import datetime


class ResponseWarning(TypedDict):
    """One thing an answer is missing, told by a `code` that stays and a `message` that may improve."""

    code: str
    message: str
    #: what the warning is about, where it is about one parameter: `resolution/dataset/parameter`, or
    #: `resolution/dataset` for a whole dataset (`parameter-without-rows`); always `resolution/dataset/parameter` for
    #: `other-window-left-out` and `window-not-closed`
    parameter: NotRequired[str]
    #: the stations the warning is about, as many as it lists (`parameter-without-rows`, `file-skipped`,
    #: `other-window-left-out`, `window-not-closed`, `station-without-rows`, `source-data-left-out`)
    stations: NotRequired[list[str]]


#: the attribute of the log record of a response warning, holding its code: what tells the line that qualifies the
#: answer (a file the provider let go, readings a check rejected, a parameter without rows, dates left out for another
#: window) from the log around it,
#: for a handler that lets only these and the errors through (`--quiet` of the command line, GH-3134)
RESPONSE_WARNING_RECORD = "response_warning"

#: the code of the warning that counts the readings the source wrote a marker for, and its message
MISSING_VALUE_MARKER = "missing-value-marker"
MISSING_VALUE_MARKER_MESSAGE = (
    "{count} readings of the source were a marker for a missing value and are null; with drop_nulls they are not in "
    "the answer, without it the text the source wrote is the `raw:` token of their quality_flags."
)

#: the code of the warning that counts the wind directions the source wrote as a calm (GH-3696): a calm is a state of
#: the wind with no direction, not a reading that is missing, so `missing-value-marker` does not count them
CALM_WIND_DIRECTION = "calm-wind-direction"
CALM_WIND_DIRECTION_MESSAGE = (
    "{count} wind directions were a calm, which the source writes as 0 and which has no direction: they are null, "
    "and no reading is missing; with drop_nulls they are not in the answer, without it `raw:0` in their "
    "quality_flags keeps them."
)

#: the code of the warning that counts the values a hard plausibility check rejected (GH-3682): the source wrote a
#: number there, not a marker, so `missing-value-marker` does not count them. `{details}` is the count per check
REJECTED_BY_PLAUSIBILITY = "rejected-by-plausibility"
REJECTED_BY_PLAUSIBILITY_MESSAGE = (
    "{count} values were numbers a plausibility check rejected ({details}; a value several checks rejected is "
    "counted under each) and are null; with drop_nulls they are not in the answer, without it the number the "
    "source wrote is the `raw:` token of their quality_flags, after `rejected:<check>`. Set the check to `soft` to "
    "keep them."
)

#: the code of the warning that names a requested parameter the source holds no values for, at any station asked about
PARAMETER_WITHOUT_ROWS = "parameter-without-rows"

#: the code of the warning that names the stations a request asked for by id (`stations=`) that returned no rows while
#: other stations of it did (GH-3828): the answer holds none of their rows, which `values` alone does not say
STATION_WITHOUT_ROWS = "station-without-rows"

#: the code of the warning that names the stations whose file the provider let go (`note_skipped_download`), so that a
#: partial answer can be told from a whole one
FILE_SKIPPED = "file-skipped"

#: the code of the warning that names the parameters whose rows of another window the provider left out of the answer
#: (`note_left_out`): the source holds values for those dates, but of a series that is not the one the parameter is
#: (Frost's 18-18 UTC precipitation beside the 06-06 UTC one, its calendar-day temperature extreme beside the 18-18
#: UTC one): no missing data, and no values of the parameter
OTHER_WINDOW_LEFT_OUT = "other-window-left-out"

#: the code of the warning that counts the values whose window had not closed when the request was served (GH-3856):
#: Frost serves the daily, monthly and annual value of a period that is still going on and marks nothing, so a
#: value of a day is left out (`note_open_window`, `returned` false) and one of the month or the year is returned,
#: marked `completeness:Incomplete` in its `quality_flags` (`returned` true). Not missing data: ask again once the
#: window has closed
WINDOW_NOT_CLOSED = "window-not-closed"

#: the code of the one warning an estimate (`interpolate`, `summarize`) tells of the source data its walk left out
#: (GH-3848): the stations it read whose file the provider let go (`note_skipped_download`), those whose dates of
#: another series were left out (`note_left_out`), those whose values of a window that had not closed the provider left
#: out (`note_open_window`, GH-3883) and those with values a hard plausibility check rejected, counted by
#: cause, in one warning for the answer. An estimate reads the stations around a point as candidates, so it tells none
#: of `file-skipped`, `other-window-left-out` and `window-not-closed` of each station, nor `parameter-without-rows`,
#: which a station without a parameter is the ordinary case of
SOURCE_DATA_LEFT_OUT = "source-data-left-out"


class SkipCause(Enum):
    """Why a provider let a file go (`note_skipped_download`), which decides what `file-skipped` advises.

    Each member holds the clause the warning gives for it (`reason`), the noun of the grouped advice (`noun`, as
    `source-data-left-out` words it) and whether the cause can heal (`may_heal`): a download that failed, a file
    withdrawn since the listing, a maintenance page and a directory found empty may be back, so asking again is worth
    it; a download refused for its size, its time or an unannounced compression, and a file that would not parse,
    mostly stay as they are, and a caller who retries them gets the same.
    """

    #: the download failed (a reset, a timeout, a 5xx, a 4xx answer)
    FAILED = ("the download failed", "a failed download", True)
    #: the file the listing named is not on the server (a 404)
    WITHDRAWN = ("the file was gone", "a withdrawn file", True)
    #: a body that is no answer: a maintenance page, an exception report, an empty 200
    MAINTENANCE = ("a maintenance page came in its place", "a maintenance page", True)
    #: the directory that was to list the files came back empty or missing
    EMPTY_DIRECTORY = ("the directory was found empty", "an empty directory", True)
    #: the download was refused: too large, too slow, or compressed while its name says it is not
    REFUSED = ("the download was refused", "a refused download", False)
    #: the file arrived and would not parse, or held what the reader cannot use
    UNPARSEABLE = ("it would not parse", "a file that would not parse", False)

    def __init__(self, reason: str, noun: str, may_heal: bool) -> None:  # noqa: FBT001
        """Keep the clause of the warning, the noun of the advice and whether the cause can heal."""
        self.reason = reason
        self.noun = noun
        self.may_heal = may_heal


def _joined(phrases: Sequence[str], conjunction: str = "and") -> str:
    """Join phrases as prose: `a`, `a and b`, `a, b and c`."""
    if len(phrases) <= 1:
        return "".join(phrases)
    return f"{', '.join(phrases[:-1])} {conjunction} {phrases[-1]}"


def tell_skip_causes(causes: Iterable[SkipCause]) -> str:
    """Give why files were let go, as a clause of `file-skipped`: `the download failed or it would not parse`."""
    wanted = set(causes)
    return _joined([cause.reason for cause in SkipCause if cause in wanted], "or")


def advise_on_skip_causes(causes: Iterable[SkipCause]) -> str:
    """Give what a caller can do about files let go for `causes`, as `file-skipped` says it.

    Only the causes that can heal are told to try again later. A refused download or a file that would not parse
    mostly stays as it is, so the advice is to report it to the provider; where both kinds occurred the two are
    grouped as the warning of an estimate (`source-data-left-out`) groups them, naming the causes that occurred.
    """
    wanted = set(causes)
    healing = [cause.noun for cause in SkipCause if cause in wanted and cause.may_heal]
    lasting = [cause.noun for cause in SkipCause if cause in wanted and not cause.may_heal]
    if not lasting:
        return "Try again later."
    if not healing:
        return (
            f"{_joined(lasting).capitalize()} is unlikely to change, so trying again will not help; if it keeps "
            "happening, report it to the provider."
        )
    return (
        f"{_joined(healing).capitalize()} may be back later, so try again; {_joined(lasting)} mostly stays as it is, "
        "and is worth reporting to the provider."
    )


#: the parameters a warning names while a walk collects one station (`collecting`), which the response warnings of
#: the request cannot tell where nothing is recorded (the library as a library)
_NAMED: ContextVar[set[str] | None] = ContextVar("wetterdienst_named_parameters", default=None)
_RECORDED: ContextVar[list[ResponseWarning] | None] = ContextVar("wetterdienst_response_warnings", default=None)
#: the warnings that count something across the whole request, by code: the count, the message, where `{count}` is
#: the number, and the count by detail (`{details}` in the message, as `range 3, stuck 2`)
_COUNTED: ContextVar[dict[str, list[Any]] | None] = ContextVar("wetterdienst_counted_warnings", default=None)


#: what a provider tells when it lets a file of the station being collected go (`note_skipped_download`): set by the
#: walk of the values around the collection of one station, and `None` outside it
_SKIPPING: ContextVar[Callable[[bool, SkipCause], None] | None] = ContextVar("wetterdienst_skipping", default=None)
#: what a provider tells when it leaves the rows of another window out of the station being collected
#: (`note_left_out`), set like `_SKIPPING`
_LEFT_OUT: ContextVar[Callable[[str, int, str], None] | None] = ContextVar("wetterdienst_left_out", default=None)
#: what a provider tells when the station being collected has values of a window that had not closed
#: (`note_open_window`), set like `_SKIPPING`
_OPEN_WINDOW: ContextVar[Callable[[str, int, datetime, bool], None] | None] = ContextVar(
    "wetterdienst_open_window", default=None
)


@contextmanager
def collecting(
    note: Callable[[bool, SkipCause], None],
    named: set[str] | None = None,
    left_out: Callable[[str, int, str], None] | None = None,
    open_window: Callable[[str, int, datetime, bool], None] | None = None,
) -> Iterator[None]:
    """Have `note` told what a provider lets go while the block runs, which is the collection of one station.

    The `parameter` of every warning raised meanwhile is added to `named`, for a walk that must not say again what
    another warning has said of a parameter (`parameter-without-rows` after `parameter-ended`): the warnings of the
    request are not kept outside a response, but the log lines are written all the same, and would repeat. Both are
    the block's alone, so that walks that overlap (interleaved, or one in the other's collection) keep to their own.
    `left_out` is told the rows of another window that the provider left out (`note_left_out`), `open_window` the
    values of a window that had not closed (`note_open_window`).
    """
    skipping = _SKIPPING.set(note)
    watching = _NAMED.set(named)
    leaving = _LEFT_OUT.set(left_out)
    opening = _OPEN_WINDOW.set(open_window)
    try:
        yield
    finally:
        _OPEN_WINDOW.reset(opening)
        _LEFT_OUT.reset(leaving)
        _NAMED.reset(watching)
        _SKIPPING.reset(skipping)


def note_left_out(parameter: str, count: int, because: str) -> None:
    """Tell that the provider left `count` dates of `parameter` out of the station being collected: another window's.

    For a source that holds more than one series of a parameter that differ in the window they sum or extremise
    (Frost's `PT6H` and `PT18H` precipitation, `PT0H` and `PT18H` temperature extremes, `PT0H` and `PT6H` mean
    temperature) and returns one. A date that
    only the other series has is left out, as a value of the other window under this parameter's name would be wrong,
    and the answer then has no row for it although the source has values: `OTHER_WINDOW_LEFT_OUT` says so once the
    walk is over (`ParameterRows.warn`), which is the difference to a parameter the source holds nothing of
    (`parameter-without-rows`, which does not name a parameter this was told of).

    ``parameter`` is `resolution/dataset/parameter`, ``because`` says which series was left out and which one is
    returned, as a clause of the warning. Nothing happens outside the collection of a station.
    """
    note = _LEFT_OUT.get()
    if note is not None and count > 0:
        note(parameter, count, because)


def note_open_window(parameter: str, count: int, closes: datetime, *, returned: bool) -> None:
    """Tell that `count` values of `parameter` at the station being collected are of a window that had not closed.

    For a source that serves the value of a period that is still going on and does not mark it (Frost: the day's
    extreme, sum or mean before the window ends, the month so far): a daily value of it is a partial extreme, sum or
    mean that comes back looking like the day's. ``returned`` is whether the provider handed the values over (marked in
    their `quality_flags`) or left them out of the answer. `WINDOW_NOT_CLOSED` says so once the walk is over
    (`ParameterRows.warn`), with the number of values and the time the earliest window closes, ``closes``, which is
    UTC. A parameter whose values were left out is no "the source has no values" (`parameter-without-rows`).

    ``parameter`` is `resolution/dataset/parameter`. Nothing happens outside the collection of a station.
    """
    note = _OPEN_WINDOW.get()
    if note is not None and count > 0:
        note(parameter, count, closes, returned)


def note_skipped_download(cause: SkipCause, *, whole_request: bool = False) -> None:
    """Tell that the provider let a file go and answers without it: a station's readings may be missing for that.

    For the places where a provider gives up on a file it expected to be there and goes on with the others: a
    download that failed for good (a refusal, a file withdrawn since the listing, a timestamp not published), a body
    that is an error in the guise of an answer (a maintenance page, an exception report), a file that would not
    parse. The station being collected is then no evidence that the source holds nothing, and
    `parameter-without-rows` does not count it (`whole_request` for a file that every station of the request is read
    from). ``cause`` is why (`SkipCause`), which `file-skipped` words its advice by. It is required: a call that left
    it out would send a caller to retry what cannot heal.

    Not for an answer that says there is nothing (a 404 for a station that does not report the parameter, Frost's
    412), nor for a download that failed and was made again with success. Nothing happens outside the collection of
    a station.

    What is told is the other side of that: once the walk is over, `file-skipped` names the stations whose file was
    let go (`ParameterRows.warn`), one warning for the request. A provider that lets a file go without calling this
    says nothing.
    """
    note = _SKIPPING.get()
    if note is not None:
        note(whole_request, cause)


def begin_response() -> None:
    """Start recording the warnings of the request being served, forgetting those of an earlier one.

    Whatever served the request before is forgotten too: the lists belong to the context the request runs
    in, which is a thread of the server for each request and the process for the command line.
    """
    _RECORDED.set([])
    _COUNTED.set({})


def count_response_warning(code: str, count: int, message: str, *, details: dict[str, int] | None = None) -> None:
    """Add `count` to the warning `code` of the request being served, whose `message` has `{count}` for the total.

    For what happens many times in a request, once for each station: the answer tells it once, with the sum.
    `details` splits the count by a reason (the check that rejected a value), summed the same way, and a `message`
    with `{details}` tells it, largest first. Nothing is recorded outside a request.
    """
    counted = _COUNTED.get()
    if counted is None or count <= 0:
        return
    entry = counted.setdefault(code, [0, message, {}])
    entry[0] += count
    for detail, number in (details or {}).items():
        entry[2][detail] = entry[2].get(detail, 0) + number


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
    log.log(level, message, extra={RESPONSE_WARNING_RECORD: code})
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


def log_counted_warnings(log: logging.Logger) -> None:
    """Log each warning that counts something across the request, once, with its total, as the command line does.

    `warn_response` logs as it records, but a counted warning (`count_response_warning`: the values a check rejected,
    the markers of the source, the calms) is only added up for the answer's `metadata`, and a CSV or a file target has
    no place for that block. The command line calls this when the walk is over, so that what it says is the whole
    count, in one line each, marked as `warn_response` marks its lines (`RESPONSE_WARNING_RECORD`, which `--quiet`
    lets through). A library call and a REST answer carry the same counts in `warnings` and log nothing here.
    """
    for code, (count, message, details) in (_COUNTED.get() or {}).items():
        log.warning(message.format(count=count, details=tell_details(details)), extra={RESPONSE_WARNING_RECORD: code})


def recorded_warnings() -> list[ResponseWarning]:
    """Give the warnings recorded since `begin_response`, in the order they were raised, the counted ones last."""
    counted = [
        ResponseWarning(code=code, message=message.format(count=count, details=tell_details(details)))
        for code, (count, message, details) in (_COUNTED.get() or {}).items()
    ]
    return [*(_RECORDED.get() or []), *counted]


def tell_details(details: dict[str, int]) -> str:
    """Give the counts by reason as `range 3, stuck 2`: the largest first, ties by name."""
    return ", ".join(
        f"{detail} {number}" for detail, number in sorted(details.items(), key=lambda item: (-item[1], item[0]))
    )
