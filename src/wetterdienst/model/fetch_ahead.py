# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fetch the files of the next stations while one is parsed (GH-3454).

`TimeseriesValues.query` walks the stations one by one, and a provider whose files are one per station downloads the
files of a station only when it reaches it, so the network is idle while a station is parsed and the parse waits for
the network. A provider that names the files of a station beforehand (`TimeseriesValues._files_ahead`) has the files of
the next few stations fetched into the cache meanwhile, by a few threads: when the walk reaches such a station, the
provider's own download finds its files in the cache and the provider's code is not different from what it was.

Nothing else about a read changes. The bytes come through the same `download_file` (its retries, its ceilings, its
cache), the provider's own download follows as it always did and raises what it always raised at the station it
raises it at, and a fetch ahead that fails is not heard of: it is the station's own download that meets the failure
again. What fetch-ahead holds the reader to is `FetchAhead`'s: a bounded number of stations, a bounded number of
connections to one host, and nothing started that the consumer has not asked for.
"""

from __future__ import annotations

import logging
import queue
import threading
from concurrent.futures import Future, wait
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import FETCH_AHEAD_MAX
from wetterdienst.util.network import _without_url_secrets, download_file

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: the most connections to one host that the fetch-ahead of every read of the process holds at once: a read that finds
#: the host at the cap leaves the file to the download of its station, which is made at its turn as it always was
HOST_CONNECTIONS = FETCH_AHEAD_MAX
_host_slots: dict[str, threading.BoundedSemaphore] = {}
_host_slots_lock = threading.Lock()


@dataclass(frozen=True)
class FilesAhead:
    """The files a provider reads for one station, as `TimeseriesValues._files_ahead` names them."""

    urls: Sequence[str]
    """The URLs the provider downloads for the station, whatever order and however many times it asks for them."""
    ttl: CacheExpiry
    """The expiry the provider downloads them with: the cache they are fetched into is the one of this expiry."""


def _host_slot(url: str) -> threading.BoundedSemaphore:
    """Give the slots of the connections that fetch-ahead may hold to the host of a URL."""
    host = urlsplit(url).netloc.lower()
    with _host_slots_lock:
        slot = _host_slots.get(host)
        if slot is None:
            slot = _host_slots[host] = threading.BoundedSemaphore(HOST_CONNECTIONS)
        return slot


class _Workers:
    """A few daemon threads that run what is submitted, and are let go of by `close`.

    Not a `ThreadPoolExecutor`: its threads are joined when the interpreter exits, so a walk that ended by an error or
    Ctrl-C would hold the exit until the downloads that were under way were over. A daemon thread that is cut off at
    exit leaves at most a temporary file, which the sweep of the cache collects, or a copy without its date (the blob
    is renamed into place whole or not at all, but its row is saved before the date is written beside it).
    """

    def __init__(self, size: int, prefix: str) -> None:
        self._size = size
        self._prefix = prefix
        self._queue: queue.SimpleQueue[tuple[Future[None], Callable[..., None], tuple[Any, ...]] | None] = (
            queue.SimpleQueue()
        )
        self._threads: list[threading.Thread] = []

    def submit(self, call: Callable[..., None], *args: Any) -> Future[None]:  # noqa: ANN401
        """Run ``call`` on one of the threads, which are started as they are needed up to the size."""
        future: Future[None] = Future()
        self._queue.put((future, call, args))
        if len(self._threads) < self._size:
            thread = threading.Thread(target=self._work, name=f"{self._prefix}-{len(self._threads)}", daemon=True)
            self._threads.append(thread)
            thread.start()
        return future

    def _work(self) -> None:
        while (item := self._queue.get()) is not None:
            future, call, args = item
            if future.set_running_or_notify_cancel():
                try:
                    call(*args)
                except BaseException as error:  # noqa: BLE001 -- handed to the future, which nobody asks
                    future.set_exception(error)
                else:
                    future.set_result(None)
            # an idle thread holds on to nothing of the read it last worked for
            del item, future, call, args

    def close(self) -> None:
        """Cancel what has not begun and tell the threads to end once what they are at is done."""
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is not None:
                item[0].cancel()
        for _ in self._threads:
            self._queue.put(None)


@dataclass(eq=False)
class _Fetch:
    """The files of one station, fetched by one thread, one after the other."""

    urls: list[str]
    ttl: CacheExpiry
    #: set when the walk comes to the station: what is under way ends, and the files left are the station's own
    #: download's, which fetches a station's files side by side where this fetches them one after the other
    stop: threading.Event
    future: Future[None] | None = None


class FetchAhead:
    """Fetch the files of the stations after the one in hand, a bounded number of them, while it is read.

    Made by `TimeseriesValues.query` for a provider that implements `_files_ahead`, and driven by `advance` once for
    each station it reaches, in order. Each station beyond the one in hand, up to `depth` of them, has its files
    fetched by a thread of a pool of `depth`, each file through `download_file` into the cache the provider's own
    download reads from. So at most `depth` stations are ahead and at most `depth` connections are open for it (and
    `HOST_CONNECTIONS` to a host for all the reads of the process), and a station is started only when the walk has
    come within `depth` of it: a consumer that stops has started nothing past that.

    What a fetch ahead does not do: it raises nothing. A hook that fails, a download that fails and a thread that
    breaks are logged at debug level and cost the station its head start, nothing more; the provider's own download
    at the station's turn goes through the same steps and fails as it would have. After a failure other than a missing
    file (a 404 is routine, a timeout or a refused connection is an outage) nothing more is fetched ahead, so that a
    host that is failing is not asked by `depth` threads on top of the walk.

    Not thread-safe: the walk drives it from one thread, the one that consumes the generator.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        depth: int,
        stations: Callable[[int], tuple[str, list[DatasetModel]] | None],
        count: int,
        files_of: Callable[[str, list[DatasetModel]], FilesAhead | None],
    ) -> None:
        """Prepare to fetch ahead for ``count`` positions of a walk.

        Args:
            settings: the settings the provider downloads with: its cache, client and certificates.
            depth: how many stations after the one in hand are fetched for.
            stations: the station of a position of the walk and the datasets to collect for it, None for a position
                the walk skips.
            count: how many positions the walk has.
            files_of: the provider's `_files_ahead`.

        """
        self._settings = settings
        self._depth = depth
        self._stations = stations
        self._count = count
        self._files_of = files_of
        self._workers: _Workers | None = None
        self._fetches: dict[int, _Fetch] = {}
        #: the positions whose files have been asked of the provider, whether or not they are fetched ahead
        self._planned: set[int] = set()
        #: every URL a station of the walk has named so far: one that was named is fetched by the first to name it
        #: (or is the business of the station in hand), so that two stations that read one file do not both fetch it
        self._seen: set[str] = set()
        self._cache: dict[int, tuple[str, list[DatasetModel]] | None] = {}
        self._failed = threading.Event()

    def advance(self, position: int, slots: int | None = None) -> None:
        """Start the fetches of the stations after ``position`` and wait for the one of ``position``, if it has one.

        Called before the provider collects the station at ``position``: when it returns, the files of this station
        that were fetched ahead are in the cache, and the stations after it, up to the depth, are being fetched.

        Args:
            position: the position of the walk the consumer is at.
            slots: how many stations the walk still collects at the most, the one in hand included, where it is
                counted (a ranked read stops after its rank): no more are fetched ahead than there are slots left.

        """
        for passed in [key for key in self._cache if key < position]:
            del self._cache[passed]
        try:
            if not self._failed.is_set():
                self._plan_ahead(position, slots)
        except Exception as error:  # noqa: BLE001 -- the stations of the walk meet it themselves, each at its turn
            log.debug("Fetch-ahead: planning failed at position %d: %r", position, error)
            self._failed.set()
        fetch = self._fetches.pop(position, None)
        if fetch is not None and fetch.future is not None:
            # the station's own download fetches its files side by side, so what this has not fetched yet is left to
            # it: the thread ends the file it is at, and one that has not begun at all is not begun
            fetch.stop.set()
            if not fetch.future.cancel():
                wait([fetch.future])

    def _plan_ahead(self, position: int, slots: int | None) -> None:
        """Ask the provider for the files of the station at ``position`` and of those within the window after it."""
        if position not in self._planned:
            # the station the walk begins at is the provider's to download as it always did, but what it reads is
            # known so that a station that reads the same file is not fetched for it a second time
            self._plan(position, fetch=False)
        window = self._depth if slots is None else min(self._depth, max(slots - 1, 0))
        ahead = 0
        following = position + 1
        while ahead < window and following < self._count and not self._failed.is_set():
            if self._station(following) is not None:
                ahead += 1
                if following not in self._planned:
                    self._plan(following, fetch=True)
            following += 1

    def close(self) -> None:
        """Stop: nothing that has not begun is begun, and what has is not followed by another file.

        A download that is under way is not cut off: the file it is of reaches the cache whole, as a download of the
        provider's would, or leaves nothing (`_LockedWholeFileCacheFileSystem._open` writes to a file of its own and
        renames it). Does not wait for it, so the consumer that stops is not kept by it; its thread ends with it.
        """
        for fetch in self._fetches.values():
            fetch.stop.set()
        if self._workers is not None:
            self._workers.close()
        self._fetches.clear()

    def _station(self, position: int) -> tuple[str, list[DatasetModel]] | None:
        if position not in self._cache:
            self._cache[position] = self._stations(position)
        return self._cache[position]

    def _plan(self, position: int, *, fetch: bool) -> None:
        """Ask the provider which files the station at ``position`` reads, and fetch those that are new."""
        self._planned.add(position)
        station = self._station(position)
        if station is None:
            return
        station_id, datasets = station
        # a hook that raises is guarded by `advance`: it stops the fetching, the station's own collection meets it
        files = self._files_of(station_id, datasets)
        if files is None or files.ttl is CacheExpiry.NO_CACHE:
            return
        urls = [url for url in dict.fromkeys(files.urls) if url not in self._seen]
        self._seen.update(files.urls)
        if not fetch or not urls:
            return
        if self._workers is None:
            self._workers = _Workers(self._depth, "wetterdienst-fetch-ahead")
        job = _Fetch(urls=urls, ttl=files.ttl, stop=threading.Event())
        self._fetches[position] = job
        job.future = self._workers.submit(self._fetch, job)

    def _fetch(self, job: _Fetch) -> None:
        """Download the files of one station into the cache, and say nothing of what goes wrong."""
        try:
            for url in job.urls:
                if job.stop.is_set() or self._failed.is_set():
                    return
                slot = _host_slot(url)
                if not slot.acquire(blocking=False):
                    log.debug("Fetch-ahead: %d connections are open to the host already", HOST_CONNECTIONS)
                    continue
                try:
                    file = download_file(
                        url=url,
                        cache_dir=self._settings.cache_dir,
                        ttl=job.ttl,
                        client_kwargs=self._settings.fsspec_client_kwargs,
                        cache_disable=self._settings.cache_disable,
                        use_certifi=self._settings.use_certifi,
                    )
                finally:
                    slot.release()
                if isinstance(file.content, Exception) and file.status != HTTPStatus.NOT_FOUND:
                    log.info(f"Fetch-ahead stops: {_without_url_secrets(url)} failed with {file.status}")
                    self._failed.set()
                    return
        except Exception as error:  # noqa: BLE001 -- the station's own download meets it again, at its turn
            log.debug("Fetch-ahead: a fetch broke: %r", error)
            self._failed.set()
