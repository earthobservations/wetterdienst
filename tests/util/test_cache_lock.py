# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Processes sharing a cache directory take turns on its metadata file and its sweep (GH-3485).

The lock file is `<directory>.lock` beside the blob directory, and the "other process" of these tests is a thread that
takes that file with a lock object of its own, which excludes the code under test exactly as another process does
(`flock` belongs to the open file, not to the process) and has none of its in-process locks.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock
from fsspec.implementations.cache_metadata import CacheMetadata
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.memory import MemoryFileSystem

from wetterdienst.util import network
from wetterdienst.util.network import _LockedWholeFileCacheFileSystem

if TYPE_CHECKING:
    import pytest


def _storage(tmp_path: Path) -> Path:
    return tmp_path / "fsspec" / "v2-ttl-ONE_HOUR"


def _lock_file(storage: Path) -> str:
    return str(storage.with_name(storage.name + ".lock"))


def _source() -> MemoryFileSystem:
    source = MemoryFileSystem()
    source.pipe_file("/mine.txt", b"mine")
    source.pipe_file("/theirs.txt", b"theirs")
    return source


def _another_view(storage: Path) -> _LockedWholeFileCacheFileSystem:
    """Build a filesystem of its own on the directory, as another process has.

    fsspec hands out the same one for the same arguments unless told not to, and that one holds the view of the first.
    """
    return _LockedWholeFileCacheFileSystem(
        fs=_source(), cache_storage=str(storage), expiry_time=3600, skip_instance_cache=True
    )


def _rows(storage: Path) -> list[str]:
    return sorted(json.loads((storage / "cache").read_text(encoding="utf-8")))


def _aged(path: Path, seconds: float) -> None:
    when = time.time() - seconds
    os.utime(path, (when, when))


def test_a_row_another_process_saves_while_this_one_saves_is_not_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The metadata file is read, merged and replaced as one step, whoever else is saving.

    Another process saves a row at the moment this one has read the file and not yet replaced it, which is the window
    in which that row used to be lost (its blob was then orphaned and fetched again). Here it saves from a thread that
    holds the lock file the way a process does, when the replace is about to happen: where the save is one step the
    other save waits for it, and where it is not it comes first and is overwritten.
    """
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    theirs = WholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    other_saved = threading.Event()

    def other_process() -> None:
        with FileLock(_lock_file(storage)):
            theirs.cat_file("/theirs.txt")
        other_saved.set()

    original = CacheMetadata._save  # noqa: SLF001
    started: list[threading.Thread] = []

    def save(self: CacheMetadata, metadata_to_save: dict, fn: str) -> None:
        # once, from the save of this filesystem: the other one is a thread of the test, which is not the one asked
        if not started and threading.current_thread() is threading.main_thread():
            started.append(threading.Thread(target=other_process))
            started[0].start()
            other_saved.wait(timeout=1)  # long enough for it to be done where nothing holds it back
        original(self, metadata_to_save, fn)

    monkeypatch.setattr(CacheMetadata, "_save", save)

    mine.cat_file("/mine.txt")
    started[0].join(timeout=30)

    assert _rows(storage) == ["/mine.txt", "/theirs.txt"]


def test_a_save_that_cannot_get_the_lock_in_time_is_skipped_and_nothing_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Another process that holds the lock for too long costs the save and not the request: no hang, no error."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    caplog.set_level(logging.WARNING, logger=network.__name__)

    with FileLock(_lock_file(storage)):
        started = time.monotonic()
        data = mine.cat_file("/mine.txt")
        waited = time.monotonic() - started

    assert data == b"mine"  # the request is answered
    assert waited < 5
    assert not (storage / "cache").exists()  # the row was not saved
    assert any("Gave up waiting" in record.message for record in caplog.records)

    # and the next save, with the lock free again, is the save it would have been
    mine.save_cache()
    assert _rows(storage) == ["/mine.txt"]


def test_a_sweep_that_cannot_get_the_lock_in_time_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A sweep is left to the next process: the expired row and its blob are where they were."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    mine.cat_file("/mine.txt")
    blob = storage / mine._mapper("/mine.txt")  # noqa: SLF001
    entries = json.loads((storage / "cache").read_text(encoding="utf-8"))
    entries["/mine.txt"]["time"] = time.time() - 7200
    (storage / "cache").write_text(json.dumps(entries), encoding="utf-8")
    _aged(blob, 7200)
    sweeper = _another_view(storage)

    with FileLock(_lock_file(storage)):
        sweeper.clear_expired_cache(expiry_time=3600)

    assert blob.is_file()
    assert _rows(storage) == ["/mine.txt"]

    sweeper.clear_expired_cache(expiry_time=3600)

    assert not blob.exists()
    assert _rows(storage) == []


def test_a_read_that_cannot_get_the_lock_in_time_goes_ahead(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A load has nothing to skip: it is what it was before there was a lock."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    storage = _storage(tmp_path)
    _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600).cat_file("/mine.txt")
    later = _another_view(storage)
    later._metadata.cached_files = [{}]  # noqa: SLF001

    with FileLock(_lock_file(storage)):
        later.load_cache()

    assert list(later._metadata.cached_files[-1]) == ["/mine.txt"]  # noqa: SLF001


def test_a_sweep_keeps_a_blob_written_within_the_expiry_whatever_its_row_says(tmp_path: Path) -> None:
    """The row is the old one and the file is the new one: a fetch renames its file onto the blob before it saves.

    In between, a sweep sees an expired row and a blob that is not expired. Removing the blob would leave the row the
    fetch saves next pointing at nothing, which is a `FileNotFoundError` for whoever reads it.
    """
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    mine.cat_file("/mine.txt")
    mine.cat_file("/theirs.txt")
    fresh = storage / mine._mapper("/mine.txt")  # noqa: SLF001
    old = storage / mine._mapper("/theirs.txt")  # noqa: SLF001
    entries = json.loads((storage / "cache").read_text(encoding="utf-8"))
    for row in entries.values():
        row["time"] = time.time() - 7200
    (storage / "cache").write_text(json.dumps(entries), encoding="utf-8")
    _aged(old, 7200)
    sweeper = _another_view(storage)

    sweeper.clear_expired_cache(expiry_time=3600)

    assert fresh.is_file()
    assert not old.exists()
    assert _rows(storage) == []


HOLDER = """
import sys
from filelock import FileLock

