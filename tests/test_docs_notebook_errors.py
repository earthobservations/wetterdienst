# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check of `docs/_ext/notebook_errors.py`: a failed `{code-cell}` fails the build unless the provider was down.

The judgement runs offline on plain records. The glue to myst-nb and Sphinx runs on a minimal project whose notebooks
are not executed but come with the outputs of a cell that failed; these need the `docs` group and are skipped
without it (`docs.yml` runs the file with it).
"""

from __future__ import annotations

import errno
import importlib.util
import io
import json
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientPayloadError, ClientResponseError, ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

from tests import conftest
from wetterdienst.exceptions import DownloadError, NoInternetError, UpstreamError
from wetterdienst.util.network import _download_error

if TYPE_CHECKING:
    from collections.abc import Callable

_EXT = Path(__file__).resolve().parents[1] / "docs" / "_ext"
_SPEC = importlib.util.spec_from_file_location("notebook_errors", _EXT / "notebook_errors.py")
assert _SPEC is not None
assert _SPEC.loader is not None
notebook_errors = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = notebook_errors  # a dataclass looks its module up, and so does Sphinx
_SPEC.loader.exec_module(notebook_errors)

_GAIERROR = ("gaierror", f"[Errno {socket.EAI_NONAME}] nodename nor servname provided, or not known")
_REFUSED = ("ConnectionRefusedError", f"[Errno {errno.ECONNREFUSED}] Connect call failed ('127.0.0.1', 1)")
_NO_INTERNET = "No internet connection: could not reach https://example.invalid/x (Cannot connect to host)"
_DOWNLOAD = "Failed to download https://example.invalid/x: 503, message='Service Unavailable'"


def _error(
    ename: str,
    evalue: str = "boom",
    *,
    cause: tuple[str, str] | None = None,
    docname: str = "usage/page",
    line: int = 1,
    timed_out: bool = False,
) -> notebook_errors.ErrorOutput:
    return notebook_errors.ErrorOutput(
        docname=docname, line=line, ename=ename, evalue=evalue, cause=cause, timed_out=timed_out
    )


def _outage(docname: str = "usage/page", line: int = 1) -> notebook_errors.ErrorOutput:
    return _error("NoInternetError", _NO_INTERNET, cause=_REFUSED, docname=docname, line=line)


_DIRECT = "\nThe above exception was the direct cause of the following exception:\n\n"
_HANDLING = "\nDuring handling of the above exception, another exception occurred:\n\n"


def _part(name: str, message: str) -> str:
    return (
        f"\x1b[0;31m{name:<42}\x1b[0m Traceback (most recent call last)\n"
        "\x1b[0;32m----> 1\x1b[0m \x1b[43mraise\x1b[49m\n\n"
        f"\x1b[0;31m{name}\x1b[0m: {message}"
    )


def _traceback(ename: str, evalue: str, cause: tuple[str, str] | None = None) -> list[str]:
    """Write a traceback as IPython does, with colours: the name above the frames, the name and message below."""
    if cause is None:
        return [_part(ename, evalue)]
    return [_part(*cause), _DIRECT, _part(ename, evalue)]


def _chain(*links: tuple[str, str], separators: tuple[str, ...]) -> list[str]:
    """Write a traceback of a chain of exceptions, the first of which is the innermost."""
    parts = [_part(*links[0])]
    for link, separator in zip(links[1:], separators, strict=True):
        parts += [separator, _part(*link)]
    return parts


# --- the judgement ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(_error("NoInternetError", _NO_INTERNET, cause=_REFUSED), id="refused"),
        pytest.param(_error("NoInternetError", _NO_INTERNET, cause=("TimeoutError", "")), id="timed out"),
        pytest.param(
            _error(
                "NoInternetError", _NO_INTERNET, cause=("OSError", f"[Errno {errno.EHOSTUNREACH}] No route to host")
            ),
            id="route",
        ),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ClientResponseError", "503, message='x'")), id="503"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("FSTimeoutError", "")), id="timeout"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ServerDisconnectedError", "x")), id="dropped"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ClientPayloadError", "x")), id="cut short"),
        pytest.param(
            _error("NoInternetError", _NO_INTERNET, cause=("OSError", "[WinError 121] The semaphore timeout period")),
            id="windows semaphore timeout",
        ),
        pytest.param(
            _error(
                "NoInternetError",
                _NO_INTERNET,
                cause=(
                    "OSError",
                    f"Multiple exceptions: [Errno {errno.ECONNREFUSED}] a, [Errno {errno.ECONNREFUSED}] b",
                ),
            ),
            id="refused on every address",
        ),
        pytest.param(_error("TimeoutError", ""), id="bare timeout"),
        pytest.param(_error("ClientResponseError", "503, message='Service Unavailable'"), id="bare 503"),
        pytest.param(_error("ServerDisconnectedError", "Server disconnected"), id="bare dropped connection"),
    ],
)
def test_a_provider_that_did_not_answer_is_a_warning_and_not_a_failure(error: notebook_errors.ErrorOutput) -> None:
    """The rule of `skip_if_upstream_unavailable`: a timeout, a refusal, a dropped connection and a 5xx."""
    verdict = notebook_errors.judge([error])
    assert verdict.outages == [error]
    assert not verdict.failures


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(_error("NoInternetError", _NO_INTERNET, cause=_GAIERROR), id="name does not resolve"),
        pytest.param(
            _error("NoInternetError", _NO_INTERNET, cause=("gaierror", f"[Errno {errno.ECONNREFUSED}] by its class")),
            id="name that does not resolve with the errno of a refusal",
        ),
        pytest.param(_error("NoInternetError", _NO_INTERNET), id="no cause"),
        pytest.param(
            _error("NoInternetError", "boom", cause=_REFUSED), id="not the message of the library (no internet)"
        ),
        pytest.param(_error("NotANoInternetError", _NO_INTERNET, cause=_REFUSED), id="name that contains no internet"),
        pytest.param(
            _error(
                "NoInternetError",
                _NO_INTERNET,
                cause=("OSError", f"Multiple exceptions: [Errno {errno.ECONNREFUSED}] a, [Errno {errno.EACCES}] b"),
            ),
            id="refused on one address and not allowed on another",
        ),
        pytest.param(_error("ClientResponseError", "404, message='Not Found'"), id="bare 404"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ClientResponseError", "404, message='x'")), id="404"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ClientResponseError", "429, message='x'")), id="429"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("FileNotFoundError", "")), id="file not found"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ClientSSLError", "x")), id="TLS"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("DownloadRefusedError", "x")), id="refused download"),
        pytest.param(_error("DownloadError", _DOWNLOAD), id="no cause"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("NotAnExceptionAnyoneKnows", "")), id="unknown cause"),
        pytest.param(_error("DownloadError", "x", cause=("TimeoutError", "")), id="not the message of the library"),
        pytest.param(_error("NotADownloadError", _DOWNLOAD, cause=("TimeoutError", "")), id="name that contains one"),
        pytest.param(_error("MissingDependencyError"), id="missing extra"),
        pytest.param(_error("KeyboardInterrupt"), id="interrupted by the user"),
    ],
)
def test_an_answer_the_provider_gave_or_any_other_error_fails_the_build(error: notebook_errors.ErrorOutput) -> None:
    """A 4xx or a name that does not resolve is what a bug of ours looks like: `tests/conftest.py` fails on both."""
    verdict = notebook_errors.judge([error])
    assert verdict.failures == [error]
    assert not verdict.outages


def test_a_cell_the_execution_timeout_interrupted_is_a_warning() -> None:
    """A slow provider is not a failure; a hang in our own code is not told apart from it."""
    error = _error("KeyboardInterrupt", "", timed_out=True)
    verdict = notebook_errors.judge([error])
    assert verdict.timeouts == [error]
    assert not verdict.failures


def test_only_a_name_error_after_an_outage_on_the_same_page_is_not_judged() -> None:
    """The cell that failed left its names undefined; an independent error after it is still a finding."""
    verdict = notebook_errors.judge(
        [
            _error("KeyError", docname="usage/export"),
            _outage(docname="usage/python-api", line=10),
            _error("NameError", docname="usage/python-api", line=20),
            _error("ValueError", docname="usage/python-api", line=30),
            _outage(docname="usage/python-api", line=40),
            _error("NameError", docname="usage/cli"),
        ]
    )
    assert [(error.docname, error.ename) for error in verdict.failures] == [
        ("usage/export", "KeyError"),
        ("usage/python-api", "ValueError"),
        ("usage/cli", "NameError"),
    ]
    assert [error.line for error in verdict.outages] == [10, 40]
    assert [error.line for error in verdict.consequences] == [20]


def test_an_error_before_the_outage_on_the_same_page_still_fails_the_build() -> None:
    """An error that came before the provider failed cannot be a consequence of it."""
    verdict = notebook_errors.judge([_error("NameError", line=1), _outage(line=2)])
    assert [error.ename for error in verdict.failures] == ["NameError"]


def test_a_build_without_errors_has_nothing_to_judge() -> None:
    """A build that does not execute, or whose cells all worked, records nothing."""
    assert notebook_errors.judge([]) == notebook_errors.Verdict()


def test_a_subclass_of_an_outage_is_one() -> None:
    """The name of an exception is all the notebook keeps, so the subclasses are asked for their names."""

    class ProviderIsDownError(DownloadError):
        pass

    error = _error("ProviderIsDownError", _DOWNLOAD, cause=("TimeoutError", ""))
    assert notebook_errors.is_outage(error)


def test_the_outages_are_errors_of_the_library_for_a_provider() -> None:
    """The classes the extension knows are `UpstreamError`s of the library."""
    assert issubclass(NoInternetError, UpstreamError)
    assert issubclass(DownloadError, UpstreamError)


# --- reading the notebook --------------------------------------------------------------------------------------


def _notebook(*cells: dict[str, Any]) -> dict[str, Any]:
    return {"cells": [{"cell_type": "code", "metadata": {}, **cell} for cell in cells]}


def _error_cell(ename: str, evalue: str = "", traceback: list[str] | None = None, **cell: Any) -> dict[str, Any]:  # noqa: ANN401
    output = {"output_type": "error", "ename": ename, "evalue": evalue, "traceback": traceback or []}
    return {"outputs": [{"output_type": "stream", "name": "stdout", "text": "x"}, output], **cell}


def test_the_error_outputs_of_a_notebook_are_collected_with_the_line_of_their_cell() -> None:
    """The line, the exception and the one it was raised from are what the warning and the verdict need."""
    traceback = _traceback("NoInternetError", _NO_INTERNET, _REFUSED)
    notebook = _notebook(
        {"outputs": []}, _error_cell("NoInternetError", _NO_INTERNET, traceback), {"cell_type": "markdown"}
    )
    (error,) = notebook_errors.error_outputs("usage/page", notebook, lambda index: 10 + index)
    assert error == _error("NoInternetError", _NO_INTERNET, cause=_REFUSED, line=11)
    assert notebook_errors.is_outage(error)


def test_a_cell_tagged_raises_exception_is_not_collected() -> None:
    """The tag says that the cell is meant to fail."""
    notebook = _notebook(_error_cell("ZeroDivisionError", metadata={"tags": ["raises-exception"]}))
    assert notebook_errors.error_outputs("usage/page", notebook, lambda index: index) == []


def test_the_interrupt_of_the_execution_timeout_is_told_from_one_the_page_raises() -> None:
    """A notebook that ran into the timeout holds the `KeyboardInterrupt` of its cell; otherwise it is a failure."""
    notebook = _notebook(_error_cell("KeyboardInterrupt"))
    (timed_out,) = notebook_errors.error_outputs("usage/page", notebook, lambda index: index, timed_out=True)
    (raised,) = notebook_errors.error_outputs("usage/page", notebook, lambda index: index)
    assert notebook_errors.judge([timed_out]).timeouts == [timed_out]
    assert notebook_errors.judge([raised]).failures == [raised]


def test_a_timeout_without_the_interrupt_of_a_cell_is_still_a_timeout() -> None:
    """A kernel that does not write the interrupt back leaves only the error of the notebook."""
    (timed_out,) = notebook_errors.error_outputs(
        "usage/page", _notebook({"outputs": []}), lambda index: index, timed_out=True
    )
    assert notebook_errors.judge([timed_out]).timeouts == [timed_out]


def _cause_of(ename: str, evalue: str, traceback: list[str]) -> tuple[str, str] | None:
    return notebook_errors.direct_cause(traceback, ename, evalue)


def test_only_the_exception_a_cell_was_raised_from_is_its_cause() -> None:
    """The chain is read from its end, and `raise ... from` is the sentence directly above the last exception."""
    link = ("DownloadError", _DOWNLOAD)
    timeout = ("TimeoutError", "")
    value = ("ValueError", "x")
    assert _cause_of(*link, _chain(timeout, link, separators=(_DIRECT,))) == timeout
    # raised while another was handled: no `__cause__`
    assert _cause_of(*link, _chain(timeout, link, separators=(_HANDLING,))) is None
    # the cause of the last one is the one next to it, whatever the chain before it
    assert _cause_of(*link, _chain(timeout, value, link, separators=(_DIRECT, _DIRECT))) == value
    assert _cause_of(*link, _chain(timeout, value, link, separators=(_DIRECT, _HANDLING))) is None
    assert _cause_of(*link, _chain(value, timeout, link, separators=(_HANDLING, _DIRECT))) == timeout
    assert _cause_of(*link, _chain(link, separators=())) is None


def test_text_in_the_message_does_not_pass_for_the_structure_of_a_chain() -> None:
    """A message that holds the sentence and a header of a traceback is the end of the last exception, not a cause."""
    forged = (
        "Failed to download https://example.invalid/x: oops\nThe above exception was the direct cause of the following"
        " exception:\n\nTimeoutError   Traceback (most recent call last)\nTimeoutError: "
    )
    assert _cause_of("DownloadError", forged, [_part("DownloadError", forged)]) is None
    error = _error("DownloadError", forged, cause=_cause_of("DownloadError", forged, [_part("DownloadError", forged)]))
    assert notebook_errors.judge([error]).failures == [error]


def test_a_traceback_that_does_not_end_with_the_error_has_no_cause() -> None:
    """What cannot be tied to the error output is not read."""
    assert _cause_of("DownloadError", _DOWNLOAD, _traceback("DownloadError", "another message", _REFUSED)) is None
    assert _cause_of("DownloadError", _DOWNLOAD, []) is None


# --- the same rule as the tests ----------------------------------------------------------------------------------


def test_the_errnos_are_those_of_the_tests() -> None:
    """`tests/conftest.py` is the rule: a connection that a host did not take up."""
    assert notebook_errors.UNANSWERED_ERRNOS == conftest._UNANSWERED_ERRNOS  # noqa: SLF001
    assert notebook_errors.WINDOWS_SEMAPHORE_TIMEOUT == conftest._WINDOWS_SEMAPHORE_TIMEOUT  # noqa: SLF001


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status, message="why")


def _download(cause: BaseException | None) -> DownloadError:
    error = _download_error(cause or ValueError(), "https://example.invalid/x")
    error.__cause__ = cause
    return error


def _no_internet(cause: BaseException | None) -> NoInternetError:
    error = NoInternetError(_NO_INTERNET)
    error.__cause__ = cause
    return error


_URL = "https://example.invalid/x"


def _caught(function: Callable[[], None]) -> Exception:
    try:
        function()
    except Exception as error:  # noqa: BLE001
        return error
    msg = "nothing was raised"
    raise AssertionError(msg)


def _download_in_the_handler_of_a_caused_error() -> None:
    try:
        try:
            raise TimeoutError  # noqa: TRY301
        except TimeoutError as timeout:
            raise ValueError("x") from timeout  # noqa: EM101
    except ValueError:
        raise _download_error(TimeoutError(), _URL)  # noqa: B904


def _download_in_the_handler_of_a_timeout() -> None:
    try:
        raise TimeoutError  # noqa: TRY301
    except TimeoutError:
        raise _download_error(TimeoutError(), _URL)  # noqa: B904


def _download_from_an_error_from_a_timeout() -> None:
    try:
        try:
            raise TimeoutError  # noqa: TRY301
        except TimeoutError as timeout:
            raise ValueError("x") from timeout  # noqa: EM101
    except ValueError as error:
        raise _download_error(error, _URL) from error


def _download_from_a_timeout_raised_while_handling() -> None:
    try:
        try:
            raise ValueError("x")  # noqa: EM101, TRY301
        except ValueError:
            raise TimeoutError  # noqa: B904
    except TimeoutError as timeout:
        raise _download_error(timeout, _URL) from timeout


_FORGED = (
    "oops\nThe above exception was the direct cause of the following exception:\n\n"
    "TimeoutError   Traceback (most recent call last)\nTimeoutError: "
)

_PINNED = [
    pytest.param(_caught(_download_in_the_handler_of_a_caused_error), id="raised while handling a caused error"),
    pytest.param(_caught(_download_in_the_handler_of_a_timeout), id="raised while handling a timeout"),
    pytest.param(_caught(_download_from_an_error_from_a_timeout), id="from an error from a timeout"),
    pytest.param(_caught(_download_from_a_timeout_raised_while_handling), id="from a timeout raised while handling"),
    pytest.param(DownloadError(_URL, _FORGED), id="reason that forges a chain"),
    pytest.param(TimeoutError(), id="bare timeout"),
    pytest.param(FSTimeoutError(), id="bare fs timeout"),
    pytest.param(_response_error(503), id="bare 503"),
    pytest.param(_response_error(404), id="bare 404"),
    pytest.param(ServerDisconnectedError("Server disconnected"), id="bare dropped connection"),
    pytest.param(
        _no_internet(OSError(f"Multiple exceptions: [Errno {errno.ECONNREFUSED}] a, [Errno {errno.EACCES}] b")),
        id="mixed errnos",
    ),
    pytest.param(
        _no_internet(socket.gaierror(socket.EAI_NONAME, "nodename nor servname provided, or not known")), id="gaierror"
    ),
    pytest.param(_no_internet(ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed")), id="refused"),
    pytest.param(_no_internet(ConnectionResetError(errno.ECONNRESET, "reset")), id="reset"),
    pytest.param(_no_internet(TimeoutError()), id="timeout"),
    pytest.param(_no_internet(OSError(errno.EHOSTUNREACH, "No route to host")), id="no route"),
    pytest.param(_no_internet(OSError(errno.ENETUNREACH, "Network is unreachable")), id="no network"),
    pytest.param(_no_internet(OSError(errno.EACCES, "Permission denied")), id="another OSError"),
    pytest.param(_no_internet(None), id="no cause"),
    pytest.param(_download(FSTimeoutError()), id="fs timeout"),
    pytest.param(_download(TimeoutError()), id="timeout of the download"),
    pytest.param(_download(_response_error(503)), id="503"),
    pytest.param(_download(_response_error(500)), id="500"),
    pytest.param(_download(_response_error(404)), id="404"),
    pytest.param(_download(_response_error(429)), id="429"),
    pytest.param(_download(_response_error(403)), id="403"),
    pytest.param(_download(FileNotFoundError("https://example.invalid/x")), id="file not found"),
    pytest.param(_download(ServerDisconnectedError("Server disconnected")), id="dropped connection"),
    pytest.param(_download(ClientPayloadError("Response payload is not completed")), id="cut short"),
    pytest.param(_download(ValueError("unparseable")), id="value"),
    pytest.param(_download(None), id="no cause"),
]


@pytest.mark.parametrize("error", _PINNED)
def test_the_extension_tells_an_outage_as_the_tests_do(error: Exception, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every failure `skip_if_upstream_unavailable` rules on, written as a kernel writes it, is ruled the same way."""
    interactiveshell = pytest.importorskip("IPython.core.interactiveshell")
    monkeypatch.setattr(conftest, "_runner_has_network", lambda: True)
    try:
        raise error  # noqa: TRY301
    except Exception as caught:  # noqa: BLE001
        # what ipykernel writes into the `traceback` of the error output
        traceback = interactiveshell.InteractiveShell.instance().InteractiveTB.structured_traceback(
            type(caught), caught, caught.__traceback__
        )
    notebook = _notebook(_error_cell(type(error).__name__, str(error), traceback))
    (found,) = notebook_errors.error_outputs("usage/page", notebook, lambda index: index)

    assert notebook_errors.is_outage(found) is conftest._is_upstream_outage(error)  # noqa: SLF001


