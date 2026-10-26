# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The cache metadata a caching filesystem holds in memory, and what a later thread is handed of it (GH-3452)."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import File, NetworkFilesystemManager, download_file, download_files

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


class _Source(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"payload " + self.path.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Keep the test output free of the access log."""


@pytest.fixture
def source() -> Iterator[ThreadingHTTPServer]:
    """Serve a small body for every path."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Source)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _url(server: ThreadingHTTPServer, path: str) -> str:
    return f"http://127.0.0.1:{server.server_port}{path}"


def _in_another_thread(function: Callable[[], object]) -> None:
    """Run `function` in a thread of its own and wait for it, as one worker of `download_files` does."""
    errors: list[BaseException] = []

    def run() -> None:
        try:
            function()
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=30)
    assert not thread.is_alive()
    if errors:
        raise errors[0]


def _download_in_another_thread(url: str, cache_dir: Path) -> File:
    """Download `url` into `cache_dir` from a thread that has ended when this returns."""
    answers: list[File] = []
    _in_another_thread(lambda: answers.append(download_file(url, cache_dir=cache_dir, ttl=CacheExpiry.ONE_HOUR)))
    return answers[0]


def test_a_filesystem_handed_to_a_later_thread_holds_the_entries_cached_since(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """A later thread given an earlier one's filesystem finds what other threads cached in between.

    fsspec names a filesystem by the arguments it is built with and the ident of the thread that builds it, and an
    ident is handed out again once its thread has ended: the thread of a later `download_files` is given the
    filesystem of an earlier one, which is not built again and so does not read the metadata file. It holds the
    entries it had when it last saved. Here the ident is the one of this thread, which gives up its registry (as a
    thread does by ending) and asks for a filesystem again.
    """
    url = _url(source, "/file.txt")
    first = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)

    # another thread caches the file: the metadata file has the entry, the filesystem above does not
    assert not _download_in_another_thread(url, tmp_path).from_cache
    assert first._check_file(url) is False  # noqa: SLF001

    NetworkFilesystemManager._get_filesystems().clear()  # noqa: SLF001
    later = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)

    # the premise: it is the filesystem of before. Were it a new one, there would be nothing to say
    assert later is first
    assert later._check_file(url) is not False  # noqa: SLF001
    assert download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR).from_cache


def test_the_second_download_files_finds_everything_the_first_cached(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """Whichever thread of the second call serves a file, the copy the first call made is found.

    The threads of the two calls are not the same ones, but their idents are, as often as not. Bounded: the rounds are
    what there is, and a round that loses an entry says which.
    """
    for round_ in range(8):
        cache = tmp_path / f"round-{round_}"
        urls = [_url(source, f"/round-{round_}/f{i}.txt") for i in range(12)]

        download_files(urls, cache_dir=cache, ttl=CacheExpiry.ONE_HOUR)
        again = download_files(urls, cache_dir=cache, ttl=CacheExpiry.ONE_HOUR)

        assert [file.url for file in again if not file.from_cache] == [], f"round {round_}"
