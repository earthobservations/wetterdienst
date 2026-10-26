"""A cache of directory listings in one SQLite file that holds JSON (GH-3326).

`diskcache` stored the listings of `FileDirCache` pickled and unpickled them on read, so whoever could
write to the cache directory could run code as the process (GHSA-w8v5-vhqr-4h9v, no fixed version).
This keeps the same listings, a `list[dict]` of JSON values, as JSON text in a table of the standard
library's `sqlite3`. Nothing in it is ever unpickled, evaluated or imported.

Several threads and several processes use one file at once:

* **One connection per thread**, never used by two threads at once: `sqlite3` connections are not
  meant to be, and a connection per thread needs no lock around the statements. A thread's connection
  is closed when the thread ends. `close()` from another thread waits for the statement that thread is
  running (a per-connection lock), because closing a connection under a running statement crashes
  CPython. They are opened with `check_same_thread=False` for this.
* **WAL and a busy timeout**: readers do not block the writer, and a writer waits for another
  writer (60 s) instead of failing with `database is locked`. Every write is one transaction that
  takes the write lock at its start (`BEGIN IMMEDIATE`), so no transaction ever has to upgrade
  a read lock, which is the one case a busy timeout does not help.
* **A `fork`ed child never uses a connection of its parent's.** No thread is inside SQLite when the
  process forks (see the gate below), because a mutex it held would be held for good in the child. The child
  closes the connections it inherited: SQLite counts the locks of a process per file, and an inherited
  connection that stays open makes the connections the child opens believe they hold locks they do
  not (`disk I/O error`).

The file is named for its schema (`listings-v1.sqlite3`), so a file of another layout, including the
`cache.db` of `diskcache`, is never opened by this.
"""

from __future__ import annotations

import contextlib
import errno
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

log = logging.getLogger(__name__)

#: The file a listings store lives in, within the directory of its TTL. The version is part of the
#: name: a layout that is ever changed gets a new name and the old file is left to the sweep.
STORE_FILENAME = "listings-v1.sqlite3"

#: Written into the file (`PRAGMA application_id`, "WDLS") and checked on opening, so that a file by
#: this name that is something else is replaced rather than read.
_APPLICATION_ID = 0x57444C53
_SCHEMA_VERSION = 1

#: How long a statement waits for a lock another connection holds, in seconds, before it gives up
#: with `database is locked`. `diskcache` used the same.
_BUSY_TIMEOUT = 60.0
#: Opening can meet a lock the busy handler does not wait for (switching a file to WAL while another
#: connection is being set up), so it is asked again a few times.
_OPEN_ATTEMPTS = 8
#: The write-ahead log is truncated to this size after a checkpoint instead of staying as large as
#: its largest transaction (a big listing).
_JOURNAL_SIZE_LIMIT = 4 * 1024 * 1024
#: A listing is 10 to 250 kB of text. On pages of 4 kB reading one walks a chain of 20 to 60 overflow
#: pages (measured: 122 us for the 90 kB listing of an hourly DWD directory, 41 us with 16 kB pages).
#: Takes effect only for a file that is made, not for one that exists.
_PAGE_SIZE = 16384

#: Only a build of SQLite without any locking (`SQLITE_THREADSAFE=0`) reports 0: there connections
#: of different threads must not run at the same time either, so every statement takes this lock.
_SERIALIZE: contextlib.AbstractContextManager[Any] = (
    threading.Lock() if sqlite3.threadsafety == 0 else contextlib.nullcontext()
)

#: An ordinary table with an index on the key, not `WITHOUT ROWID`: there the 10 to 250 kB value sits
#: in the b-tree that is searched, and a lookup walked its overflow pages (measured, 100 listings of
#: 88 kB: a miss took 19 us instead of 2.5, a hit 40 instead of 18).
_CREATE = """
CREATE TABLE IF NOT EXISTS listing (
    key TEXT PRIMARY KEY NOT NULL,
    expires REAL,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS listing_expires ON listing (expires);
"""

