"""Start several processes together on one empty cache directory, and count what goes wrong (GH-3467).

Used by `test_cache_first_start.py`, and runnable on its own to try a machine:

    python -m tests.util.cache_first_start_stress [ROUNDS] [PROCESSES]

A round is one empty directory and `PROCESSES` fresh interpreters (spawned, so each one's first
`NetworkFilesystemManager.register` is its first sweep) that wait at a barrier and then each download the
same urls through `download_files`' thread pool, from a local server. Nothing sleeps. What a round reports:

* `crashes`: the processes whose `download_files` raised (`FileExistsError` through `register` above all),
* `fallbacks`: the processes that found the directory gone from under them and went on in a temporary one, whose
  copies nobody else sees,
* `misses`: the files a call made after all the processes had finished did not find in the cache.

Several processes that all miss at the same moment legitimately fetch the same file once each, so the number of
requests the server saw is no measure: the call after is.
"""

from __future__ import annotations

import multiprocessing as mp
import sys
import tempfile
import threading
import traceback
from collections import Counter
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import _cache_dir_fallbacks, download_files

PATHS = [f"/first-start/{index}.txt" for index in range(12)]


class _Server(ThreadingHTTPServer):
    #: the default backlog is 5, which processes x threads connecting at once overflow (macOS resets the connection)
    request_queue_size = 128


class _Source(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.server.hits[self.path] += 1  # ty: ignore[unresolved-attribute]
        body = b"payload " + self.path.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Keep the output free of the access log."""


@dataclass
class Round:
    """What one round found."""

    crashes: list[str] = field(default_factory=list)
    fallbacks: int = 0
    misses: int = 0
    requests: int = 0


def run_worker(cache_dir: str, urls: list[str], barrier: object, results: object) -> None:
    """One process: wait for the others, then download every url; reports a traceback or nothing to `results`."""
    try:
        barrier.wait(timeout=120)  # type: ignore[attr-defined]
        files = download_files(urls, cache_dir=Path(cache_dir), ttl=CacheExpiry.ONE_HOUR)
        failed = [file.url for file in files if file.status != 200]
        results.put((f"status of {failed}" if failed else "", bool(_cache_dir_fallbacks)))  # type: ignore[attr-defined]
    except BaseException:  # noqa: BLE001
        results.put((traceback.format_exc(), bool(_cache_dir_fallbacks)))  # type: ignore[attr-defined]


def run_round(directory: Path, processes: int = 6) -> Round:
    """Start `processes` together on `directory`, which is empty, and return what went wrong."""
    server = _Server(("127.0.0.1", 0), _Source)
    server.hits = Counter()  # ty: ignore[unresolved-attribute]
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    try:
        urls = [f"http://127.0.0.1:{server.server_address[1]}{path}" for path in PATHS]
        context = mp.get_context("spawn")
        barrier = context.Barrier(processes)
        results = context.Queue()
        workers = [
            context.Process(target=run_worker, args=(str(directory), urls, barrier, results), daemon=True)
            for _ in range(processes)
        ]
        for worker in workers:
            worker.start()
        found = Round()
        for _ in workers:
            problem, fell_back = results.get(timeout=300)
            found.fallbacks += fell_back
            if problem:
                found.crashes.append(problem)
        for worker in workers:
            worker.join(timeout=60)
        before = sum(server.hits.values())  # ty: ignore[unresolved-attribute]
        # the call after: everything the processes fetched should be there, whoever fetched it
        again = download_files(urls, cache_dir=directory, ttl=CacheExpiry.ONE_HOUR)
        found.misses = sum(not file.from_cache for file in again)
        found.requests = before
        return found
    finally:
        server.shutdown()
        server.server_close()
        serving.join(timeout=5)


if __name__ == "__main__":
    rounds, processes = (int(argument) for argument in [*sys.argv[1:3], *["20", "6"][len(sys.argv) - 1 :]])
    with_a_crash = with_a_miss = with_a_fallback = 0
    for _ in range(rounds):
        with tempfile.TemporaryDirectory() as directory:
            found = run_round(Path(directory), processes)
        with_a_crash += bool(found.crashes)
        with_a_miss += bool(found.misses)
        with_a_fallback += bool(found.fallbacks)
        if found.crashes:
            print(found.crashes[0].strip().splitlines()[-1])  # noqa: T201
    print(f"{rounds} rounds: {with_a_crash} with a crash, {with_a_fallback} with a fallback, {with_a_miss} with a miss")  # noqa: T201
