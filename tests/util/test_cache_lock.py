# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Processes sharing a cache directory take turns on its metadata file and its sweep (GH-3485).

The lock file is `<directory>.lock` beside the blob directory, and the "other process" of these tests is a thread that
takes that file with a lock object of its own, which excludes the code under test exactly as another process does
(`flock` belongs to the open file, not to the process) and has none of its in-process locks.
"""

from __future__ import annotations

import errno
import inspect
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from filelock import FileLock, Timeout
from fsspec.implementations.cache_metadata import CacheMetadata
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.memory import MemoryFileSystem

from wetterdienst.util import network
from wetterdienst.util.network import _LockedWholeFileCacheFileSystem, _OneWriteCacheMetadata


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

    original = _OneWriteCacheMetadata._save  # noqa: SLF001
    started: list[threading.Thread] = []

    def save(self: CacheMetadata, metadata_to_save: dict, fn: str) -> None:
        # once, from the save of this filesystem: the other one is a thread of the test, which is not the one asked
        if not started and threading.current_thread() is threading.main_thread():
            started.append(threading.Thread(target=other_process))
            started[0].start()
            other_saved.wait(timeout=1)  # long enough for it to be done where nothing holds it back
        original(self, metadata_to_save, fn)

    monkeypatch.setattr(_OneWriteCacheMetadata, "_save", save)

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


def test_a_read_that_cannot_get_the_lock_in_time_keeps_its_view_and_does_not_read_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On Windows a read that meets another process's replace is a `PermissionError`: without the lock there is none.

    The view stays what it was, which costs a fetch again at most, and the next miss asks again.
    """
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    storage = _storage(tmp_path)
    _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600).cat_file("/mine.txt")
    later = _another_view(storage)
    later._metadata.cached_files = [{}]  # noqa: SLF001
    reads: list[str] = []
    original = CacheMetadata._load  # noqa: SLF001

    def load(self: CacheMetadata, fn: str) -> dict:
        reads.append(fn)
        return original(self, fn)

    monkeypatch.setattr(CacheMetadata, "_load", load)

    with FileLock(_lock_file(storage)):
        later.load_cache()

    assert reads == []
    assert list(later._metadata.cached_files[-1]) == []  # noqa: SLF001

    later.load_cache()  # the holder is gone

    assert list(later._metadata.cached_files[-1]) == ["/mine.txt"]  # noqa: SLF001


def test_a_view_built_while_the_lock_is_held_is_empty_and_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first load of a filesystem is a load like any other: it is skipped, and the filesystem is still built."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    storage = _storage(tmp_path)
    _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600).cat_file("/mine.txt")

    with FileLock(_lock_file(storage)):
        late = _another_view(storage)
        assert list(late._metadata.cached_files[-1]) == []  # noqa: SLF001

    assert late.cat_file("/mine.txt") == b"mine"
    assert _rows(storage) == ["/mine.txt"]  # the save merged what was on disk


def test_an_entry_dropped_while_the_lock_is_held_by_another_leaves_the_file_unread_and_unwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row that stays names a blob that is not there, which every filesystem reads as a copy that is not held."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    mine.cat_file("/mine.txt")
    blob = storage / mine._mapper("/mine.txt")  # noqa: SLF001
    before = (storage / "cache").read_bytes()
    status = (storage / "cache").stat()
    saves: list[str] = []
    original = _OneWriteCacheMetadata._save  # noqa: SLF001

    def spy(self: CacheMetadata, data: dict, fn: str) -> None:
        saves.append(fn)
        original(self, data, fn)

    monkeypatch.setattr(_OneWriteCacheMetadata, "_save", spy)

    with FileLock(_lock_file(storage)):
        mine.pop_from_cache("/mine.txt")

    assert saves == []  # fsspec's drop would have saved: read, merge and replace, without the lock
    assert (storage / "cache").read_bytes() == before
    assert (storage / "cache").stat().st_ino == status.st_ino  # not replaced
    assert (storage / "cache").stat().st_mtime_ns == status.st_mtime_ns
    assert not blob.exists()
    assert not mine._metadata.check_file("/mine.txt", None)  # noqa: SLF001
    assert not _another_view(storage)._metadata.check_file("/mine.txt", None)  # noqa: SLF001


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
    # the wait above marked the directory, and a marked one is only tried: the save below is to be a wait of its
    # own, with a timeout that a slow runner (Windows) does not come near unless the lock is held, and a save far
    # under it
    network._cache_dirs_contended_until.clear()  # noqa: SLF001
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 5.0)
    started = time.monotonic()
    mine.save_cache()

    assert time.monotonic() - started < 2.5  # not waited for
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
        network._locked_across_processes(storage, otherwise="a") as outer,  # noqa: SLF001
        network._locked_across_processes(storage, otherwise="b") as inner,  # noqa: SLF001
    ):
        assert outer is True
        assert inner is True
    assert time.monotonic() - started < 1

    # released once the outermost hold ends: another lock object on the file takes it at once
    with FileLock(_lock_file(storage), timeout=1):
        pass


