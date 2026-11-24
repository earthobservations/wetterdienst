# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the DuckDB connection of the SQL filter cannot do, and the release it runs on (GHSA-332g-7w2w-4w59).

The filter is for the library and the command line, where the caller is the host's own user. It still runs the
condition on a connection that has external access off, its configuration locked, no extension to fetch or load, no
secret to keep, one thread and a memory limit (`wetterdienst.io.sql_filter._open_connection`), on DuckDB 1.5.3 or
newer. Each test names the restriction it holds and tries to break it, on that very connection.

Every connection of this module has both extension repository settings pointed at a listener on 127.0.0.1 (the
fixture `loopback`), the raw ones that are controls included, and a test that is left with a connection to it fails:
what one of these tests breaks never reaches a real host.
"""

# ruff: noqa: S608 (the SQL here is the test's own strings, and a statement that must be refused is the point)
from __future__ import annotations

import datetime as dt
import socket
import subprocess
import sys
import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING

import polars as pl
import pytest

from wetterdienst.exceptions import UnsupportedDependencyError
from wetterdienst.io.export import ExportMixin
from wetterdienst.io.sql_filter import _open_connection, _require_supported_duckdb, filter_by_sql

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

duckdb = pytest.importorskip("duckdb")

pytestmark = pytest.mark.sql


CANARY = "CANARY-secret-text-of-the-host"


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "station_id": ["01048"],
            "elevation": [645.0],
            "region": ["Bayern"],
            "name": ["Freyung vorm Wald"],
            "vals": [[1.0, 2.0]],
        }
    )


#: table functions that read, list or sniff a file or a path
FILE_FUNCTIONS = [
    "read_csv",
    "read_csv_auto",
    "read_json",
    "read_json_auto",
    "read_ndjson",
    "read_parquet",
    "parquet_scan",
    "parquet_metadata",
    "parquet_schema",
    "parquet_file_metadata",
    "parquet_kv_metadata",
    "read_text",
    "read_blob",
    "glob",
    "sniff_csv",
]


class _Listener:
    """A socket on 127.0.0.1 in a process of its own that counts the connections made to it, closing each at once.

    A process of its own because DuckDB may hold the GIL while it connects, and a thread here could not answer. A
    client that does connect is closed on and fails, so a restriction that fails fails its test and does not hang it.
    The process names the port each connection came from, so that a probe of our own, made last, tells when every
    connection before it has been counted: `sync` waits for that instead of for a pause.
    """

    code = """
import socket

server = socket.socket()
server.bind(("127.0.0.1", 0))
server.listen(16)
print(server.getsockname()[1], flush=True)
while True:
    connection, peer = server.accept()
    print("connection", peer[1], flush=True)
    connection.close()
