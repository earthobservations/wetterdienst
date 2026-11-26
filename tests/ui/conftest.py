# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures of the surface tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from wetterdienst.ui import core

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def _forget_auth_probes() -> Generator[None]:
    """Start and end every test with no answer of a credential probe kept, as `get_auth` reuses them for a minute."""
    core._auth_probes.clear()  # noqa: SLF001
    yield
    core._auth_probes.clear()  # noqa: SLF001


_CHARTS_SWITCHED_ON = pytest.StashKey[bool]()
#: what the host's environment says of the setting before any test, which a test of the command line must find as it is
AMBIENT_PLOTTING = os.environ.get("WD_RESTAPI_PLOTTING")
_CLI_TESTS = Path(__file__).parent / "cli"


def _is_cli_test(item: pytest.Item) -> bool:
    """Tell whether a test is one of `tests/ui/cli`: the setting is the REST API's, and the command line ignores it."""
    return item.path.is_relative_to(_CLI_TESTS)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None]:
    """Switch the charts of the REST API on for every surface test that did not say otherwise (GH-4461).

    Off is the default (`WD_RESTAPI_PLOTTING`), and the tests that ask for a chart expect one. This is a hook and no
    fixture because many modules of this directory clear every `WD_*` variable in a fixture of their own, which a
    fixture of this file, set up before theirs, would not survive: it is set once the fixtures are. A test that holds
    the refusal sets the variable to false in a fixture or in its body; one that holds the default deletes it in its
    body. It is taken away again once the fixtures are finished (`pytest_runtest_teardown`), after a `monkeypatch`
    has put back what it found.
    """
    result = yield
    # not for the command line, which has no such setting: its tests run with the variable as it is
    item.stash[_CHARTS_SWITCHED_ON] = "WD_RESTAPI_PLOTTING" not in os.environ and not _is_cli_test(item)
    if item.stash[_CHARTS_SWITCHED_ON]:
        os.environ["WD_RESTAPI_PLOTTING"] = "true"
    return result


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None]:
    """Take the variable away that `pytest_runtest_setup` set, once the fixtures have put back theirs."""
    try:
        return (yield)
    finally:
        if item.stash.get(_CHARTS_SWITCHED_ON, False):
            os.environ.pop("WD_RESTAPI_PLOTTING", None)
