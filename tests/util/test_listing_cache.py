# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the SQLite store that keeps the directory listings (GH-3326)."""

import contextlib
import datetime as dt
import gc
import json
import logging
import os
import signal
import sqlite3
import stat
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tests.util.listing_cache_stress import stress
from wetterdienst.util import listing_cache
from wetterdienst.util.listing_cache import (
    STORE_FILENAME,
    ListingNotStorableError,
    ListingStore,
    decode_listing,
    encode_listing,
    make_private_dir,
)


@contextlib.contextmanager
def _database(path: Path) -> Iterator[sqlite3.Connection]:
    """Open an SQLite file, commit what the test did and close it (`with sqlite3.connect()` does not close)."""
    connection = sqlite3.connect(path)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


_posix_modes = pytest.mark.skipif(os.name == "nt", reason="file modes are not enforced on Windows")


def _listing(prefix: str = "http://example.com/") -> list[dict]:
    return [
        {"name": f"{prefix}stundenwerte_TU_00044_akt.zip", "size": None, "type": "file"},
        {"name": f"{prefix}sub/", "size": None, "type": "directory"},
    ]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ListingStore]:
    """Return a store in a directory of its own, closed after the test."""
    opened = ListingStore(tmp_path / "cache" / STORE_FILENAME)
    yield opened
    opened.close()


# the JSON round trip


def test_what_a_listing_holds_comes_back_equal(store: ListingStore) -> None:
    """What `fsspec` puts in a listing entry (`str`, `None`, ints, floats) is returned type for type."""
    listing = [
        {"name": "http://example.com/ä ö/€.zip", "size": None, "type": "file"},
        {"name": "http://example.com/b", "size": 12345678901234567890, "type": "file", "mtime": 1.5, "flag": True},
        {"name": "http://example.com/\ud800", "size": 0, "type": "file", "nested": {"a": [1, 2.0, None]}},
    ]
    store.set("key", listing, None)

    stored = store.get("key")

    assert stored == listing
    assert [type(entry["size"]) for entry in stored] == [type(entry["size"]) for entry in listing]
    assert type(stored[1]["flag"]) is bool
    assert type(stored[2]["nested"]["a"][1]) is float


def test_a_real_listing_round_trips(store: ListingStore) -> None:
    """The entries `HTTPFileSystem._ls_real` makes are `{"name": str, "size": None, "type": "file" | "directory"}`."""
    listing = [
        {
            "name": f"https://opendata.dwd.de/climate/hourly/stundenwerte_TU_{i:05d}_akt.zip",
            "size": None,
            "type": "file",
        }
        for i in range(2000)
    ]
    store.set("https://opendata.dwd.de/climate/hourly/", listing, 300.0)

    assert store.get("https://opendata.dwd.de/climate/hourly/") == listing


@pytest.mark.parametrize(
    "value",
    [
        pytest.param([{"name": b"bytes"}], id="bytes"),
        pytest.param([{"name": dt.datetime(2026, 1, 1, tzinfo=dt.UTC)}], id="datetime"),
        pytest.param([{"name": ("a", "tuple")}], id="tuple"),
        pytest.param([{1: "int key"}], id="int-key"),
        pytest.param([{None: "none key"}], id="none-key"),
        pytest.param([{"size": float("nan")}], id="nan"),
        pytest.param([{"size": float("inf")}], id="inf"),
        pytest.param([{"name": {1, 2}}], id="set"),
        pytest.param([{"name": object()}], id="object"),
        pytest.param({"name": "a dict, not a list"}, id="dict"),
        pytest.param([["a", "list"]], id="list-of-lists"),
        pytest.param("text", id="str"),
        pytest.param(None, id="none"),
    ],
)
def test_a_value_that_would_not_come_back_unchanged_is_refused_and_not_stored(
    store: ListingStore, value: object
) -> None:
    """`json` alone turns a tuple into a list and an int key into a str without a word; here it raises."""
    with pytest.raises(ListingNotStorableError):
        store.set("key", value, None)  # type: ignore[arg-type]

    assert store.get("key") is None
    assert store.count() == 0


def test_a_refused_write_leaves_the_earlier_listing(store: ListingStore) -> None:
    """A refused write leaves the earlier listing."""
    store.set("key", _listing(), None)

    with pytest.raises(ListingNotStorableError):
        store.set("key", [{"name": b"bytes"}], None)

    assert store.get("key") == _listing()


