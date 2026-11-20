# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the process remembers of a page it read, and of a read that failed: `ReadMemory` (GH-4074)."""

from __future__ import annotations

import threading

import pytest

from wetterdienst.exceptions import DownloadError, ProviderRateLimitError
from wetterdienst.util.read_memory import ReadMemory, canonical


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> _Clock:
    """Give the clock of a test."""
    return _Clock()


@pytest.fixture
def memory(clock: _Clock) -> ReadMemory[str]:
    """Give a memory that keeps a page for an hour and a failure for a minute."""
    return ReadMemory(kept_for=3600.0, failure_kept_for=60.0, failures=(DownloadError,), clock=clock)


def test_a_page_is_read_once_until_its_time_is_up(memory: ReadMemory[str], clock: _Clock) -> None:
    """A second ask is answered from the memory; after `kept_for` the page is read again."""
    reads: list[int] = []

    def read() -> str:
        reads.append(1)
        return f"page {len(reads)}"

    assert [memory.get("k", read) for _ in range(3)] == ["page 1"] * 3
    clock.now += 3599
    assert memory.get("k", read) == "page 1"
    clock.now += 2
    assert memory.get("k", read) == "page 2"
    assert len(reads) == 2


def test_a_failure_of_the_page_is_raised_as_a_new_error_and_kept_for_its_own_time(
    memory: ReadMemory[str], clock: _Clock
) -> None:
    """Each ask of a page that is down gets its own error without a read, for a minute."""
    reads: list[int] = []

    def read() -> str:
        reads.append(1)
        if len(reads) == 1:
            url = "https://example.invalid/page"
            raise DownloadError(url, "503")
        return "page"

    raised = []
    for _ in range(3):
        with pytest.raises(DownloadError) as caught:
            memory.get("k", read)
        raised.append(caught.value)
    assert len(reads) == 1
    assert len({id(error) for error in raised}) == 3
    (_until, kept) = memory.entries["k"]
    assert isinstance(kept, Exception)
    assert kept.__traceback__ is None
    clock.now += 61
    assert memory.get("k", read) == "page"
    assert len(reads) == 2


def test_a_rate_limit_is_raised_and_not_kept(memory: ReadMemory[str]) -> None:
    """The wait a 429 carries is of its answer: the next ask reads again."""
    reads: list[int] = []

    def read() -> str:
        reads.append(1)
        if len(reads) < 3:
            url = "https://example.invalid/page"
            raise ProviderRateLimitError(url, "limited", 7)
        return "page"

    for expected in (1, 2):
        with pytest.raises(ProviderRateLimitError):
            memory.get("k", read)
        assert len(reads) == expected
    assert memory.get("k", read) == "page"


def test_an_error_that_is_not_the_pages_is_raised_and_not_kept(memory: ReadMemory[str]) -> None:
    """A bug is not remembered for a minute as if the page were down."""

    def read() -> str:
        msg = "a bug"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        memory.get("k", read)
    assert memory.entries == {}


def test_the_threads_that_ask_together_share_one_read_and_another_key_is_another_read(
    memory: ReadMemory[str],
) -> None:
    """A caller that finds nothing waits for the read of its key, and finds what it left; a key of its own reads."""
    inside, release = threading.Event(), threading.Event()
    reads: list[str] = []

    def read_of(key: str) -> str:
        reads.append(key)
        if key == "slow":
            inside.set()
            assert release.wait(10)
        return f"page of {key}"

    results: list[str] = []
    threads = [
        threading.Thread(target=lambda: results.append(memory.get("slow", lambda: read_of("slow")))) for _ in range(4)
    ]
    for thread in threads:
        thread.start()
    assert inside.wait(10)
    # while the slow key is read, another key is not held up by it
    assert memory.get("quick", lambda: read_of("quick")) == "page of quick"
    release.set()
    for thread in threads:
        thread.join(10)
    assert sorted(reads) == ["quick", "slow"]
    assert results == ["page of slow"] * 4


def test_what_has_run_out_goes_when_another_is_stored_and_forget_clears_all(
    memory: ReadMemory[str], clock: _Clock
) -> None:
    """The memory does not grow with the keys asked for, and its locks go with them."""
    for key in "abcde":
        memory.get(key, lambda key=key: key)
    assert len(memory.entries) == 5
    clock.now += 3601
    memory.get("later", lambda: "later")
    assert list(memory.entries) == ["later"]
    assert set(memory._key_locks) <= {"later"}  # noqa: SLF001
    memory.forget()
    assert memory.entries == {}


def test_the_clock_is_asked_at_each_use_so_that_a_replaced_one_is_the_one_used(clock: _Clock) -> None:
    """A caller hands over a function that looks its clock up by name, which a test replaces."""
    current = [clock]
    memory: ReadMemory[str] = ReadMemory(
        kept_for=10.0,
        failure_kept_for=1.0,
        failures=(DownloadError,),
        clock=lambda: current[0](),  # noqa: PLW0108
    )
    assert memory.get("k", lambda: "first") == "first"
    other = _Clock()
    other.now = clock.now + 11
    current[0] = other
    assert memory.get("k", lambda: "second") == "second"


def test_settings_that_are_equal_are_equal_as_keys() -> None:
    """Mappings by sorted key and sequences as tuples, so that equal settings are one key."""
    one = {"a": {"y": 1, "x": [2, 3]}, "b": 2}
    other = {"b": 2, "a": {"x": [2, 3], "y": 1}}
    assert canonical(one) == canonical(other)
    assert canonical(one) != canonical({**one, "b": 3})
