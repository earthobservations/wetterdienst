# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a single download may be: its size, the time it takes, and a body that arrives compressed (GH-3340)."""

from __future__ import annotations

import asyncio
import gzip
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util import network
from wetterdienst.util.network import DownloadRefusedError, download_file

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

#: the ceiling the tests hold downloads to, in place of the two gigabytes they are held to
LIMIT = 1000
BODY = b"0123456789" * 50  # 500 bytes, inside the ceiling
LARGE = b"0123456789" * 200  # 2000 bytes, outside it


class _Handler(BaseHTTPRequestHandler):
    """Serve bodies of the sizes and the pace a download is held to."""

    def log_message(self, *args: object) -> None:
        pass

    def _send(self, body: bytes, *, length: bool = True, **headers: str) -> None:
        self.send_response(200)
        if length:
            self.send_header("Content-Length", str(len(body)))
        else:
            self.send_header("Transfer-Encoding", "chunked")
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), value)
        self.end_headers()
        if length:
            self.wfile.write(body)
        else:
            for start in range(0, len(body), 100):
                chunk = body[start : start + 100]
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.write(b"0\r\n\r\n")

    def do_GET(self) -> None:
        path = self.path
        if path == "/small.csv":
            self._send(BODY)
        elif path == "/large.csv":
            self._send(LARGE)
        elif path == "/large-without-length.csv":
            self._send(LARGE, length=False)
        elif path == "/inflates.csv":
            # a few dozen bytes on the wire that are two thousand once the client has undone the encoding
            self._send(gzip.compress(LARGE), Content_Encoding="gzip")
        elif path in {"/compressed.csv", "/compressed.csv.gz"}:
            self._send(gzip.compress(BODY))
        elif path == "/trickle.csv":
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for _ in range(100):
                    self.wfile.write(b"1\r\n0\r\n")
                    self.wfile.flush()
                    time.sleep(0.05)
                self.wfile.write(b"0\r\n\r\n")
            except OSError:
                pass  # the client gave up, which is the point
        else:
            self.send_error(404)


