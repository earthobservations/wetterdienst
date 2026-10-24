# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what AEMET's envelope and "datos" body leave in the cache (GH-2750, GH-2887).

AEMET reports most of its errors in the body of an HTTP 200, which the download layer caches for the
whole `ttl` like an answer, and its "datos" link is pre-signed and can fail while the envelope that
holds it is still cached. These go through the real caching filesystem, against a local server
that answers as AEMET does, and without a key of AEMET's.
"""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.aemet.observation import api as aemet_api
from wetterdienst.provider.aemet.observation.api import AemetKeyRejectedError, AemetObservationRequest, _fetch_datos
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_INVENTORY = "/valores/climatologicos/inventarioestaciones/todasestaciones"
_ENVELOPE = "/envelope"
_PAYLOAD = b'[{"indicativo": "0016A"}]'


class _Aemet(BaseHTTPRequestHandler):
    """Answer each path with its scripted bodies in turn, the last for good, as HTTP 200 unless a status is given."""

    def do_GET(self) -> None:
        server = self.server
        server.requests.append(self.path)
        bodies = server.script[self.path]
        body = bodies.pop(0) if len(bodies) > 1 else bodies[0]
        status, body = body if isinstance(body, tuple) else (200, body)
        self.send_response(status)
        if status == HTTPStatus.FOUND:  # the body of a redirect is the address it leads to
            self.send_header("Location", body.decode())
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
        pytest.param(b"<html>maintenance</html>", id="html"),
        pytest.param(_envelope(200), id="no-link"),
    ],
)
def test_a_failed_envelope_is_asked_for_again(aemet: ThreadingHTTPServer, failure: bytes) -> None:
    """An envelope that is a failure is not read back from the cache: the next request asks AEMET again."""
    aemet.script = {
        _ENVELOPE: [failure, _envelope(200, datos=_url(aemet, "/datos"))],
        "/datos": [_PAYLOAD],
    }
    settings = Settings()
    assert isinstance(_fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES), Exception)
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES) == _PAYLOAD
    assert aemet.requests == [_ENVELOPE, _ENVELOPE, "/datos"]


def test_an_estado_401_is_asked_for_again_at_once_and_not_read_back_from_the_cache(
    aemet: ThreadingHTTPServer,
) -> None:
    """The refusal is cached like any 200: the second request must reach AEMET, which accepts the key then (GH-3022)."""
    aemet.script = {
        _ENVELOPE: [_envelope(401), _envelope(200, datos=_url(aemet, "/datos"))],
        "/datos": [_PAYLOAD],
    }
    assert _fetch_datos(_url(aemet, _ENVELOPE), Settings(), CacheExpiry.FIVE_MINUTES) == _PAYLOAD
    assert aemet.requests == [_ENVELOPE, _ENVELOPE, "/datos"]


def test_a_key_refused_twice_is_refused_and_the_refusal_is_not_kept(aemet: ThreadingHTTPServer) -> None:
    """Two `estado` 401 are a refused key, asked twice and no more; the next request asks AEMET again."""
    aemet.script = {
        _ENVELOPE: [_envelope(401), _envelope(401), _envelope(200, datos=_url(aemet, "/datos"))],
        "/datos": [_PAYLOAD],
    }
    settings = Settings()
    assert isinstance(_fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES), AemetKeyRejectedError)
    assert aemet.requests == [_ENVELOPE, _ENVELOPE]
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES) == _PAYLOAD


def test_a_good_envelope_stays_in_the_cache(aemet: ThreadingHTTPServer) -> None:
    """Dropping what failed does not cost the cache what worked."""
    aemet.script = {_ENVELOPE: [_envelope(200, datos=_url(aemet, "/datos"))], "/datos": [_PAYLOAD]}
    settings = Settings()
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES) == _PAYLOAD
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.FIVE_MINUTES) == _PAYLOAD
    assert aemet.requests == [_ENVELOPE, "/datos"]


def test_an_envelope_whose_link_failed_is_asked_for_again(aemet: ThreadingHTTPServer) -> None:
    """A link that cannot be fetched is not handed out again by the cached envelope that holds it."""
    aemet.script = {
        _ENVELOPE: [_envelope(200, datos=_url(aemet, "/expired")), _envelope(200, datos=_url(aemet, "/datos"))],
        "/expired": [(404, b"expired")],
        "/datos": [_PAYLOAD],
    }
    settings = Settings()
    assert isinstance(_fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.METAINDEX), Exception)
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.METAINDEX) == _PAYLOAD
    # the download layer tries the dead link more than once; what counts is that the envelope is asked again
    assert aemet.requests[0] == _ENVELOPE
    assert set(aemet.requests[1:-2]) == {"/expired"}
    assert aemet.requests[-2:] == [_ENVELOPE, "/datos"]


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(b"<html>maintenance</html>", id="html"),
        pytest.param(_envelope(429), id="estado-429"),
        pytest.param(b"", id="empty"),
    ],
)
def test_a_datos_body_that_is_no_array_is_asked_for_again(aemet: ThreadingHTTPServer, failure: bytes) -> None:
    """A body AEMET answered with a 200 but that is an error is not read back, nor is the link to it."""
    aemet.script = {
        _ENVELOPE: [_envelope(200, datos=_url(aemet, "/datos"))],
        "/datos": [failure, _PAYLOAD],
    }
    settings = Settings()
    assert isinstance(_fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.METAINDEX), Exception)
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.METAINDEX) == _PAYLOAD
    assert aemet.requests == [_ENVELOPE, "/datos", _ENVELOPE, "/datos"]


def test_an_empty_array_is_an_answer(aemet: ThreadingHTTPServer) -> None:
    """A station without records in the range gets `[]`, which is data and stays in the cache."""
    aemet.script = {_ENVELOPE: [_envelope(200, datos=_url(aemet, "/datos"))], "/datos": [b"[]"]}
    settings = Settings()
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.METAINDEX) == b"[]"
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.METAINDEX) == b"[]"
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


def test_a_link_to_another_host_than_aemets_is_not_fetched_and_the_envelope_is_asked_for_again(
    aemet: ThreadingHTTPServer,
) -> None:
    """The "datos" link is the envelope's to name, and a host that is not AEMET's is never asked (GH-3339)."""
    elsewhere = f"http://localhost:{aemet.server_port}/internal-only"
    aemet.script = {
        _ENVELOPE: [_envelope(200, datos=elsewhere), _envelope(200, datos=_url(aemet, "/datos"))],
        "/internal-only": [b'[{"secret": "internal-only"}]'],
        "/datos": [_PAYLOAD],
    }
    settings = Settings()
    refused = _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.METAINDEX)
    assert isinstance(refused, DownloadError)
    assert "the link was not fetched" in str(refused)
    assert aemet.requests == [_ENVELOPE]
    assert _fetch_datos(_url(aemet, _ENVELOPE), settings, CacheExpiry.METAINDEX) == _PAYLOAD
    assert aemet.requests == [_ENVELOPE, _ENVELOPE, "/datos"]


def test_a_redirect_of_the_request_that_carries_the_key_to_another_host_is_not_followed(
    aemet: ThreadingHTTPServer,
) -> None:
    """The key is sent in a header aiohttp does not drop on a redirect, so the redirect is not followed (GH-3338)."""
    aemet.script = {
        _ENVELOPE: [(302, f"http://localhost:{aemet.server_port}/internal-only".encode())],
        "/internal-only": [_envelope(200, datos=_url(aemet, "/datos"))],
    }
    refused = _fetch_datos(_url(aemet, _ENVELOPE), Settings(), CacheExpiry.METAINDEX)
    assert isinstance(refused, DownloadError)
    assert aemet.requests == [_ENVELOPE]
