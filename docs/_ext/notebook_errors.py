# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Sphinx extension that fails the build on a failed `{code-cell}`, unless the provider was down.

myst-nb has no setting between "a cell that fails is shown and the build goes on"
(`nb_execution_raise_on_error` off, the default) and "the first cell that fails stops the build"
(`nb_execution_raise_on_error`, which also stops on a provider that is down for an hour). This extension is the
setting between: the notebooks run with `nb_execution_allow_errors`, every error output is recorded as it is
rendered, with the name of its exception, and when the build is done

- an error that is an outage (`NoInternetError`, `DownloadError`: the provider did not answer) is a warning, and the
  page shows its traceback;
- any other error fails the build, with the page, the cell and the exception of each;
- an error after an outage on the same page is not judged: the cell that failed left its names undefined, so what
  follows is a consequence, not a finding.

A cell that is meant to fail carries the tag `raises-exception`, as myst-nb documents it, and is not recorded. A build
that does not execute (`-D nb_execution_mode=off`, which `docs.yml` builds with) renders no error output and so
needs neither the network nor this extension.

`judge` takes plain records and knows nothing of Sphinx, so `tests/test_docs_notebook_errors.py` runs it offline.
"""

from __future__ import annotations

import dataclasses as dc
import functools
from typing import TYPE_CHECKING, Any

from wetterdienst.exceptions import DownloadError, NoInternetError

if TYPE_CHECKING:
    from sphinx.application import Sphinx

#: the exceptions that mean the provider did not answer, not that the page is wrong
OUTAGES: tuple[type[Exception], ...] = (NoInternetError, DownloadError)

#: the tag with which a cell says that it is meant to fail
EXPECTED_FAILURE_TAG = "raises-exception"


@dc.dataclass(frozen=True)
class ErrorOutput:
    """The error output of one cell: where it is and what was raised."""

    docname: str
    cell: int
    line: int
    ename: str
    evalue: str

    def __str__(self) -> str:
        """Name the page, the line of the cell and the exception."""
        return f"{self.docname}, line {self.line}: {self.ename}: {self.evalue}".strip()


@dc.dataclass(frozen=True)
class Verdict:
    """What the errors of a build amount to."""

    #: cells that failed because the provider did not answer
    outages: list[ErrorOutput] = dc.field(default_factory=list)
    #: cells that failed after an outage on the same page, which are not judged
    consequences: list[ErrorOutput] = dc.field(default_factory=list)
    #: cells that failed for another reason: the build fails for these
    failures: list[ErrorOutput] = dc.field(default_factory=list)


def outage_names() -> frozenset[str]:
    """Give the names of the exceptions that are an outage, those of the classes and of their subclasses."""
    names: set[str] = set()
    todo = list(OUTAGES)
    while todo:
        exception = todo.pop()
        names.add(exception.__name__)
        todo.extend(exception.__subclasses__())
    return frozenset(names)


def judge(errors: list[ErrorOutput]) -> Verdict:
    """Sort the error outputs of a build into outages, their consequences and failures.

    The errors of a page are in the order of its cells.
    """
    outage = outage_names()
    outages, consequences, failures = [], [], []
    down: set[str] = set()
    for error in errors:
        if error.ename in outage:
            outages.append(error)
            down.add(error.docname)
        elif error.docname in down:
            consequences.append(error)
        else:
            failures.append(error)
    return Verdict(outages=outages, consequences=consequences, failures=failures)


def record_error_outputs(errors: list[ErrorOutput]) -> None:
    """Make myst-nb tell `errors` of each error output it renders: the rendered node has no exception name."""
    from myst_nb.core.render import NbElementRenderer  # noqa: PLC0415

    original = NbElementRenderer.render_error
    if getattr(original, "records_errors", False):
        return

    @functools.wraps(original)
    def render_error(
        self: NbElementRenderer, output: Any, cell_metadata: dict, cell_index: int, source_line: int
    ) -> Any:
        if EXPECTED_FAILURE_TAG not in cell_metadata.get("tags", []):
            errors.append(
                ErrorOutput(
                    docname=self.renderer.sphinx_env.docname,
                    cell=cell_index,
                    line=source_line,
                    ename=output.get("ename", ""),
                    evalue=output.get("evalue", ""),
                )
            )
        return original(self, output, cell_metadata, cell_index, source_line)

    render_error.records_errors = True
    NbElementRenderer.render_error = render_error


def setup(app: Sphinx) -> dict[str, Any]:
    """Record the error outputs while the pages are read, and judge them when the build is done."""
    from sphinx.errors import SphinxError  # noqa: PLC0415
    from sphinx.util import logging  # noqa: PLC0415

    logger = logging.getLogger(__name__)
    errors: list[ErrorOutput] = []
    record_error_outputs(errors)

    def start(_app: Sphinx) -> None:
        errors.clear()

    def finish(_app: Sphinx, exception: Exception | None) -> None:
        if exception is not None:
            return
        verdict = judge(errors)
        for error in verdict.outages:
            logger.warning(
                "the provider did not answer, the page shows the traceback: %s",
                error,
                type="wetterdienst",
                subtype="outage",
            )
        if verdict.consequences:
            logger.warning(
                "%d cell(s) failed after an outage on the same page and were not judged:\n%s",
                len(verdict.consequences),
                "\n".join(f"  {error}" for error in verdict.consequences),
                type="wetterdienst",
                subtype="outage",
            )
        if verdict.failures:
            lines = "\n".join(f"  {error}" for error in verdict.failures)
            msg = f"{len(verdict.failures)} cell(s) failed with an error that is not an outage of a provider:\n{lines}"
            raise SphinxError(msg)

    app.connect("builder-inited", start)
    app.connect("build-finished", finish)
    return {"version": "1", "parallel_read_safe": False, "parallel_write_safe": True}
