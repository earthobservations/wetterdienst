# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A 200 of Hub'Eau that is no JSON is an outage, and is not kept in the cache (GH-4236).

Hub'Eau answers an HTML waiting page ("votre patience") with a 200 when it is overloaded. `download_file` holds a 200
for the whole expiry, so the page is dropped before the `DownloadError` is raised, and the next request asks again.
Through the real download and cache, against a server of this machine.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.eaufrance.hubeau.api import _paged_rows

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

WAITING_PAGE = b"<html><body><h1>Merci de votre patience</h1></body></html>"


class Hubeau:
    """A server that answers each path with the body set for it, and counts the requests of each."""

    def __init__(self, base: str) -> None:
        """Start with no body: a path that is not set is a 404."""
        self.base = base
        self.bodies: dict[str, bytes] = {}
        self.hits: dict[str, int] = {}


@pytest.fixture
def hubeau() -> Iterator[Hubeau]:
    """Serve Hub'Eau's pages from this machine."""
    holder: dict[str, Hubeau] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state = holder["state"]
            path = self.path.split("?", maxsplit=1)[0]
            state.hits[path] = state.hits.get(path, 0) + 1
            body = state.bodies.get(path)
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if body.startswith(b"<") else "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """Say nothing."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    holder["state"] = Hubeau(f"http://127.0.0.1:{server.server_address[1]}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield holder["state"]
    server.shutdown()
    server.server_close()


def _rows(url: str, cache_dir: Path) -> list[dict]:
    return _paged_rows(url, Settings(cache_dir=cache_dir), ttl=CacheExpiry.METAINDEX, timeout=10)


def _page(rows: list[dict], next_url: str | None = None) -> bytes:
    return json.dumps({"data": rows, "next": next_url}).encode()


def test_a_good_answer_is_kept(hubeau: Hubeau, tmp_path: Path) -> None:
    """Test the control: the page is asked once, and the second read comes from the cache."""
    hubeau.bodies["/stations"] = _page([{"n": 1}])
    url = f"{hubeau.base}/stations?format=json"

    assert _rows(url, tmp_path) == _rows(url, tmp_path) == [{"n": 1}]
    assert hubeau.hits["/stations"] == 1


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(WAITING_PAGE, id="html"),
        pytest.param(b"not json at all", id="text"),
        pytest.param(b"\xff\xfe\x00 not text", id="binary"),
        pytest.param(b'[{"n": 1}]', id="a-list"),
    ],
)
def test_an_answer_that_is_no_json_object_is_raised_and_not_kept(hubeau: Hubeau, tmp_path: Path, body: bytes) -> None:
    """Test that a bad 200 is a `DownloadError` naming the URL, and is asked again where it was kept for the expiry."""
    hubeau.bodies["/stations"] = body
    url = f"{hubeau.base}/stations?format=json&en_service=true"

    with pytest.raises(DownloadError) as raised:
        _rows(url, tmp_path)

    assert raised.value.url == f"{hubeau.base}/stations"
    assert f"{hubeau.base}/stations" in str(raised.value)
    hubeau.bodies["/stations"] = _page([{"n": 1}])

    assert _rows(url, tmp_path) == [{"n": 1}]
    assert hubeau.hits["/stations"] == 2


def test_a_waiting_page_for_a_later_page_is_raised_not_a_short_answer(hubeau: Hubeau, tmp_path: Path) -> None:
    """Test that the cursor's second page being the waiting page raises, and only that page is asked again."""
    hubeau.bodies["/first"] = _page([{"n": 1}], f"{hubeau.base}/second")
    hubeau.bodies["/second"] = WAITING_PAGE
    url = f"{hubeau.base}/first"

    with pytest.raises(DownloadError) as raised:
        _rows(url, tmp_path)

    assert raised.value.url == f"{hubeau.base}/second"
    hubeau.bodies["/second"] = _page([{"n": 2}])

    assert _rows(url, tmp_path) == [{"n": 1}, {"n": 2}]
    assert hubeau.hits == {"/first": 1, "/second": 2}
