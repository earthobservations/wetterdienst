# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures of the KNMI tests: the EDR API served from a local port (GH-3928)."""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import pytest

from tests.provider.knmi.observation.edr_stub import EdrStub
from wetterdienst.provider.knmi.observation import download, edr

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture(autouse=True)
def _no_ambient_settings(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests, a key of KNMI among them, out of the settings.

    The tests that need no key or a key of their own say so; a remote test reads the key where it is configured.
    """
    if request.node.get_closest_marker("remote"):
        return
    for name in list(os.environ):
        # `WD_FRAMES_SNAPSHOT` is a switch of the test run, read when the test ends: a write run of the frame snapshot
        # (`uv run poe frames:snapshot`) would otherwise take these tests for a comparison and record none of them
        if name.startswith("WD_") and name not in {"WD_CACHE_DIR", "WD_FRAMES_SNAPSHOT"}:
            monkeypatch.delenv(name)
    # the settings read `.env` from the working directory
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def edr_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[EdrStub]:
    """Serve the EDR API, with no data, on a local port, and have the provider ask it."""
    server = EdrStub([])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(edr, "EDR_BASE_URL", f"http://127.0.0.1:{server.server_port}/edr/v1")
    # one attempt is a failure: the retries of a 5xx are not what is tested
    monkeypatch.setattr(download, "RETRY_WAIT_INITIAL_SECONDS", 0.0)
    monkeypatch.setattr(download, "RETRY_WAIT_MAX_SECONDS", 0.0)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