def test_a_key_that_is_no_str_is_refused_on_write_and_missing_on_read(store: ListingStore) -> None:
    """A key that is no str is refused on write and missing on read."""
    with pytest.raises(ListingNotStorableError):
        store.set(1, _listing(), None)  # type: ignore[arg-type]

    assert store.get(1) is None  # type: ignore[arg-type]
    assert not store.contains(1)
    assert not store.delete(1)  # type: ignore[arg-type]


def test_a_key_that_cannot_be_encoded_is_a_miss(store: ListingStore) -> None:
    """A key that cannot be encoded is a miss."""
    assert store.get("http://example.com/\ud800") is None
    assert not store.contains("http://example.com/\ud800")


def test_encoding_and_decoding_are_each_others_inverse() -> None:
    """Encoding and decoding are each others inverse."""
    listing = _listing()
    assert decode_listing(encode_listing(listing)) == listing
    assert json.loads(encode_listing(listing)) == listing


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{",
        "{}",
        "[1]",
        '["a"]',
        "null",
        '"text"',
        '[{"size": NaN}]',
        '[{"size": Infinity}]',
        '[{"size": 1e400}]',
        pytest.param("[" * 100_000, id="nested-too-deep"),
    ],
)
def test_a_text_that_is_no_listing_is_not_decoded(text: str) -> None:
    """A text that is no listing is not decoded."""
    with pytest.raises((ValueError, RecursionError)):
        decode_listing(text)


def test_json_stored_as_a_blob_is_no_listing() -> None:
    """Only text is a listing: a BLOB that holds valid JSON is not."""
    with pytest.raises(TypeError):
        decode_listing(b'[{"name": "x"}]')


def test_a_key_that_cannot_be_stored_and_an_expiry_that_is_no_number_are_refused(store: ListingStore) -> None:
    """A lone surrogate is no key, NaN is no number of seconds (it was stored as 'never expires')."""
    with pytest.raises(ListingNotStorableError):
        store.set("http://example.com/\ud800", _listing(), None)
    with pytest.raises(ValueError, match="NaN"):
        store.set("key", _listing(), float("nan"))

    store.set("key", _listing(), None)
    assert store.keys() == ["key"], "the refused writes left the store usable"


@pytest.mark.parametrize(
    "planted",
    [
        b"\x80\x04\x95not a pickle that matters",
        b"cos\nsystem\n(S'true'\ntR.",
        "{}",
        "[1]",
        "not json",
        5,
        '[{"name": "x"}]'.encode("utf-16"),
        b'[{"name": "\xff"}]',
    ],
    ids=["pickle-protocol-4", "pickle-protocol-0", "object", "list-of-int", "text", "int", "utf-16", "not-utf-8"],
)
def test_a_row_that_is_no_listing_is_dropped_not_returned(
    store: ListingStore, planted: object, caplog: pytest.LogCaptureFixture
) -> None:
    """A row planted by anything but this store: refused, removed, and said once."""
    store.set("other", _listing(), None)
    with _database(store.path) as database:
        database.execute("INSERT OR REPLACE INTO listing (key, expires, value) VALUES ('planted', NULL, ?)", (planted,))
    caplog.set_level(logging.WARNING, logger=listing_cache.log.name)

    assert store.get("planted") is None

    assert store.get("planted") is None
    assert store.get("other") == _listing()
    assert sum("is no listing" in record.getMessage() for record in caplog.records) == 1
    with _database(store.path) as database:
        assert database.execute("SELECT count(*) FROM listing WHERE key = 'planted'").fetchone() == (0,)


def test_a_text_that_is_no_utf8_is_dropped_and_its_content_is_not_in_the_error(store: ListingStore) -> None:
    """The `sqlite3` module would raise an error that quotes the stored text; the row is dropped instead."""
    with _database(store.path) as database:
        database.execute(
            "INSERT INTO listing (key, expires, value) VALUES ('bad', NULL, CAST(? AS TEXT))",
            (b'[{"name": "secret-looking \xff"}]',),
        )

    assert store.get("bad") is None
    assert store.contains("bad") is False