# The statements, written out: each takes the clock as its last parameter where it reads only entries that
# have not expired (`expires IS NULL` is "never"; an expiry of 0 is expired at once, not "never").
# the value comes back as bytes whatever it is, so that text which is no UTF-8 is dropped by `get` and
# not raised by the `sqlite3` module (with the stored text in the message)
_GET = (
    "SELECT typeof(value) = 'text', CAST(value AS BLOB) FROM listing WHERE key = ? AND (expires IS NULL OR expires > ?)"
)
_CONTAINS = "SELECT 1 FROM listing WHERE key = ? AND (expires IS NULL OR expires > ?)"
_KEYS = (
    "SELECT CAST(key AS BLOB) FROM listing WHERE typeof(key) = 'text' AND (expires IS NULL OR expires > ?) ORDER BY key"
)
_COUNT = "SELECT count(*) FROM listing WHERE typeof(key) = 'text' AND (expires IS NULL OR expires > ?)"

#: The clock the expiry times are read from; a test replaces it rather than waiting.
_now = time.time

_stores: weakref.WeakSet[ListingStore] = weakref.WeakSet()


class ListingNotStorableError(TypeError):
    """A value that would not come back from the cache as it went in."""


def make_private_dir(path: Path) -> None:
    """Make `path` and the directories above it that are missing, each with mode 0o700.

    A directory that exists is left exactly as it is, whoever owns it and whatever its mode: this
    never changes a directory it did not make. On Windows the mode is ignored; a umask can only
    take bits away.

    Raises:
        OSError: If a directory cannot be made.

    """
    path = Path(path)
    if path.is_dir():
        return
    if path.parent != path:
        make_private_dir(path.parent)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        # a directory that was there when `mkdir` looked and is gone when this does is not an error: another process
        # removed it, and it is made again (GH-3467)
        if path.is_dir():
            return
        if path.exists() or path.is_symlink():
            raise
        make_private_dir(path)


def encode_listing(value: object) -> str:
    """Write a listing as JSON text, or raise if it would not come back equal.

    A listing is a `list` of `dict`s of `str` keys and JSON values (`str`, numbers, `bool`,
    `None`, `list`, `dict`), which is all `HTTPFileSystem` makes of an index page. `json` alone
    turns a tuple into a list and an `int` key into a `str` silently, so the text is read back and
    compared before it is stored. That costs one parse per write, and a write follows a download.

    Raises:
        ListingNotStorableError: If the value is no list of dicts or not JSON that reads back the
            same (bytes, datetimes, tuples, keys that are not `str`, NaN).

    """
    if not isinstance(value, list) or not all(isinstance(entry, dict) for entry in value):
        msg = "a listing is a list of dicts"
        raise ListingNotStorableError(msg)
    try:
        text = json.dumps(value, separators=(",", ":"), allow_nan=False)
        same = json.loads(text) == value
    except (TypeError, ValueError, RecursionError) as error:
        msg = f"a listing must be JSON: {error}"
        raise ListingNotStorableError(msg) from error
    if not same:
        msg = "a listing must come back from JSON as it went in (no tuples, no keys that are not str)"
        raise ListingNotStorableError(msg)
    return text


def _refuse_constant(name: str) -> None:
    msg = f"{name} is no JSON"
    raise ValueError(msg)


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        msg = f"{text} is no finite number"
        raise ValueError(msg)
    return value


def decode_listing(text: object) -> list[dict]:
    """Read a listing from JSON text, as strictly as `encode_listing` writes it.

    Raises:
        ValueError: If the text is no JSON list of objects, or holds NaN, Infinity or a number that
            overflows.
        TypeError: If it is no `str` (a value of another SQLite type, a BLOB included).
        RecursionError: If it is nested too deep to read.

    """
    if not isinstance(text, str):
        msg = f"a listing is stored as text, not {type(text).__name__}"
        raise TypeError(msg)
    value = json.loads(text, parse_constant=_refuse_constant, parse_float=_finite_float)
    if not isinstance(value, list) or not all(isinstance(entry, dict) for entry in value):
        msg = "not a listing"
        raise ValueError(msg)
    return value