lock = FileLock(sys.argv[1])
lock.acquire()
print("held", flush=True)
sys.stdin.read()
"""


def test_a_lock_left_by_a_process_that_was_killed_holds_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The operating system releases a lock with its process, so a killed one leaves a file and no lock.

    The holder takes the lock file and is killed (SIGKILL, `TerminateProcess`), without releasing it. While it lives
    the save waits for it; once it is gone the lock is free at once, with the file still there.
    """
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.3)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    caplog.set_level(logging.WARNING, logger=network.__name__)
    holder = subprocess.Popen(  # noqa: S603
        [sys.executable, "-I", "-c", HOLDER, _lock_file(storage)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"

        mine.cat_file("/mine.txt")
        assert not (storage / "cache").exists()  # the holder is alive: skipped, after the timeout

        holder.kill()
        holder.wait(timeout=30)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=30)
        for stream in (holder.stdin, holder.stdout):
            if stream is not None:
                stream.close()

    assert Path(_lock_file(storage)).exists()  # what a killed process leaves
    caplog.clear()
    started = time.monotonic()
    mine.save_cache()

    assert time.monotonic() - started < 0.3  # not waited for
    assert not any("Gave up waiting" in record.message for record in caplog.records)
    assert _rows(storage) == ["/mine.txt"]


def test_the_lock_is_reentrant_within_a_thread(
    tmp_path: Path,
) -> None:
    """Loads and saves nest (a save inside a hold of the same directory) without waiting for themselves."""
    storage = _storage(tmp_path)
    storage.mkdir(parents=True)

    started = time.monotonic()
    with (
        network._locked_across_processes(storage, what="a") as outer,  # noqa: SLF001
        network._locked_across_processes(storage, what="b") as inner,  # noqa: SLF001
    ):
        assert outer is True
        assert inner is True
    assert time.monotonic() - started < 1

    # released once the outermost hold ends: another lock object on the file takes it at once
    with FileLock(_lock_file(storage), timeout=1):
        pass
