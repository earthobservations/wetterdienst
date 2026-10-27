"""The files of the next stations are fetched while one is parsed (GH-3454), and the answer is the one it was without.

A local server stands in for the upstream: it can delay each file, fail one, and says how many connections it had open
at once, so that what the fetch-ahead holds itself to is read off the server and not off the code.
"""

from __future__ import annotations

import datetime as dt
import gc
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import polars as pl
import pytest
import stamina
from polars.testing import assert_frame_equal

from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model import fetch_ahead
from wetterdienst.model.fetch_ahead import FetchAhead, FilesAhead
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.settings import Settings
from wetterdienst.util.network import download_file, download_files

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from pathlib import Path

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.model.result import ValuesResult

PARAMETERS = [("daily", "climate_summary", "temperature_air_mean_2m")]
THREADS = "wetterdienst-fetch-ahead"
#: where a connection is refused: nothing listens on port 1 of a test host
REFUSED = "http://127.0.0.1:1"


class _Handler(BaseHTTPRequestHandler):
    """Answer `/<station>/<n>` with the body `<station>:<n>`, after the delay and with the status the test set."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Say nothing: a test that fails prints what it needs."""

    def do_GET(self) -> None:
        """Count the connection, hold it for the delay, answer."""
        server = cast("_Upstream", self.server)
        with server.lock:
            server.requests.append(self.path)
            server.active += 1
            server.max_active = max(server.max_active, server.active)
        try:
            if server.gate is not None and not self.path.startswith("/0/"):
                server.gate.wait(timeout=20)
            time.sleep(server.delay(self.path))
            status = server.statuses.get(self.path, 200)
            body = self.path.removeprefix("/").replace("/", ":").encode() if status == 200 else b"error"
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        finally:
            with server.lock:
                server.active -= 1


class _Upstream(ThreadingHTTPServer):
    """A server that records what it was asked and how much at once."""

    #: connections that wait to be accepted: the default of 5 resets some of the dozen a download of many files opens
    request_queue_size = 128

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.delay: Callable[[str], float] = lambda _path: 0.0
        self.statuses: dict[str, int] = {}
        self.requests: list[str] = []
        self.active = 0
        self.max_active = 0
        #: while set and not yet released, the files of the stations after the first are held back
        self.gate: threading.Event | None = None
        self.lock = threading.Lock()

    @property
    def url(self) -> str:
        """The address."""
        return f"http://127.0.0.1:{self.server_port}"

    def asked(self, station: int) -> list[str]:
        """Give the paths asked of one station, in the order they came."""
        with self.lock:
            return [path for path in self.requests if path.startswith(f"/{station}/")]

    def stations_asked(self) -> set[int]:
        """Give the stations a request has come for."""
        with self.lock:
            return {int(path.split("/")[1]) for path in self.requests}

    def wait_for(self, count: int) -> None:
        """Wait until ``count`` files of stations after the first have been asked for."""
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            with self.lock:
                if len([path for path in self.requests if not path.startswith("/0/")]) >= count:
                    return
            time.sleep(0.01)
        msg = f"{count} files were not asked for"
        raise AssertionError(msg)

    def settle(self, quiet: float = 0.08) -> None:
        """Wait until nothing is asked any more and nothing is being answered."""
        last = -1
        stable_since = time.monotonic()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            with self.lock:
                seen, active = len(self.requests), self.active
            if seen != last or active:
                last, stable_since = seen, time.monotonic()
            elif time.monotonic() - stable_since >= quiet:
                return
            time.sleep(0.01)
        msg = "the server did not settle"
        raise AssertionError(msg)


@pytest.fixture
def upstream() -> Iterator[_Upstream]:
    """Run an `_Upstream` on a port of its own."""
    server = _Upstream()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def fetch_ahead_wanted() -> None:
    """Say to `tests/conftest.py` that these tests are of the fetch-ahead, which it keeps out of the others."""


@pytest.fixture(autouse=True)
def _no_waiting_between_attempts() -> Iterator[None]:
    """Retry a failed download at once, as the other network tests do."""
    with stamina.set_testing(True, attempts=2):
        yield