def test_keys_that_are_no_text_of_ours_are_not_listed(store: ListingStore) -> None:
    """A planted BLOB key, or text that is no UTF-8, is neither listed nor counted."""
    store.set("good", _listing(), None)
    with _database(store.path) as database:
        database.execute("INSERT INTO listing (key, expires, value) VALUES (?, NULL, '[]')", (b"\x01",))
        database.execute(
            "INSERT INTO listing (key, expires, value) VALUES (CAST(? AS TEXT), NULL, '[]')", (b"\xff\xfe",)
        )

    assert store.keys() == ["good"]
    assert store.count() == 2, "the key that is bytes is not counted; the text that is no UTF-8 is, and not listed"


def test_the_deferred_closes_can_be_drained_by_two_threads_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two threads that both see the list not empty: the second must not fail on the pop."""
    connections = [sqlite3.connect(":memory:", check_same_thread=False) for _ in range(50)]
    monkeypatch.setattr(listing_cache, "_deferred_closes", list(connections))
    barrier = threading.Barrier(4)
    errors: list[BaseException] = []

    def drain() -> None:
        barrier.wait()
        try:
            for _ in range(200):
                listing_cache._drain_deferred_closes()  # noqa: SLF001
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=drain) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert listing_cache._deferred_closes == []  # noqa: SLF001


def test_a_pop_from_an_emptied_list_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The window between 'is it empty' and 'pop', made wide: another thread took the last one."""

    class Vanishing(list):
        def __bool__(self) -> bool:
            return True

    monkeypatch.setattr(listing_cache, "_deferred_closes", Vanishing())

    listing_cache._drain_deferred_closes()  # noqa: SLF001


def test_a_store_that_waited_the_busy_timeout_does_not_wait_again_to_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opening asks again for a lock the busy handler answered at once, not for one it waited the timeout for."""
    path = tmp_path / STORE_FILENAME
    ListingStore(path).close()
    monkeypatch.setattr(listing_cache, "_BUSY_TIMEOUT", 0.3)
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    attempts = []
    real_prepare = listing_cache._prepare  # noqa: SLF001

    def counting(conn: sqlite3.Connection) -> None:
        attempts.append(1)
        real_prepare(conn)

    monkeypatch.setattr(listing_cache, "_prepare", counting)
    try:
        with pytest.raises(sqlite3.OperationalError):
            ListingStore(path)
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert len(attempts) == 1


# what is kept, and for how long


def test_the_expiry_of_an_entry_is_read_off_the_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The expiry of an entry is read off the clock."""
    now = [1_000_000.0]
    monkeypatch.setattr(listing_cache, "_now", lambda: now[0])
    store = ListingStore(tmp_path / STORE_FILENAME)
    store.set("short", _listing(), 10.0)
    store.set("long", _listing(), 100.0)
    store.set("forever", _listing(), None)
    store.set("now", _listing(), 0.0)

    assert store.get("now") is None, "an expiry of 0 is expired as it is written, not 'never'"
    assert store.keys() == ["forever", "long", "short"]

    now[0] += 10.0
    assert store.keys() == ["forever", "long"]
    assert store.count() == 2
    assert store.expire() == 2, "'short', and 'now', which stays in the file until a write or this removes it"

    now[0] += 1e9
    assert store.keys() == ["forever"]
    store.close()


def test_delete_and_clear(store: ListingStore) -> None:
    """Delete and clear."""
    store.set("a", _listing(), None)
    store.set("b", _listing(), None)

    assert store.delete("a")
    assert not store.delete("a")
    assert store.keys() == ["b"]

    store.clear()

    assert store.count() == 0


def test_a_second_store_on_the_file_sees_the_first_ones_listings(tmp_path: Path) -> None:
    """A second store on the file sees the first ones listings."""
    path = tmp_path / STORE_FILENAME
    first = ListingStore(path)
    first.set("key", _listing(), None)
    first.close()

    second = ListingStore(path)

    assert second.get("key") == _listing()
    second.close()


# the file


@_posix_modes
def test_the_directories_it_makes_are_private_and_the_ones_that_exist_are_not_touched(tmp_path: Path) -> None:
    """The directories it makes are private and the ones that exist are not touched."""
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o755)
    previous_umask = os.umask(0o022)
    try:
        ListingStore(shared / "wetterdienst-fsspec" / "300.0" / STORE_FILENAME).close()
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE(shared.stat().st_mode) == 0o755, "an existing directory keeps its mode"
    for made in (shared / "wetterdienst-fsspec", shared / "wetterdienst-fsspec" / "300.0"):
        assert stat.S_IMODE(made.stat().st_mode) == 0o700