def test_a_holder_that_is_stuck_costs_one_wait_and_not_one_per_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The wait is with `_cache_dir_lock` held, so a stuck holder must not be waited for once for every file.

    The first save waits for the timeout and marks the directory; the saves after it only try the lock, until a hold
    gets it (the holder is gone) and the directory is not marked any more.
    """
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.5)
    storage = _storage(tmp_path)
    source = _source()
    for index in range(10):
        source.pipe_file(f"/f{index}.txt", b"x")
    mine = _LockedWholeFileCacheFileSystem(fs=source, cache_storage=str(storage), expiry_time=3600)
    caplog.set_level(logging.WARNING, logger=network.__name__)

    with FileLock(_lock_file(storage)):
        started = time.monotonic()
        for index in range(10):
            mine.cat_file(f"/f{index}.txt")
        waited = time.monotonic() - started

    assert waited < 2.5  # ten files, 0.5 s once and not three times each
    assert len([record for record in caplog.records if "Gave up waiting" in record.message]) == 1

    mine.save_cache()  # the holder is gone: the very next save is a save
    assert len(_rows(storage)) == 10


@pytest.mark.skipif(sys.platform == "win32", reason="the file system without flock is simulated through fcntl")
def test_a_file_system_without_flock_goes_without_the_lock_and_never_makes_a_soft_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ENOSYS` from `flock` is no lock, not a marker file.

    A marker that a dead process (or another host) left would hold every later save for good.
    """
    import fcntl  # noqa: PLC0415

    def no_flock(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.ENOSYS, "Function not implemented")

    monkeypatch.setattr(fcntl, "flock", no_flock)
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 5.0)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    # what a soft lock of a process on another host would have left
    Path(_lock_file(storage)).write_text("4242\nsome-other-host\n", encoding="utf-8")

    started = time.monotonic()
    mine.cat_file("/mine.txt")
    mine.cat_file("/theirs.txt")

    assert time.monotonic() - started < 2.5
    assert _rows(storage) == ["/mine.txt", "/theirs.txt"]


def test_the_rename_of_a_fetched_file_and_its_row_are_made_under_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sweep of another process cannot read the old row between the rename onto the blob and the new row."""
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    held_during_rename: list[bool] = []
    original = os.replace

    def replace(source: str, target: str) -> None:
        if str(source).endswith(".tmp") and not str(target).endswith(".lm"):
            try:
                with FileLock(_lock_file(storage), timeout=0):
                    held_during_rename.append(False)
            except Timeout:
                held_during_rename.append(True)
        original(source, target)

    monkeypatch.setattr(network.os, "replace", replace)

    mine.cat_file("/mine.txt")

    assert held_during_rename == [True]


def test_the_reclaim_leaves_a_directory_that_is_held_and_takes_its_lock_file_with_one_that_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is removed from under a process that is in the middle of something in the directory."""
    monkeypatch.setattr(network, "_reclaim_done", set())
    root = tmp_path / "fsspec"
    keep = root / "v2-ttl-ONE_HOUR"
    old = root / "ttl-ONE_HOUR"  # a layout no build writes any more
    for directory in (keep, old):
        directory.mkdir(parents=True)
    (old / "a-blob").write_bytes(b"payload")
    _aged(old, 7200)
    lock_file = Path(_lock_file(old))

    with FileLock(str(lock_file)):
        network._reclaim_unreachable_cache_dirs(root, keep=keep)  # noqa: SLF001
        assert old.is_dir()

    monkeypatch.setattr(network, "_reclaim_done", set())
    network._reclaim_unreachable_cache_dirs(root, keep=keep)  # noqa: SLF001

    assert not old.exists()
    assert not lock_file.exists()
    assert keep.is_dir()


def test_a_successful_hold_ends_the_period_of_a_marked_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mark is for as long as the holder is there: the first hold that gets the lock takes it away."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)

    with FileLock(_lock_file(storage)):
        mine.cat_file("/mine.txt")
    assert storage in network._cache_dirs_contended_until  # noqa: SLF001

    mine.cat_file("/theirs.txt")  # the holder is gone, and a try is enough

    assert storage not in network._cache_dirs_contended_until  # noqa: SLF001
    assert _rows(storage) == ["/mine.txt", "/theirs.txt"]