class ListingStore:
    """Listings by key in one SQLite file, with an optional expiry time for each.

    Safe for any number of threads and processes on one file. A key is a `str`, a value a listing
    (see `encode_listing`); an entry whose expiry time has passed is never returned.
    """

    def __init__(self, path: Path) -> None:
        """Open the store, making the file (mode 0o600) and its directory (0o700) if they are missing.

        Raises:
            OSError: If the directory or the file cannot be made or opened.
            sqlite3.OperationalError: If the database cannot be written (for instance, a file
                that is read-only), or stays locked for longer than the busy timeout.
            sqlite3.DatabaseError: If the file is still no database after it was replaced.

        """
        self.path = Path(path)
        self._local = threading.local()
        self._handles: weakref.WeakSet[_Connection] = weakref.WeakSet()
        self._handles_lock = threading.Lock()
        _stores.add(self)
        # opened here so that a directory that cannot be used is met by whoever builds the cache,
        # who can fall back, and not by the first listing
        with self._use():
            pass

    def close(self) -> None:
        """Close the connection of every thread, each when its statement is done.

        The store opens a new one on its next use.
        """
        self._local = threading.local()
        with self._handles_lock:
            handles = list(self._handles)
            self._handles.clear()
        for handle in handles:
            handle.close()

    def get(self, key: object) -> list[dict] | None:
        """Return the live listing stored under `key`, or None."""
        if not isinstance(key, str):
            return None
        try:
            with self._use() as conn:
                row = conn.execute(_GET, (key, _now())).fetchone()
        except UnicodeEncodeError:  # a key with a lone surrogate was never stored
            return None
        if row is None:
            return None
        try:
            is_text, raw = row
            if not is_text:
                msg = "a listing is stored as text"
                raise TypeError(msg)  # noqa: TRY301
            return decode_listing(raw.decode())
        except (ValueError, TypeError, RecursionError):  # UnicodeDecodeError is a ValueError
            # not something this wrote: dropped rather than handed to fsspec, and said
            log.warning(f"ignoring a cache entry that is no listing, removed from {self.path}")
            self.delete(key)
            return None

    def set(self, key: str, value: list[dict], expire: float | None) -> None:
        """Store `value` under `key` for `expire` seconds, or for good if `expire` is None.

        Expired entries are removed in the same transaction.

        Raises:
            ListingNotStorableError: If `key` is no `str` that SQLite can store, or `value` would
                not read back the same.
            ValueError: If `expire` is NaN.

        """
        if not isinstance(key, str):
            msg = f"the key of a listing is a str, not {type(key).__name__}"
            raise ListingNotStorableError(msg)
        try:
            key.encode()
        except UnicodeEncodeError as error:
            msg = "the key of a listing is text that can be stored"
            raise ListingNotStorableError(msg) from error
        if expire is not None and math.isnan(expire):
            msg = "the expiry time of a listing is a number of seconds, not NaN"
            raise ValueError(msg)
        text = encode_listing(value)
        now = _now()
        expires = None if expire is None else now + expire
        with self._use() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM listing WHERE expires <= ?", (now,))
                conn.execute(
                    "INSERT OR REPLACE INTO listing (key, expires, value) VALUES (?, ?, ?)", (key, expires, text)
                )
                conn.execute("COMMIT")
            except BaseException:
                # never leave a write transaction open on a connection that is kept: it would hold the
                # write lock for every process
                if conn.in_transaction:
                    with contextlib.suppress(sqlite3.Error):
                        conn.execute("ROLLBACK")
                raise

    def contains(self, key: object) -> bool:
        """Whether a live listing is stored under `key`."""
        if not isinstance(key, str):
            return False
        try:
            with self._use() as conn:
                row = conn.execute(_CONTAINS, (key, _now())).fetchone()
        except UnicodeEncodeError:
            return False
        return row is not None

    def delete(self, key: object) -> bool:
        """Remove `key`; whether it was there."""
        if not isinstance(key, str):
            return False
        try:
            with self._use() as conn:
                return conn.execute("DELETE FROM listing WHERE key = ?", (key,)).rowcount > 0
        except UnicodeEncodeError:
            return False

    def keys(self) -> list[str]:
        """Return the keys of the live listings, in order."""
        with self._use() as conn:
            rows = conn.execute(_KEYS, (_now(),)).fetchall()
        keys = []
        for (raw,) in rows:
            with contextlib.suppress(UnicodeDecodeError):  # a key that is no text of ours is not listed
                keys.append(raw.decode())
        return keys

    def count(self) -> int:
        """Return the number of live listings."""
        with self._use() as conn:
            return conn.execute(_COUNT, (_now(),)).fetchone()[0]

    def clear(self) -> None:
        """Remove every listing."""
        with self._use() as conn:
            conn.execute("DELETE FROM listing")

    def expire(self) -> int:
        """Remove the listings that have expired; how many."""
        with self._use() as conn:
            return conn.execute("DELETE FROM listing WHERE expires <= ?", (_now(),)).rowcount

    # connections

    @contextlib.contextmanager
    def _use(self) -> Iterator[sqlite3.Connection]:
        """Lend the connection of this thread, opened on its first use, for one operation.

        The lock of the connection is what lets `close()` of another thread wait for the operation.
        """
        with _inside_sqlite(), _SERIALIZE:
            while True:
                handle = self._handle()
                with handle.lock:
                    conn = handle.conn
                    if conn is not None:
                        yield conn
                        return
                # closed by `close()` between taking the handle and its lock: take a new one

    def _handle(self) -> _Connection:
        handle = getattr(self._local, "handle", None)
        if handle is None or handle.conn is None:
            handle = _Connection(self._open())
            with self._handles_lock:
                self._handles.add(handle)
            self._local.handle = handle
        return handle

    def _open(self) -> sqlite3.Connection:
        """Open a connection of the calling thread, replacing a file that is no listings store."""
        make_private_dir(self.path.parent)
        replaced = False
        started = time.monotonic()
        for attempt in range(_OPEN_ATTEMPTS):
            conn = _connect(self.path)
            try:
                _prepare(conn)
            except sqlite3.OperationalError as error:
                conn.close()
                # asked again only for a lock the busy handler did not wait for (it answers at once); one
                # it waited the whole timeout for is not asked for eight times over
                if not _is_busy(error) or attempt == _OPEN_ATTEMPTS - 1 or time.monotonic() - started >= _BUSY_TIMEOUT:
                    raise
                time.sleep(min(0.01 * 2**attempt, 0.5))
            except sqlite3.DatabaseError:
                # "file is not a database", "malformed", or a database of another application: a
                # cache is rebuilt, once; a file that is still wrong after that is raised
                conn.close()
                if replaced:
                    raise
                replaced = True
                log.warning(f"{self.path} is not a listings cache, replacing it")
                _remove_database_files(self.path)
            else:
                return conn
        msg = f"could not open {self.path}"  # pragma: no cover
        raise sqlite3.OperationalError(msg)  # pragma: no cover

    def _after_fork_in_child(self) -> None:
        """Close the connections of the parent, which are not the child's to use."""
        self._handles_lock = threading.Lock()
        for handle in list(self._handles):
            handle.close_in_child()
        self._handles.clear()
        self._local = threading.local()