@pytest.fixture(autouse=True)
def _fresh_host_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give each test the connection slots of a process that has fetched nothing ahead."""
    monkeypatch.setattr(fetch_ahead, "_host_slots", {})


def _stations_frame(station_ids: Sequence[str], late: Sequence[str] = ()) -> pl.DataFrame:
    utc = ZoneInfo("UTC")
    return pl.DataFrame(
        {
            "resolution": ["daily"] * len(station_ids),
            "dataset": ["climate_summary"] * len(station_ids),
            "station_id": list(station_ids),
            "start_timestamp": [
                dt.datetime(2025, 1, 1, tzinfo=utc) if station in late else dt.datetime(1900, 1, 1, tzinfo=utc)
                for station in station_ids
            ],
            "end_timestamp": [dt.datetime(2030, 1, 1, tzinfo=utc)] * len(station_ids),
            "latitude": [50.0 + index / 10 for index in range(len(station_ids))],
            "longitude": [8.0] * len(station_ids),
            "elevation": [100.0] * len(station_ids),
            "name": list(station_ids),
            "region": ["x"] * len(station_ids),
        },
    )


def _values_class(
    urls_of: Callable[[str], list[str]],
    *,
    hook: bool = True,
    named: Callable[[str], list[str]] | None = None,
    parallel: bool = False,
) -> type[DwdObservationValues]:
    """Make a provider whose files are the URLs `urls_of` gives for a station, as DWD's are, and `named` names.

    With ``parallel`` it downloads the files of a station side by side, through `download_files`, as DWD's
    does; without, one after the other.
    """

    class Values(DwdObservationValues):
        collected: list[tuple[str, float]]

        def _files_ahead(self, station_id: str, datasets: Sequence[DatasetModel]) -> FilesAhead | None:  # noqa: ARG002
            return FilesAhead(urls=(named or urls_of)(station_id), ttl=CacheExpiry.FIVE_MINUTES)

        def _collect_station_parameter_or_dataset(
            self,
            station_id: str,
            parameter_or_dataset: object,  # noqa: ARG002
        ) -> pl.DataFrame:
            settings = self.sr.settings
            rows = []
            urls = urls_of(station_id)
            arguments = {
                "cache_dir": settings.cache_dir,
                "ttl": CacheExpiry.FIVE_MINUTES,
                "client_kwargs": settings.fsspec_client_kwargs,
                "cache_disable": settings.cache_disable,
                "use_certifi": settings.use_certifi,
            }
            files = (
                download_files(urls=urls, **arguments)
                if parallel
                else (download_file(url=url, **arguments) for url in urls)
            )
            for file in files:
                if file.status != 404:
                    file.raise_if_exception()
                if isinstance(file.content, Exception):
                    continue
                station, number = file.content.read().decode().split(":")
                rows.append(
                    (dt.datetime(2000, 1, 1 + int(number), tzinfo=ZoneInfo("UTC")), int(station) * 10 + int(number))
                )
            return pl.DataFrame(
                {
                    "timestamp": [row[0] for row in rows],
                    "parameter": ["tmk"] * len(rows),
                    "value": [float(row[1]) for row in rows],
                },
                schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
            )

    if not hook:
        Values._files_ahead = TimeseriesValues._files_ahead  # noqa: SLF001
    return Values


def _reader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    stations: int,
    urls_of: Callable[[str], list[str]],
    depth: int,
    cache: str = "cache",
    hook: bool = True,
    named: Callable[[str], list[str]] | None = None,
    parallel: bool = False,
    late: Sequence[int] = (),
) -> TimeseriesValues:
    """Build the values of ``stations`` stations numbered from 0, read from the cache directory ``cache``."""
    ids = [f"{index:05d}" for index in range(stations)]
    stations_frame = _stations_frame(ids, [ids[index] for index in late])
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda self: stations_frame.lazy())  # noqa: ARG005
    monkeypatch.setattr(
        DwdObservationRequest, "_values", _values_class(urls_of, hook=hook, named=named, parallel=parallel)
    )
    settings = Settings(cache_dir=tmp_path / cache, fetch_ahead=depth)
    # the stations that begin in 2025 are passed over by a window that ends before
    window = {
        "start": dt.datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")),
        "end": dt.datetime(2010, 1, 1, tzinfo=ZoneInfo("UTC")),
    }
    request = DwdObservationRequest(parameters=PARAMETERS, settings=settings, **(window if late else {}))
    return request.filter_by_station_id(ids).values()


def _files(upstream: _Upstream, count: int) -> Callable[[str], list[str]]:
    """Give the files of a station: ``count`` of them under its number."""
    return lambda station_id: [f"{upstream.url}/{int(station_id)}/{n}" for n in range(count)]


def _fetch_threads() -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread.name.startswith(THREADS)]


def _walk_time(
    upstream: _Upstream,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    depth: int,
    attempts: int,
    stations: int,
    files: int,
    parallel: bool = False,
) -> tuple[float, int]:
    """Read ``stations`` stations of ``files`` files cold: the fastest of ``attempts`` and the overlap of connections.

    The overlap is the most connections the server had open at once. A busy machine only slows a walk, so the
    fastest of several is the one it got least wrong.
    """
    best = float("inf")
    upstream.max_active = 0
    for attempt in range(attempts):
        reader = _reader(
            monkeypatch,
            tmp_path,
            stations=stations,
            urls_of=_files(upstream, files),
            depth=depth,
            cache=f"d{depth}-{attempt}",
            parallel=parallel,
        )
        began = time.perf_counter()
        assert len(list(reader.query())) == stations
        best = min(best, time.perf_counter() - began)
    return best, upstream.max_active


def _wait_for_no_threads() -> None:
    deadline = time.monotonic() + 15
    while _fetch_threads() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert _fetch_threads() == []


def _station_ids(results: Sequence[ValuesResult]) -> list[str]:
    return [result.df.get_column("station_id")[0] for result in results]


# 1. the answer is the one the walk gave without it, in the same order


@pytest.mark.parametrize("seed", range(6))
def test_the_answer_is_the_one_a_walk_without_it_gives_whatever_order_the_files_arrive_in(
    seed: int, upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Whatever the number of stations, files, delays and missing files, depth and order of the answer are the same.

    The delays are random per file, so the files of later stations arrive before those of earlier ones; a
    fetch-ahead that handed results over in the order of arrival, or that dropped a file that came early, would be
    seen in the frame. A file that is not there (404) is part of the case.
    """
    rng = random.Random(seed)  # noqa: S311
    stations = rng.randint(2, 9)
    count = rng.randint(1, 3)
    delays = {f"/{s}/{n}": rng.uniform(0.0, 0.06) for s in range(stations) for n in range(count)}
    upstream.delay = lambda path: delays.get(path, 0.0)
    upstream.statuses = {f"/{s}/{n}": 404 for s in range(stations) for n in range(count) if rng.random() < 0.15}
    urls_of = _files(upstream, count)

    sequential = _reader(monkeypatch, tmp_path, stations=stations, urls_of=urls_of, depth=0, cache="sequential")
    expected = list(sequential.query())
    upstream.requests.clear()
    ahead = _reader(monkeypatch, tmp_path, stations=stations, urls_of=urls_of, depth=rng.randint(1, 8), cache="ahead")
    results = list(ahead.query())

    assert _station_ids(results) == _station_ids(expected)
    assert len(results) == len(expected)
    for got, want in zip(results, expected, strict=True):
        assert_frame_equal(got.df, want.df)
    # and the walk fetched every file once: what was fetched ahead was found in the cache
    asked = [path for path in upstream.requests if path not in upstream.statuses]
    assert sorted(asked) == sorted(set(asked))


