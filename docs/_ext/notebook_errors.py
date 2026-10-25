# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Sphinx extension that fails the build on a failed `{code-cell}`, unless the provider did not answer.

myst-nb has no setting between "a cell that fails is shown and the build goes on"
(`nb_execution_raise_on_error` off, the default) and "the first cell that fails stops the build"
(`nb_execution_raise_on_error`, which also stops on a provider that is down for an hour). This extension is the
setting between: the notebooks run with `nb_execution_allow_errors`, the error outputs of every executed notebook
are collected as myst-nb hands the notebook on (whatever the cell hides of its output), and when the build is done

- a provider that did not answer is a warning (`wetterdienst.outage`), and the page shows its traceback. That mirrors
  the main cases of `skip_if_upstream_unavailable` in `tests/conftest.py`, read off the traceback of the notebook: a
  `NoInternetError` whose connection timed out, was refused, reset or had no route, and a `DownloadError` (or the bare
  failure) caused by a timeout, a dropped connection, a body cut short or a 5xx. A 4xx or a 404 is the provider
  answering, a name that does not resolve is what a decommissioned host looks like, and `DownloadError` for another
  cause (a TLS failure, a refused redirect or link) fails the build. It is stricter than the tests where it cannot
  see: a `DownloadError` caused by a `NoInternetError`, and the 5xx that AEMET reports in the envelope of a 200; and
  it does not ask whether the machine has a network (`_runner_has_network`);
- a cell that was interrupted by `nb_execution_timeout` is a warning too (`wetterdienst.outage`): the provider was
  slow. A hang in our own code looks the same, and is not told apart;
- a `NameError` after one of these on the same page is a consequence of the cell that failed, and not judged;
- any other error fails the build, with the page, the line and the exception of each, after all pages are written.

A cell that is meant to fail carries the tag `raises-exception`, as myst-nb documents it, and is not recorded. A build
that does not execute (`-D nb_execution_mode=off`, which `docs.yml` builds with) has no error output to find and so
needs neither the network nor this extension.