"""

    def __init__(self) -> None:
        self.process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-I", "-c", self.code], stdout=subprocess.PIPE, text=True
        )
        assert self.process.stdout is not None
        self.port = int(self.process.stdout.readline())
        self.count = 0
        self._probes: set[int] = set()
        self._seen: set[int] = set()
        self._changed = threading.Condition()
        threading.Thread(target=self._count, daemon=True).start()

    def _count(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            port = int(line.split()[1])
            with self._changed:
                if port in self._probes:
                    self._seen.add(port)
                else:
                    self.count += 1
                self._changed.notify_all()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def sync(self) -> int:
        """Give the connections counted so far, after every one made before this call has been counted."""
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
            with self._changed:
                self._probes.add(port)
            probe.connect(("127.0.0.1", self.port))
            with self._changed:
                assert self._changed.wait_for(lambda: port in self._seen, timeout=30), "the listener did not answer"
                return self.count
        finally:
            probe.close()

    def close(self) -> None:
        self.process.kill()
        self.process.wait()


@pytest.fixture(scope="module")
def _listener() -> Iterator[_Listener]:
    server = _Listener()
    try:
        yield server
    finally:
        server.close()


class _Loopback:
    """What the listener has been asked since the test began."""

    def __init__(self, listener: _Listener) -> None:
        self.listener = listener
        self.start = listener.sync()
        #: a test that must make a connection, the control that shows the listener is reached, says so
        self.expected = False

    @property
    def url(self) -> str:
        return self.listener.url

    def hits(self) -> int:
        return self.listener.sync() - self.start


@pytest.fixture(autouse=True)
def loopback(_listener: _Listener, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Loopback]:
    """Point both extension repository settings of every connection at the listener, and fail a test it was asked by."""
    real_connect = duckdb.connect

    def connect(*args: object, config: dict | None = None, **kwargs: object) -> object:
        repository = {"custom_extension_repository": _listener.url, "autoinstall_extension_repository": _listener.url}
        return real_connect(*args, config={**(config or {}), **repository}, **kwargs)

    monkeypatch.setattr(duckdb, "connect", connect)
    state = _Loopback(_listener)
    yield state
    if not state.expected:
        assert state.hits() == 0, "a connection was made to the extension repository"


def test_the_listener_counts_the_connections_made_to_it(loopback: _Loopback) -> None:
    """Control: the count of the other tests can be more than zero, for a connection made to the listener."""
    loopback.expected = True
    assert loopback.hits() == 0
    for made in (1, 2, 3):
        with socket.create_connection(("127.0.0.1", loopback.listener.port), timeout=10):
            pass
        assert loopback.hits() == made


def test_a_connection_that_may_fetch_what_it_lacks_asks_the_listener(loopback: _Loopback) -> None:
    """Control: a connection with the defaults that needs a file system for a URL asks the repository, the listener.

    It is the repository settings the fixture sets that this shows the listener is behind: the restrictions of the
    connection of the filter are tested to leave the count at zero, which would hold as well of a listener that
    nothing could reach.
    """
    loopback.expected = True
    raw = duckdb.connect()
    try:
        with pytest.raises(duckdb.Error):
            raw.execute(f"SELECT count(*) FROM read_csv('{loopback.url}/x.csv')")
    finally:
        raw.close()

    assert loopback.hits() >= 1


@pytest.fixture(autouse=True)
def _away_from_the_checkout(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test in a directory and a home of its own, so that a file a failing test writes lands there."""
    away = tmp_path_factory.mktemp("away")
    monkeypatch.chdir(away)
    monkeypatch.setenv("HOME", str(away))
    monkeypatch.setenv("USERPROFILE", str(away))


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Provide a working directory with a secret in it, and a home directory that must stay empty."""
    work = tmp_path / "work"
    home = tmp_path / "home"
    work.mkdir()
    home.mkdir()
    work.joinpath("secret.csv").write_text(f"elevation\n{CANARY}\n")
    work.joinpath("secret.txt").write_text(CANARY)
    monkeypatch.chdir(work)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return SimpleNamespace(
        work=work,
        home=home,
        csv=work.joinpath("secret.csv").as_posix(),
        txt=work.joinpath("secret.txt").as_posix(),
    )


def _left_untouched(host: SimpleNamespace, *, also: tuple[str, ...] = ()) -> None:
    """Nothing was written to the working directory or the home (DuckDB on Windows has another home: see the control)."""
    assert sorted(path.name for path in host.work.iterdir()) == sorted(["secret.csv", "secret.txt", *also])
    assert list(host.home.rglob("*")) == []


@pytest.fixture
def connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """Provide the connection a condition is run on, with the frame in it."""
    con = _open_connection(duckdb, _frame())
    try:
        yield con
    finally:
        con.close()


def _must_not_connect(*_args: object, **_kwargs: object) -> None:
    pytest.fail("the filter connected, on a DuckDB it must refuse")


@pytest.mark.parametrize(
    "version",
    [
        "1.5.2",
        "1.4.4",
        "1.3.0",
        "1.1.0",
        "0.10.3",
        "1.5",
        "1.5.2.post4",
        "1.5.3.dev2",
        "1.5.3rc1",
        "1.5.3-alpha1",
        "",
        "x",
    ],
)
def test_a_duckdb_older_than_1_5_3_is_refused_before_it_is_used(monkeypatch: pytest.MonkeyPatch, version: str) -> None:
    """Restriction: the filter runs on DuckDB 1.5.3 or newer, and on nothing it cannot tell is.

    The refusal is an `UnsupportedDependencyError`, a `MissingDependencyError`: the command line prints its message,
    which says what to install, as one line.
    """
    monkeypatch.setattr(duckdb, "__version__", version)
    monkeypatch.setattr(duckdb, "connect", _must_not_connect)

    with pytest.raises(UnsupportedDependencyError, match=r"1\.5\.3") as caught:
        filter_by_sql(_frame(), "true")
    assert version in str(caught.value) or version == ""


@pytest.mark.parametrize(
    "version",
    [
        "1.5.3",
        "1.5.3.post1",
        "1.5.4-12-gabcdef",
        "v1.5.3",
        " 1.5.3 ",
        "1.5.3+local",
        "1.5.4.dev1",
        "1.5.10",
        "1.10.0",
        "2.0.1",
    ],
)
def test_a_duckdb_of_1_5_3_or_newer_is_accepted_however_the_version_is_written(version: str) -> None:
    """Restriction: the version is read tolerantly, so a build of a release that is new enough is not refused."""
    _require_supported_duckdb(SimpleNamespace(__version__=version))  # ty: ignore[invalid-argument-type]


def test_the_export_to_duckdb_does_not_ask_the_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The export keeps working: it needs no more than the one release the `duckdb` extra names."""
    monkeypatch.setattr(duckdb, "__version__", "1.5.2")
    target = f"duckdb:///{(tmp_path / 'out.duckdb').as_posix()}?table=weather"

    ExportMixin(df=_frame().drop("vals")).to_target(target)

    con = duckdb.connect(str(tmp_path / "out.duckdb"))
    try:
        assert con.execute("SELECT count(*) FROM weather").fetchall() == [(1,)]
    finally:
        con.close()