class _Connection:
    """A connection with the lock that keeps `close()` from closing it under a running statement.

    The store keeps it in a `threading.local`, so it lives as long as the thread, and a thread of
    a server that comes and goes does not leave its connection (and the three files it holds
    open) behind. `check_same_thread=False` is what lets the thread that collects it, or `close()`,
    close it.
    """

    __slots__ = ("__weakref__", "_finalizer", "conn", "lock")

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn: sqlite3.Connection | None = conn
        self.lock = threading.Lock()
        self._finalizer = weakref.finalize(self, _close, conn, os.getpid())
        # not at interpreter exit: closing a daemon thread's connection from the main thread could
        # be under a statement, which crashes CPython. SQLite recovers an unclosed WAL by itself.
        self._finalizer.atexit = False

    def close(self) -> None:
        """Close the connection once nothing is running on it."""
        with self.lock:
            self.conn = None
            self._finalizer()

    def close_in_child(self) -> None:
        """Close the connection in a forked child, unless the thread that used it held its lock at the fork.

        That thread is gone, and so is whatever it was doing with SQLite: if it was forking from inside
        an operation, or the wait of the fork gave up on it, the connection is left alone (it is
        dropped, not closed) rather than waited for.
        """
        if self.lock.acquire(blocking=False):
            try:
                self.conn = None
                self._finalizer()
            finally:
                self.lock.release()
        else:
            if self.conn is not None:
                _kept_open.append(self.conn)  # dropped, a connection would be closed by its deallocation
            self.conn = None
            self._finalizer.detach()


