# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for URL utilities."""

from pathlib import Path

import pytest

from wetterdienst.exceptions import ExportRefusedError
from wetterdienst.util.url import ConnectionString, redact_password


def test_connectionstring_database_from_path() -> None:
    """Test if database can be set via path."""
    url = "foobar://host:1234/dbname"
    cs = ConnectionString(url)
    assert cs.protocol == "foobar"
    assert cs.host == "host"
    assert cs.port == 1234
    assert cs.database == "dbname"
    assert cs.table == "weather"


def test_connectionstring_database_from_query_param() -> None:
    """Test if database can be set via query parameter."""
    url = "foobar://host:1234/?database=dbname"
    cs = ConnectionString(url)
    assert cs.database == "dbname"


def test_connectionstring_username_password_host() -> None:
    """Test if username, password and host can be set."""
    url = "foobar://username:password@host/?database=dbname"
    cs = ConnectionString(url)
    assert cs.username == "username"
    assert cs.password == "password"  # noqa: S105
    assert cs.host == "host"


def test_connectionstring_table_from_query_param() -> None:
    """Test if table can be set via query parameter."""
    url = "foobar://host:1234/?database=dbname&table=tablename"
    cs = ConnectionString(url)
    assert cs.table == "tablename"


def test_connectionstring_temporary_file(tmp_path: Path) -> None:
    """Test if a temporary file can be used as a connection string."""
    filepath = tmp_path.joinpath("foobar.txt")
    url = f"file://{filepath}"
    cs = ConnectionString(url)
    assert cs.path == str(filepath)


@pytest.mark.parametrize(
    "database",
    [
        "/var/folders/rk/dwd_obs_daily_climate_summary.duckdb",
        r"C:\Users\RUNNER~1\AppData\Local\Temp\dwd_obs_daily_climate_summary.duckdb",
        "dwd.duckdb",
    ],
    ids=["posix-absolute", "windows-absolute", "relative"],
)
def test_connectionstring_gives_back_the_file_path_it_was_given(database: str) -> None:
    r"""A file sink is addressed by a path, and has to read back as the same path on every platform.

    The database is the URL path with one leading slash removed, so exactly one slash belongs
    between the scheme and the path -- which a POSIX path then supplies itself and a Windows path
    does not. One slash too many is silent on POSIX, where a doubled `//` still resolves, and is
    `Cannot open file "//C:\..."` on Windows, DuckDB reading the leftover slash as a UNC share.
    """
    assert ConnectionString(f"duckdb:///{database}?table=stations").database == database