#: the settings of `_open_connection` with the value each must read, written here and not read from the module, so
#: that removing one from it fails this test
EXPECTED_SETTINGS = {
    "autoinstall_known_extensions": "false",
    "autoload_known_extensions": "false",
    "allow_community_extensions": "false",
    "allow_persistent_secrets": "false",
    "secret_directory": "",
    "enable_external_access": "false",
    "lock_configuration": "true",
    "threads": "1",
    "max_temp_directory_size": "0 bytes",
    "temp_directory": "",
}


#: only on the releases that have them
EXPECTED_SINCE_2_0 = {"async_threads": "0", "allow_extension_repositories": "forbidden"}


@pytest.mark.parametrize("name", [*EXPECTED_SETTINGS, *EXPECTED_SINCE_2_0])
def test_each_setting_of_the_connection_is_set(connection: duckdb.DuckDBPyConnection, name: str) -> None:
    """Restriction: the connection of the filter has each of these settings, where the release has it."""
    rows = connection.execute("SELECT value FROM duckdb_settings() WHERE name = ?", [name]).fetchall()
    if not rows:
        assert name in EXPECTED_SINCE_2_0, f"{name} is gone from DuckDB {duckdb.__version__}"
        pytest.skip(f"DuckDB {duckdb.__version__} has no {name}")
    expected = {**EXPECTED_SETTINGS, **EXPECTED_SINCE_2_0}[name]
    assert (rows[0][0] or "") == expected


