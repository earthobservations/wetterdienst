# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The signature of a pre-signed URL is in no log line and no error a download leaves behind (GH-3341).

KNMI and AEMET hand out a link that grants a file for an hour to whoever holds it, in the query of the URL. Against a
local server that answers such a link the three ways a download ends -- a body, a 404 and a 5xx -- the URL is looked for
in everything the library writes and keeps for them: the log (stamina's retry records included) and the error that
comes back with the failed `File`.
"""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from aiohttp import ClientError, ClientResponseError, InvalidURL, RequestInfo
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import (
    _without_url_queries,
    _without_url_secrets,
    _without_url_secrets_in,
    download_file,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_QUERY = "?X-Amz-Credential=AKIAFAKE&X-Amz-Signature=FAKESIGNATURE0123456789"
_SECRETS = ("AKIAFAKE", "FAKESIGNATURE", "X-Amz")


class _Signed(BaseHTTPRequestHandler):
    """A server that answers by the path: `ok.nc`, `missing.nc` (a 404) and `broken.nc` (a 503)."""

    def log_message(self, *_args: object) -> None:
        """Keep the test output quiet."""

    def do_GET(self) -> None:
        name = self.path.split("?", maxsplit=1)[0]
        if name == "/ok.nc":
            body = b"data"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif name == "/missing.nc":
            self.send_error(404)
        else:
            self.send_error(503)


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    """Give the address of a local server."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Signed)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.mark.parametrize(
    ("name", "status"),
    [("ok.nc", 200), ("missing.nc", 404), ("broken.nc", 503)],
)
def test_a_download_leaves_the_signature_in_no_log_line_and_no_error(
    server: str, tmp_path: Path, caplog: pytest.LogCaptureFixture, name: str, status: int
) -> None:
    """The log names the file and the host, and the error of a failure carries no query."""
    url = f"{server}/{name}{_QUERY}"
    with caplog.at_level(logging.DEBUG):
        file = download_file(url, tmp_path, CacheExpiry.FIVE_MINUTES)

    assert file.status == status
    # what the library and stamina (whose retry record carries the repr of the error) write; fsspec's own debug
    # line of the request is not the library's to change
    written = "\n".join(
        f"{record.getMessage()} {vars(record)}"
        for record in caplog.records
        if record.name.startswith(("wetterdienst", "stamina"))
    )
    assert f"{server}/{name}" in written, "the log still says which file it is"
    for secret in _SECRETS:
        assert secret not in written
    if isinstance(file.content, Exception):
        shown = f"{file.content!s}{file.content!r}"
        for secret in _SECRETS:
            assert secret not in shown


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        (f"https://s3.example.com/a/b.nc{_QUERY}", "https://s3.example.com/a/b.nc"),
        ("https://user:pw@s3.example.com/b.nc#frag", "https://***@s3.example.com/b.nc"),
        ("https://s3.example.com/b.nc", "https://s3.example.com/b.nc"),
    ],
)
def test_a_url_is_shown_without_its_query(url: str, shown: str) -> None:
    """A query, a fragment and user information are cut."""
    assert _without_url_secrets(url) == shown


def test_urls_in_a_text_are_shown_without_their_query() -> None:
    """Every URL of a message is cut, and the words around them stay."""
    text = f"404, message='Not Found', url='https://s3.example.com/b.nc{_QUERY}' and http://a.example/x?k=1: done"
    assert _without_url_secrets_in(text) == (
        "404, message='Not Found', url='https://s3.example.com/b.nc' and http://a.example/x: done"
    )


def _request_info(url: str) -> RequestInfo:
    return RequestInfo(url=URL(url), method="GET", headers=CIMultiDictProxy(CIMultiDict()), real_url=URL(url))


def test_a_response_error_shows_its_request_and_its_redirects_without_the_query() -> None:
    """`str()` and `repr()` of an error with the url of the request and of the redirect it followed."""
    link = f"https://s3.example.com/b.nc{_QUERY}"
    error = ClientResponseError(
        _request_info(link),
        (
            SimpleNamespace(url=URL(link)),
            SimpleNamespace(url=URL("https://s3.example.com/r"), headers={"Location": link}),
        ),
        status=503,
        message="Service Unavailable",
    )  # ty: ignore[invalid-argument-type]

    assert _without_url_queries(error) is error

    shown = f"{error!s}{error!r}"
    for secret in _SECRETS:
        assert secret not in shown
    assert "https://s3.example.com/b.nc" in shown
    assert error.status == 503
    assert error.history == ()


def test_an_error_that_renders_an_attribute_shows_it_without_the_query() -> None:
    """The `filename` of an `OSError` and the `_url` of an invalid-URL error, which `args` does not give."""
    link = f"https://s3.example.com/b.nc{_QUERY}"
    os_error = FileNotFoundError(2, "No such file", link)
    invalid = InvalidURL(URL(link))
    as_url = ClientError(URL(link))

    for error in (_without_url_queries(os_error), _without_url_queries(invalid), _without_url_queries(as_url)):
        shown = f"{error!s}{error!r}"
        for secret in _SECRETS:
            assert secret not in shown
    assert "https://s3.example.com/b.nc" in str(os_error)


def test_an_error_without_a_url_is_left_as_it_was() -> None:
    """An error whose arguments are no text is returned unchanged."""
    error = ValueError(1, ("a", 2), None)
    assert _without_url_queries(error).args == (1, ("a", 2), None)
