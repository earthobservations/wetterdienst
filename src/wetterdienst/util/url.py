# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Helper class to support ``IoAccessor.export()``."""

from urllib.parse import parse_qs, urlparse

# targets that name a file rather than a server, and so carry no credentials; a Windows path
# such as `file://C:/data@x.csv` would otherwise read as user `C` with a password
_PATH_SCHEMES = frozenset({"file", "duckdb", "sqlite"})


def redact_password(url: str) -> str:
    """Give back a connection string with its password replaced by ``***``, for a log line.

    The password slot is where a SQL or CrateDB target carries its password and where the
    InfluxDB 2 and 3 targets carry their API token, and the CLI logs at INFO by default, so a
    target printed verbatim lands in cron mail, journald or a CI log. The username stays: it says
    which account was used and is no secret. Everything else comes back exactly as given.

    The string is read as SQLAlchemy reads it rather than as ``urlparse`` does: SQLAlchemy takes a
    password holding an unencoded ``/``, ``#`` or ``?`` and connects with it, where ``urlparse``
    ends the host part at that character and finds no password at all. So the username runs to
    the first ``:`` and holds no ``/`` or ``@``, and the password from there to the first ``@``,
    or to the last ``@`` before the host part ends at a ``/``, ``?`` or ``#``, which is where
    ``urlparse`` ends a password holding an ``@`` itself. An ``@`` in the path or query is left
    alone, except in a target with no password whose ``host:port`` is followed by one: SQLAlchemy
    reads the port and what follows up to that ``@`` as a password, and so it is hidden too.
    Nothing here raises, so a log line naming a malformed target still prints.
    """
    scheme, separator, rest = url.partition("://")
    username, colon, after = rest.partition(":")
    first_at = after.find("@")
    if (
        not separator
        or scheme.split("+")[0].lower() in _PATH_SCHEMES
        or not colon
        or first_at == -1
        or "/" in username
        or "@" in username
    ):
        return url
    host_end = min((i for i in (after.find(c, first_at) for c in "/?#") if i != -1), default=len(after))
    return f"{scheme}://{username}:***{after[after.rfind('@', 0, host_end) :]}"


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
        """Get the username from the URL."""
        return self.url.username

    @property
    def password(self) -> str | None:
        """Get the password from the URL."""
        return self.url.password

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