`judge` takes plain records and knows nothing of Sphinx, so `tests/test_docs_notebook_errors.py` runs it offline.
"""

from __future__ import annotations

import dataclasses as dc
import errno
import functools
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from wetterdienst.exceptions import DownloadError, NoInternetError

if TYPE_CHECKING:
    from collections.abc import Callable

    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

#: the tag with which a cell says that it is meant to fail
EXPECTED_FAILURE_TAG = "raises-exception"

#: what myst-nb calls the error of a notebook that ran into `nb_execution_timeout`
TIMEOUT = "CellTimeoutError"

#: what a connection that a host did not take up fails with, as in `tests/conftest.py` (a test holds them together)
UNANSWERED_ERRNOS = frozenset(
    {errno.ETIMEDOUT, errno.ECONNREFUSED, errno.ECONNRESET, errno.EHOSTUNREACH, errno.ENETUNREACH}
)
#: `ERROR_SEM_TIMEOUT` of Windows, as in `tests/conftest.py`
WINDOWS_SEMAPHORE_TIMEOUT = 121

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_DIRECT_CAUSE = "The above exception was the direct cause of the following exception:"
_SEPARATOR = re.compile(
    rf"^({re.escape(_DIRECT_CAUSE)}|During handling of the above exception, another exception occurred:)[ \t]*$",
    re.MULTILINE,
)
_HEADER = re.compile(r"^(\w+)\s+Traceback \(most recent call last\)\s*$", re.MULTILINE)
_ERRNO = re.compile(r"\[Errno (-?\d+)\]")
_STATUS = re.compile(r"^(\d{3})\b")


@dc.dataclass(frozen=True)
class ErrorOutput:
    """The error output of one cell: where it is, what was raised and what it was raised from."""

    docname: str
    line: int
    ename: str
    evalue: str
    #: the name and the message of the exception the error was raised from (`raise ... from`), if the traceback has it
    cause: tuple[str, str] | None = None
    #: the cell was interrupted because the notebook ran into `nb_execution_timeout`
    timed_out: bool = False

    def __str__(self) -> str:
        """Name the page, the line of the cell and the exception."""
        return f"{self.docname}, line {self.line}: {self.ename}: {self.evalue}".strip()


@dc.dataclass(frozen=True)
class Verdict:
    """What the errors of a build amount to."""

    #: cells that failed because the provider did not answer
    outages: list[ErrorOutput] = dc.field(default_factory=list)
    #: cells that were interrupted by the execution timeout
    timeouts: list[ErrorOutput] = dc.field(default_factory=list)
    #: `NameError`s after an outage on the same page, which are not judged
    consequences: list[ErrorOutput] = dc.field(default_factory=list)
    #: cells that failed for another reason: the build fails for these
    failures: list[ErrorOutput] = dc.field(default_factory=list)


def _subclass_names(root: type[Exception]) -> frozenset[str]:
    """Give the names of an exception class and of its subclasses."""
    names: set[str] = set()
    todo = [root]
    while todo:
        exception = todo.pop()
        names.add(exception.__name__)
        todo.extend(exception.__subclasses__())
    return frozenset(names)


def direct_cause(traceback: list[str], ename: str, evalue: str) -> tuple[str, str] | None:
    """Read the exception that the last one of a traceback was raised from, as IPython writes it, if any.

    The error output of a notebook has only the name and the message of the exception that was raised; the rest of
    its chain is in the traceback, where each exception opens with its name above the frames and ends with its
    name and message, and the one that caused the next is told so before it. A chain joins its exceptions with one
    of two sentences, and only "the direct cause" is `raise ... from`: the other is an exception raised while another
    was handled, which `__cause__` is not.

    The last exception is taken off the end first, by the name and the message the error output has, so that text in
    its message cannot pass for the structure of the chain; what is left is read from its end. Without that end, no
    cause is told.
    """
    text = _ANSI.sub("", "\n".join(traceback)).rstrip()
    last = f"{ename}: {evalue}".rstrip() if evalue else ename
    if not text.endswith(last):
        return None
    text = text[: -len(last)]
    separators = list(_SEPARATOR.finditer(text))
    if not separators or separators[-1].group(1) != _DIRECT_CAUSE:
        return None
    begin = separators[-2].end() if len(separators) > 1 else 0
    cause = text[begin : separators[-1].start()]
    header = _HEADER.search(cause)
    if header is None:
        return None
    name = header.group(1)
    messages = re.findall(rf"^(?:[\w.]+\.)?{name}(?:: ?(.*))?$", cause[header.end() :], re.MULTILINE)
    return name, (messages[-1] if messages else "")


def _exception_class(name: str) -> type[BaseException] | None:
    """Find the class that a traceback names, among those that a download fails with."""
    import builtins  # noqa: PLC0415
    import socket  # noqa: PLC0415
    import ssl  # noqa: PLC0415

    import aiohttp  # noqa: PLC0415
    import fsspec.exceptions  # noqa: PLC0415

    for namespace in (builtins, socket, ssl, aiohttp, fsspec.exceptions):
        found = getattr(namespace, name, None)
        if isinstance(found, type) and issubclass(found, BaseException):
            return found
    return None


def _host_did_not_answer(cause: tuple[str, str] | None) -> bool:
    """Say whether the `OSError` under a `NoInternetError` is a host that did not take up the connection.

    As `_host_did_not_answer` of `tests/conftest.py`: a timeout, a refusal, a reset or abort, no route to the host or
    its network. Not a name that did not resolve (`socket.gaierror`).
    """
    if cause is None:
        return False
    name, message = cause
    failure = _exception_class(name)
    if failure is None or not issubclass(failure, OSError):
        return False
    import socket  # noqa: PLC0415

    if issubclass(failure, socket.gaierror):
        return False
    # aiohappyeyeballs joins the errors of every address it tried into one message: all of them must be unanswered
    found = {int(number) for number in _ERRNO.findall(message)}
    return (
        issubclass(failure, (TimeoutError, ConnectionError))
        or (bool(found) and found <= UNANSWERED_ERRNOS)
        or f"[WinError {WINDOWS_SEMAPHORE_TIMEOUT}]" in message
    )


def _download_failed_in_a_blip(cause: tuple[str, str] | None) -> bool:
    """Say whether the failure under a `DownloadError` is what `_worth_retrying` asks again for.

    A timeout, a dropped connection, a body that stopped arriving mid-read, a 5xx. Not a TLS failure, a 4xx or a
    missing file, and not a download that has no cause to tell.
    """
    if cause is None:
        return False
    import ssl  # noqa: PLC0415

    from aiohttp import (  # noqa: PLC0415
        ClientConnectionError,
        ClientPayloadError,
        ClientResponseError,
        ClientSSLError,
    )
    from fsspec.exceptions import FSTimeoutError  # noqa: PLC0415

    name, message = cause
    failure = _exception_class(name)
    if failure is None or issubclass(failure, (ClientSSLError, ssl.SSLError)):
        return False
    if issubclass(failure, ClientResponseError):
        status = _STATUS.match(message)
        return status is not None and int(status.group(1)) >= HTTPStatus.INTERNAL_SERVER_ERROR
    return issubclass(failure, (ClientConnectionError, ClientPayloadError, FSTimeoutError, TimeoutError))


def is_outage(error: ErrorOutput) -> bool:
    """Say whether an error is the provider not answering, by the rule `skip_if_upstream_unavailable` states.

    The class of the error is told by its name, so the shape of its message is asked for as well: it is the one
    `_no_internet_error` and `_download_error` write.
    """
    if error.ename in _subclass_names(NoInternetError):
        return error.evalue.startswith("No internet connection: could not reach ") and _host_did_not_answer(error.cause)
    if error.ename in _subclass_names(DownloadError):
        return error.evalue.startswith("Failed to download ") and _download_failed_in_a_blip(error.cause)
    # a failure that reaches the cell without the wrapper of the library, as `_is_upstream_outage` takes it
    return _download_failed_in_a_blip((error.ename, error.evalue))


def judge(errors: list[ErrorOutput]) -> Verdict:
    """Sort the error outputs of a build into outages, timeouts, their consequences and failures.

    The errors of a page are in the order of its cells. After a cell that did not finish, a `NameError` is what the
    names it should have defined give, and nothing else is taken for a consequence.
    """
    outages, timeouts, consequences, failures = [], [], [], []
    down: set[str] = set()
    for error in errors:
        if error.timed_out:
            timeouts.append(error)
            down.add(error.docname)
        elif is_outage(error):
            outages.append(error)
            down.add(error.docname)
        elif error.docname in down and error.ename == "NameError":
            consequences.append(error)
        else:
            failures.append(error)
    return Verdict(outages=outages, timeouts=timeouts, consequences=consequences, failures=failures)


def error_outputs(
    docname: str,
    notebook: Any,  # noqa: ANN401
    cell_line: Callable[[int], int],
    *,
    timed_out: bool = False,
) -> list[ErrorOutput]:
    """Collect the error outputs of an executed notebook.

    Args:
        docname: The page the notebook is.
        notebook: The notebook, with the outputs it has after it ran.
        cell_line: Gives the line of a cell in the page.
        timed_out: Whether the notebook ran into the execution timeout (`exec_metadata` of myst-nb has
            `CellTimeoutError`), which stops it, and leaves the output of the cell it interrupted a `KeyboardInterrupt`.

    """
    found = []
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code" or EXPECTED_FAILURE_TAG in cell.get("metadata", {}).get("tags", []):
            continue
        for output in cell.get("outputs", []):
            if output.get("output_type") != "error":
                continue
            ename = output.get("ename", "")
            evalue = output.get("evalue", "")
            found.append(
                ErrorOutput(
                    docname=docname,
                    line=cell_line(index),
                    ename=ename,
                    evalue=evalue,
                    cause=direct_cause(output.get("traceback", []), ename, evalue),
                    timed_out=timed_out and ename == "KeyboardInterrupt",
                )
            )
    if timed_out and not any(error.timed_out for error in found):
        found.append(ErrorOutput(docname, 0, TIMEOUT, "a cell ran into the execution timeout", timed_out=True))
    return found


class _Build:
    """The build that is reading the pages, which the patched myst-nb reports the errors it finds to."""

    app: Sphinx | None = None


def _store(env: BuildEnvironment) -> dict[str, list[ErrorOutput]]:
    """Give the error outputs of each page, which the environment keeps (and hands from a reading process)."""
    if not hasattr(env, "notebook_error_outputs"):
        env.notebook_error_outputs = {}  # ty: ignore[unresolved-attribute]
    return env.notebook_error_outputs  # ty: ignore[unresolved-attribute]


def record_error_outputs() -> None:
    """Make myst-nb hand the executed notebook of each page over: no event of it does.

    The notebook is entered as a context manager when the page is read, executed or restored from the cache by then,
    and with every output it has, those that the page does not show among them.
    """
    from myst_nb.core.execute.base import NotebookClientBase  # noqa: PLC0415

    original = NotebookClientBase.__enter__
    if getattr(original, "records_errors", False):
        return

    @functools.wraps(original)
    def enter(self: NotebookClientBase) -> NotebookClientBase:
        client = original(self)
        app = _Build.app
        if app is not None and app.env.docname:
            metadata = client.exec_metadata
            _store(app.env)[app.env.docname] = error_outputs(
                app.env.docname,
                client.notebook,
                client.cell_line,
                timed_out=bool(metadata) and metadata["error"] == TIMEOUT,
            )
        return client

    enter.records_errors = True
    NotebookClientBase.__enter__ = enter


def setup(app: Sphinx) -> dict[str, Any]:
    """Record the error outputs while the pages are read, and judge them when the build is done."""
    from sphinx.util import logging  # noqa: PLC0415

    logger = logging.getLogger(__name__)
    record_error_outputs()

    def start(app: Sphinx) -> None:
        _Build.app = app

    def purge(_app: Sphinx, env: BuildEnvironment, docname: str) -> None:
        _store(env).pop(docname, None)

    def merge(_app: Sphinx, env: BuildEnvironment, docnames: set[str], other: BuildEnvironment) -> None:
        theirs = _store(other)
        _store(env).update({docname: theirs[docname] for docname in docnames if docname in theirs})

    def finish(app: Sphinx, exception: Exception | None) -> None:
        _Build.app = None
        if exception is not None:
            return
        store = _store(app.env)
        verdict = judge([error for docname in sorted(store) for error in store[docname]])
        for error in verdict.outages:
            logger.warning(
                "the provider did not answer, the page shows the traceback: %s",
                error,
                type="wetterdienst",
                subtype="outage",
            )
        for error in verdict.timeouts:
            logger.warning(
                "a cell ran into nb_execution_timeout, a slow provider or a hang in our code: %s",
                error,
                type="wetterdienst",
                subtype="outage",
            )
        if verdict.consequences:
            logger.warning(
                "%d NameError(s) after a cell that did not finish on the same page, not judged:\n%s",
                len(verdict.consequences),
                "\n".join(f"  {error}" for error in verdict.consequences),
                type="wetterdienst",
                subtype="outage",
            )
        for error in verdict.failures:
            logger.error("a cell failed with an error that is not an outage of a provider: %s", error)
        if verdict.failures:
            app.statuscode = 1

    app.connect("builder-inited", start)
    app.connect("env-purge-doc", purge)
    app.connect("env-merge-info", merge)
    app.connect("build-finished", finish)
    return {"version": "2", "parallel_read_safe": True, "parallel_write_safe": True}
