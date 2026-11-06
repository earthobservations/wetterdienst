# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A local server that answers as nginx does for a directory, which is what DWD's server is (GH-3819).

It is not a mock of a function: a request is a real one. A directory with a `/` at its end is an index page (a link to
the parent, one for each file), a path without it that names a directory is a 301 to the one with it (which nginx does
and which is what makes fsspec take an empty directory for a file), a file is served, `HEAD` is answered, and anything
else is a 404. Checked against nginx 1.31.3 and `opendata.dwd.de` when it was written.
"""

from __future__ import annotations

import http.server
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


class NginxLike:
    """What the server holds now, and how it answers: change it between requests as DWD does."""

    def __init__(self, *, redirect: bool = True) -> None:
        """Start with nothing: no directory, no file."""
        #: answer `/x` with a 301 to `/x/`, as nginx does; without, a 404
        self.redirect = redirect
        #: path with `/` at its end to the files in it
        self.directories: dict[str, list[str]] = {}
        #: the files any other directory holds, if it is not declared above or missing (None: a 404)
        self.default: list[str] | None = None
        #: directories that are not there
        self.missing: set[str] = set()
        #: paths answered with a page of their own, whatever they are: (content type, body), status 200. A CDN's error
        #: page answered with a 200, or a JSON error, stands for a directory this way
        self.pages: dict[str, tuple[str, bytes]] = {}
        #: paths answered with a status of their own and no body, before anything else (a 404 or a 503 on a path)
        self.statuses: dict[str, int] = {}
        #: the same for the successive requests of a path, one status for each (None: answered as it would be), until
        #: the list is used up: `[None, 503]` fails the second GET only, which is the one fsspec's `_isfile` makes
        self.flaky: dict[str, list[int | None]] = {}
        #: paths of files, which are served whole
        self.files: set[str] = set()
        #: every request the server met, as (method, path with query)
        self.requests: list[tuple[str, str]] = []
        #: where it is: `http://127.0.0.1:<port>`
        self.base = ""

    def files_of(self, path: str) -> list[str] | None:
        """Give the files of the directory at a path with `/` at its end, None where there is none."""
        if path in self.missing:
            return None
        if path in self.directories:
            return self.directories[path]
        return self.default

    def page(self, path: str, files: list[str]) -> bytes:
        """Write the index page as nginx does: a link to the parent, one for each file, and the sizes and times."""
        links = "".join(f'<a href="{name}">{name}</a>   06-Nov-2026 12:15:08   379\n' for name in files)
        body = f'<h1>Index of {path}</h1><hr><pre><a href="../">../</a>\n{links}</pre><hr>'
        return f"<html><head><title>Index of {path}</title></head><body>{body}</body></html>".encode()

    def answer(self, path: str) -> tuple[int, list[tuple[str, str]], bytes]:
        """Say what the server answers for a path: the status, the headers and the body."""
        if self.flaky.get(path) and (status := self.flaky[path].pop(0)) is not None:
            return status, [], b""
        if path in self.statuses:
            return self.statuses[path], [], b""
        if path in self.pages:
            content_type, body = self.pages[path]
            return 200, [("Content-Type", content_type)], body
        if path in self.files:
            return 200, [("Content-Type", "application/zip")], b"x"
        if path.endswith("/"):
            files = self.files_of(path)
            if files is not None:
                return 200, [("Content-Type", "text/html")], self.page(path, files)
        elif self.redirect and self.files_of(f"{path}/") is not None:
            return 301, [("Location", f"{path}/")], b""
        return 404, [], b""


@contextmanager
def serving(*, redirect: bool = True) -> Iterator[NginxLike]:
    """Run an `NginxLike` on a local port, and stop it."""
    state = NginxLike(redirect=redirect)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def _answer(self, *, body: bool) -> None:
            path = self.path.split("?")[0]
            state.requests.append((self.command, self.path))
            status, headers, content = state.answer(path)
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            if body:
                self.wfile.write(content)

        def do_GET(self) -> None:
            self._answer(body=True)

        def do_HEAD(self) -> None:
            self._answer(body=False)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    state.base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        yield state
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
