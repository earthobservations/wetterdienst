# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Several processes starting on one empty cache directory do not sweep it away under each other (GH-3467)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.memory import MemoryFileSystem

from tests.util.cache_first_start_stress import run_round
from wetterdienst.util.listing_cache import make_private_dir
from wetterdienst.util.network import _LockedWholeFileCacheFileSystem


def _view(storage: Path) -> _LockedWholeFileCacheFileSystem:
    """Build the caching filesystem a process has on a directory: it reads the metadata as it is now."""
    return _LockedWholeFileCacheFileSystem(fs=MemoryFileSystem(), cache_storage=str(storage), expiry_time=3600)


def _another_process_caches(storage: Path, name: str = "/seeded.txt") -> Path:
    """Cache a file into `storage` the way a second process does, through a filesystem of its own; return its blob."""
    source = MemoryFileSystem()
    source.pipe_file(name, b"payload")
    other = WholeFileCacheFileSystem(fs=source, cache_storage=str(storage), expiry_time=3600)
    other.cat_file(name)
    return storage / other._mapper(name)  # noqa: SLF001


def _entries(storage: Path) -> dict:
    return json.loads((storage / "cache").read_text(encoding="utf-8"))


def test_a_sweep_of_an_empty_snapshot_leaves_what_another_process_wrote_since(tmp_path: Path) -> None:
    """The snapshot of a process that started first is empty, and a copy another process has since written is not.

    What the sweep ran from was the snapshot, so it took the empty directory for an empty cache and removed it, with
    the copy that had just been put into it.
    """
    storage = tmp_path / "fsspec" / "v2-ttl-ONE_HOUR"
    first = _view(storage)  # builds on an empty directory: nothing to read, nothing to expire
    blob = _another_process_caches(storage)

    first.clear_expired_cache(expiry_time=3600)

    assert blob.is_file()
    assert list(_entries(storage)) == ["/seeded.txt"]


def test_a_sweep_that_expires_every_entry_removes_those_and_not_the_directory(tmp_path: Path) -> None:
    """What a sweep removes is the entries that expired and their blobs: not the directory, not anything else in it."""
    storage = tmp_path / "fsspec" / "v2-ttl-ONE_HOUR"
    blob = _another_process_caches(storage)
    entries = _entries(storage)
    entries["/seeded.txt"]["time"] = time.time() - 7200
    (storage / "cache").write_text(json.dumps(entries), encoding="utf-8")
    first = _view(storage)
    # a copy another process has written since this one read the metadata: its entry is not in the snapshot
    elsewhere = storage / "written-by-another-process"
    elsewhere.write_bytes(b"payload")

    first.clear_expired_cache(expiry_time=3600)

    assert not blob.exists()
    assert elsewhere.is_file()
    assert _entries(storage) == {}


def test_a_sweep_with_nothing_expired_writes_nothing(tmp_path: Path) -> None:
    """The metadata file is the one place two processes can lose each other's rows, so it is left alone."""
    storage = tmp_path / "fsspec" / "v2-ttl-ONE_HOUR"
    _another_process_caches(storage)
    first = _view(storage)
    _another_process_caches(storage, "/second.txt")  # a row this view does not hold, which a write would drop
    before = (storage / "cache").read_bytes()

    first.clear_expired_cache(expiry_time=3600)

    assert (storage / "cache").read_bytes() == before
    assert sorted(_entries(storage)) == ["/second.txt", "/seeded.txt"]