@pytest.fixture
def server() -> Iterator[str]:
    """Serve on a local port, and give the address."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _small_ceilings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network, "MAX_DOWNLOAD_BYTES", LIMIT)
    monkeypatch.setattr(network, "MAX_DOWNLOAD_SECONDS", 1)


def _fetch(url: str, tmp_path: Path, *, cached: bool, **kwargs: object) -> network.File:
    ttl = CacheExpiry.FIVE_MINUTES if cached else CacheExpiry.NO_CACHE
    return download_file(url, tmp_path, ttl, attempts=2, **kwargs)  # ty: ignore[invalid-argument-type]


@pytest.fixture(params=[False, True], ids=["uncached", "cached"])
def cached(request: pytest.FixtureRequest) -> bool:
    """Both ways a download is made: straight into memory, and through the file cache."""
    return request.param


def test_a_body_inside_the_ceiling_is_taken(server: str, tmp_path: Path, cached: bool) -> None:  # noqa: FBT001
    """The ceiling touches nothing that is inside it."""
    file = _fetch(f"{server}/small.csv", tmp_path, cached=cached)
    file.raise_if_exception()
    assert file.status == 200
    assert file.content.read() == BODY  # ty: ignore[unresolved-attribute]


@pytest.mark.parametrize("name", ["large.csv", "large-without-length.csv", "inflates.csv"])
def test_a_body_past_the_ceiling_is_a_download_error(
    server: str,
    tmp_path: Path,
    cached: bool,  # noqa: FBT001
    name: str,
) -> None:
    """Whether the body says how large it is or not, and whether it is large on the wire or once unencoded."""
    file = _fetch(f"{server}/{name}", tmp_path, cached=cached)
    assert isinstance(file.content, DownloadRefusedError)
    with pytest.raises(DownloadError, match=r"larger than the 0\.0009537 MB a download is held to") as raised:
        file.raise_if_exception()
    assert raised.value.__cause__ is file.content
    # the message names the file and the ceiling, and nothing else
    assert str(raised.value) == f"Failed to download {server}/{name}: {file.content}"
    if cached:
        assert not any(path.is_file() and path.suffix == ".tmp" for path in tmp_path.rglob("*"))


def test_a_body_that_says_it_is_too_large_is_refused_before_it_is_read() -> None:
    """The headers are enough: not a byte of the body is asked for from the stream."""

    class _Stream:
        async def read(self, _size: int) -> bytes:
            msg = "the body was read"
            raise AssertionError(msg)

    response = SimpleNamespace(content_length=LIMIT + 1, content=_Stream())
    with pytest.raises(DownloadRefusedError, match="larger than"):
        asyncio.run(network._read_capped(response, LIMIT))  # noqa: SLF001  # ty: ignore[invalid-argument-type]


def test_a_failed_download_is_not_asked_for_again(server: str, tmp_path: Path) -> None:
    """A body that is too large is as large the second time: one request, not two."""
    requests = []
    original = _Handler.do_GET

    def counting(self: _Handler) -> None:
        requests.append(self.path)
        original(self)

    _Handler.do_GET = counting  # ty: ignore[invalid-assignment]
    try:
        _fetch(f"{server}/large.csv", tmp_path, cached=False)
    finally:
        _Handler.do_GET = original  # ty: ignore[invalid-assignment]
    assert requests == ["/large.csv"]


def test_a_given_ceiling_replaces_the_default(server: str, tmp_path: Path, cached: bool) -> None:  # noqa: FBT001
    """`max_bytes` is the ceiling of that download: lower than the default, and higher."""
    smaller = _fetch(f"{server}/small.csv", tmp_path, cached=cached, max_bytes=100)
    assert isinstance(smaller.content, DownloadRefusedError)
    larger = _fetch(f"{server}/large.csv", tmp_path, cached=cached, max_bytes=5000)
    larger.raise_if_exception()
    assert larger.nbytes == len(LARGE)


def test_a_download_that_takes_too_long_is_a_download_error(server: str, tmp_path: Path, cached: bool) -> None:  # noqa: FBT001
    """A server that never goes silent keeps no download for longer than the time it is held to (5 s of bytes, 1 s)."""
    started = time.monotonic()
    file = _fetch(f"{server}/trickle.csv", tmp_path, cached=cached)
    assert time.monotonic() - started < 4
    assert isinstance(file.content, DownloadRefusedError)
    with pytest.raises(DownloadError, match="took longer than the 1 seconds a download is held to"):
        file.raise_if_exception()


def test_the_client_timeout_does_not_count_as_the_time_ceiling(
    server: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A timeout of the client is the timeout it was, and no refusal of the ceilings."""
    monkeypatch.setattr(network, "MAX_DOWNLOAD_SECONDS", 60)
    file = download_file(
        f"{server}/trickle.csv", tmp_path, CacheExpiry.NO_CACHE, client_kwargs={"timeout": 0.01}, attempts=1
    )
    assert isinstance(file.content, TimeoutError)
    assert not isinstance(file.content, DownloadRefusedError)


@pytest.mark.parametrize("name", ["compressed.csv"])
def test_a_body_that_is_compressed_while_its_name_is_not_is_refused(server: str, tmp_path: Path, name: str) -> None:
    """`polars.read_csv` unpacks a gzip body without a ceiling, so a table does not arrive compressed."""
    file = _fetch(f"{server}/{name}", tmp_path, cached=False)
    assert isinstance(file.content, DownloadRefusedError)
    with pytest.raises(DownloadError, match="the file is compressed, which a file of its name is not"):
        file.raise_if_exception()


def test_a_body_that_is_compressed_under_a_name_that_says_so_is_taken(server: str, tmp_path: Path) -> None:
    """The providers that serve compressed files name them so, and unpack them within a ceiling."""
    file = _fetch(f"{server}/compressed.csv.gz", tmp_path, cached=False)
    file.raise_if_exception()
    assert gzip.decompress(file.content.read()) == BODY  # ty: ignore[unresolved-attribute]


def test_the_settings_are_untouched_by_the_ceilings() -> None:
    """The ceilings are constants of the network module, not settings (nothing has asked to move them)."""
    assert not {"max_download_bytes", "max_download_seconds"} & set(Settings.model_fields)
