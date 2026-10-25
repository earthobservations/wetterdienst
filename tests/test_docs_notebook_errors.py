# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check of `docs/_ext/notebook_errors.py`: a failed `{code-cell}` fails the build unless the provider was down.

The judgement runs offline on plain records. The glue to myst-nb and Sphinx runs on a minimal project whose notebooks
are not executed but come with the outputs of a cell that failed; these need the `docs` group and are skipped
without it (`docs.yml` runs the file with it).
"""

from __future__ import annotations

import importlib.util
import io
import json
import socket
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientPayloadError, ClientResponseError, ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

from tests import conftest
from wetterdienst.exceptions import DownloadError, NoInternetError, UpstreamError
from wetterdienst.util.network import _download_error

_EXT = Path(__file__).resolve().parents[1] / "docs" / "_ext"
_SPEC = importlib.util.spec_from_file_location("notebook_errors", _EXT / "notebook_errors.py")
assert _SPEC is not None
assert _SPEC.loader is not None
notebook_errors = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = notebook_errors  # a dataclass looks its module up, and so does Sphinx
_SPEC.loader.exec_module(notebook_errors)

_GAIERROR = ("gaierror", "[Errno 8] nodename nor servname provided, or not known")
_REFUSED = ("ConnectionRefusedError", "[Errno 61] Connect call failed ('127.0.0.1', 1)")
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


def _traceback(ename: str, evalue: str, cause: tuple[str, str] | None = None) -> list[str]:
    """Write a traceback as IPython does, with colours: the name above the frames, the name and message below."""

    def part(name: str, message: str) -> str:
        return (
            f"\x1b[0;31m{name:<42}\x1b[0m Traceback (most recent call last)\n"
            "\x1b[0;32m----> 1\x1b[0m \x1b[43mraise\x1b[49m\n\n"
            f"\x1b[0;31m{name}\x1b[0m: {message}"
        )

    if cause is None:
        return [part(ename, evalue)]
    return [
        part(*cause),
        "\nThe above exception was the direct cause of the following exception:\n\n",
        part(ename, evalue),
    ]


# --- the judgement ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(_error("NoInternetError", _NO_INTERNET, cause=_REFUSED), id="refused"),
        pytest.param(_error("NoInternetError", _NO_INTERNET, cause=("TimeoutError", "")), id="timed out"),
        pytest.param(
            _error("NoInternetError", _NO_INTERNET, cause=("OSError", "[Errno 65] No route to host")), id="route"
        ),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ClientResponseError", "503, message='x'")), id="503"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("FSTimeoutError", "")), id="timeout"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ServerDisconnectedError", "x")), id="dropped"),
        pytest.param(_error("DownloadError", _DOWNLOAD, cause=("ClientPayloadError", "x")), id="cut short"),
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
        pytest.param(_error("NoInternetError", _NO_INTERNET), id="no cause"),
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
    (timed_out,) = notebook_errors.error_outputs("usage/page", notebook, lambda index: index, "CellTimeoutError")
    (raised,) = notebook_errors.error_outputs("usage/page", notebook, lambda index: index)
    assert notebook_errors.judge([timed_out]).timeouts == [timed_out]
    assert notebook_errors.judge([raised]).failures == [raised]


def test_a_timeout_without_the_interrupt_of_a_cell_is_still_a_timeout() -> None:
    """A kernel that does not write the interrupt back leaves only the error of the notebook."""
    (timed_out,) = notebook_errors.error_outputs(
        "usage/page", _notebook({"outputs": []}), lambda index: index, "CellTimeoutError"
    )
    assert notebook_errors.judge([timed_out]).timeouts == [timed_out]


def test_a_notebook_that_stopped_for_another_reason_fails_the_build() -> None:
    """A kernel that died leaves no cell to blame."""
    (error,) = notebook_errors.error_outputs(
        "usage/page", _notebook({"outputs": []}), lambda index: index, "DeadKernelError"
    )
    assert notebook_errors.judge([error]).failures == [error]
    assert not notebook_errors.error_outputs(
        "usage/page", _notebook({"outputs": []}), lambda index: index, "CellExecutionError"
    )


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


_PINNED = [
    pytest.param(_no_internet(socket.gaierror(8, "nodename nor servname provided, or not known")), id="gaierror"),
    pytest.param(_no_internet(ConnectionRefusedError(61, "Connect call failed")), id="refused"),
    pytest.param(_no_internet(ConnectionResetError(54, "reset")), id="reset"),
    pytest.param(_no_internet(TimeoutError()), id="timeout"),
    pytest.param(_no_internet(OSError(65, "No route to host")), id="no route"),
    pytest.param(_no_internet(OSError(101, "Network is unreachable")), id="no network"),
    pytest.param(_no_internet(OSError(13, "Permission denied")), id="another OSError"),
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
    """Write a project of notebooks that come with the outputs of the cells, and need no kernel."""
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


def _build(root: Path, *, parallel: int = 1) -> tuple[int, str]:
    pytest.importorskip("myst_nb")
    pytest.importorskip("nbformat")
    from sphinx.application import Sphinx  # noqa: PLC0415

    warning = io.StringIO()
    app = Sphinx(
        str(root),
        str(root),
        str(root / "_build"),
        str(root / "_doctrees"),
        "html",
        status=None,
        warning=warning,
        freshenv=True,
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
        str(root), str(root), str(root / "_build"), str(root / "_doctrees"), "html",
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
