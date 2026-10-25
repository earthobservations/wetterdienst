# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check of `docs/_ext/notebook_errors.py`: a failed `{code-cell}` fails the build unless the provider was down."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from wetterdienst.exceptions import DownloadError, NoInternetError, UpstreamError

_PATH = Path(__file__).resolve().parents[1] / "docs" / "_ext" / "notebook_errors.py"
_SPEC = importlib.util.spec_from_file_location("notebook_errors", _PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
notebook_errors = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = notebook_errors  # a dataclass looks its module up
_SPEC.loader.exec_module(notebook_errors)


def _error(ename: str, docname: str = "usage/page", cell: int = 0) -> notebook_errors.ErrorOutput:
    return notebook_errors.ErrorOutput(docname=docname, cell=cell, line=cell * 10, ename=ename, evalue="boom")


@pytest.mark.parametrize("ename", ["NoInternetError", "DownloadError"])
def test_an_outage_is_a_warning_and_not_a_failure(ename: str) -> None:
    """A provider that does not answer does not fail the build."""
    verdict = notebook_errors.judge([_error(ename)])
    assert [error.ename for error in verdict.outages] == [ename]
    assert not verdict.failures
    assert not verdict.consequences


@pytest.mark.parametrize("ename", ["MissingDependencyError", "NameError", "InvalidParameterError", "KeyError"])
def test_any_other_error_fails_the_build(ename: str) -> None:
    """An error that is no outage, `MissingDependencyError` of a missing extra among them, is a finding."""
    verdict = notebook_errors.judge([_error(ename)])
    assert [error.ename for error in verdict.failures] == [ename]
    assert not verdict.outages


def test_the_errors_after_an_outage_on_the_same_page_are_not_judged() -> None:
    """The cell that failed left its names undefined, so a `NameError` after it is no finding."""
    verdict = notebook_errors.judge(
        [
            _error("KeyError", docname="usage/export"),
            _error("NoInternetError", docname="usage/python-api", cell=1),
            _error("NameError", docname="usage/python-api", cell=2),
            _error("DownloadError", docname="usage/python-api", cell=3),
            _error("NameError", docname="usage/cli"),
        ]
    )
    assert [error.docname for error in verdict.failures] == ["usage/export", "usage/cli"]
    assert [error.cell for error in verdict.outages] == [1, 3]
    assert [error.cell for error in verdict.consequences] == [2]


def test_an_error_before_the_outage_on_the_same_page_still_fails_the_build() -> None:
    """An error that came before the provider failed cannot be a consequence of it."""
    verdict = notebook_errors.judge([_error("KeyError", cell=0), _error("NoInternetError", cell=1)])
    assert [error.ename for error in verdict.failures] == ["KeyError"]


def test_a_build_without_errors_has_nothing_to_judge() -> None:
    """A build that does not execute, or whose cells all worked, records nothing."""
    assert notebook_errors.judge([]) == notebook_errors.Verdict()


def test_a_subclass_of_an_outage_is_one() -> None:
    """The name of an exception is all the notebook keeps, so the subclasses are asked for their names."""

    class ProviderIsDownError(DownloadError):
        pass

    assert "ProviderIsDownError" in notebook_errors.outage_names()
    assert not notebook_errors.judge([_error("ProviderIsDownError")]).failures


def test_the_outages_are_the_errors_of_a_provider_that_did_not_answer() -> None:
    """The set is the two classes the library raises for it, and they are `UpstreamError`s."""
    assert set(notebook_errors.OUTAGES) == {NoInternetError, DownloadError}
    assert all(issubclass(outage, UpstreamError) for outage in notebook_errors.OUTAGES)


def test_myst_nb_is_asked_to_hand_over_the_name_of_the_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each error output myst-nb renders is recorded with its exception, unless its cell is meant to fail."""
    render = pytest.importorskip("myst_nb.core.render")
    monkeypatch.setattr(render.NbElementRenderer, "render_error", lambda *_args: ["rendered"])
    recorded: list = []
    notebook_errors.record_error_outputs(recorded)
    renderer = SimpleNamespace(renderer=SimpleNamespace(sphinx_env=SimpleNamespace(docname="usage/page")))
    output = {"ename": "NoInternetError", "evalue": "no connection"}

    assert render.NbElementRenderer.render_error(renderer, output, {}, 3, 42) == ["rendered"]
    assert render.NbElementRenderer.render_error(renderer, output, {"tags": ["raises-exception"]}, 4, 50) == [
        "rendered"
    ]

    assert recorded == [
        notebook_errors.ErrorOutput(
            docname="usage/page", cell=3, line=42, ename="NoInternetError", evalue="no connection"
        )
    ]
