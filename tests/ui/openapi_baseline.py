# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The OpenAPI document of the last release, which the served one is held to (GH-3131).

`tests/ui/openapi.snapshot.json` is the document as the pull request leaves it, so a change to it is a diff to read.
`tests/ui/openapi.baseline.json` is the document **as it was released**: what a client written against that release
relies on. A change that removes or changes something the baseline offers fails the test, whether or not the snapshot
was regenerated with it (see `tests/ui/openapi_diff.py` for what is compared).

The baseline is refreshed once for each release, in the release commit, with

    uv run poe contracts:baseline

(all the baselines of `tests/baselines/common.py` at once; `uv run poe openapi:baseline` does this one)

and `x-release` in it must be the version of `pyproject.toml`, which the same test enforces, so a release that
does not refresh it fails. Until then it stays the document of the release before: a change that breaks it is
either not made, or approved with a reason in `ACCEPTED_BREAKS` of `tests/ui/openapi_diff.py`, and the entry is
removed when the baseline is refreshed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.baselines.common import RELEASE, project_version, read, write
from tests.ui.openapi_snapshot import build_document

BASELINE = Path(__file__).parent / "openapi.baseline.json"

__all__ = ["BASELINE", "RELEASE", "project_version", "read_baseline", "write_baseline"]


def read_baseline() -> dict[str, Any]:
    """Read the committed baseline."""
    return read(BASELINE)


def write_baseline() -> None:
    """Write the served document as the baseline of the version in `pyproject.toml`."""
    write(BASELINE, build_document())


if __name__ == "__main__":
    write_baseline()
