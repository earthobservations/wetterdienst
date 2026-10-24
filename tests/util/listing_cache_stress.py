"""Hammer one listings store from several processes of several threads, and count what goes wrong.

Used by `test_listing_cache.py`, and runnable on its own to try a Python or a machine:

    python -m tests.util.listing_cache_stress DIRECTORY [PROCESSES] [THREADS] [ITERATIONS]

Nothing here sleeps: every worker starts at a barrier and then runs flat out, so the load is as
contended as the machine allows, whatever its speed. What is checked:

* no call raises (`database is locked` above all),
* a listing that is read is one that was written whole: every entry of a value carries the tag of
  its writer and iteration, so a value mixed from two writes, or cut short, is found,
* an entry that was written with no expiry and never deleted is still there when everyone is done.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import sys
import threading
import traceback
from pathlib import Path

from wetterdienst.util.listing_cache import STORE_FILENAME, ListingStore

SHARED_KEYS = [f"https://example.com/shared/{index}/" for index in range(12)]


class _CollectWarnings(logging.Handler):
    def __init__(self, into: list[str]) -> None:
        super().__init__(level=logging.WARNING)
        self.into = into

    def emit(self, record: logging.LogRecord) -> None:
        self.into.append(f"the store warned: {record.getMessage()}")


def listing_for(tag: str) -> list[dict]:
    """Return the listing a writer stores under `tag`: its length and every entry are functions of the tag."""
    rows = 40 + sum(map(ord, tag)) % 60
    return [{"name": f"{tag}/{row}.zip", "size": None, "type": "file", "tag": tag, "rows": rows} for row in range(rows)]


def is_whole(listing: list[dict]) -> bool:
    """Whether `listing` is exactly what `listing_for` makes of the tag it carries."""
    return bool(listing) and listing == listing_for(listing[0]["tag"])


def private_key(worker: int, thread: int, index: int) -> str:
    """Return the key of an entry written once, for good, and checked at the end."""
    return f"https://example.com/private/{worker}/{thread}/{index}/"


def run_thread(  # noqa: C901
    path: Path, worker: int, thread: int, iterations: int, shared: ListingStore, errors: list[str]
) -> int:
    """One thread's share of the work; returns how many private entries it wrote."""
    store = shared if thread % 2 else ListingStore(path)
    private = 0
    try:
        for i in range(iterations):
            key = SHARED_KEYS[(i + thread) % len(SHARED_KEYS)]
            tag = f"{worker}.{thread}.{i}"
            step = i % 8
            if step < 4:
                value = store.get(key)
                if value is not None and not is_whole(value):
                    errors.append(f"torn value under {key}: {value[:2]}")
            elif step == 4:
                store.set(key, listing_for(tag), None if i % 16 else 600.0)
            elif step == 5:
                store.set(key, listing_for(tag), 0.0)  # expired as it is written
            elif step == 6:
                store.delete(key)
            else:
                store.set(private_key(worker, thread, private), listing_for(tag), None)
                private += 1
            if i % 40 == 0:
                store.count()
                store.keys()
                store.expire()
                assert store.contains(key) in {True, False}
            if i % 97 == 0:
                # a connection opened in the middle of everything else
                ListingStore(path).get(key)
    except BaseException as error:  # noqa: BLE001
        errors.append(f"{getattr(error, 'sqlite_errorname', '')}\n{traceback.format_exc()}")
    finally:
        if store is not shared:
            store.close()
    return private


def run_worker(path: str, worker: int, threads: int, iterations: int, barrier: object, results: object) -> None:
    """One process: `threads` threads on one shared store and some of their own; reports to `results`."""
    errors: list[str] = []
    written: dict[int, int] = {}
    # a row that cannot be decoded is dropped with a warning and read as a miss: that is a torn value too
    handler = _CollectWarnings(errors)
    logging.getLogger("wetterdienst.util.listing_cache").addHandler(handler)
    shared = ListingStore(Path(path))

    def target(thread: int) -> None:
        barrier.wait(timeout=120)  # type: ignore[attr-defined]
        written[thread] = run_thread(Path(path), worker, thread, iterations, shared, errors)

    pool = [threading.Thread(target=target, args=(thread,)) for thread in range(threads)]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    shared.close()
    results.put((worker, written, errors))  # type: ignore[attr-defined]


def stress(  # noqa: C901
    directory: Path, processes: int = 4, threads: int = 4, iterations: int = 400
) -> list[str]:
    """Run the workers on `directory` and return every problem found (an empty list is a pass)."""
    path = directory / STORE_FILENAME
    context = mp.get_context("spawn")
    barrier = context.Barrier(processes * threads)
    results = context.Queue()
    workers = [
        context.Process(target=run_worker, args=(str(path), worker, threads, iterations, barrier, results), daemon=True)
        for worker in range(processes)
    ]
    for process in workers:
        process.start()
    problems: list[str] = []
    written: dict[tuple[int, int], int] = {}
    for _ in workers:
        worker, counts, errors = results.get(timeout=300)
        problems.extend(errors)
        written.update({(worker, thread): count for thread, count in counts.items()})
    for process in workers:
        process.join(timeout=60)
        if process.exitcode != 0:
            problems.append(f"a worker exited with {process.exitcode}")

    store = ListingStore(path)
    try:
        for (worker, thread), count in written.items():
            for index in range(count):
                value = store.get(private_key(worker, thread, index))
                if value is None:
                    problems.append(f"entry {worker}/{thread}/{index} was lost")
                elif not is_whole(value):
                    problems.append(f"entry {worker}/{thread}/{index} is torn")
        for key in SHARED_KEYS:
            value = store.get(key)
            if value is not None and not is_whole(value):
                problems.append(f"torn value under {key}")
    finally:
        store.close()
    return problems


if __name__ == "__main__":
    found = stress(
        Path(sys.argv[1]),
        *(int(argument) for argument in sys.argv[2:5]),
    )
    print("\n".join(found) if found else "ok")  # noqa: T201
    sys.exit(1 if found else 0)
