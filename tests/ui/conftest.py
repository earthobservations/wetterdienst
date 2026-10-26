# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures of the surface tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from wetterdienst.ui.core import clear_auth_probes

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def _forget_auth_probes() -> Generator[None]:
    """Start and end every test with no answer of a credential probe kept, as `get_auth` reuses them for a minute."""
    clear_auth_probes()
    yield
    clear_auth_probes()