def test_the_fetch_ahead_ran(upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The equality above is not that of two walks that both fetch one station at a time."""
    upstream.delay = lambda _path: 0.05
    reader = _reader(monkeypatch, tmp_path, stations=6, urls_of=_files(upstream, 1), depth=4)

    results = reader.query()
    next(results)
    upstream.settle()

    assert upstream.stations_asked() == {0, 1, 2, 3, 4}
    results.close()


# 2. and 7. the stations fetched ahead are bounded, and nothing is started before it is asked for


def test_no_more_than_depth_stations_are_ahead_of_the_one_in_hand(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The stations asked for are the one in hand and `depth` after it, and nothing at all before the walk begins."""
    stations, depth = 10, 3
    reader = _reader(monkeypatch, tmp_path, stations=stations, urls_of=_files(upstream, 2), depth=depth)

    results = reader.query()
    upstream.settle()
    assert upstream.requests == [], "a generator that has not been asked for a station has started a download"

    for index in range(stations):
        next(results)
        upstream.settle()
        assert upstream.stations_asked() == set(range(min(index + depth, stations - 1) + 1))
    with pytest.raises(StopIteration):
        next(results)


def test_a_station_that_the_walk_passes_over_takes_no_place_in_the_window(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Stations that begin after the window are not read, so the files of the next two that are read are fetched."""
    reader = _reader(monkeypatch, tmp_path, stations=8, urls_of=_files(upstream, 1), depth=2, late=[1, 2])

    results = reader.query()
    next(results)
    upstream.settle()

    assert upstream.stations_asked() == {0, 3, 4}
    results.close()


def test_a_ranked_walk_fetches_no_station_beyond_its_rank(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A read of the nearest two stations does not fetch the files of the stations after them."""
    reader = _reader(monkeypatch, tmp_path, stations=8, urls_of=_files(upstream, 1), depth=4)
    ranked = reader.sr.request.filter_by_rank(latlon=(50.0, 8.0), rank=2).values()

    assert len(list(ranked.query())) == 2
    upstream.settle()

    assert upstream.stations_asked() == {0, 1}


# 3. a failure is met at its station, as it was


def _failure_of(error: BaseException, upstream: _Upstream) -> tuple[type[BaseException], str]:
    return type(error), str(error).replace(upstream.url, "<upstream>")


@pytest.mark.parametrize("failing", ["outage", "refused"])
def test_a_failure_is_met_at_its_station_and_after_the_stations_before_it(
    failing: str, upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The stations before the failing one are answered, the failing one raises what it raised, none after it is read.

    The failing station is inside the window while the walk is at station 0, so its file was asked for ahead and
    failed there; nothing was heard of it until the walk came to it.
    """
    broken = 3
    upstream.statuses = {f"/{broken}/0": 503}
    urls = _files(upstream, 1)

    def urls_of(station_id: str) -> list[str]:
        if failing == "refused" and int(station_id) == broken:
            return [f"{REFUSED}/{broken}/0"]
        return urls(station_id)

    outcomes = []
    for depth in (0, 4):
        reader = _reader(monkeypatch, tmp_path, stations=8, urls_of=urls_of, depth=depth, cache=f"depth{depth}")
        results = reader.query()
        answered = []
        error = None
        try:
            answered.extend(_station_ids([next(results)]) for _ in range(8))
        except (DownloadError, NoInternetError) as caught:
            error = caught
        outcomes.append((answered, _failure_of(error, upstream) if error else None))

    assert outcomes[0] == outcomes[1]
    answered, failure = outcomes[1]
    assert answered == [["00000"], ["00001"], ["00002"]]
    assert failure is not None
    assert failure[0] is (DownloadError if failing == "outage" else NoInternetError)


def test_a_failure_after_the_last_station_read_is_not_raised(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A station that fails inside the window is not heard of by a consumer that stops before it."""
    upstream.statuses = {"/4/0": 503}
    reader = _reader(monkeypatch, tmp_path, stations=6, urls_of=_files(upstream, 1), depth=4)

    results = reader.query()
    first = [next(results) for _ in range(2)]
    upstream.settle()

    assert _station_ids(first) == ["00000", "00001"]
    assert 4 in upstream.stations_asked()
    results.close()


def test_nothing_more_is_fetched_ahead_after_a_failure(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """After an outage (not a 404) the host is not asked for the next stations: the walk goes on one at a time."""
    upstream.statuses = {"/1/0": 503}
    reader = _reader(monkeypatch, tmp_path, stations=6, urls_of=_files(upstream, 1), depth=1)

    results = reader.query()
    next(results)
    with pytest.raises(DownloadError):
        next(results)

    assert upstream.stations_asked() == {0, 1}


def test_a_missing_file_is_no_reason_to_stop_fetching_ahead(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A 404 is routine, for a station that does not measure what is asked for, and the next stations are fetched."""
    upstream.statuses = {"/1/0": 404}
    reader = _reader(monkeypatch, tmp_path, stations=6, urls_of=_files(upstream, 1), depth=1)

    results = reader.query()
    next(results)
    upstream.settle()
    assert upstream.stations_asked() == {0, 1}
    # station 1 has no data and is passed over, so the walk is at station 2 and has fetched the one after it
    assert _station_ids([next(results)]) == ["00002"]
    upstream.settle()

    assert upstream.stations_asked() == {0, 1, 2, 3}
    results.close()


def test_a_file_that_several_stations_read_is_fetched_once(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file of the whole network, as the monthly files of IMGW are, is not fetched by a thread for each station."""
    upstream.delay = lambda _path: 0.05
    shared = f"{upstream.url}/99/0"

    def urls_of(station_id: str) -> list[str]:
        return [shared, f"{upstream.url}/{int(station_id)}/0"]

    reader = _reader(monkeypatch, tmp_path, stations=8, urls_of=urls_of, depth=4)

    assert len(list(reader.query())) == 8

    assert sorted(upstream.requests) == sorted(["/99/0", *(f"/{s}/0" for s in range(8))])


# 4. a consumer that stops


def test_a_closed_walk_starts_nothing_more_and_leaves_no_thread_and_no_part_of_a_file(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """What is under way ends with its file, what was waiting is not begun, the cache holds whole files only."""
    # the four stations ahead are in flight, at their first file, when the walk is closed
    upstream.gate = threading.Event()
    reader = _reader(monkeypatch, tmp_path, stations=12, urls_of=_files(upstream, 4), depth=4)

    results = reader.query()
    next(results)
    upstream.wait_for(4)
    results.close()
    upstream.gate.set()
    _wait_for_no_threads()
    upstream.settle()

    # each thread finished the file it was at and went no further, where it would have gone on to the four it has
    assert sorted(path for path in upstream.requests if not path.startswith("/0/")) == [
        "/1/0",
        "/2/0",
        "/3/0",
        "/4/0",
    ]
    cached = [path for path in (tmp_path / "cache").rglob("*") if path.is_file()]
    assert [path for path in cached if path.suffix == ".tmp"] == []
    blobs = [path for path in cached if path.name not in {"cache", ".last-used"} and path.suffix != ".lm"]
    # the four files of the station in hand, the first file of each of the four after it, each whole
    assert sorted(blob.read_bytes() for blob in blobs) == sorted(
        [f"0:{n}".encode() for n in range(4)] + [f"{s}:0".encode() for s in range(1, 5)]
    )


def test_a_walk_that_is_dropped_starts_nothing_more(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A generator that is let go of (a streamed answer whose client has gone) stops its fetches like a closed one."""
    upstream.gate = threading.Event()
    reader = _reader(monkeypatch, tmp_path, stations=12, urls_of=_files(upstream, 3), depth=4)

    results = reader.query()
    next(results)
    upstream.wait_for(4)
    del results
    gc.collect()
    upstream.gate.set()
    _wait_for_no_threads()
    upstream.settle()

    assert sorted(path for path in upstream.requests if not path.startswith("/0/")) == [
        "/1/0",
        "/2/0",
        "/3/0",
        "/4/0",
    ]


def test_a_walk_that_ran_to_the_end_leaves_no_thread(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every thread of the fetch-ahead is gone when the last station has been read."""
    reader = _reader(monkeypatch, tmp_path, stations=6, urls_of=_files(upstream, 1), depth=4)

    list(reader.query())

    _wait_for_no_threads()


# 5. the cache the files are fetched into


def test_the_files_fetched_by_other_threads_into_a_new_cache_are_found_by_the_walk(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Threads that begin on a cache directory that is not there write its metadata beside each other (GH-3452).

    The thread of the walk made its view of the metadata before they wrote, and finds the files they fetched all the
    same: each file is asked of the server once, and the answer is the one of a walk with one thread.
    """
    count = 3
    urls_of = _files(upstream, count)
    upstream.delay = lambda _path: 0.02
    fresh = _reader(monkeypatch, tmp_path, stations=9, urls_of=urls_of, depth=8, cache="new/dir/cache")

    results = list(fresh.query())

    assert sorted(upstream.requests) == sorted(f"/{s}/{n}" for s in range(9) for n in range(count))
    expected = list(_reader(monkeypatch, tmp_path, stations=9, urls_of=urls_of, depth=0, cache="sequential").query())
    for got, want in zip(results, expected, strict=True):
        assert_frame_equal(got.df, want.df)


# 6. connections to one host


def test_a_walk_holds_no_more_than_depth_connections_beside_its_own(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`depth` connections for the stations ahead and one for the station in hand: five at the most for four."""
    upstream.delay = lambda _path: 0.05
    reader = _reader(monkeypatch, tmp_path, stations=20, urls_of=_files(upstream, 2), depth=4)

    list(reader.query())

    assert 2 <= upstream.max_active <= 4 + 1


def test_the_reads_of_a_process_hold_no_more_than_the_cap_of_connections_to_a_host_between_them(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Three walks beside each other, as a REST server has, do not open `depth` connections each to one host."""
    cap, walks = 2, 3
    monkeypatch.setattr(fetch_ahead, "HOST_CONNECTIONS", cap)
    upstream.delay = lambda _path: 0.05
    # all of them read from the one request class the helper patches, so the readers are built first and read after
    readers = [
        _reader(monkeypatch, tmp_path, stations=12, urls_of=_files(upstream, 1), depth=4, cache=f"walk{index}")
        for index in range(walks)
    ]
    answers: list[int] = []
    threads = [threading.Thread(target=lambda r=r: answers.append(len(list(r.query())))) for r in readers]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert answers == [12] * walks
    # the fetch-ahead of all of them holds `cap`, and each walk its own connection beside
    assert upstream.max_active <= cap + walks


def test_the_default_depth_is_modest() -> None:
    """The default is what a caller is told it is, and the most is a hard limit."""
    assert Settings().fetch_ahead == 4
    with pytest.raises(ValueError, match="less than or equal to 8"):
        Settings(fetch_ahead=9)
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        Settings(fetch_ahead=-1)


# 8. what it is for, and what it does not cost


def test_the_files_of_many_stations_are_fetched_clearly_faster_than_one_station_after_the_other(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With a latency per file, 24 stations are read in well under the time of one after the other (about 4x).

    What is held is the overlap, which the server counts and a busy machine does not change: one connection at a time
    without it, three or more with it. The clock only has to agree (it is 4 times where nothing else runs; a machine
    under a load of 90 has made it 1.5): the numbers are the benchmark's, in the pull request.
    """
    upstream.delay = lambda _path: 0.05
    sequential, sequential_overlap = _walk_time(
        upstream, monkeypatch, tmp_path, depth=0, attempts=2, stations=24, files=1
    )
    ahead, ahead_overlap = _walk_time(upstream, monkeypatch, tmp_path, depth=4, attempts=3, stations=24, files=1)

    assert sequential_overlap == 1
    assert ahead_overlap >= 3
    assert sequential >= 1.1 * ahead, (sequential, ahead)


def test_one_station_is_read_as_it_was(upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A read of one station makes no fetch-ahead: no thread, no further request, and no longer."""
    upstream.delay = lambda _path: 0.05
    made: list[object] = []
    original = FetchAhead.__init__

    def counting(self: FetchAhead, **kwargs: object) -> None:
        made.append(self)
        original(self, **kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(FetchAhead, "__init__", counting)
    timings = {}
    for depth in (0, 4):
        reader = _reader(monkeypatch, tmp_path, stations=1, urls_of=_files(upstream, 3), depth=depth, cache=f"d{depth}")
        began = time.perf_counter()
        assert len(list(reader.query())) == 1
        timings[depth] = time.perf_counter() - began

    assert made == []
    assert _fetch_threads() == []
    assert timings[4] <= 2 * timings[0] + 0.3, timings


def test_it_is_off_where_nothing_is_cached_or_it_is_switched_off(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With `fetch_ahead=0` or the cache disabled, a file fetched ahead would be fetched again: so none is."""
    upstream.delay = lambda _path: 0.01
    off = _reader(monkeypatch, tmp_path, stations=5, urls_of=_files(upstream, 1), depth=0)
    stage = off.query()
    next(stage)
    upstream.settle()
    assert upstream.stations_asked() == {0}
    stage.close()

    upstream.requests.clear()
    uncached = _reader(monkeypatch, tmp_path, stations=5, urls_of=_files(upstream, 1), depth=4, cache="uncached")
    uncached.sr.request.settings.cache_disable = True
    stage = uncached.query()
    next(stage)
    upstream.settle()
    assert upstream.stations_asked() == {0}
    stage.close()


def test_a_provider_without_the_hook_is_read_as_it_was(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A provider that does not name its files has none fetched ahead."""
    reader = _reader(monkeypatch, tmp_path, stations=5, urls_of=_files(upstream, 1), depth=4, hook=False)
    stage = reader.query()
    next(stage)
    upstream.settle()

    assert upstream.stations_asked() == {0}
    stage.close()


def test_a_files_ahead_that_raises_is_not_heard_of_until_its_station(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A hook that fails for a station leaves it to its own collection, and nothing more is fetched ahead."""
    urls = _files(upstream, 1)

    def named(station_id: str) -> list[str]:
        if int(station_id) == 1:
            msg = "no listing"
            raise RuntimeError(msg)
        return urls(station_id)

    reader = _reader(monkeypatch, tmp_path, stations=4, urls_of=urls, depth=1, named=named)

    results = reader.query()
    assert _station_ids([next(results)]) == ["00000"]
    assert _station_ids([next(results)]) == ["00001"]
    upstream.settle()
    asked_with_the_hook_failed = upstream.stations_asked()
    assert _station_ids(list(results)) == ["00002", "00003"]

    assert asked_with_the_hook_failed == {0, 1}
    assert sorted(upstream.requests) == ["/0/0", "/1/0", "/2/0", "/3/0"]


def test_a_fetch_that_breaks_is_not_heard_of_and_stops_the_fetching(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A thread that meets an error of its own (a cache that cannot be written) leaves its station to the walk."""
    broken = {"once": True}

    def breaking(**kwargs: object) -> object:
        if broken["once"]:
            broken["once"] = False
            msg = "no space left"
            raise OSError(msg)
        return download_file(**kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(fetch_ahead, "download_file", breaking)
    reader = _reader(monkeypatch, tmp_path, stations=4, urls_of=_files(upstream, 1), depth=1)

    results = reader.query()
    next(results)
    next(results)
    upstream.settle()
    asked = upstream.stations_asked()
    assert _station_ids(list(results)) == ["00002", "00003"]

    assert asked == {0, 1}


def test_a_station_with_many_files_is_read_no_slower_than_without_the_fetch_ahead(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A provider fetches the files of a station side by side, and the fetch-ahead fetches them one after the other.

    So when the walk comes to a station whose files are not all there yet, the thread ends the file it is at and the
    rest are the station's own download's, which takes them together: twenty files a station are not read slower
    than without it (they were, by two and a half times, when the walk waited for the thread to finish them all).
    """
    upstream.delay = lambda _path: 0.1
    kwargs = {"stations": 8, "files": 20, "parallel": True, "attempts": 3}
    sequential, _ = _walk_time(upstream, monkeypatch, tmp_path, depth=0, **kwargs)
    ahead, _ = _walk_time(upstream, monkeypatch, tmp_path, depth=4, **kwargs)

    # without the stop the walk takes about two and a half times as long
    assert ahead <= 1.7 * sequential + 0.4, (sequential, ahead)


def test_a_station_with_two_files_is_still_read_faster(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The head start counts where the files of a station are few: the files of the stations ahead come beside its own.

    Two files a station, which the collection fetches side by side: two connections at a time without the fetch-ahead,
    more with it (4 of its own beside them). Counted by the server, not timed.
    """
    upstream.delay = lambda _path: 0.05
    kwargs = {"stations": 20, "files": 2, "parallel": True, "attempts": 1}
    _, sequential_overlap = _walk_time(upstream, monkeypatch, tmp_path, depth=0, **kwargs)
    _, ahead_overlap = _walk_time(upstream, monkeypatch, tmp_path, depth=4, **kwargs)

    assert sequential_overlap == 2
    assert ahead_overlap >= 4


def test_the_threads_do_not_hold_up_the_end_of_the_interpreter(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The threads of the fetch-ahead are daemon threads: a walk that ends by an error does not wait at exit."""
    upstream.gate = threading.Event()
    reader = _reader(monkeypatch, tmp_path, stations=6, urls_of=_files(upstream, 1), depth=4)

    results = reader.query()
    next(results)
    upstream.wait_for(4)
    threads = _fetch_threads()
    results.close()
    upstream.gate.set()
    _wait_for_no_threads()

    assert len(threads) == 4
    assert all(thread.daemon for thread in threads)


def test_a_failure_to_plan_the_stations_ahead_is_not_heard_of_before_their_turn(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """What is asked of a station ahead (its datasets, its window) is under the guard that stops the fetching ahead."""
    reader = _reader(monkeypatch, tmp_path, stations=6, urls_of=_files(upstream, 1), depth=4)
    original = type(reader)._requested_datasets  # noqa: SLF001
    calls = []

    def failing(self: TimeseriesValues, available: list[DatasetModel]) -> list[DatasetModel]:
        calls.append(available)
        if len(calls) == 3:
            msg = "no datasets"
            raise RuntimeError(msg)
        return original(self, available)

    monkeypatch.setattr(type(reader), "_requested_datasets", failing)

    results = list(reader.query())

    assert _station_ids(results) == [f"{index:05d}" for index in range(6)]
    assert len(calls) == 3


def test_a_summary_and_an_interpolation_fetch_nothing_ahead(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """They stop the walk where the stations found are enough, which no number says: what was ahead is thrown away.

    A plain read of the same stations makes a fetch-ahead.
    """
    pytest.importorskip("shapely")
    pytest.importorskip("utm")
    from wetterdienst.core.interpolate import get_interpolated_df  # noqa: PLC0415
    from wetterdienst.core.summarize import get_summarized_df  # noqa: PLC0415
    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415

    latitude, longitude = 50.0, 8.9
    offsets = [(-0.03, -0.03), (-0.03, 0.03), (0.03, 0.03), (0.03, -0.03), (0.05, 0.0), (0.0, 0.05)]
    stations = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": f"{index:05d}",
                "latitude": latitude + d_lat,
                "longitude": longitude + d_lon,
                "elevation": 100.0,
                "distance": 4.0 + index / 10,
            }
            for index, (d_lat, d_lon) in enumerate(offsets)
        ],
    )
    reader = _reader(monkeypatch, tmp_path, stations=len(offsets), urls_of=_files(upstream, 1), depth=4)
    request = reader.sr.request

    def by_distance(
        self: DwdObservationRequest,
        latlon: tuple[float, float],  # noqa: ARG001
        distance: float,  # noqa: ARG001
        df_all: pl.DataFrame | None = None,  # noqa: ARG001
    ) -> StationsResult:
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.BY_DISTANCE)

    monkeypatch.setattr(DwdObservationRequest, "filter_by_distance", by_distance)
    made: list[object] = []
    original = FetchAhead.__init__

    def counting(self: FetchAhead, **kwargs: object) -> None:
        made.append(self)
        original(self, **kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(FetchAhead, "__init__", counting)

    assert len(list(reader.query())) == len(offsets)
    assert len(made) == 1
    made.clear()
    for get_df in (get_summarized_df, get_interpolated_df):
        get_df(request, latitude, longitude)
    assert made == []
