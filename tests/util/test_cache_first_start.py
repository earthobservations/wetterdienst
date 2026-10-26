# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Several processes starting on one empty cache directory do not sweep it away under each other (GH-3467)."""

from __future__ import annotations

import json
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


@pytest.mark.cflake
def test_processes_that_start_together_on_an_empty_directory_neither_crash_nor_leave_it(tmp_path: Path) -> None:
    """Six fresh processes at a barrier, the same twelve urls: no `FileExistsError`, no process cut off from the others.

    `python -m tests.util.cache_first_start_stress ROUNDS` runs more of them and counts the rounds. A copy that
    two processes both fetch because both missed at the same moment is not a failure of this test; one that a sweep
    removed is, and that is what `fallbacks` and the crashes carry.
    """
    found = run_round(tmp_path, processes=6)

    assert found.crashes == []
    assert found.fallbacks == 0