@pytest.mark.parametrize(
    "statement",
    [
        "SET autoinstall_known_extensions = true",
        "SET autoload_known_extensions = true",
        "SET allow_community_extensions = true",
        "SET allow_persistent_secrets = true",
        "SET secret_directory = '.'",
        "SET enable_external_access = true",
        "SET lock_configuration = false",
        "RESET enable_external_access",
        "PRAGMA enable_external_access = true",
        "SET threads = 8",
        "SET memory_limit = '100GB'",
        "SET temp_directory = '.tmp'",
        "SET max_temp_directory_size = '10GB'",
        "SET custom_extension_repository = 'http://127.0.0.1:9'",
        "SET extension_directory = '.'",
        "SET home_directory = '/'",
    ],
)
def test_the_configuration_of_the_connection_is_locked(connection: duckdb.DuckDBPyConnection, statement: str) -> None:
    """Restriction: no setting of the connection can be changed once it is open, whatever runs on it."""
    with pytest.raises(duckdb.InvalidInputException, match="configuration has been locked"):
        connection.execute(statement)


def test_a_connection_that_stores_no_secret_writes_none(host: SimpleNamespace) -> None:
    """Control: a persistent secret is a file, unless the setting is off.

    The directory is set, as DuckDB on Windows does not take the home directory from this process's environment and
    would write the control's secret to the one of whoever runs the test.
    """
    directory = f"SET secret_directory = '{(host.home / 'secrets').as_posix()}'"
    control = duckdb.connect()
    try:
        control.execute(directory)
        control.execute("CREATE PERSISTENT SECRET s (TYPE http, BEARER_TOKEN 'x')")
    finally:
        control.close()
    assert [path for path in host.home.rglob("*") if path.is_file()], "the control wrote no secret"
    for path in list(host.home.rglob("*")):
        if path.is_file():
            path.unlink()

    quiet = duckdb.connect(config={"allow_persistent_secrets": False})
    try:
        quiet.execute(directory)
        with pytest.raises(duckdb.InvalidInputException, match="Persistent secrets are disabled"):
            quiet.execute("CREATE PERSISTENT SECRET s (TYPE http, BEARER_TOKEN 'x')")
    finally:
        quiet.close()
    assert [path for path in host.home.rglob("*") if path.is_file()] == []


#: conditions of the documentation, the examples, the command line's help and the tests of the repository, each with
#: the station ids it keeps of `_documented_frame` (01048, then 00001)
DOCUMENTED = {
    "parameter='temperature_air_2m' AND value < -7.0;": ["01048"],
    "parameter='wind_gust_max' AND value > 20.0": ["00001"],
    "wind_gust_max > 20.0": ["01048"],
    "region='Sachsen'": ["01048"],
    "region = 'Sachsen'": ["01048"],
    "lower(name) LIKE lower('%dresden%')": ["00001"],
    "name LIKE 'Dre%'": ["00001"],
    "name = 'Cottbus'": ["01048"],
    "station_id = '01048'": ["01048"],
    "station_id IN ('00001', '00002')": ["00001"],
    "value > 2": ["00001"],
    "value > 100": [],
    "latitude > 45": ["01048", "00001"],
    "timestamp < '2021-01-02'": ["01048", "00001"],
    "timestamp > '2021-01-01'": ["01048"],
    "timestamp >= '2020-01-01' AND timestamp < '2022-01-01'": ["01048"],
    "nrfa_id = '52017'": ["01048"],
    "site_id = 'F7000001'": ["01048"],
    "short_code = '37'": ["01048"],
    "true": ["01048", "00001"],
    "value>1": ["00001"],
    "state='Sachsen'": ["01048"],
}


def _documented_frame() -> pl.DataFrame:
    """Give two stations that have the columns of the documented conditions, each condition matching one or both."""
    return pl.DataFrame(
        {
            "station_id": ["01048", "00001"],
            "name": ["Cottbus", "Dresden"],
            "region": ["Sachsen", "Bayern"],
            "state": ["Sachsen", "Bayern"],
            "parameter": ["temperature_air_2m", "wind_gust_max"],
            "value": [-8.0, 21.0],
            "wind_gust_max": [25.0, 10.0],
            "latitude": [51.0, 46.0],
            "timestamp": [dt.datetime(2021, 1, 1, 12, tzinfo=dt.UTC), dt.datetime(2019, 6, 1, tzinfo=dt.UTC)],
            "nrfa_id": ["52017", "1"],
            "site_id": ["F7000001", "x"],
            "short_code": ["37", "1"],
        }
    )


