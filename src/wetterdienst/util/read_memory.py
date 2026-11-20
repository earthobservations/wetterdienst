# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the process remembers of a page it read, and of a read that failed (GH-4073, GH-4074).

A station list is read more than once by a request (`history` twice, a filter and then a lookup), and the page that
enriches it (DWD's Stationslexikon, WMO's OSCAR register) is big, so parsing it each time, and with the cache off
downloading it, costs. `ReadMemory` keeps what `read` returned for `kept_for` seconds, and a failure of a kind that is
the page's (`failures`) for `failure_kept_for`, so that a page that is down is asked for once and not by every request,
which raises the same error, a new one each time, without asking. A rate limit (`ProviderRateLimitError`) is raised and
not kept: the wait it carries is the provider's of that answer.

One read of a key at a time: a caller that finds nothing in the memory takes the lock of its key, and one that waited
for it finds what the first read left (a page or a failure), so a host that drops connections is waited for by one
caller and not by every thread of the process, one after the other. Another key is another lock.
"""

from __future__ import annotations

import copy
import threading
import time
from typing import TYPE_CHECKING, Generic, TypeVar

from wetterdienst.exceptions import ProviderRateLimitError

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable

    from wetterdienst.settings import Settings

T = TypeVar("T")


def canonical(value: object) -> object:
    """Write a settings value so that equal ones are equal as keys: mappings by sorted key, sequences as tuples."""
    if isinstance(value, dict):
        return tuple(sorted(((str(key), canonical(item)) for key, item in value.items()), key=lambda pair: pair[0]))
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(canonical(item) for item in value)
    return repr(value)


def settings_key(settings: Settings) -> tuple:
    """Name what a copy of a page depends on: the cache it comes from and how it was asked for."""
    return (
        str(settings.cache_dir),
        settings.cache_disable,
        settings.use_certifi,
        canonical(settings.fsspec_client_kwargs or {}),
    )


def _fresh(error: Exception) -> Exception:
    """Copy an error without the frames it was raised through, so that what is remembered holds none of a request."""
    fresh = copy.copy(error).with_traceback(None)
    fresh.__cause__ = error.__cause__
    return fresh


class ReadMemory(Generic[T]):
    """The memory of one kind of page, by key: see the module docstring."""

    def __init__(
        self,
        *,
        kept_for: float,
        failure_kept_for: float,
        failures: tuple[type[Exception], ...],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Keep a page for `kept_for` seconds and a failure of one of `failures` for `failure_kept_for`.

        `clock` is called for each look at the time, so that a caller can hand over a function that reads a name which
        a test replaces.
        """
        self.kept_for = kept_for
        self.failure_kept_for = failure_kept_for
        self.failures = failures
        self._clock = clock
        #: what is remembered by key: when it is forgotten, and the page or the error of the read that failed
        self.entries: dict[Hashable, tuple[float, T | Exception]] = {}
        self._lock = threading.Lock()
        self._key_locks: dict[Hashable, threading.Lock] = {}

    def _remembered(self, key: Hashable) -> T | None:
        """Give the page kept for a key, raise the failure kept for it, or give None where there is neither."""
        with self._lock:
            kept = self.entries.get(key)
            if kept is None or self._clock() >= kept[0]:
                return None
        if isinstance(kept[1], Exception):
            raise _fresh(kept[1])
        return kept[1]

    def _remember(self, key: Hashable, kept_for: float, what: T | Exception) -> None:
        """Keep what was read for `kept_for` seconds, and drop what has run out, so that the memory does not grow."""
        now = self._clock()
        with self._lock:
            for old in [old for old, (until, _) in self.entries.items() if until <= now]:
                del self.entries[old]
            self.entries[key] = (now + kept_for, what)
            for old in [old for old, lock in self._key_locks.items() if old not in self.entries and not lock.locked()]:
                del self._key_locks[old]

    def get(self, key: Hashable, read: Callable[[], T]) -> T:
        """Give the page of a key from the memory, or `read` it, one read of the key at a time.

        Raises:
            ProviderRateLimitError: what `read` raised for a 429, which is not remembered: the next call asks again.
            Exception: one of `failures`, from `read` or, a new copy of it, from the memory.

        """
        kept = self._remembered(key)
        if kept is not None:
            return kept
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            # the caller that held the lock before this one has left a page or a failure
            kept = self._remembered(key)
            if kept is not None:
                return kept
            try:
                page = read()
            except ProviderRateLimitError:
                raise
            except self.failures as error:
                self._remember(key, self.failure_kept_for, _fresh(error))
                raise
            self._remember(key, self.kept_for, page)
            return page

    def forget(self) -> None:
        """Forget every page and failure (a test's, or a process that must read again)."""
        with self._lock:
            self.entries.clear()