def test_the_period_of_a_marked_directory_runs_out_and_a_holder_that_is_still_there_is_waited_for_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A minute (here a fraction of a second) later the holder may have been stuck for that long and be gone, or not."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(network, "_CACHE_LOCK_CONTENDED_SECONDS", 0.6)
    storage = _storage(tmp_path)
    source = _source()
    source.pipe_file("/third.txt", b"x")
    source.pipe_file("/fourth.txt", b"x")
    mine = _LockedWholeFileCacheFileSystem(fs=source, cache_storage=str(storage), expiry_time=3600)

    with FileLock(_lock_file(storage)):
        started = time.monotonic()
        mine.cat_file("/mine.txt")  # waits, and marks
        first = time.monotonic() - started
        started = time.monotonic()
        mine.cat_file("/theirs.txt")  # marked: only tried
        marked = time.monotonic() - started
        time.sleep(0.7)
        started = time.monotonic()
        mine.cat_file("/third.txt")  # the period is over: waits again
        again = time.monotonic() - started

    assert first >= 0.25
    assert marked < 0.2
    assert again >= 0.25


def test_inside_the_period_a_load_only_tries_and_a_hold_ends_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A marked directory is not waited for by a load either, until the first hold that gets the lock."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 2.0)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    network._cache_dirs_contended_until[storage] = time.monotonic() + 60  # noqa: SLF001

    with FileLock(_lock_file(storage)):
        started = time.monotonic()
        mine.load_cache()
        waited = time.monotonic() - started

    assert waited < 1.0
    assert storage in network._cache_dirs_contended_until  # noqa: SLF001

    mine.load_cache()  # nobody holds it: a try is enough

    assert storage not in network._cache_dirs_contended_until  # noqa: SLF001


def test_the_period_of_a_marked_directory_runs_out_for_a_load_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After the period a load waits for the lock again, with the stamp of the lock file unchanged: a stuck holder."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.3)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    network._cache_dirs_contended_until[storage] = time.monotonic() - 1  # noqa: SLF001

    with FileLock(_lock_file(storage)):
        started = time.monotonic()
        mine.load_cache()
        waited = time.monotonic() - started

    assert waited >= 0.25
    assert storage in network._cache_dirs_contended_until  # noqa: SLF001


def _handing_the_lock_round(storage: Path, stop: threading.Event) -> threading.Thread:
    """Start the other processes of a queue: a lock that is taken, held a moment and let go of, again and again.

    The stamp is moved after each hold is taken, as `_locked_across_processes` does for every hold.
    """

    def cycle() -> None:
        lock = FileLock(_lock_file(storage), thread_local=False)
        while not stop.is_set():
            with lock:
                os.utime(_lock_file(storage))
                time.sleep(0.1)
            time.sleep(0.02)

    thread = threading.Thread(target=cycle)
    thread.start()
    return thread


def test_a_wait_goes_on_while_the_lock_goes_from_hand_to_hand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A queue is no reason to give up: only one hold for the whole timeout is."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.3)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    stop = threading.Event()
    cycling = _handing_the_lock_round(storage, stop)
    gave_up = []
    monkeypatch.setattr(network.log, "warning", lambda *args, **_kwargs: gave_up.append(args))
    try:
        time.sleep(0.15)  # the lock is in the hands of the other
        with network._locked_across_processes(storage, otherwise="x", wait=None) as proceed:  # noqa: SLF001
            got = proceed
        mine.cat_file("/mine.txt")
    finally:
        stop.set()
        cycling.join()

    assert got is True
    assert gave_up == []
    assert storage not in network._cache_dirs_contended_until  # noqa: SLF001
    assert _rows(storage) == ["/mine.txt"]


def test_a_wait_behind_a_lock_that_keeps_moving_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lock that moves without ever reaching this process is given up on after `_CACHE_LOCK_MAX_WAIT_SECONDS`."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.4)
    monkeypatch.setattr(network, "_CACHE_LOCK_MAX_WAIT_SECONDS", 0.5)
    stamps = iter(range(10_000))
    monkeypatch.setattr(network, "_lock_stamp", lambda _lock_file: next(stamps))  # the stamp changes at every look
    storage = _storage(tmp_path)
    storage.mkdir(parents=True)

    with FileLock(_lock_file(storage)):
        started = time.monotonic()
        with network._locked_across_processes(storage, otherwise="x") as proceed:  # noqa: SLF001
            waited = time.monotonic() - started

    assert proceed is False
    assert 0.45 <= waited < 0.7  # the cap and not the cap and another timeout
    assert storage in network._cache_dirs_contended_until  # noqa: SLF001


