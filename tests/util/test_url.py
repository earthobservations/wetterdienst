# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for URL utilities."""

from pathlib import Path

import pytest

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
        pytest.param(
            "postgresql://scott@db:5432/dwd?opt=a@b",
            "postgresql://scott@db:5432/dwd?opt=a@b",
            id="username-only-at-in-query",
        ),
        # a path is not a password, whatever it holds
        pytest.param("file://C:/data@x.csv", "file://C:/data@x.csv", id="file-two-slashes"),
        pytest.param("duckdb://C:/data/obs@1.duckdb", "duckdb://C:/data/obs@1.duckdb", id="duckdb-two-slashes"),
        pytest.param("sqlite+pysqlite://C:/obs@1.db", "sqlite+pysqlite://C:/obs@1.db", id="sqlite-two-slashes"),
        # `urlparse` raises on this; the log line naming it must not
        pytest.param("postgresql://u:p@[::1/db", "postgresql://u:***@[::1/db", id="malformed-ipv6"),
    ],
)
def test_redact_password_hides_the_password_and_keeps_the_rest(url: str, redacted: str) -> None:
    """The password slot reads `***`; the username, host, path and query read as they were given."""
    assert redact_password(url) == redacted