@pytest.mark.parametrize(("clause", "expected"), DOCUMENTED.items(), ids=list(DOCUMENTED))
def test_the_documented_conditions_run_on_a_frame(clause: str, expected: list[str]) -> None:
    """The conditions of the documentation filter a frame that has their columns, end to end, to the rows they name."""
    kept = filter_by_sql(_documented_frame(), clause).get_column("station_id").to_list()

    assert kept == expected


@pytest.mark.parametrize(
    "clause",
    [
        "true; SELECT * FROM duckdb_settings()",
        "true; CREATE TABLE t AS SELECT 1",
        "true; SET enable_external_access = true",
        "true; INSTALL httpfs",
        "true; LOAD httpfs",
        "true; ATTACH 'x.db'",
        "true; COPY df TO 'x.csv'",
        "true; PRAGMA enable_profiling",
        "true; EXPORT DATABASE 'x'",
        "true) ; SELECT 1 --",
        "true) UNION SELECT 1 --",
        "true\n; SET enable_external_access = true",
        "x IS NULL; --",
        "true ORDER BY elevation",
        "true LIMIT 0",
        "elevation > 1 WHERE false",
        "elevation > 1 FROM range(3)",
        "elevation > 1 AS x",
        "elevation > 1 FETCH FIRST 1 ROWS ONLY",
        "elevation > 1 OFFSET 1",
        "elevation > 1 GROUP BY elevation",
        "elevation > 1 HAVING true",
        "elevation > 1 QUALIFY true",
        "elevation > 1 USING SAMPLE 1",
        "elevation > 1 UNION SELECT true",
        "elevation > 1 WITH x AS (SELECT 1) SELECT 1",
    ],
)
def test_a_clause_pasted_into_a_statement_is_caught(clause: str) -> None:
    """Restriction: the clause is one condition in parentheses, so what is pasted after it is a `ParserException`.

    A condition that pasted into a statement would be a second statement, a `FROM`, a `LIMIT`, which DuckDB then
    runs or drops without a word.
    """
    with pytest.raises(duckdb.ParserException):
        filter_by_sql(_frame(), clause)


@pytest.mark.parametrize("clause", ["region = 'Bayern';", "region = 'Bayern' ; ; ", "region = 'Bayern' -- Freyung"])
def test_a_trailing_semicolon_or_comment_is_taken(clause: str) -> None:
    """A trailing semicolon, as a clause copied from a statement has, and a trailing comment are no second thing."""
    assert filter_by_sql(_frame(), clause).get_column("station_id").to_list() == ["01048"]


def test_a_condition_that_closes_the_parentheses_it_is_wrapped_in_stays_one_expression() -> None:
    """Restriction: what closes the parenthesis and opens another is still one expression, on the same rows."""
    frame = pl.DataFrame({"station_id": ["01048", "01050"], "elevation": [645.0, 10.0]})
    assert filter_by_sql(frame, "elevation > 100) OR (elevation < 0").get_column("station_id").to_list() == ["01048"]
    assert filter_by_sql(frame, "elevation > 100 /* ) */").height == 1
    assert filter_by_sql(frame, "elevation > 100 --) \n").height == 1
    # two expressions in parentheses are not one
    with pytest.raises(duckdb.Error):
        filter_by_sql(frame, "elevation > 100) , (elevation < 0")


