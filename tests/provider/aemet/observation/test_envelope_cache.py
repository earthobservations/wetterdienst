# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what AEMET's envelope leaves in the cache (GH-2750).

AEMET reports most of its errors in the body of an HTTP 200, which the download layer caches for the
whole `ttl` like an answer. These go through the real caching filesystem, against a local server
that answers as AEMET does, and without a key of AEMET's.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.aemet.observation import api as aemet_api
from wetterdienst.provider.aemet.observation.api import AemetObservationRequest, _fetch_datos
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_INVENTORY = "/valores/climatologicos/inventarioestaciones/todasestaciones"
_ENVELOPE = "/envelope"


class _Aemet(BaseHTTPRequestHandler):
    """Answer each path with its scripted bodies in turn, the last one for good, always as HTTP 200."""

    def do_GET(self) -> None:
        server = self.server
        server.requests.append(self.path)
        bodies = server.script[self.path]
        body = bodies.pop(0) if len(bodies) > 1 else bodies[0]
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the test output quiet."""


def _envelope(estado: int, **extra: str) -> bytes:
    return json.dumps({"estado": estado, "descripcion": "the answer", **extra}).encode()


@pytest.fixture
def aemet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[ThreadingHTTPServer]:
    """Serve a local stand-in for AEMET, with a throwaway key and a cache of its own."""
    monkeypatch.setenv("WD_AUTH__AEMET", "dummy-key-for-test")
    monkeypatch.setenv("WD_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("WD_CACHE_DISABLE", "false")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Aemet)
    server.requests = []
    server.script = {}
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(aemet_api, "_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _url(server: ThreadingHTTPServer, path: str) -> str:
    return f"http://127.0.0.1:{server.server_port}{path}"


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(_envelope(429), id="estado-429"),
        pytest.param(_envelope(500), id="estado-500"),
        pytest.param(_envelope(401), id="estado-401"),
        pytest.param(b"<html>maintenance</html>", id="html"),
        pytest.param(_envelope(200), id="no-link"),
    ],
)
def test_a_failed_envelope_is_asked_for_again(aemet: ThreadingHTTPServer, failure: bytes) -> None:
    """An envelope that is a failure is not read back from the cache: the next request asks AEMET again."""
    aemet.script = {
        _ENVELOPE: [failure, _envelope(200, datos=_url(aemet, "/datos"))],
        "/datos": [b"payload"],
    }
    settings = Settings()
    assert isinstance(_fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES), Exception)
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES) == b"payload"
    assert aemet.requests == [_ENVELOPE, _ENVELOPE, "/datos"]


def test_a_good_envelope_stays_in_the_cache(aemet: ThreadingHTTPServer) -> None:
    """Dropping what failed does not cost the cache what worked."""
    aemet.script = {_ENVELOPE: [_envelope(200, datos=_url(aemet, "/datos"))], "/datos": [b"payload"]}
    settings = Settings()
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES) == b"payload"
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES) == b"payload"
    assert aemet.requests == [_ENVELOPE, "/datos"]


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        pytest.param(_envelope(429), None, id="estado-429"),
        pytest.param(_envelope(500), None, id="estado-500"),
        pytest.param(b"<html>maintenance</html>", None, id="html"),
        pytest.param(_envelope(401), False, id="estado-401"),
    ],
)
def test_a_failed_probe_is_asked_for_again(aemet: ThreadingHTTPServer, failure: bytes, expected: bool | None) -> None:  # noqa: FBT001
    """A probe that came back as a failure or a refusal is not answered from the cache by the next one."""
    aemet.script = {_INVENTORY: [failure, _envelope(200)]}
    assert AemetObservationRequest.is_valid() is expected
    assert AemetObservationRequest.is_valid() is True
    assert aemet.requests == [_INVENTORY, _INVENTORY]


def test_an_accepted_probe_is_answered_from_the_cache_for_a_while(aemet: ThreadingHTTPServer) -> None:
    """The acceptance is what the cache is for: polling does not ask AEMET again within the minute."""
    aemet.script = {_INVENTORY: [_envelope(200)]}
    assert AemetObservationRequest.is_valid() is True
    assert AemetObservationRequest.is_valid() is True
    assert aemet.requests == [_INVENTORY]
