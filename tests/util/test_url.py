# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for URL utilities."""

from pathlib import Path

import pytest

from wetterdienst.util.url import ConnectionString


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
