# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what `KMLReader.download` asks the server for (GH-3003).

The run is fetched through the real caching filesystem, from a local server that records the
methods it was asked with.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_BODY = b"a run of MOSMIX, as many bytes as the progress bar is told"
_RUN = "/kml/MOSMIX_L_2026101700_01001.kmz"


class _Dwd(BaseHTTPRequestHandler):
    """Answer the run for a GET and its size for a HEAD, and note which was asked."""

    def _answer(self, *, body: bool) -> None:
        self.server.requests.append(self.command)
        self.send_response(200)
        self.send_header("Content-Length", str(len(_BODY)))
        self.end_headers()
        if body:
            self.wfile.write(_BODY)

    def do_GET(self) -> None:
        self._answer(body=True)

    def do_HEAD(self) -> None:
        self._answer(body=False)

    def log_message(self, *args: object) -> None:
        """Keep the test output quiet."""


@pytest.fixture
def server() -> Iterator[ThreadingHTTPServer]:
    """Serve a local stand-in for DWD's opendata."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Dwd)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _download(server: ThreadingHTTPServer, tmp_path: Path, *, cache_disable: bool) -> bytes:
    settings = Settings(cache_dir=tmp_path, cache_disable=cache_disable)
    reader = KMLReader(station_ids=["01001"], settings=settings)
    return reader.download(f"http://127.0.0.1:{server.server_port}{_RUN}").getvalue()


def test_a_cached_run_asks_the_server_for_nothing(server: ThreadingHTTPServer, tmp_path: Path) -> None:
    """The size of a run the cache holds is on the disk: no HEAD, and no request at all once it is cached."""
    assert _download(server, tmp_path, cache_disable=False) == _BODY
    assert server.requests == ["GET"]

    server.requests.clear()
    assert _download(server, tmp_path, cache_disable=False) == _BODY
    assert server.requests == []


def test_a_run_that_is_not_cached_is_sized_by_a_head(server: ThreadingHTTPServer, tmp_path: Path) -> None:
    """A stream that is held nowhere has no size but the server's, which still sizes the progress bar."""
    assert _download(server, tmp_path, cache_disable=True) == _BODY
    assert "HEAD" in server.requests