@pytest.mark.parametrize("name", FILE_FUNCTIONS)
def test_the_functions_that_read_a_file_are_refused_by_the_connection(
    host: SimpleNamespace, connection: duckdb.DuckDBPyConnection, name: str
) -> None:
    """Restriction: reading, listing and sniffing a file is a `PermissionException` of the connection."""
    known = connection.execute(
        "SELECT count(*) FROM duckdb_functions() WHERE function_name = ? AND function_type IN ('table', 'table_macro')",
        [name],
    ).fetchone()
    if not known or not known[0]:
        pytest.skip(f"DuckDB {duckdb.__version__} has no table function {name}")
    for path in (host.csv, "secret.csv", "./secret.csv", "file:" + host.csv):
        with pytest.raises(duckdb.PermissionException, match="file system operations are disabled"):
            connection.execute(f"SELECT count(*) FROM {name}('{path}')")
    _left_untouched(host)


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT count(*) FROM '{csv}'",
        'SELECT count(*) FROM "{csv}"',
        "SELECT count(*) FROM read_csv(concat('{dir}', '/', 'secret.csv'))",
        "SELECT count(*) FROM read_csv(list_value('{csv}'))",
        "SELECT count(*) FROM read_csv('{csv}', columns = {{'a': 'VARCHAR'}}, header = false)",
        "SELECT count(*) FROM read_csv('{csv}', filename = true, hive_partitioning = true)",
        "SELECT count(*) FROM query('SELECT * FROM read_csv(''{csv}'')')",
        "SELECT count(*) FROM query('FROM ''{csv}''')",
        "SELECT count(*) FROM json_execute_serialized_sql(json_serialize_sql('SELECT * FROM read_csv(''{csv}'')'))",
        "SELECT count(*) FROM glob('.tmp/*')",
        "SELECT count(*) FROM glob('{dir}/*')",
        "SELECT count(*) FROM glob('/*')",
        "SELECT count(*) FROM read_text('.tmp/secret.txt')",
    ],
)
def test_the_connection_refuses_a_file_however_it_is_asked_for(
    host: SimpleNamespace, connection: duckdb.DuckDBPyConnection, statement: str
) -> None:
    """Restriction: a file stays out of reach of the connection whichever way a statement asks for it."""
    host.work.joinpath(".tmp").mkdir()
    host.work.joinpath(".tmp", "secret.txt").write_text(CANARY)
    with pytest.raises(duckdb.PermissionException):
        connection.execute(statement.format(csv=host.csv, dir=host.work.as_posix()))
    _left_untouched(host, also=(".tmp",))


def test_the_connection_cannot_see_the_python_objects_of_the_caller(connection: duckdb.DuckDBPyConnection) -> None:
    """Restriction: the frame is the one table; DuckDB's replacement scan of Python variables is off."""
    secret_local = pl.DataFrame({"a": [1, 2, 3]})  # noqa: F841
    control = duckdb.connect()
    try:
        assert control.sql("SELECT count(*) FROM secret_local").fetchall() == [(3,)]
    finally:
        control.close()
    for statement in (
        "SELECT count(*) FROM secret_local",
        "SELECT count(*) FROM main.secret_local",
        "SELECT count(*) FROM query_table('secret_local')",
        "SELECT count(*) FROM query('SELECT * FROM secret_local')",
    ):
        with pytest.raises(duckdb.CatalogException):
            connection.execute(statement)


def test_the_connection_makes_no_connection(
    host: SimpleNamespace, connection: duckdb.DuckDBPyConnection, loopback: _Loopback
) -> None:
    """Restriction: a URL is refused before a connection is made, which a listener on 127.0.0.1 counts."""
    url = loopback.url
    for statement in (
        f"SELECT count(*) FROM read_csv('{url}/x.csv')",
        f"SELECT count(*) FROM read_json('{url}/x.json')",
        f"SELECT count(*) FROM read_parquet('{url}/x.parquet')",
        f"SELECT count(*) FROM read_text('{url}/x.txt')",
        f"SELECT count(*) FROM '{url}/x.csv'",
        f"SELECT count(*) FROM glob('{url}/*')",
        f"SELECT count(*) FROM read_csv('{url.replace('http', 'https')}/x.csv')",
        f"SELECT count(*) FROM read_csv('s3://127.0.0.1:{loopback.listener.port}/x.csv')",
    ):
        with pytest.raises(duckdb.PermissionException, match="file system operations are disabled"):
            connection.execute(statement)
    for statement in (f"INSTALL httpfs FROM '{url}'", f"COPY df TO '{url}/out.csv'"):
        with pytest.raises(duckdb.PermissionException):
            connection.execute(statement)
    assert loopback.hits() == 0
    _left_untouched(host)


