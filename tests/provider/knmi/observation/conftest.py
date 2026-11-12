# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures of the KNMI tests: the EDR API served from a local port (GH-3928)."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from tests.provider.knmi.observation.edr_stub import EdrStub
from wetterdienst.provider.knmi.observation import api, edr

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def edr_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[EdrStub]:
    """Serve the EDR API, with no data, on a local port, and have the provider ask it."""
    server = EdrStub([])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(edr, "EDR_BASE_URL", f"http://127.0.0.1:{server.server_port}/edr/v1")
    # one attempt is a failure: the retries of a 5xx are not what is tested
    monkeypatch.setattr(api, "_RETRY_WAIT_INITIAL_SECONDS", 0.0)
    monkeypatch.setattr(api, "_RETRY_WAIT_MAX_SECONDS", 0.0)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