def test_every_hold_moves_the_stamp_of_the_lock_file(tmp_path: Path) -> None:
    """What the waiters of other processes read as progress."""
    storage = _storage(tmp_path)
    storage.mkdir(parents=True)
    lock_file = Path(_lock_file(storage))
    # the file is set to the beginning of time, and looked at inside a hold: where the platform removes the lock file
    # when it is let go (Windows) there is nothing to look at outside one
    lock_file.touch()
    os.utime(lock_file, (1, 1))

    with network._locked_across_processes(storage, otherwise="x"):  # noqa: SLF001
        assert lock_file.stat().st_mtime > 1_000_000


def test_a_wait_gives_up_one_timeout_after_the_lock_stopped_moving_and_not_at_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lock moves for a while and then one holder sticks: the progress that was made does not buy the cap."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(network, "_CACHE_LOCK_MAX_WAIT_SECONDS", 30.0)
    looks = iter(range(10_000))
    monkeypatch.setattr(network, "_lock_stamp", lambda _lock_file: min(next(looks), 3))  # moves three times
    storage = _storage(tmp_path)
    storage.mkdir(parents=True)

    with FileLock(_lock_file(storage)):
        started = time.monotonic()
        with network._locked_across_processes(storage, otherwise="x") as proceed:  # noqa: SLF001
            waited = time.monotonic() - started

    assert proceed is False
    assert 0.7 <= waited < 2.0  # four timeouts: the three that saw it move and the one that did not


def test_a_try_against_a_lock_that_keeps_moving_returns_at_once_and_marks_nothing(tmp_path: Path) -> None:
    """`wait=0` is a try: the progress of the lock is no reason to wait."""
    storage = _storage(tmp_path)
    storage.mkdir(parents=True)
    stop = threading.Event()
    cycling = _handing_the_lock_round(storage, stop)
    try:
        time.sleep(0.15)
        started = time.monotonic()
        with network._locked_across_processes(storage, otherwise="x", wait=0):  # noqa: SLF001
            waited = time.monotonic() - started
    finally:
        stop.set()
        cycling.join()

    assert waited < 0.3
    assert storage not in network._cache_dirs_contended_until  # noqa: SLF001


def test_a_load_that_is_skipped_keeps_the_rows_the_view_holds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Not emptied and not replaced by what is on the disk now."""
    monkeypatch.setattr(network, "_CACHE_LOCK_TIMEOUT_SECONDS", 0.2)
    storage = _storage(tmp_path)
    mine = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    mine.cat_file("/mine.txt")
    _another_view(storage).cat_file("/theirs.txt")  # a row this view does not hold

    with FileLock(_lock_file(storage)):
        mine.load_cache()

    assert list(mine._metadata.cached_files[-1]) == ["/mine.txt"]  # noqa: SLF001


def test_the_metadata_is_written_as_fsspec_writes_it_and_through_the_class_that_does_it_in_one_go(
    tmp_path: Path,
) -> None:
    """The file is the same bytes, so that nothing that reads it can tell; and the filesystem does write through it.

    Catches fsspec changing how `CacheMetadata._save` writes (the bytes differ, or the signature does), and the hook in
    `_LockedWholeFileCacheFileSystem.__init__` (the class of its metadata) being lost.
    """
    assert list(inspect.signature(CacheMetadata._save).parameters) == ["self", "metadata_to_save", "fn"]  # noqa: SLF001
    rows = {
        f"/p/{index}": {
            "original": f"/p/{index}",
            "fn": f"{index:064x}",
            "blocks": True,
            "time": 1793000000.123456 + index,
            "uid": '\u00e4"x',
        }
        for index in range(50)
    }
    theirs = tmp_path / "fsspec-writes"
    ours = tmp_path / "we-write"

    CacheMetadata(["/"])._save(rows, str(theirs))  # noqa: SLF001
    storage = _storage(tmp_path)
    view = _LockedWholeFileCacheFileSystem(fs=_source(), cache_storage=str(storage), expiry_time=3600)
    view._metadata._save(rows, str(ours))  # noqa: SLF001

    assert type(view._metadata) is _OneWriteCacheMetadata  # noqa: SLF001
    assert ours.read_bytes() == theirs.read_bytes()
    assert [path.name for path in tmp_path.iterdir() if path.name.startswith("we-write-")] == []  # no temp file left
