# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""No way into the network leaks a raw network exception (GH-3120).

AGENTS.md promises that a failed connection is a `NoInternetError` and any other failure of a download a
`DownloadError`, naming the URL with the failure as its `__cause__`: that is what the REST API answers with a 503, 502
or 504, where a bare `ssl.SSLError`, `OSError`, `aiohttp.ClientError` or `TimeoutError` would be a 500, a defect of
the server. Every place that performs the request is held to it here, against a local server that fails the five
ways a network does: a connection reset, a TLS handshake that fails, a silence, a 5xx and a refused connection.

The places are the shared helpers of `util/network.py` and the one reader of a provider that does not go through
them (`KMLReader`, which `dwd/mosmix` and `dwd/dmo` read their runs with). `test_no_provider_meets_the_network_itself`
holds the rest of the providers to the helpers by reading their imports, so that a new reader that meets the network
by itself is a failure here and gets a row below.
"""

from __future__ import annotations

import ast
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import stamina
from aiohttp import ClientTimeout

import wetterdienst
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.settings import Settings
from wetterdienst.ui.core import failure_status, timed_out
from wetterdienst.util.network import (
    download_file,
    download_files,
    list_remote_directory_fsspec,
    list_remote_files_fsspec,
    post_file,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

#: how long a silent server is waited for; the server holds the connection for longer
_PATIENCE_SECONDS = 0.3


class _Hostile(BaseHTTPRequestHandler):
    """A server that fails the way a network does, by the path it is asked for."""

    def log_message(self, *_args: object) -> None:
        """Keep the test output quiet."""

    def do_GET(self) -> None:
        self._fail()

    def do_POST(self) -> None:
        self._fail()

    def do_HEAD(self) -> None:
        self._fail()

    def _fail(self) -> None:
        if self.path == "/reset":
            # SO_LINGER with a timeout of zero turns the close into a reset (RST) of the connection
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            self.connection.close()
        elif self.path == "/silence":
            self.server.release.wait(10)
        elif self.path == "/truncated":
            self.send_response(200)
            self.send_header("Content-Length", "1000")
            self.end_headers()
            self.wfile.write(b"cut")
            self.connection.close()
        else:
            self.send_response(int(self.path.removeprefix("/")))
            self.send_header("Content-Length", "0")
            self.end_headers()


@pytest.fixture
def hostile() -> Iterator[ThreadingHTTPServer]:
    """Run `_Hostile` on a port of its own."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Hostile)
    server.release = threading.Event()
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        # a handler that keeps a connection waits on this, and closing the server waits on the handler
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _one_attempt() -> Iterator[None]:
    """Ask once: the retries are no part of what is held here, and each of them waits."""
    with stamina.set_testing(True, attempts=1):
        yield


def _closed_port() -> int:
    """Give a port nothing listens on."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


#: each way a network fails: the URL of it, and the error the caller is to see
_FAILURES: dict[str, tuple[Callable[[ThreadingHTTPServer], str], type[Exception]]] = {
    # the server hangs up with a reset after it was asked
    "reset": (lambda server: f"http://127.0.0.1:{server.server_port}/reset", DownloadError),
    # a handshake spoken to a server that speaks no TLS: `ClientConnectorSSLError`, a `ssl.SSLError` underneath
    "tls": (lambda server: f"https://127.0.0.1:{server.server_port}/ok", DownloadError),
    "timeout": (lambda server: f"http://127.0.0.1:{server.server_port}/silence", DownloadError),
    "timeout of the whole request": (lambda server: f"http://127.0.0.1:{server.server_port}/silence", DownloadError),
    "5xx": (lambda server: f"http://127.0.0.1:{server.server_port}/503", DownloadError),
    "truncated": (lambda server: f"http://127.0.0.1:{server.server_port}/truncated", DownloadError),
    "refused": (lambda _server: f"http://127.0.0.1:{_closed_port()}/ok", NoInternetError),
}
#: ... and the timeout of the client: a number bounds each silence, a `ClientTimeout` with a total the whole request
_CLIENT_KWARGS = {"timeout": _PATIENCE_SECONDS}
_TOTAL_TIMEOUT_KWARGS = {"timeout": ClientTimeout(total=_PATIENCE_SECONDS)}


def _assert_the_documented_error(url: str, expected: type[Exception], raised: Exception, *, mode: str) -> None:
    """Check that the caller sees the library's error for the failure, naming the URL, not the library underneath."""
    assert type(raised) is expected, f"{type(raised).__module__}.{type(raised).__qualname__}: {raised}"
    assert url.split("/", 3)[2] in str(raised), "the error names the host it was raised for"
    # the cause is what the server did, which the REST API reads the status from
    assert raised.__cause__ is not None
    # raised outside the `except` that met the failure, so that no aiohttp error, which holds the connection key and
    # so a proxy's password, hangs on it as its context
    assert raised.__context__ is None
    if mode.startswith("timeout"):
        assert failure_status(raised) == 504
        assert timed_out(raised)
    elif expected is DownloadError:
        assert failure_status(raised) == 502
    else:
        assert failure_status(raised) == 503