@pytest.mark.parametrize(
    ("url", "redacted"),
    [
        pytest.param(
            "postgresql://scott:tiger@db.example.org:5432/dwd?table=weather",
            "postgresql://scott:***@db.example.org:5432/dwd?table=weather",
            id="sql",
        ),
        pytest.param(
            "influxdb2://acme:t5PJry6Tye==@localhost/?database=dwd&table=weather",
            "influxdb2://acme:***@localhost/?database=dwd&table=weather",
            id="influxdb2-token",
        ),
        pytest.param("mysql://:secret@localhost/dwd", "mysql://:***@localhost/dwd", id="no-username"),
        pytest.param("mysql://root:p@ss:w@rd@localhost/dwd", "mysql://root:***@localhost/dwd", id="at-in-password"),
        pytest.param(
            "crate://crate@localhost/dwd?table=weather", "crate://crate@localhost/dwd?table=weather", id="no-password"
        ),
        pytest.param("duckdb:///dwd.duckdb?table=weather", "duckdb:///dwd.duckdb?table=weather", id="file"),
        pytest.param("file:///C:/data/obs@1.csv", "file:///C:/data/obs@1.csv", id="file-drive-letter-and-at"),
        pytest.param("influxdb://localhost/?database=dwd", "influxdb://localhost/?database=dwd", id="no-userinfo"),
        # `urlparse` ends the host part at the first `/`, `#` or `?` and so finds no password in
        # these, while SQLAlchemy connects with `pa/ss`, `p#ss` and `pa?ss` as the password
        pytest.param("postgresql://scott:pa/ss@db/dwd", "postgresql://scott:***@db/dwd", id="slash-in-password"),
        pytest.param(
            "postgresql://scott:p#ss@db/dwd?table=weather",
            "postgresql://scott:***@db/dwd?table=weather",
            id="hash-in-password",
        ),
        pytest.param(
            "postgresql://scott:pa?ss@db/dwd", "postgresql://scott:***@db/dwd", id="question-mark-in-password"
        ),
        pytest.param(
            "influxdb2://acme:ab/cd==@localhost/?database=dwd",
            "influxdb2://acme:***@localhost/?database=dwd",
            id="influxdb2-token-with-slash",
        ),
        # nothing but the password is touched, not even what `urlunparse` would normalise
        pytest.param("PostgreSQL://scott:x@h/db?", "PostgreSQL://scott:***@h/db?", id="kept-verbatim"),
        # an `@` in the path or query is not the end of the password
        pytest.param(
            "postgresql://scott:tiger@db/dwd?table=weather&note=a@b",
            "postgresql://scott:***@db/dwd?table=weather&note=a@b",
            id="at-in-query",
        ),
        pytest.param(
            "postgresql://scott:pa/ss@db/dwd?note=a@b",
            "postgresql://scott:***@db/dwd?note=a@b",
            id="slash-and-at-in-query",
        ),
        # Azure Database for PostgreSQL logs in as `user@server`, which SQLAlchemy connects with
        pytest.param(
            "postgresql://user@srv:secret@srv.postgres.database.azure.com:5432/dwd?sslmode=require",
            "postgresql://user@srv:***@srv.postgres.database.azure.com:5432/dwd?sslmode=require",
            id="at-in-username",
        ),
        # a path is not a password, whatever it holds
        pytest.param("file://C:/data@x.csv", "file://C:/data@x.csv", id="file-two-slashes"),
        pytest.param("duckdb://C:/data/obs@1.duckdb", "duckdb://C:/data/obs@1.duckdb", id="duckdb-two-slashes"),
        pytest.param("sqlite://C:/obs@1.db", "sqlite://C:/obs@1.db", id="sqlite-two-slashes"),
        # but a dialect that takes its passphrase from the password slot is not a plain path
        pytest.param(
            "sqlite+pysqlcipher://:passphrase@/dwd.db?table=weather",
            "sqlite+pysqlcipher://:***@/dwd.db?table=weather",
            id="sqlcipher-passphrase",
        ),
        # `urlparse` raises on this; the log line naming it must not
        pytest.param("postgresql://u:p@[::1/db", "postgresql://u:***@[::1/db", id="malformed-ipv6"),
    ],
)
def test_redact_password_hides_the_password_and_keeps_the_rest(url: str, redacted: str) -> None:
    """The password slot reads `***`; the username, host, path and query read as they were given."""
    assert redact_password(url) == redacted


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://scott:tiger@db.example.org:5432/dwd?table=weather&sslmode=require",
        "postgresql+psycopg2://scott:pa/ss@db/dwd?table=obs",
        "postgresql://scott:pa?ss@db/dwd?table=obs",
        "postgresql://scott:p#ss@db/dwd",
        "postgresql://scott:pa%2Fss%40x@db/dwd",
        "postgresql://user@srv:secret@srv.postgres.database.azure.com:5432/dwd?sslmode=require",
        "postgresql://u:p@[::1]:5432/dwd",
        "postgresql://[::1]:5432/dwd?table=a@b",
        "postgresql://scott:tiger@db/dwd?options=a&options=b",
        "mysql://:secret@localhost/dwd",
        "sqlite:///dwd.sqlite?table=weather",
        "sqlite+pysqlcipher://:passphrase@/dwd.db?table=weather",
        "crate://crate:hun/ter2@localhost:4200/dwd?table=weather",
        "influxdb2://acme:Ab/Cd==@localhost/?database=dwd",
    ],
)
def test_connectionstring_reads_a_target_as_sqlalchemy_does(url: str) -> None:
    """Every sink reads a target as the SQL sinks' SQLAlchemy reads it, so they cannot disagree."""
    sqlalchemy = pytest.importorskip("sqlalchemy")
    assert ConnectionString(url).to_sqlalchemy_url() == sqlalchemy.make_url(url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # `urlparse` ended the host part at the first `/`, `?` or `#` and read port `Ab`
        pytest.param(
            "influxdb2://acme:Ab/Cd==@localhost/?database=dwd",
            ("influxdb2", "localhost", None, "acme", "Ab/Cd==", "dwd", "weather"),
            id="slash",
        ),
        pytest.param(
            "crate://crate:hun?ter#2@localhost:4200/dwd?table=obs",
            ("crate", "localhost", 4200, "crate", "hun?ter#2", "dwd", "obs"),
            id="question-mark-and-hash",
        ),
        pytest.param(
            "influxdb://root:a:b@localhost:8087/obs",
            ("influxdb", "localhost", 8087, "root", "a:b", "obs", "weather"),
            id="colon",
        ),
    ],
)
def test_connectionstring_reads_a_password_holding_delimiters(url: str, expected: tuple) -> None:
    """A `/`, `?`, `#` or `:` in a password stays in it, and the host, port and database are read."""
    cs = ConnectionString(url)
    assert (cs.protocol, cs.host, cs.port, cs.username, cs.password, cs.database, cs.table) == expected


@pytest.mark.parametrize(
    ("url", "pieces"),
    [
        pytest.param("postgresql://scott:pw-HEAD@ss:pw-TAIL@db/dwd", ["pw-HEAD", "ss:pw-TAIL"], id="at-then-colon"),
        pytest.param("influxdb2://acme:tok-HEAD@tok-TAIL@localhost/", ["tok-HEAD", "tok-TAIL"], id="at"),
    ],
)
def test_connectionstring_refuses_a_password_holding_an_unencoded_at(url: str, pieces: list[str]) -> None:
    """An `@` that would end the password leaves an `@` in the host or port; the refusal names neither."""
    with pytest.raises(ExportRefusedError, match="%40") as excinfo:
        ConnectionString(url)
    for piece in pieces:
        assert piece not in str(excinfo.value)


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("not a url:secret", id="no-scheme"),
        pytest.param("influxdb2://acme@localhost:se-cret/", id="port-not-a-number"),
    ],
)
def test_connectionstring_refuses_a_target_it_cannot_read_without_naming_it(url: str) -> None:
    """A target that is not a URL, or names a port that is not a number, is refused, naming neither."""
    with pytest.raises(ExportRefusedError) as excinfo:
        ConnectionString(url)
    assert "secret" not in str(excinfo.value)
    assert "se-cret" not in str(excinfo.value)


def test_connectionstring_decodes_a_percent_encoded_username_and_password() -> None:
    """An encoded password reaches InfluxDB decoded, as SQLAlchemy decodes one for the SQL sinks.

    Without it, the advice to write a `/` in a token as `%2F` would send InfluxDB `Ab%2FCd==`.
    """
    cs = ConnectionString("influxdb2://ac%40me:Ab%2FCd%3D%3D@localhost/?database=dwd")
    assert cs.username == "ac@me"
    assert cs.password == "Ab/Cd=="  # noqa: S105
    assert ConnectionString("influxdb://localhost/?database=dwd").password is None
