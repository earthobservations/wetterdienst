# -*- coding: utf-8 -*-
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

    def get_database(self):

        # Try to get database name from query parameter.
        database = self.get_query_param("database")

        # Try to get database name from URL path.
        if database is None:
            if self.url.path.startswith("/"):
                database = self.url.path[1:]

        return database or "dwd"

    def get_table(self):
        return self.get_query_param("table") or "weather"

    def get_path(self):
        return self.url.path or self.url.netloc

    def get_query_param(self, name):
        query = parse_qs(self.url.query)
        try:
            return query[name][0]
        except (KeyError, IndexError):
            return None
