# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from urllib.parse import parse_qs, urlparse


class ConnectionString:
    """
    Helper class to support ``IoAccessor.export()``.
    """

    def __init__(self, url):
        self.url_raw = url
        self.url = urlparse(url)

    @property
    def protocol(self):
        return self.url.scheme

    @property
    def host(self):
        return self.url.hostname

    @property
    def port(self):
        return self.url.port

    @property
    def username(self):
        return self.url.username

    @property
    def password(self):
        return self.url.password

    @property
    def database(self):
        # Try to get database name from query parameter.
        database = self.get_query_param("database") or self.get_query_param("bucket")

        # Try to get database name from URL path.
        if not database:
            if self.url.path.startswith("/"):
                database = self.url.path[1:]

        return database or "dwd"

    @property
    def table(self):
        return self.get_query_param("table") or "weather"

    @property
    def path(self):
        return self.url.path or self.url.netloc

    def get_query_param(self, name):
        query = parse_qs(self.url.query)
        try:
            return query[name][0]
        except (KeyError, IndexError):
            return None
