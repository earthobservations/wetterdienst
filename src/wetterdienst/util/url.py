# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Helper class to support ``IoAccessor.export()``."""

import re
from urllib.parse import parse_qs, unquote, urlparse

from wetterdienst.exceptions import ExportRefusedError

# targets that name a file rather than a server, and so carry no credentials; a Windows path
# such as `file://C:/data@x.csv` would otherwise read as user `C` with a password. Matched
# exactly: a dialect such as `sqlite+pysqlcipher` takes its passphrase from the password slot
_PATH_SCHEMES = frozenset({"file", "duckdb", "sqlite"})


def redact_password(url: str) -> str:
    """Give back a connection string with its password replaced by ``***``, for a log line.

    The password slot is where a SQL or CrateDB target carries its password and where the
    InfluxDB 2 and 3 targets carry their API token, and the CLI logs at INFO by default, so a
    target printed verbatim lands in cron mail, journald or a CI log. The username stays: it says
    which account was used and is no secret. The rest comes back as given.

    Every sink reads the target as SQLAlchemy does (`ConnectionString`), but ``urlparse``, the
    other common reading, disagrees with it on an unencoded ``@``, ``/``, ``#`` or ``?``, so
    whatever either reads as the password is hidden. Both start it after the first ``:``,
    provided no ``/`` comes before it. SQLAlchemy ends it at the first ``@`` after that, so a
    password holding a ``/`` is still found and an Azure-style username such as ``user@server``
    is kept; ``urlparse`` ends it at the last ``@`` before the host part ends at a ``/``, ``?``
    or ``#``, so a password holding an ``@`` is found.
    A target with no password but a ``host:port`` followed by an ``@`` in its path or query is cut
    at that ``@``, as SQLAlchemy reads it. Nothing here raises, so a log line naming a malformed
    target still prints.
    """
    scheme, separator, rest = url.partition("://")
    username, colon, _ = rest.partition(":")
    if not separator or scheme.lower() in _PATH_SCHEMES or not colon or "/" in username:
        return url
    start = len(username) + 1
    host_end = min((i for i in (rest.find(c) for c in "/?#") if i != -1), default=len(rest))
    end = max(rest.find("@", start), rest.rfind("@", start, host_end))
    if end == -1:
        return url
    return f"{scheme}://{username}:***{rest[end:]}"


# the pattern SQLAlchemy's `make_url` reads a URL with (`sqlalchemy/engine/url.py`), so that
# the sinks that do not connect through SQLAlchemy read a target as the ones that do. The
# password runs to the first `@`, so it may hold a `/`, `?`, `#` or `:` unencoded
_URL_PATTERN = re.compile(
    r"""
        (?P<name>[\w\+]+)://
        (?:
            (?P<username>[^:/]*)
            (?::(?P<password>[^@]*))?
        @)?
        (?:
            (?:
                \[(?P<ipv6host>[^/\?]+)\] |
                (?P<ipv4host>[^/:\?]+)
            )?
            (?::(?P<port>[^/\?]*))?
        )?
        (?:/(?P<database>[^\?]*))?
        (?:\?(?P<query>.*))?
    """,
    re.VERBOSE,
)

# a file sink is addressed by a path, not read with SQLAlchemy's pattern: a Windows path
# such as `duckdb:///C:\data\dwd.duckdb` would give it a host `C`
_FILE_PREFIXES = ("file://", "duckdb://")


class ConnectionString:
    """Read an export target, once, for every sink.

    A server target is read as SQLAlchemy reads it, whichever sink it is for: InfluxDB and
    CrateDB read it with `urlparse` before, which ends the host part at the first `/`, `?` or
    `#`, so a password holding one was split and its pieces became the port and database, and
    from there a log line. The username, password and database are percent-decoded, as
    SQLAlchemy decodes them. A DuckDB target is a path, and is read with `urlparse`; a file
    target's path is everything after `file://`, so `file://out/data.csv` is relative and
    `file:///data/out.csv` absolute.

    Raises:
        ExportRefusedError: The target is not a URL, names a port that is not a number, or its
            password holds an unencoded `@`. SQLAlchemy ends the password at the first `@`, so
            the rest of it would be read as the host and port; that is told apart from a real
            host by the `@` left in it. The message names no part of the target. A password
            holding an `@` and, after it, a `/` or `?` reads as a shorter password, a host and
            a database or query, and a target with no password but a `host:port` and an `@` in
            its path or query reads as one with a password; no reading of the string can tell
            either from a target that means just that, so such an `@` is written `%40`.

    """

    def __init__(self, url: str) -> None:
        """Initialize a ConnectionString object.

        Args:
            url: The URL to parse.

        """
        self.url_raw = url
        if url.startswith(_FILE_PREFIXES):
            parsed = urlparse(url)
            self._name = parsed.scheme
            self._host = self._port = self._username = self._password = None
            self._database = parsed.path[1:] if parsed.path.startswith("/") else None
            self._query = parsed.query
            # a file target's path is everything after `file://`, as `alerts` and `history` read
            # it: `urlparse` takes the first segment of `file://out/data.csv` as a host and leaves
            # `/data.csv`, so the relative path would land at the root
            self._path = url.removeprefix("file://") if url.startswith("file://") else parsed.path or parsed.netloc
            return
        match = _URL_PATTERN.match(url)
        if match is None:
            msg = "The target is not a URL of the form scheme://[user[:password]@]host[:port][/database][?query]."
            raise ExportRefusedError(msg)
        parts = match.groupdict()
        host = parts["ipv4host"] or parts["ipv6host"]
        port = parts["port"] or None
        if "@" in (host or "") or "@" in (port or ""):
            msg = (
                "The target's password holds an '@' that is not percent-encoded, which ends it "
                "early, so the rest of it would be read as the host and port. Write it as %40."
            )
            raise ExportRefusedError(msg)
        # `int` reads digits such as `²` that a port is not made of, and names them when it fails
        if port is not None and not (port.isascii() and port.isdigit()):
            msg = "The target's port is not a number."
            raise ExportRefusedError(msg)
        self._name: str = parts["name"]
        self._host: str | None = host
        self._port: int | None = None if port is None else int(port)
        self._username: str | None = None if parts["username"] is None else unquote(parts["username"])
        self._password: str | None = None if parts["password"] is None else unquote(parts["password"])
        self._database: str | None = None if parts["database"] is None else unquote(parts["database"])
        self._query: str = parts["query"] or ""
        self._path: str = self._database or ""

    @property
    def protocol(self) -> str:
        """Get the protocol from the URL."""
        return self._name.lower()

    @property
    def host(self) -> str | None:
        """Get the host from the URL."""
        return self._host

    @property
    def port(self) -> int | None:
        """Get the port from the URL."""
        return self._port

    @property
    def username(self) -> str | None:
        """Get the username from the URL, percent-decoded."""
        return self._username

    @property
    def password(self) -> str | None:
        """Get the password from the URL, percent-decoded."""
        return self._password

    @property
    def database(self) -> str:
        """Get the database name from the URL."""
        # Try to get database name from query parameter, then from the URL path.
        return self.get_query_param("database") or self.get_query_param("bucket") or self._database or "dwd"

    @property
    def table(self) -> str:
        """Get the table name from the URL."""
        return self.get_query_param("table") or "weather"

    @property
    def path(self) -> str:
        """Get the path from the URL."""
        return self._path

    def get_query_param(self, name: str) -> str | None:
        """Get a query parameter from the URL."""
        query = parse_qs(self._query)
        try:
            return query[name][0]
        except (KeyError, IndexError):
            return None
