# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures of the surface tests."""

from __future__ import annotations

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