def test_the_directory_that_is_removed_between_the_check_and_the_creation_is_made_after_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`mkdir` says the directory exists, and a moment later it does not: that is not an error, it is made again."""
    target = tmp_path / "fsspec" / "v2-ttl-ONE_HOUR"
    original = Path.mkdir
    answered: list[Path] = []

    def mkdir(self: Path, *args: object, **kwargs: object) -> None:
        if self == target and not answered:
            answered.append(self)
            raise FileExistsError(str(self))  # the other process's directory, which is already gone again
        original(self, *args, **kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(Path, "mkdir", mkdir)

    make_private_dir(target)

    assert answered == [target]
    assert target.is_dir()


def _aged(path: Path, seconds: float) -> Path:
    when = time.time() - seconds
    os.utime(path, (when, when))
    return path


def test_a_sweep_collects_the_files_no_row_names_that_are_older_than_the_expiry(tmp_path: Path) -> None:
    """What the removal of the whole directory used to collect and the sweep now leaves: orphans, and only old ones."""
    storage = tmp_path / "fsspec" / "v2-ttl-ONE_HOUR"
    live = _another_process_caches(storage)
    sidecar = live.with_name(live.name + ".lm")
    sidecar.write_text("{}", encoding="utf-8")
    old_orphan = storage / "a-blob-whose-row-was-lost"
    old_temp = storage / "a-blob.0123456789abcdef.tmp"
    young_orphan = storage / "a-blob-fetched-just-now"
    young_temp = storage / "a-blob.fedcba9876543210.tmp"
    for orphan in (old_orphan, old_temp, young_orphan, young_temp):
        orphan.write_bytes(b"payload")
    _aged(old_orphan, 7200)
    _aged(old_temp, 7200)
    (storage / ".last-used").touch()
    _aged(live, 7200)  # old, but a row names it
    _aged(sidecar, 7200)
    _aged(storage / "cache", 7200)
    _aged(storage / ".last-used", 7200)
    first = _view(storage)

    first.clear_expired_cache(expiry_time=3600)

    assert not old_orphan.exists()
    assert not old_temp.exists()
    assert young_orphan.is_file()
    assert young_temp.is_file()
    assert live.is_file()
    assert sidecar.is_file()
    assert (storage / "cache").is_file()
    assert (storage / ".last-used").is_file()


def test_a_stalled_fetch_is_older_than_a_short_ttl_and_is_not_taken_from_under_it(tmp_path: Path) -> None:
    """The file of a fetch in flight moves when bytes arrive, so with a TTL of seconds it is older than the expiry.

    Another process's sweep keeps what is younger than an hour whatever the TTL, and takes what is older.
    """
    storage = tmp_path / "fsspec" / "v2-ttl-FIVE_SECONDS"
    storage.mkdir(parents=True)
    stalled = storage / "a-blob.0123456789abcdef.tmp"
    orphan = storage / "an-orphan"
    abandoned = storage / "a-blob.fedcba9876543210.tmp"
    for path in (stalled, orphan, abandoned):
        path.write_bytes(b"payload")
    _aged(stalled, 60)  # older than the TTL, younger than the floor
    _aged(orphan, 60)
    _aged(abandoned, 7200)
    first = _LockedWholeFileCacheFileSystem(fs=MemoryFileSystem(), cache_storage=str(storage), expiry_time=5)

    first.clear_expired_cache(expiry_time=5)

    assert stalled.is_file()
    assert orphan.is_file()
    assert not abandoned.exists()


def test_a_blob_that_cannot_be_removed_does_not_stop_the_sweep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows refuses to remove a file that is open: the metadata is saved by then, and the rest still goes."""
    storage = tmp_path / "fsspec" / "v2-ttl-ONE_HOUR"
    blob = _another_process_caches(storage)
    entries = _entries(storage)
    entries["/seeded.txt"]["time"] = time.time() - 7200
    (storage / "cache").write_text(json.dumps(entries), encoding="utf-8")
    orphan = storage / "an-orphan"
    orphan.write_bytes(b"payload")
    _aged(orphan, 7200)
    first = _view(storage)
    original = Path.unlink

    def unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == blob:
            raise PermissionError(str(self))
        original(self, *args, **kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(Path, "unlink", unlink)

    first.clear_expired_cache(expiry_time=3600)

    assert _entries(storage) == {}
    assert not orphan.exists()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows cannot replace the metadata file while another process has it open: PermissionError in "
    "save_cache, which needs a cross-process lock (GH-3485)",
)
@pytest.mark.cflake
def test_processes_that_start_together_on_an_empty_directory_neither_crash_nor_leave_it(tmp_path: Path) -> None:
    """Six fresh processes at a barrier, the same twelve urls: no process raises, none goes private.

    It counts crashes (`FileExistsError` and the like) and fallbacks, not misses: `python -m
    tests.util.cache_first_start_stress ROUNDS` runs more rounds and counts the misses too, which are rows lost to
    another process's save (GH-3485) and not a thing the sweep decides.
    """
    found = run_round(tmp_path, processes=6)

    assert found.crashes == []
    assert found.fallbacks == 0