@_posix_modes
def test_the_database_and_its_journal_files_are_private(tmp_path: Path) -> None:
    """The database and its journal files are private."""
    previous_umask = os.umask(0o000)
    try:
        store = ListingStore(tmp_path / "d" / STORE_FILENAME)
        store.set("key", _listing(), None)
    finally:
        os.umask(previous_umask)

    names = sorted(p.name for p in (tmp_path / "d").iterdir())
    assert STORE_FILENAME in names
    for path in (tmp_path / "d").iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, path.name
    store.close()


@_posix_modes
def test_an_existing_database_keeps_the_mode_its_owner_gave_it(tmp_path: Path) -> None:
    """An existing database keeps the mode its owner gave it."""
    path = tmp_path / STORE_FILENAME
    ListingStore(path).close()
    path.chmod(0o640)

    ListingStore(path).close()

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_make_private_dir_is_idempotent_and_tolerates_a_race(tmp_path: Path) -> None:
    """Make private dir is idempotent and tolerates a race."""
    target = tmp_path / "a" / "b" / "c"
    errors: list[BaseException] = []
    barrier = threading.Barrier(8)

    def make() -> None:
        barrier.wait()
        try:
            make_private_dir(target)
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=make) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert target.is_dir()


def test_make_private_dir_refuses_a_path_below_a_file(tmp_path: Path) -> None:
    """Make private dir refuses a path below a file."""
    (tmp_path / "file").write_text("x")

    with pytest.raises(OSError):  # noqa: PT011
        make_private_dir(tmp_path / "file" / "below")


@_posix_modes
def test_a_link_in_the_place_of_the_database_is_not_followed(tmp_path: Path) -> None:
    """A link in the place of the database is not followed."""
    target = tmp_path / "target"
    target.write_text("important")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / STORE_FILENAME).symlink_to(target)

    with pytest.raises(OSError):  # noqa: PT011
        ListingStore(tmp_path / "cache" / STORE_FILENAME)

    assert target.read_text() == "important"