#: statements the parser keeps out of a condition, run on the connection itself: each is refused there too, with the
#: class that DuckDB refuses it with. Where DuckDB 1.x does not know the statement it is a `ParserException`, and a
#: statement of DuckDB 2.0 is run, and refused, as one of the others
_PERMISSION = (duckdb.PermissionException,)


_KNOWN_FROM_2_0 = (duckdb.ParserException, duckdb.PermissionException)


REFUSED_STATEMENTS = [
    ("ATTACH 'x.db' AS x", _PERMISSION),
    ("CREATE EXTENSION REPOSITORY r WITH PREFIX 'http://127.0.0.1:1'", _KNOWN_FROM_2_0),
    ("COPY df TO 'out.csv'", _PERMISSION),
    ("COPY df TO 'out.parquet' (FORMAT parquet)", _PERMISSION),
    ("COPY (SELECT * FROM df) TO 'out.json' (FORMAT json)", _PERMISSION),
    ("EXPORT DATABASE 'out'", _PERMISSION),
    ("CREATE TEMP TABLE t AS SELECT * FROM 'secret.csv'", _PERMISSION),
    ("CREATE VIEW v AS SELECT * FROM read_csv('secret.csv')", _PERMISSION),
    ("SELECT * FROM 'secret.csv'", _PERMISSION),
    ("SELECT * FROM glob('*')", _PERMISSION),
    ("SELECT * FROM duckdb_extensions()", _PERMISSION),
    ("EXPLAIN ANALYZE SELECT * FROM read_csv('secret.csv')", _PERMISSION),
    ("DESCRIBE SELECT * FROM read_csv('secret.csv')", _PERMISSION),
]


@pytest.mark.parametrize(("statement", "refused_as"), REFUSED_STATEMENTS)
def test_the_connection_refuses_what_the_parser_keeps_out(
    host: SimpleNamespace,
    connection: duckdb.DuckDBPyConnection,
    loopback: _Loopback,
    statement: str,
    refused_as: tuple[type[Exception], ...],
) -> None:
    """Restriction: a statement, were it run, reaches nothing and writes nothing.

    After it, on the one connection, the settings are as set, the secret is still out of reach, nothing was
    written and nothing was connected to.
    """
    with pytest.raises(refused_as):
        connection.execute(statement.replace("127.0.0.1:1", f"127.0.0.1:{loopback.listener.port}"))
    settings = dict(
        connection.execute(
            "SELECT name, value FROM duckdb_settings() WHERE name IN ('enable_external_access', 'lock_configuration')"
        ).fetchall()
    )
    assert settings == {"enable_external_access": "false", "lock_configuration": "true"}
    with pytest.raises(duckdb.PermissionException):
        connection.execute(f"SELECT * FROM read_text('{host.txt}')")
    assert loopback.hits() == 0
    _left_untouched(host)


def test_a_condition_stays_within_its_memory() -> None:
    """Restriction: a condition that builds more than the limit allows is refused where it is built.

    The limit is 1 GiB plus the size of the frame, as the check is of the connection that the filter opens: a list of
    200 million integers needs 1.6 GB.
    """
    with pytest.raises(duckdb.OutOfMemoryException):
        filter_by_sql(_frame(), "(SELECT len(list(i)) FROM range(200000000) t(i)) > 0")
    assert filter_by_sql(_frame(), "(SELECT len(list(i)) FROM range(20000000) t(i)) > 0").height == 1