def _close(conn: sqlite3.Connection, pid: int) -> None:
    """Close `conn`, which the process `pid` opened, without ever waiting.

    A finalizer runs when the last reference goes, in any thread and under any lock the caller holds, so
    it must not wait for a fork that may be waiting for that lock. If a fork is pending, or the gate is
    busy, the connection is closed after the fork instead (`_deferred_closes`).

    In a forked child the gate is not entered: CPython runs this for the connections of the threads
    that did not survive the fork before any at-fork hook, and no thread was inside SQLite at the fork,
    so no mutex is held.
    """
    try:
        if os.getpid() != pid:
            conn.close()
            return
        if _try_inside_sqlite():
            try:
                conn.close()
            finally:
                _leave_counted()
        else:
            _deferred_closes.append(conn)
    except Exception:  # noqa: BLE001, S110
        pass  # a connection that cannot be closed, or a module torn down at interpreter exit: nothing to do


def _leave_counted() -> None:
    global _in_sqlite  # noqa: PLW0603
    with _gate_lock:
        _in_sqlite -= 1


#: Held while a database file is made and opened. See `_connect`.
_connect_lock = threading.Lock()


def _connect(path: Path) -> sqlite3.Connection:
    """Open `path`, making it with mode 0o600 if it does not exist.

    SQLite would make it with 0o666 less the umask, and gives its -wal and -shm files the mode of
    the file, so the file is made here. The descriptor made for that is closed at once, and
    **closing any descriptor of a file drops every POSIX lock the process holds on it**, those
    of the connections of other threads included: the cause of `disk I/O error` and a corrupt
    database in the first stress test of this. So it is only ever done for a file that does not
    exist yet, which no connection of this process can have open, and with `_connect_lock` held
    from before the check until the connection has the file open, so that no thread opens the file
    between its making and the close of that descriptor. A link in the file's place is refused: SQLite would follow it.
    """
    with _connect_lock:
        if path.is_symlink():
            msg = f"{path} is a link"
            raise OSError(errno.ELOOP, msg)
        with contextlib.suppress(FileExistsError):
            os.close(os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600))
        if not os.access(path, os.W_OK):
            # SQLite opens a file it cannot write read-only and goes on, to fail at the first write
            msg = "the database is not writable"
            raise PermissionError(errno.EACCES, msg, str(path))
        return sqlite3.connect(path, timeout=_BUSY_TIMEOUT, isolation_level=None, check_same_thread=False)


def _prepare(conn: sqlite3.Connection) -> None:
    """Bring a fresh connection to the schema, WAL and the settings every connection needs."""
    # the file is read back from a directory that may be written by someone else
    conn.execute("PRAGMA trusted_schema = OFF")
    conn.execute("PRAGMA cell_size_check = ON")
    setconfig = getattr(conn, "setconfig", None)  # Python 3.12 and later
    defensive = getattr(sqlite3, "SQLITE_DBCONFIG_DEFENSIVE", None)
    if setconfig is not None and defensive is not None:
        setconfig(defensive, True)  # noqa: FBT003
    conn.execute(f"PRAGMA page_size = {_PAGE_SIZE}")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    application_id = conn.execute("PRAGMA application_id").fetchone()[0]
    if (version, application_id) != (_SCHEMA_VERSION, _APPLICATION_ID):
        _create_schema(conn)
    if str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute(f"PRAGMA journal_size_limit = {_JOURNAL_SIZE_LIMIT}")
    # takes and gives back the write lock: a database that cannot be written is met here, as
    # `attempt to write a readonly database`, and not by the first listing
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("COMMIT")


def _require_empty(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]:
        msg = "a database of something else"
        raise sqlite3.DatabaseError(msg)


def _create_schema(conn: sqlite3.Connection) -> None:
    """Make the table in an empty file; raise `sqlite3.DatabaseError` for a file that holds anything else."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        # another process may have made it while this waited for the lock
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        application_id = conn.execute("PRAGMA application_id").fetchone()[0]
        if (version, application_id) != (_SCHEMA_VERSION, _APPLICATION_ID):
            _require_empty(conn)
            for statement in filter(None, (part.strip() for part in _CREATE.split(";"))):
                conn.execute(statement)
            conn.execute(f"PRAGMA application_id = {_APPLICATION_ID}")
            conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
    except BaseException:
        with contextlib.suppress(sqlite3.Error):
            conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _is_busy(error: sqlite3.OperationalError) -> bool:
    """Whether `error` is another connection's lock (SQLITE_BUSY or SQLITE_LOCKED, and their kinds)."""
    code = getattr(error, "sqlite_errorcode", None)  # Python 3.11 and later
    if code is not None:
        return (code & 0xFF) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
    return "locked" in str(error) or "busy" in str(error)  # pragma: no cover


