# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures of the Frost tests."""

from __future__ import annotations

import pytest

from wetterdienst.provider.metno.frost import api as frost_api


@pytest.fixture(autouse=True)
def _no_second_look_at_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Have a 403 read as the status alone, as a refusal that cannot be asked for again is.

    The reader asks a 403 once more to read why (a window over the limit of 100,000 observations, GH-3748), which is
    a connection: a test that stubs the download has no body to give, and the one that does stubs `read_refusal`.
    """
    monkeypatch.setattr(frost_api, "read_refusal", lambda *_args, **_kwargs: None)