def test_a_file_that_is_no_database_is_replaced(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A file that is no database is replaced."""
    caplog.set_level(logging.WARNING, logger=listing_cache.log.name)
    path = tmp_path / STORE_FILENAME
    path.write_bytes(b"this is not an SQLite file at all, " * 100)

    store = ListingStore(path)
    store.set("key", _listing(), None)

    assert store.get("key") == _listing()
    assert any("not a listings cache" in record.getMessage() for record in caplog.records)
    store.close()


def test_a_database_of_another_application_is_replaced(tmp_path: Path) -> None:
    """A valid SQLite file by this name that is not ours (another `application_id`) is not read."""
    path = tmp_path / STORE_FILENAME
    with _database(path) as database:
        database.execute("CREATE TABLE listing (key TEXT, expires REAL, value TEXT)")
        database.execute("INSERT INTO listing VALUES ('key', NULL, '[{\"name\": \"planted\"}]')")

    store = ListingStore(path)

    assert store.get("key") is None
    store.close()


def test_the_database_is_in_wal_mode_with_its_schema_version(store: ListingStore) -> None:
    """The database is in wal mode with its schema version."""
    with _database(store.path) as database:
        assert database.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert database.execute("PRAGMA user_version").fetchone() == (1,)
        assert database.execute("PRAGMA application_id").fetchone() == (listing_cache._APPLICATION_ID,)  # noqa: SLF001


# threads, processes, forks


def test_every_thread_has_a_connection_of_its_own(store: ListingStore) -> None:
    """Every thread has a connection of its own."""
    store.set("key", _listing(), None)
    seen: dict[int, sqlite3.Connection] = {}
    barrier = threading.Barrier(4)

    def use() -> None:
        barrier.wait()
        store.get("key")
        seen[threading.get_ident()] = store._handle().conn  # noqa: SLF001
        barrier.wait()  # all alive at once, so no thread's connection is dropped for another's

    threads = [threading.Thread(target=use) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len({id(connection) for connection in seen.values()}) == 4
    assert store._handle().conn not in seen.values()  # noqa: SLF001


def test_the_connection_of_a_thread_that_ended_is_closed(store: ListingStore) -> None:
    """A thread of a server that comes and goes does not leave its connection, and the files it holds, behind."""
    connections: list[sqlite3.Connection] = []

    def use() -> None:
        store.get("key")
        connections.append(store._handle().conn)  # noqa: SLF001

    thread = threading.Thread(target=use)
    thread.start()
    thread.join()
    gc.collect()  # not needed by CPython, which frees a thread's locals as it ends; other interpreters may

    (connection,) = connections
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    assert store.get("key") is None, "a miss, answered: the thread that is left has a working connection"


def test_close_closes_every_thread_s_connection_and_the_store_goes_on(store: ListingStore) -> None:
    """Close closes every thread s connection and the store goes on."""
    store.set("key", _listing(), None)
    opened: list[sqlite3.Connection] = []
    done = threading.Event()
    release = threading.Event()

    def use() -> None:
        store.get("key")
        opened.append(store._handle().conn)  # noqa: SLF001
        done.set()
        release.wait()

    thread = threading.Thread(target=use)
    thread.start()
    done.wait()
    main = store._handle().conn  # noqa: SLF001

    store.close()

    for connection in (*opened, main):
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")
    assert store.get("key") == _listing(), "a closed store opens a new connection when it is used again"
    release.set()
    thread.join()


def _fork_children(count: int, child: Callable[[], bool]) -> list[int]:
    """Fork `count` children that each run `child`, die after 30 s, and report; return their exit codes.

    The children are made while the caller's other threads are inside SQLite, which is when a mutex of
    SQLite's is held at the instant of the fork. They are waited for by whoever calls this.
    """
    children = []
    for _ in range(count):
        pid = os.fork()
        if pid == 0:  # pragma: no cover - the child
            status = 1
            try:
                signal.alarm(30)  # a hang is a failure, not a test that never ends
                status = 0 if child() else 2
            finally:
                os._exit(status)
        children.append(pid)
    return children


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")
@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")
def test_a_child_forked_while_a_thread_writes_can_use_the_cache(tmp_path: Path) -> None:
    """The child reads what the parent stored and writes its own, whatever a thread of the parent is doing.

    A second thread of the parent writes flat out while the fork happens. Without the gate, SQLite's
    mutex is held by it at the instant of the fork, and the first thing the child does with SQLite
    waits for it forever (the child kills itself after 30 seconds, so that this fails the test).
    """
    store = ListingStore(tmp_path / STORE_FILENAME)
    store.set("parent", _listing(), None)
    stop = threading.Event()
    started = threading.Event()

    def hammer() -> None:
        index = 0
        while not stop.is_set():
            store.set(f"hammer-{index % 5}", _listing(), None)
            started.set()
            index += 1

    def child() -> bool:
        store.set("child", _listing("http://child/"), None)
        return store.get("parent") == _listing() and store.get("child") is not None

    hammering = threading.Thread(target=hammer)
    hammering.start()
    started.wait()
    try:
        children = _fork_children(5, child)
        # stopped once the forks are made: it would starve the children of the write lock
        stop.set()
        hammering.join()
        statuses = [os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) for pid in children]
    finally:
        stop.set()
        hammering.join()

    assert statuses == [0] * 5
    assert store.get("child") == _listing("http://child/")
    assert store.get("parent") == _listing()
    store.close()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")
@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")
def test_a_child_forked_while_connections_are_closed_does_not_hang(tmp_path: Path) -> None:
    """Closing a connection is SQLite too: a fork must not happen under it (the child hung, one in two).

    The parent closes all the connections of its store in a loop while a second thread uses it. The
    child opens a store of another file, which is what waits for the mutex; it does not use the
    parent's file, whose WAL the parent deletes under the child each time it closes its last connection.
    """
    store = ListingStore(tmp_path / "parent" / STORE_FILENAME)
    stop = threading.Event()
    started = threading.Event()

    def use() -> None:
        while not stop.is_set():
            store.set("key", _listing(), None)
            started.set()

    def close() -> None:
        while not stop.is_set():
            store.close()

    def child() -> bool:
        other = ListingStore(tmp_path / "child" / STORE_FILENAME)
        other.set("key", _listing(), None)
        return other.get("key") == _listing()

    threads = [threading.Thread(target=use), threading.Thread(target=close)]
    for thread in threads:
        thread.start()
    started.wait()
    try:
        children = _fork_children(8, child)
    finally:
        stop.set()
        for thread in threads:
            thread.join()
    statuses = [os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) for pid in children]

    assert statuses == [0] * 8
    store.close()


def test_close_waits_for_the_statement_another_thread_is_running(store: ListingStore) -> None:
    """Closing a connection under a running statement crashes CPython; `close()` takes the connection's lock."""
    stop = threading.Event()
    started = threading.Event()
    errors: list[BaseException] = []

    def work() -> None:
        index = 0
        try:
            while not stop.is_set():
                store.set(f"key-{index % 5}", _listing(), None)
                store.get(f"key-{index % 5}")
                store.delete(f"key-{(index + 1) % 5}")
                started.set()
                index += 1
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    workers = [threading.Thread(target=work) for _ in range(2)]
    for worker in workers:
        worker.start()
    started.wait()
    for _ in range(5):
        store.close()
    stop.set()
    for worker in workers:
        worker.join()

    assert errors == []


@pytest.mark.slow
def test_threads_and_processes_on_one_directory_lose_nothing_and_never_see_a_torn_value(tmp_path: Path) -> None:
    """Three processes of four threads read, write, expire and delete the same keys flat out.

    Nothing sleeps: the workers start at a barrier. A raised `database is locked`, a value that is
    mixed from two writes or cut short, and an entry that was written for good and is gone are all
    failures (see `tests/util/listing_cache_stress.py`, which also runs by hand with more of each).
    """
    problems = stress(tmp_path, processes=3, threads=4, iterations=200)

    assert problems == []


def test_a_fork_does_not_wait_for_ever_for_an_operation_that_never_ended(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A count that an exception from a signal handler left behind must not hold every later fork back."""
    caplog.set_level(logging.WARNING, logger=listing_cache.log.name)
    monkeypatch.setattr(listing_cache, "_FORK_WAIT", 0.05)
    monkeypatch.setattr(listing_cache, "_in_sqlite", 1)  # the leaked count

    listing_cache._before_fork()  # noqa: SLF001
    listing_cache._after_fork_in_parent()  # noqa: SLF001

    assert any("not done" in record.getMessage() for record in caplog.records)
    assert listing_cache._forks_pending == 0  # noqa: SLF001


def test_the_gate_can_be_entered_again_by_the_thread_that_is_in_it_while_a_fork_is_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finalizer that the garbage collector runs inside an operation must not wait for the fork that waits for it."""
    monkeypatch.setattr(listing_cache, "_FORK_WAIT", 5.0)
    with listing_cache._inside_sqlite():  # noqa: SLF001
        monkeypatch.setattr(listing_cache, "_forks_pending", 1)
        with listing_cache._inside_sqlite():  # noqa: SLF001
            pass
        listing_cache._before_fork()  # noqa: SLF001 -- a thread that forks from inside does not wait for itself
        listing_cache._after_fork_in_parent()  # noqa: SLF001
    assert listing_cache._in_sqlite == 0  # noqa: SLF001


def test_a_connection_that_is_released_while_a_fork_is_pending_is_closed_after_it(
    store: ListingStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A finalizer never waits: it can run under any lock its caller holds, which a fork's hooks may need."""
    connection = sqlite3.connect(store.path.parent / "other.db")
    monkeypatch.setattr(listing_cache, "_forks_pending", 1)

    listing_cache._close(connection, os.getpid())  # noqa: SLF001

    assert connection.execute("SELECT 1").fetchone() == (1,), "put off, not closed and not waited for"
    monkeypatch.setattr(listing_cache, "_forks_pending", 0)
    listing_cache._drain_deferred_closes()  # noqa: SLF001
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_a_fork_stays_pending_until_every_fork_that_began_is_done() -> None:
    """Two threads forking at once: the first one's end must not let operations in under the second."""
    listing_cache._before_fork()  # noqa: SLF001
    listing_cache._before_fork()  # noqa: SLF001
    listing_cache._after_fork_in_parent()  # noqa: SLF001
    try:
        assert listing_cache._forks_pending == 1  # noqa: SLF001
    finally:
        listing_cache._after_fork_in_parent()  # noqa: SLF001
    assert listing_cache._forks_pending == 0  # noqa: SLF001


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")
@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")
def test_a_child_forked_from_inside_an_operation_can_use_the_cache(tmp_path: Path) -> None:
    """The forking thread holds the lock of its own connection: the child must not wait for it."""
    store = ListingStore(tmp_path / STORE_FILENAME)
    store.set("parent", _listing(), None)

    def child() -> bool:
        store.set("child", _listing("http://child/"), None)
        return store.get("parent") == _listing()

    with store._use():  # noqa: SLF001
        children = _fork_children(3, child)
    statuses = [os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) for pid in children]

    assert statuses == [0] * 3
    store.close()