def _remove_database_files(path: Path) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        with contextlib.suppress(FileNotFoundError):
            Path(f"{path}{suffix}").unlink()


#: Who is inside SQLite, so that `fork` never happens while a thread is. SQLite keeps process-wide
#: mutexes (the allocator's, the page cache's), and one that a thread holds at the instant of the fork
#: is held for good in the child, by a thread that no longer exists: the first thing the child does with
#: SQLite then waits forever (seen: one child in four, a thread writing while another forks).
#: `before` waits for the operations running and holds new ones back until the fork is done.
#:
#: Everything this module does with SQLite is inside it -- operations, closing a connection, the sweep's
#: look into an old database -- and it can be entered again by the thread that is in it. SQLite used by
#: anything else in the process is not behind it. A fork waits for an operation that waits for a lock
#: another process holds (up to the busy timeout), so the wait is bounded (`_FORK_WAIT`, then a warning):
#: a fork is not held back for ever by a count that an exception from a signal handler left behind.
#:
#: Plain locks and polling rather than a `threading.Condition`: its `__enter__` is Python code, and a
#: `KeyboardInterrupt` between its acquire and its `try` left the lock held for good, so that every
#: later operation of every thread waited for it. A plain lock is taken in one step.
_gate_lock = threading.Lock()
_in_sqlite = 0
_forks_pending = 0
_thread_gate = threading.local()
_FORK_WAIT = 10.0
_GATE_POLL = 0.001
#: Connections whose close was put off because a fork was pending (or the gate busy) when their last
#: reference went: closing must never wait, as a finalizer can run while the caller holds any lock.
_deferred_closes: list[sqlite3.Connection] = []
#: Connections of a forked child that a thread of the parent may have been inside: never closed there.
_kept_open: list[sqlite3.Connection] = []


def _drain_deferred_closes() -> None:
    while True:
        try:
            conn = _deferred_closes.pop()
        except IndexError:  # another thread took the last one
            return
        with contextlib.suppress(Exception):
            conn.close()


@contextlib.contextmanager
def _inside_sqlite() -> Iterator[None]:
    """Keep a `fork` from happening while the caller is inside SQLite."""
    global _in_sqlite  # noqa: PLW0603
    depth = getattr(_thread_gate, "depth", 0)
    counted = False
    while depth == 0 and not counted:
        with _gate_lock:
            if not _forks_pending:
                _in_sqlite += 1
                counted = True
        if not counted:
            time.sleep(_GATE_POLL)
    _thread_gate.depth = depth + 1
    try:
        if counted and _deferred_closes:
            _drain_deferred_closes()
        yield
    finally:
        _thread_gate.depth = depth
        if counted:
            with _gate_lock:
                _in_sqlite -= 1


def _try_inside_sqlite() -> bool:
    """Count the caller as inside SQLite if no fork is pending and the gate is free, without waiting."""
    global _in_sqlite  # noqa: PLW0603
    if not _gate_lock.acquire(blocking=False):
        return False
    try:
        if _forks_pending:
            return False
        _in_sqlite += 1
        return True
    finally:
        _gate_lock.release()


def _before_fork() -> None:
    global _forks_pending  # noqa: PLW0603
    own = 1 if getattr(_thread_gate, "depth", 0) else 0  # a thread that forks from inside does not wait for itself
    with _gate_lock:
        _forks_pending += 1
    deadline = time.monotonic() + _FORK_WAIT
    while _in_sqlite > own:
        if time.monotonic() >= deadline:
            log.warning(f"forking while {_in_sqlite - own} operation(s) on the listings cache are not done")
            break
        time.sleep(_GATE_POLL)