def _download_file(url: str, tmp_path: Path, client_kwargs: dict) -> None:
    download_file(url, cache_dir=tmp_path, client_kwargs=client_kwargs, cache_disable=True).raise_if_exception()


def _download_file_cached(url: str, tmp_path: Path, client_kwargs: dict) -> None:
    download_file(url, cache_dir=tmp_path, client_kwargs=client_kwargs).raise_if_exception()


def _download_files(url: str, tmp_path: Path, client_kwargs: dict) -> None:
    for file in download_files([url], cache_dir=tmp_path, client_kwargs=client_kwargs, cache_disable=True):
        file.raise_if_exception()


def _post_file(url: str, tmp_path: Path, client_kwargs: dict) -> None:  # noqa: ARG001
    post_file(url, client_kwargs=client_kwargs).raise_if_exception()


def _list_files(url: str, tmp_path: Path, client_kwargs: dict) -> None:
    list_remote_files_fsspec(url, Settings(cache_dir=tmp_path, cache_disable=True, fsspec_client_kwargs=client_kwargs))


def _list_directory(url: str, tmp_path: Path, client_kwargs: dict) -> None:
    list_remote_directory_fsspec(
        url, Settings(cache_dir=tmp_path, cache_disable=True, fsspec_client_kwargs=client_kwargs)
    )


def _kml_reader(url: str, tmp_path: Path, client_kwargs: dict, *, cache_disable: bool) -> None:
    settings = Settings(cache_dir=tmp_path, cache_disable=cache_disable, fsspec_client_kwargs=client_kwargs)
    KMLReader(station_ids=["01001"], settings=settings).download(url)


#: every way into the network that is not a provider's own parser: the shared helpers, and the reader that goes
#: through fsspec by itself
_READERS: dict[str, Callable[[str, Path, dict], None]] = {
    "download_file": _download_file,
    "download_file (cached)": _download_file_cached,
    "download_files": _download_files,
    "post_file": _post_file,
    "list_remote_files_fsspec": _list_files,
    "list_remote_directory_fsspec": _list_directory,
    "KMLReader.download": lambda url, tmp_path, kwargs: _kml_reader(url, tmp_path, kwargs, cache_disable=True),
    "KMLReader.download (cached)": lambda url, tmp_path, kwargs: _kml_reader(
        url, tmp_path, kwargs, cache_disable=False
    ),
}