# --- the glue to myst-nb and Sphinx ------------------------------------------------------------------------------


def _write_project(root: Path, pages: dict[str, list[dict[str, Any]]]) -> Path:
    """Write a project of notebooks that come with the outputs of the cells, and need no kernel, into `root/src`."""
    root = root / "src"  # myst-nb writes beside the sources, and a second build would read what it wrote
    root.mkdir()
    (root / "conf.py").write_text(
        f"import sys\nsys.path.insert(0, {str(_EXT)!r})\n"
        "extensions = ['myst_nb', 'notebook_errors']\n"
        "nb_execution_mode = 'off'\nnb_execution_allow_errors = True\n"
        "suppress_warnings = ['myst-nb.lexer']\nroot_doc = 'index'\n",
        encoding="utf8",
    )
    names = sorted(pages)
    (root / "index.md").write_text("# Scratch\n\n```{toctree}\n" + "\n".join(names) + "\n```\n", encoding="utf8")
    for name, cells in pages.items():
        notebook = {
            "cells": [
                {
                    "cell_type": "code",
                    "id": f"cell{index}",
                    "execution_count": 1,
                    "metadata": cell.get("metadata", {}),
                    "source": "pass",
                    "outputs": cell["outputs"],
                }
                for index, cell in enumerate(cells)
            ],
            "metadata": {"kernelspec": {"name": "python3", "display_name": "python3", "language": "python"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        (root / f"{name}.ipynb").write_text(json.dumps(notebook), encoding="utf8")
    return root


def _cell(ename: str, evalue: str = "", cause: tuple[str, str] | None = None, **metadata: Any) -> dict[str, Any]:  # noqa: ANN401
    output = {
        "output_type": "error",
        "ename": ename,
        "evalue": evalue,
        "traceback": _traceback(ename, evalue, cause),
    }
    return {"outputs": [output], "metadata": metadata}


def _build(root: Path, *, parallel: int = 1, fresh: bool = True) -> tuple[int, str]:
    pytest.importorskip("myst_nb")
    pytest.importorskip("nbformat")
    from sphinx.application import Sphinx  # noqa: PLC0415

    warning = io.StringIO()
    app = Sphinx(
        str(root),
        str(root),
        str(root.parent / "_build"),
        str(root.parent / "_doctrees"),
        "html",
        status=None,
        warning=warning,
        freshenv=fresh,
        parallel=parallel,
    )
    app.build()
    return app.statuscode, warning.getvalue()


_OUTAGE_CELL = _cell("NoInternetError", _NO_INTERNET, _REFUSED)


def test_a_provider_that_did_not_answer_is_a_warning_in_the_build(tmp_path: Path) -> None:
    """The build goes on, and the warning names the page and the line."""
    status, warnings = _build(
        _write_project(tmp_path, {"page": [_OUTAGE_CELL, _cell("NameError", "name 'df' is not defined")]})
    )
    assert status == 0
    assert "page, line" in warnings
    assert "[wetterdienst.outage]" in warnings
    assert "1 NameError(s) after a cell that did not finish on the same page, not judged" in warnings


def test_any_other_error_fails_the_build(tmp_path: Path) -> None:
    """The status is not 0 so that Read the Docs fails the build, and the message names the page and the exception."""
    status, warnings = _build(_write_project(tmp_path, {"page": [_cell("ValueError", "a real bug")]}))
    assert status == 1
    assert "page, line" in warnings
    assert "ValueError: a real bug" in warnings


def test_an_error_after_an_outage_on_the_same_page_still_fails_the_build(tmp_path: Path) -> None:
    """Only the `NameError` the failed cell causes is let through."""
    status, _ = _build(_write_project(tmp_path, {"page": [_OUTAGE_CELL, _cell("ValueError", "unrelated")]}))
    assert status == 1


def test_a_cell_that_hides_its_output_is_judged_all_the_same(tmp_path: Path) -> None:
    """The check reads the notebook, not the page, so `remove-output` does not hide a failure."""
    status, _ = _build(_write_project(tmp_path, {"page": [_cell("ValueError", "hidden", tags=["remove-output"])]}))
    assert status == 1


def test_a_cell_tagged_raises_exception_does_not_fail_the_build(tmp_path: Path) -> None:
    """The tag is how myst-nb says that a cell is meant to fail."""
    status, _ = _build(_write_project(tmp_path, {"page": [_cell("ZeroDivisionError", "x", tags=["raises-exception"])]}))
    assert status == 0


@pytest.mark.skipif(sys.platform == "win32", reason="Sphinx reads in parallel only where it can fork")
def test_the_errors_of_pages_read_in_parallel_are_judged(tmp_path: Path) -> None:
    """The reading processes hand the errors on to the build; Sphinx reads in parallel from six pages on."""
    pages = {f"page{index}": [_OUTAGE_CELL] for index in range(6)}
    pages["broken"] = [_cell("ValueError", "a real bug")]
    status, warnings = _build(_write_project(tmp_path, pages), parallel=2)
    assert status == 1
    assert "broken, line" in warnings
    assert warnings.count("[wetterdienst.outage]") == 6
    # Sphinx reads in one process, and says so, from an extension that does not declare itself safe to read in parallel
    assert "parallel" not in warnings


def test_a_build_that_did_not_finish_is_not_judged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A build that raised has its own error to report, and no verdict on the pages it did not finish."""
    pytest.importorskip("myst_nb")
    from sphinx.application import Sphinx  # noqa: PLC0415
    from sphinx.builders.html import StandaloneHTMLBuilder  # noqa: PLC0415

    def broken(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError

    monkeypatch.setattr(StandaloneHTMLBuilder, "write_documents", broken)
    root = _write_project(tmp_path, {"page": [_cell("ValueError", "a real bug")]})
    warning = io.StringIO()
    app = Sphinx(
        str(root), str(root), str(root.parent / "_build"), str(root.parent / "_doctrees"), "html",
        status=None, warning=warning, freshenv=True,
    )  # fmt: skip
    with pytest.raises(RuntimeError):
        app.build()
    assert app.statuscode == 0
    assert "not an outage" not in warning.getvalue()
    assert notebook_errors._Build.app is None  # noqa: SLF001


def test_myst_nb_is_not_patched_twice() -> None:
    """Two builds in a process enter a notebook once each."""
    pytest.importorskip("myst_nb")
    from myst_nb.core.execute.base import NotebookClientBase  # noqa: PLC0415

    notebook_errors.record_error_outputs()
    patched = NotebookClientBase.__enter__
    notebook_errors.record_error_outputs()
    assert NotebookClientBase.__enter__ is patched
    assert patched.records_errors


def test_the_errors_of_a_page_that_is_gone_are_gone(tmp_path: Path) -> None:
    """The environment keeps the errors of the pages from one build to the next, and forgets those of a removed page."""
    root = _write_project(tmp_path, {"broken": [_cell("ValueError", "a real bug")], "fine": [_OUTAGE_CELL]})
    status, _ = _build(root)
    assert status == 1

    (root / "broken.ipynb").unlink()
    (root / "index.md").write_text("# Scratch\n\n```{toctree}\nfine\n```\n", encoding="utf8")
    status, warnings = _build(root, fresh=False)
    assert status == 0, warnings


# --- a kernel ----------------------------------------------------------------------------------------------------


def _run_notebook(root: Path, source: str, *, timeout: int = 30) -> tuple[int, str]:
    """Execute a page with a kernel, as Read the Docs does."""
    pytest.importorskip("ipykernel")
    root = root / "src"
    root.mkdir()
    (root / "conf.py").write_text(
        f"import sys\nsys.path.insert(0, {str(_EXT)!r})\n"
        "extensions = ['myst_nb', 'notebook_errors']\n"
        f"nb_execution_mode = 'force'\nnb_execution_allow_errors = True\nnb_execution_timeout = {timeout}\n"
        "suppress_warnings = ['myst-nb.lexer']\n",
        encoding="utf8",
    )
    (root / "index.md").write_text(
        "---\nfile_format: mystnb\nkernelspec: {name: python3, display_name: python3, language: python}\n---\n"
        f"# Page\n\n```{{code-cell}} ipython3\n{source}\n```\n",
        encoding="utf8",
    )
    return _build(root)


def test_a_cell_that_raises_in_a_kernel_fails_the_build(tmp_path: Path) -> None:
    """The notebook comes back from the kernel with the error output, which the extension finds."""
    status, warnings = _run_notebook(tmp_path, 'raise ValueError("a real bug")')
    assert status == 1
    assert "ValueError: a real bug" in warnings


def test_a_cell_that_runs_into_the_execution_timeout_is_a_warning(tmp_path: Path) -> None:
    """The kernel is interrupted, and the interrupt is told from one the page raises."""
    status, warnings = _run_notebook(tmp_path, "import time\ntime.sleep(30)", timeout=1)
    assert status == 0
    assert "nb_execution_timeout" in warnings
