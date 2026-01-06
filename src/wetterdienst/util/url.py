# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Helper class to support ``IoAccessor.export()``."""

from urllib.parse import parse_qs, urlparse


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
    def host(self) -> str:
        """Get the host from the URL."""
        return self.url.hostname

    @property
    def port(self) -> int:
        """Get the port from the URL."""
        return self.url.port

    @property
    def username(self) -> str:
        """Get the username from the URL."""
        return self.url.username

    @property
    def password(self) -> str:
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