@pytest.mark.parametrize("mode", list(_FAILURES))
@pytest.mark.parametrize("reader", list(_READERS))
def test_a_network_failure_is_the_librarys_error(
    reader: str, mode: str, hostile: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """A reset, a TLS failure, a silence, a 5xx, a cut-short body and a refusal reach the caller as `UpstreamError`s.

    Never the `ssl.SSLError`, `OSError`, `aiohttp.ClientError` or `TimeoutError` underneath, which the REST API
    would answer with a 500.
    """
    make_url, expected = _FAILURES[mode]
    url = make_url(hostile)

    with pytest.raises(Exception) as raised:  # noqa: PT011 -- the type is what is asserted
        _READERS[reader](
            url, tmp_path, _TOTAL_TIMEOUT_KWARGS if mode == "timeout of the whole request" else _CLIENT_KWARGS
        )

    _assert_the_documented_error(url, expected, raised.value, mode=mode)


#: the modules of a provider that import a network library, each with why that is no way round the helpers
_MEETS_THE_NETWORK_BY_ITSELF = {
    # reads its runs through fsspec for the cache's sake and maps what it meets with `_failed_file`, the function
    # `download_file` maps with: held above as `KMLReader.download`. What it imports is the connector error of the
    # size of a run, which it does not need
    "dwd/mosmix/access.py": "KMLReader.download, held above",
    # catches the aiohttp error an earlier release raised, for a caller that still sends one
    "eaufrance/hubeau/api.py": "an except clause only",
    # builds a basic-auth header
    "metno/frost/api.py": "no request of its own",
}
#: the libraries that perform or raise network I/O
_NETWORK_LIBRARIES = frozenset({"aiohttp", "requests", "httpx", "httpx2", "urllib3", "ssl", "socket", "ftplib"})
#: ... and `urllib.request`, the part of `urllib` that does: `urllib.parse` is no network
_NETWORK_MODULES = frozenset({"urllib.request", "urllib.error", "http.client", "http.cookiejar"})


def _imports_of(path: Path) -> set[str]:
    """Give the modules a source file imports, as dotted names."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _provider_sources() -> list[Path]:
    root = Path(wetterdienst.__file__).parent / "provider"
    return sorted(root.rglob("*.py"))


def test_no_provider_meets_the_network_itself() -> None:
    """A provider fetches through `util/network.py`, whose errors are the library's, or is named here.

    A module that imports `aiohttp`, `ssl`, `requests`, `urllib.request` or the like performs the request, or
    catches what it raises, by itself, and so sees the raw exception the helpers map. A new one is a row in
    `_READERS` above and an entry in `_MEETS_THE_NETWORK_BY_ITSELF`.
    """
    root = Path(wetterdienst.__file__).parent / "provider"
    found = {}
    for path in _provider_sources():
        imports = _imports_of(path)
        met = {name for name in imports if name.split(".")[0] in _NETWORK_LIBRARIES or name in _NETWORK_MODULES}
        if met:
            found[path.relative_to(root).as_posix()] = sorted(met)
    assert set(found) <= set(_MEETS_THE_NETWORK_BY_ITSELF), found


#: the `raise <file>.content` of a provider that cannot be reached with an exception, each with why
_RAISES_ITS_CONTENT_UNREACHABLY = {
    # narrowing for the type checker, after `raise_if_exception()` has raised the error
    ("dmi/observation/api.py", "_iter_station_value_pages"): "after raise_if_exception()",
    # called with the files that are a `BytesIO`
    ("dwd/derived/download.py", "_unpack_climate_derived_data"): "only given files that arrived",
    # a failed download has no bytes and is dropped with the empty files, after the group's failures were raised
    ("dwd/road/api.py", "__parse_dwd_road_weather_data"): "only given files of more than 142 bytes",
    # a `NoInternetError`, which is the library's own error
    ("metoffice/observation/download.py", "get_ceda_token"): "a NoInternetError",
}


def _raises_of_content(path: Path) -> list[tuple[str, int]]:
    """Give the function and the line of each ``raise <name>.content`` in a source file."""
    found = []

    def walk(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function
            if (
                isinstance(child, ast.Raise)
                and isinstance(child.exc, ast.Attribute)
                and child.exc.attr == "content"
                and child.cause is None
            ):
                found.append((function, child.lineno))
            walk(child, name)

    walk(ast.parse(path.read_text(encoding="utf-8")), "<module>")
    return found


def test_no_provider_raises_the_exception_a_download_stored() -> None:
    """`raise file.content` raises the aiohttp, `OSError` or `TimeoutError` a download stored, bare.

    A provider that reads `File.content` itself raises `file.raise_if_exception()`, or `as_outage` for a failure
    it answers otherwise: the `DownloadError` or `NoInternetError` the REST API maps to a 502, 503 or 504.
    """
    root = Path(wetterdienst.__file__).parent / "provider"
    found = {
        (path.relative_to(root).as_posix(), function)
        for path in _provider_sources()
        for function, _line in _raises_of_content(path)
    }
    assert found == set(_RAISES_ITS_CONTENT_UNREACHABLY)


@pytest.mark.parametrize("cache_disable", [True, False], ids=["uncached", "cached"])
def test_a_run_that_is_not_there_is_a_download_error(
    hostile: ThreadingHTTPServer, tmp_path: Path, *, cache_disable: bool
) -> None:
    """A run that was listed and is gone is a 404, and `KMLReader` raises it as `File.raise_if_exception` does.

    Not the `FileNotFoundError` of fsspec, which the REST API would answer with a 500 (GH-3120).
    """
    url = f"http://127.0.0.1:{hostile.server_port}/404"

    with pytest.raises(DownloadError, match=r"/404") as raised:
        _kml_reader(url, tmp_path, _CLIENT_KWARGS, cache_disable=cache_disable)

    assert failure_status(raised.value) == 502
