# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The work of a request ends between files too: fetch-ahead, `download_file` and `download_files` (GH-4429).

`tests/ui/test_work_stops_at_timeout.py` holds the walk over the stations to the timeout of a request. What is held
here is what a walk does with its files once the answer of its request is gone: the threads that fetch the next stations
begin no file, a download is not begun, the files of a download of many are not begun, and what was begun is whole in
the cache. A local server stands in for the upstream, as in `test_fetch_ahead.py`, whose fixtures these tests use.
"""

from __future__ import annotations

import contextvars
import threading
from typing import TYPE_CHECKING

import pytest

from tests.model import test_fetch_ahead as upstream_of_the_tests
from tests.model.test_fetch_ahead import _files, _reader, _Upstream, _wait_for_no_threads
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.cancellation import Cancellation, WorkAbandoned, cancellable
from wetterdienst.util.network import download_file, download_files

if TYPE_CHECKING:
    from pathlib import Path

    from wetterdienst.model.values import TimeseriesValues


# the fixtures of the tests that fetch ahead: a local upstream, no waiting between attempts, no connection slots held
upstream = upstream_of_the_tests.upstream
fetch_ahead_wanted = upstream_of_the_tests.fetch_ahead_wanted
_no_waiting_between_attempts = upstream_of_the_tests._no_waiting_between_attempts  # noqa: SLF001
_fresh_host_slots = upstream_of_the_tests._fresh_host_slots  # noqa: SLF001


def _arguments(tmp_path: Path) -> dict[str, object]:
    settings = Settings(cache_dir=tmp_path / "files")
    return {
        "cache_dir": settings.cache_dir,
        "ttl": CacheExpiry.FIVE_MINUTES,
        "client_kwargs": settings.fsspec_client_kwargs,
        "cache_disable": settings.cache_disable,
        "use_certifi": settings.use_certifi,
    }


def _reader_of(upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TimeseriesValues:
    """Read 8 stations of 3 files each, four stations ahead."""
    return _reader(monkeypatch, tmp_path, stations=8, urls_of=_files(upstream, 3), depth=4)


def test_the_threads_that_fetch_ahead_begin_no_file_once_the_answer_is_gone(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A thread at the first file of a station ahead does not go on to its second when the request's answer is gone.

    The walk is left where it is (it has not asked for the next station), so that it is not the walk's end that
    stops them: the threads have no context of the request and look at the cancellation they were made with.
    """
    first_ahead, second_ahead = upstream.hold("/1/0"), upstream.hold("/2/0")
    cancel = Cancellation()
    with cancellable(cancel):
        results = _reader_of(upstream, monkeypatch, tmp_path).query()
        next(results)
        assert upstream.arrival("/1/0").wait(20)
        assert upstream.arrival("/2/0").wait(20)
        # the threads are in the first file of two stations ahead, and the answer goes
        cancel.set("timeout")
        first_ahead.set()
        second_ahead.set()
        upstream.settle({1, 2, 3, 4})

        # each began its station and fetched no file of it after the first
        assert upstream.asked(1) == ["/1/0"]
        assert upstream.asked(2) == ["/2/0"]

        # and the walk ends at the next station, which closes the fetching
        with pytest.raises(WorkAbandoned):
            next(results)
    _wait_for_no_threads()
    # no station beyond those that were ahead was started
    assert upstream.stations_asked() <= {0, 1, 2, 3, 4}


def test_what_was_fetched_ahead_is_whole_in_the_cache_when_the_walk_ends(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every file that was begun is in the cache whole: it is read from there, without a request, afterwards."""
    cancel = Cancellation()
    reader = _reader_of(upstream, monkeypatch, tmp_path)
    with cancellable(cancel):
        results = reader.query()
        next(results)
        upstream.settle({0, 1, 2, 3, 4})
        cancel.set("timeout")
        with pytest.raises(WorkAbandoned):
            next(results)
    _wait_for_no_threads()
    asked = list(dict.fromkeys(upstream.requests))
    assert asked

    settings = reader.sr.settings
    for path in asked:
        file = download_file(
            url=f"{upstream.url}{path}",
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
        )
        assert file.from_cache, path
        assert file.content.read().decode() == path.removeprefix("/").replace("/", ":")
    assert list(dict.fromkeys(upstream.requests)) == asked


def test_a_download_is_not_begun_for_a_request_whose_answer_is_gone(upstream: _Upstream, tmp_path: Path) -> None:
    """`download_file` raises before it opens anything: the server is not asked."""
    cancel = Cancellation()
    cancel.set("timeout")

    with cancellable(cancel), pytest.raises(WorkAbandoned):
        download_file(url=f"{upstream.url}/7/0", **_arguments(tmp_path))

    assert upstream.requests == []
    # and for a request with no cancellation, as for Python and the command line, it is downloaded
    assert download_file(url=f"{upstream.url}/7/0", **_arguments(tmp_path)).content.read() == b"7:0"


def test_the_files_of_a_download_of_many_that_have_not_begun_are_not_begun(upstream: _Upstream, tmp_path: Path) -> None:
    """When the answer goes after a few files, the pool does not begin the rest of the hundred."""
    cancel = Cancellation()
    urls = [f"{upstream.url}/9/{n}" for n in range(100)]

    def delay(_path: str) -> float:
        if len(upstream.requests) >= 3:
            cancel.set("timeout")
        return 0.01

    upstream.delay = delay
    with cancellable(cancel), pytest.raises(WorkAbandoned):
        download_files(urls=urls, **_arguments(tmp_path))

    # the ones that were under way ended; not one of the rest was asked for (at most the pool of 32 and the three)
    assert 3 <= len(upstream.requests) <= 3 + 32


def test_a_download_in_hand_is_finished_whole_when_the_answer_goes(upstream: _Upstream, tmp_path: Path) -> None:
    """The answer goes while a file is on its way: it arrives, is cached whole and is read from there later."""
    held = upstream.hold("/5/0")
    cancel = Cancellation()
    outcome: dict[str, object] = {}

    def download() -> None:
        with cancellable(cancel):
            try:
                outcome["file"] = download_file(url=f"{upstream.url}/5/0", **_arguments(tmp_path))
            except BaseException as error:  # noqa: BLE001
                outcome["error"] = error

    thread = threading.Thread(target=contextvars.copy_context().run, args=(download,))
    thread.start()
    assert upstream.arrival("/5/0").wait(20)
    cancel.set("timeout")
    held.set()
    thread.join(20)

    assert "error" not in outcome
    assert outcome["file"].content.read() == b"5:0"
    again = download_file(url=f"{upstream.url}/5/0", **_arguments(tmp_path))
    assert again.from_cache
    assert again.content.read() == b"5:0"
    assert upstream.asked(5) == ["/5/0"]
