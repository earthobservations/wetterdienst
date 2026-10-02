# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Helper class to support ``IoAccessor.export()``."""

from urllib.parse import parse_qs, unquote, urlparse

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

    The SQL sinks read the target with SQLAlchemy and the others with ``urlparse``, and the two
    disagree on an unencoded ``@``, ``/``, ``#`` or ``?``, so whatever either reads as the password
    is hidden. Both start it after the first ``:``, provided no ``/`` comes before it. SQLAlchemy
    ends it at the first ``@`` after that, so a password holding a ``/`` is still found and an
    Azure-style username such as ``user@server`` is kept; ``urlparse`` ends it at the last ``@``
    before the host part ends at a ``/``, ``?`` or ``#``, so a password holding an ``@`` is found.
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


def unencoded_password_delimiters(url: str) -> frozenset[str]:
    """Name the delimiters a target's password may hold unencoded, of ``/``, ``?``, ``#`` and ``@``.

    The two parsers that read a target split such a password differently. ``urlparse`` ends the
    host part at the first ``/``, ``?`` or ``#``, so a password holding one of them is cut there
    and the rest is read as the path, query or fragment. SQLAlchemy ends the password at the
    first ``@``, so a password holding one is cut there and the rest is read as the host and
    port. Either way the target is read with the wrong host, port, password, database or table.

    The password starts after the first ``:``, provided no ``/`` comes before it and the host is
    not an IPv6 literal. Where it ends cannot be told from the string once it may hold an ``@``,
    so this takes the last ``@`` before the query: a password holding an ``@`` is found whatever
    follows it up to there, and an ``@`` in the query, as in ``?application_name=me@host``, is
    not counted. A ``host:port`` whose first ``@`` is in the query has no password, so
    ``influxdb://localhost:8086/?table=a@b`` names nothing. What this cannot find: a password
    holding an ``@`` with a ``?`` or ``#`` after it, or one of digits followed by a ``?`` or
    ``#``, reads as a shorter password or as a port. Nothing here raises, and nothing of the
    password comes back but which delimiters it may hold.
    """
    scheme, separator, rest = url.partition("://")
    username, colon, _ = rest.partition(":")
    if not separator or scheme.lower() in _PATH_SCHEMES or not colon or "/" in username or username.startswith("["):
        return frozenset()
    start = len(username) + 1
    first = rest.find("@", start)
    if first == -1:
        return frozenset()
    host_end = min((i for i in (rest.find(c, start) for c in "/?#") if i != -1), default=len(rest))
    if rest[start:host_end].isdigit() and any(c in rest[start:first] for c in "?#"):
        return frozenset()
    query = min((i for i in (rest.find(c, first) for c in "?#") if i != -1), default=len(rest))
    end = rest.rfind("@", start, query)
    return frozenset(c for c in "/?#@" if c in rest[start:end])


class ConnectionString:
    """Helper class to support ``IoAccessor.export()``."""

    def __init__(self, url: str) -> None:
        """Initialize a ConnectionString object.

        Args:
            url: The URL to parse.

        """
        self.url_raw = url
        self.url = urlparse(url)

    @property
    def protocol(self) -> str:
        """Get the protocol from the URL."""
        return self.url.scheme

    @property
    def host(self) -> str | None:
        """Get the host from the URL."""
        return self.url.hostname

    @property
    def port(self) -> int | None:
        """Get the port from the URL."""
        return self.url.port

    @property
    def username(self) -> str | None:
        """Get the username from the URL, percent-decoded as SQLAlchemy decodes it."""
        return None if self.url.username is None else unquote(self.url.username)

    @property
    def password(self) -> str | None:
        """Get the password from the URL, percent-decoded as SQLAlchemy decodes it."""
        return None if self.url.password is None else unquote(self.url.password)

    @property
    def database(self) -> str:
        """Get the database name from the URL."""
        # Try to get database name from query parameter.
        database = self.get_query_param("database") or self.get_query_param("bucket")

        # Try to get database name from URL path.
        if not database and self.url.path.startswith("/"):
            database = self.url.path[1:]

        return database or "dwd"

    @property
    def table(self) -> str:
        """Get the table name from the URL."""
        return self.get_query_param("table") or "weather"

    @property
    def path(self) -> str:
        """Get the path from the URL."""
        return self.url.path or self.url.netloc

    def get_query_param(self, name: str) -> str | None:
        """Get a query parameter from the URL."""
        query = parse_qs(self.url.query)
        try:
            return query[name][0]
        except (KeyError, IndexError):
            return None
