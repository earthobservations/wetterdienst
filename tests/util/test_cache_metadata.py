# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The cache metadata a caching filesystem holds in memory, and what a later thread is handed of it (GH-3452)."""

from __future__ import annotations

import json
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import (
    File,
    NetworkFilesystemManager,
    _LockedWholeFileCacheFileSystem,
    cached_copy_is_held,
    cached_file_time,
    download_file,
    download_files,
    drop_cached_file,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


class _Source(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.server.hits[self.path] += 1  # ty: ignore[unresolved-attribute]
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
    server.hits = Counter()  # ty: ignore[unresolved-attribute]
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


def _held_in_memory(filesystem: object, url: str) -> bool:
    """Say whether the copy is in what the filesystem holds in memory, without the read a miss now makes."""
    return bool(filesystem._metadata.check_file(url, None))  # noqa: SLF001


def test_a_filesystem_handed_to_a_later_thread_finds_the_entries_cached_since(
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
    assert not _held_in_memory(first, url)

    NetworkFilesystemManager._get_filesystems().clear()  # noqa: SLF001
    later = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)

    # the premise: it is the filesystem of before. Were it a new one, there would be nothing to say
    assert later is first
    assert download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR).from_cache


def test_a_thread_that_keeps_its_filesystem_finds_what_another_thread_cached(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """A thread that built its filesystem long ago (the main thread, a worker of a server) is no different.

    It never asks for a filesystem again, so nothing at that point could refresh it: what it holds is read again where
    it finds nothing, within the 10 s after which fsspec reads the file on its own.
    """
    url = _url(source, "/file.txt")
    mine = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)
    assert not cached_copy_is_held(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert not _download_in_another_thread(url, tmp_path).from_cache
    assert not _held_in_memory(mine, url)

    assert cached_copy_is_held(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR).from_cache


def test_a_copy_another_thread_cached_is_dropped_by_a_thread_that_keeps_its_filesystem(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """Dropping a copy finds it though this thread's view of the metadata is older than the copy."""
    url = _url(source, "/file.txt")
    mine = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)
    _download_in_another_thread(url, tmp_path)
    assert not _held_in_memory(mine, url)

    drop_cached_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert cached_file_time(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR) is None


def test_a_hit_reads_nothing_and_a_read_that_fails_on_a_miss_keeps_the_view(
    source: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hit does not read the file (that of a big cache is megabytes), and a read that fails on a miss is no failure.

    The read that fails is one that passes (on Windows, a file another process is replacing). A file cut short is
    not that, and stays an error where it was.
    """
    url = _url(source, "/file.txt")
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    reads: list[int] = []
    original = _LockedWholeFileCacheFileSystem.load_cache

    def counting(self: _LockedWholeFileCacheFileSystem) -> None:
        reads.append(1)
        original(self)

    monkeypatch.setattr(_LockedWholeFileCacheFileSystem, "load_cache", counting)

    for _ in range(100):
        assert download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR).from_cache
        assert cached_copy_is_held(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert reads == []

    # a file another thread has changed is read again by a miss, and one that is unreadable then leaves the answer of
    # the view: no copy, fetched
    _download_in_another_thread(_url(source, "/third.txt"), tmp_path)
    reads.clear()

    def unreadable(_self: _LockedWholeFileCacheFileSystem) -> None:
        reads.append(1)
        message = "Expecting value"
        raise ValueError(message)

    monkeypatch.setattr(_LockedWholeFileCacheFileSystem, "load_cache", unreadable)
    other = _url(source, "/other.txt")
    assert not cached_copy_is_held(other, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert reads
    fetched = download_file(other, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert (fetched.status, fetched.from_cache) == (200, False)


def _metadata_on_disk(cache_dir: Path) -> dict:
    (metadata_file,) = cache_dir.rglob("cache")
    return json.loads(metadata_file.read_text(encoding="utf-8"))


def test_a_thread_that_opens_a_file_directly_finds_what_another_thread_cached(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """`open` on the filesystem (the reader of a forecast does) is asked for the copy as `download_file` is."""
    url = _url(source, "/kml.kmz")
    mine = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)
    _download_in_another_thread(url, tmp_path)

    with mine.open(url, block_size=0) as handle:
        assert handle.read() == b"payload /kml.kmz"

    assert source.hits["/kml.kmz"] == 1  # ty: ignore[unresolved-attribute]


def test_a_copy_older_than_refetch_before_is_asked_for_again_where_another_thread_fetched_it_since(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """A view that holds a copy too old for the caller reads the file again before it fetches."""
    url = _url(source, "/r.txt")
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    time.sleep(0.05)
    cut = time.time()
    time.sleep(0.05)
    refetched = _in_thread_result(
        lambda: download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR, refetch_before=cut)
    )
    assert not refetched.from_cache

    again = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR, refetch_before=cut)

    assert again.from_cache
    assert source.hits["/r.txt"] == 2  # ty: ignore[unresolved-attribute]


def _in_thread_result(function: Callable[[], File]) -> File:
    answers: list[File] = []
    _in_another_thread(lambda: answers.append(function()))
    return answers[0]


def test_a_miss_reads_the_metadata_file_once(
    source: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A view older than `cache_check` is read again by fsspec on a lookup: that is the read of the miss."""
    url = _url(source, "/file.txt")
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    mine = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)
    reads: list[int] = []
    original = _LockedWholeFileCacheFileSystem.load_cache

    def counting(self: _LockedWholeFileCacheFileSystem) -> None:
        reads.append(1)
        original(self)

    monkeypatch.setattr(_LockedWholeFileCacheFileSystem, "load_cache", counting)
    other = _url(source, "/other.txt")

    mine.last_cache = time.time() - 60
    assert not cached_copy_is_held(other, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert len(reads) == 1

    # `cached_file_time` refreshes as a lookup does: once for a file another thread changed, never for one that is not
    reads.clear()
    assert cached_file_time(other, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR) is None
    assert reads == []
    third = _url(source, "/third.txt")
    _download_in_another_thread(third, tmp_path)
    reads.clear()
    assert cached_file_time(third, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR) is not None
    assert len(reads) == 1


def test_a_reload_cannot_fall_between_the_record_of_a_fetch_and_its_save(
    source: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One filesystem used by two threads (the reader of a forecast moves threads) does not lose the entry it records.

    A thread that reads the metadata file again replaces what the filesystem holds before it puts back what only this
    filesystem held, so between the record of a fetch and the line that sets its time the entry is not there. The
    other thread is started from inside the save, which is where the two meet, and must wait for the lock. This
    asserts the mechanism (the wait) and then the outcome (the entry is on disk).
    """
    mine = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)
    url = _url(source, "/new.txt")
    other = _url(source, "/never.txt")
    original = _LockedWholeFileCacheFileSystem.save_cache
    waited: list[bool] = []
    readers: list[threading.Thread] = []

    def save_with_a_reader_waiting(self: _LockedWholeFileCacheFileSystem) -> None:
        reader = threading.Thread(target=lambda: self._check_file(other))
        readers.append(reader)
        reader.start()
        reader.join(timeout=0.3)
        waited.append(reader.is_alive())
        original(self)

    monkeypatch.setattr(_LockedWholeFileCacheFileSystem, "save_cache", save_with_a_reader_waiting)

    with mine.open(url, block_size=0) as handle:
        handle.read()
    readers[0].join(timeout=30)

    assert waited == [True]
    assert url in _metadata_on_disk(tmp_path)


def test_a_filesystem_that_another_thread_misses_on_loses_none_of_the_entries_it_records(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """The same, as a run: opens in one thread while another asks for copies that are not there. Bounded."""
    mine = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)
    stop = threading.Event()

    def misses() -> None:
        index = 0
        while not stop.is_set():
            mine._check_file(_url(source, f"/never/{index}"))  # noqa: SLF001
            index += 1

    thread = threading.Thread(target=misses)
    thread.start()
    urls = [_url(source, f"/c/{index}.txt") for index in range(150)]
    try:
        for url in urls:
            with mine.open(url, block_size=0) as handle:
                handle.read()
    finally:
        stop.set()
        thread.join(timeout=30)

    on_disk = _metadata_on_disk(tmp_path)
    assert [url for url in urls if url not in on_disk] == []


def test_an_entry_another_process_dropped_is_written_back_by_the_thread_that_fetched_it(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """A reload keeps what this filesystem holds, as fsspec's save does, so the entry a racing process lost comes back.

    Two processes that save at once can write the file from a read older than the other's entry. The filesystem that
    fetched the file holds it and writes it back with its next save: a reload that replaced what it held by what the
    file says would not.
    """
    x = _url(source, "/x.txt")
    y = _url(source, "/y.txt")
    download_file(x, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    (metadata_file,) = tmp_path.rglob("cache")
    entries = json.loads(metadata_file.read_text(encoding="utf-8"))
    del entries[x]
    metadata_file.write_text(json.dumps(entries), encoding="utf-8")

    download_file(y, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert x in _metadata_on_disk(tmp_path)
    assert _in_thread_result(lambda: download_file(x, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)).from_cache


def _rewrite_metadata(cache_dir: Path, change: Callable[[dict], None]) -> None:
    """Change the metadata file as another process's write would."""
    (metadata_file,) = cache_dir.rglob("cache")
    entries = json.loads(metadata_file.read_text(encoding="utf-8"))
    change(entries)
    metadata_file.write_text(json.dumps(entries), encoding="utf-8")


def test_the_later_time_of_an_entry_wins_where_the_view_and_the_file_both_hold_it(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """The refresh merges as fsspec's save does: the newer of two records of a copy is the one kept, whichever side."""
    older = _url(source, "/older.txt")
    newer = _url(source, "/newer.txt")
    download_file(older, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    download_file(newer, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    held = cached_file_time(older, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert held is not None
    in_the_future = time.time() + 600

    def change(entries: dict) -> None:
        entries[older]["time"] = 0  # the file has an older record than the view
        entries[newer]["time"] = in_the_future  # and a newer one

    _rewrite_metadata(tmp_path, change)
    assert not cached_copy_is_held(_url(source, "/never.txt"), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert cached_file_time(older, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR) == held
    assert cached_file_time(newer, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR) == in_the_future


def test_an_entry_of_the_file_without_a_time_does_not_cost_the_view_what_only_it_holds(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """A record that says nothing usable is no failure, and the entries only this filesystem holds are kept."""
    x = _url(source, "/x.txt")
    y = _url(source, "/y.txt")
    download_file(x, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    download_file(y, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    def change(entries: dict) -> None:
        del entries[y]  # a record another process dropped
        del entries[x]["time"]  # one that lost its time
        entries["http://example.invalid/bad"] = {"original": "bad", "fn": "bad", "blocks": True, "time": "soon"}

    _rewrite_metadata(tmp_path, change)

    assert not cached_copy_is_held(_url(source, "/never.txt"), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert cached_copy_is_held(x, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert cached_copy_is_held(y, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)


def test_a_view_that_another_thread_moved_while_this_one_looked_is_asked_again(
    source: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two threads on one filesystem: a miss that was answered by the older view is not returned once the view moved."""
    x = _url(source, "/x.txt")
    z = _url(source, "/z.txt")
    mine = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False)
    _download_in_another_thread(x, tmp_path)
    original = mine._metadata.check_file  # noqa: SLF001
    armed = [True]

    def check_file(path: str, cfs: object) -> object:
        answer = original(path, cfs)
        if armed[0] and path == x:
            armed[0] = False

            def other() -> None:
                with mine.open(z, block_size=0) as handle:
                    handle.read()

            thread = threading.Thread(target=other)
            thread.start()
            thread.join(timeout=30)
        return answer

    monkeypatch.setattr(mine._metadata, "check_file", check_file)  # noqa: SLF001

    with mine.open(x, block_size=0) as handle:
        handle.read()

    assert source.hits["/x.txt"] == 1  # ty: ignore[unresolved-attribute]


def test_a_miss_on_a_file_that_has_not_changed_since_it_was_read_reads_nothing(
    source: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The file of a big cache is megabytes: asking about a file and then fetching it reads it where it has moved."""
    download_file(_url(source, "/warm.txt"), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    reads: list[int] = []
    original = _LockedWholeFileCacheFileSystem.load_cache

    def counting(self: _LockedWholeFileCacheFileSystem) -> None:
        reads.append(1)
        original(self)

    monkeypatch.setattr(_LockedWholeFileCacheFileSystem, "load_cache", counting)

    for index in range(20):
        cold = _url(source, f"/cold/{index}.txt")
        assert not cached_copy_is_held(cold, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
        assert not download_file(cold, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR).from_cache
    assert reads == []

    # a file that another thread has changed is read once, by the first miss that finds it so
    _download_in_another_thread(_url(source, "/other.txt"), tmp_path)
    reads.clear()
    for index in range(3):
        assert not cached_copy_is_held(_url(source, f"/never/{index}"), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert len(reads) == 1


def test_the_second_download_files_finds_everything_the_first_cached(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """Whichever thread of the second call serves a file, the copy the first call made is found.

    The threads of the two calls are not the same ones, but their idents are, as often as not. Bounded: the rounds are
    what there is, and a round that loses an entry says which.
    """
    for round_ in range(6):
        cache = tmp_path / f"round-{round_}"
        urls = [_url(source, f"/round-{round_}/f{i}.txt") for i in range(20)]

        download_files(urls, cache_dir=cache, ttl=CacheExpiry.ONE_HOUR)
        again = download_files(urls, cache_dir=cache, ttl=CacheExpiry.ONE_HOUR)

        assert [file.url for file in again if not file.from_cache] == [], f"round {round_}"