def _after_fork_in_parent() -> None:
    global _forks_pending  # noqa: PLW0603
    with _gate_lock:
        _forks_pending -= 1
    _drain_deferred_closes()


def _after_fork_in_child() -> None:
    global _connect_lock, _gate_lock, _in_sqlite, _forks_pending, _thread_gate  # noqa: PLW0603
    # state that threads of the parent held at the fork is held for good in the child
    _gate_lock = threading.Lock()
    _thread_gate = threading.local()
    _in_sqlite = 0
    _forks_pending = 0
    _connect_lock = threading.Lock()
    _drain_deferred_closes()
    for store in list(_stores):
        store._after_fork_in_child()  # noqa: SLF001


if hasattr(os, "register_at_fork"):
    os.register_at_fork(before=_before_fork, after_in_parent=_after_fork_in_parent, after_in_child=_after_fork_in_child)


#: What `diskcache` left in a TTL's directory: `cache.db` with its `-wal` and `-shm`, and the values
#: it kept in files, in directories named by two hex digits at two levels (`ab/cd/<hex>.val`).
_DISKCACHE_FILES = ("cache.db", "cache.db-wal", "cache.db-shm")
_DISKCACHE_VALUE_DIR = re.compile(r"^[0-9a-f]{2}$")
_SQLITE_HEADER = b"SQLite format 3\x00"


def remove_diskcache_leftovers(directory: Path, *, idle_for: float) -> bool:
    """Remove the files `diskcache` left in `directory`, when nothing has written to them for `idle_for` seconds.

    They are never read (see the module docstring), so this only gives back the space. An older
    wetterdienst that runs beside this one and still writes them is left alone: the default cache
    directory is shared by every install of a user. One that only reads its cache (`diskcache` writes
    nothing on a hit) cannot be told from an idle one: it loses its cache after the hour and makes a
    new one. Only a `cache.db` that is a regular file with the tables of a `diskcache` database
    counts, and only what `diskcache` makes is removed: if anything else is in one of its value
    directories, that directory stays.

    Returns:
        Whether anything was removed. Never raises.

    """
    try:
        database = directory / "cache.db"
        if database.is_symlink() or not database.is_file():
            return False
        # the idle check before the look into the database: that opens it, and the files it makes
        # (a WAL database gets a -wal and a -shm) would be written just now
        newest = max(
            ((directory / name).stat().st_mtime for name in _DISKCACHE_FILES if (directory / name).exists()),
            default=time.time(),  # gone meanwhile (another process swept): nothing to remove
        )
        if newest > time.time() - idle_for:
            return False
        if not _is_diskcache_database(database):
            return False
        for name in _DISKCACHE_FILES:
            (directory / name).unlink(missing_ok=True)
        for child in directory.iterdir():
            if _DISKCACHE_VALUE_DIR.match(child.name) and child.is_dir() and not child.is_symlink():
                _remove_value_dir(child)
    except Exception:
        log.debug(f"Failed removing what diskcache left in {directory}", exc_info=True)
        return False
    return True


def _is_diskcache_database(database: Path) -> bool:
    """Whether `database` is the SQLite file of a `diskcache.Cache`: the tables `Cache` and `Settings`.

    Opened read-only, immutable (no lock and no -wal or -shm file made) and by URI, and nothing in it
    is read but the names of its tables. The tables of a WAL database that has not been checkpointed
    are not seen, which only leaves its files where they are.
    """
    try:
        with database.open("rb") as stream:
            if stream.read(len(_SQLITE_HEADER)) != _SQLITE_HEADER:
                return False
        with _inside_sqlite():
            connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro&immutable=1", uri=True, timeout=1.0)
            try:
                tables = {name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                connection.close()
    except (OSError, sqlite3.Error):
        return False
    return {"Cache", "Settings"} <= tables


def _remove_value_dir(top: Path) -> None:
    """Remove `top` if it holds nothing but `diskcache`'s value directories and `.val` files."""
    for root, dirs, files in os.walk(top, followlinks=False):
        if not all(_DISKCACHE_VALUE_DIR.match(name) for name in dirs) or not all(
            name.endswith(".val") for name in files
        ):
            return
        if any(Path(root, name).is_symlink() for name in (*dirs, *files)):
            return
    import shutil  # noqa: PLC0415

    shutil.rmtree(top)
