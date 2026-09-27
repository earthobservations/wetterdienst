# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the guard that holds `-m "not remote"` to being offline."""

import socket
from pathlib import Path

import pytest

from tests.conftest import _SOCKET_CONNECT, NetworkAccessBlockedError, _is_local_address
from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import download_file, list_remote_files_fsspec

#: RFC 5737 TEST-NET-1, so the guard is asked about an address that needs no name resolution to
#: reach and is routable nowhere. The refusal happens before a packet is sent either way.
UNROUTABLE = "192.0.2.1"


def test_an_unmarked_test_cannot_reach_upstream() -> None:
    """The refusal names the address, so what is missing a marker is read off the failure."""
    with (
        socket.socket() as sock,
        pytest.raises(NetworkAccessBlockedError, match=r"network access blocked: \('example.org', 80\)"),
    ):
        sock.connect(("example.org", 80))


def test_the_refusal_says_what_to_do_about_it() -> None:
    """A test reaching upstream is either remote or written wrong, and the message says both."""
    with socket.socket() as sock, pytest.raises(NetworkAccessBlockedError, match=r"pytest\.mark\.remote"):
        sock.connect_ex(("example.org", 80))


def test_the_refusal_is_not_an_oserror() -> None:
    """What the guard raises has to be outside everything the library degrades on.

    aiohttp turns an `OSError` from a connect into `ClientConnectorError`, which is the library's
    signal for being offline -- and being offline is a thing it answers rather than reports.
    """
    assert not issubclass(NetworkAccessBlockedError, OSError)


def test_a_blocked_listing_says_so_rather_than_coming_back_empty() -> None:
    """A directory that is not there and one that was never asked for are different answers.

    `list_remote_files_fsspec` returns `[]` for both a missing directory and an offline library, so
    a guard it could absorb left a test asserting an empty listing passing while testing nothing,
    and every other test failing as `url ... does not have a list of files` -- an upstream
    restructure, to read it.
    """
    with pytest.raises(NetworkAccessBlockedError):
        list_remote_files_fsspec(
            url=f"https://{UNROUTABLE}/some/directory/",
            settings=Settings(),
            cache_expiry=CacheExpiry.METAINDEX,
        )


def test_a_blocked_download_says_so_rather_than_carrying_no_internet(tmp_path: Path) -> None:
    """A refused download leaves by raising, and not as the `File` every real failure comes back as.

    `download_file` answers a failure with a `File` carrying the exception, and `raise_if_exception`
    logs the offline one at debug and returns -- which is how a provider ends up handing back an
    empty frame instead of failing. A missing marker has to be louder than the condition it
    imitates, so this one case leaves through the call stack.
    """
    with pytest.raises(NetworkAccessBlockedError):
        download_file(
            url=f"https://{UNROUTABLE}/some/file.csv",
            cache_dir=tmp_path,
            ttl=CacheExpiry.NO_CACHE,
        )


@pytest.mark.remote
def test_a_remote_test_is_not_guarded() -> None:
    """Nothing is patched where the marker is there, rather than patched and waved through."""
    assert socket.socket.connect is _SOCKET_CONNECT


def test_loopback_stays_open() -> None:
    """pytest-xdist talks to its workers over it, and the local-server fixtures need it too."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.socket() as client:
            client.connect(server.getsockname())


@pytest.mark.parametrize(
    ("address", "local"),
    [
        pytest.param(("127.0.0.1", 8000), True, id="loopback-v4"),
        pytest.param(("::1", 8000, 0, 0), True, id="loopback-v6"),
        pytest.param(("localhost", 8000), True, id="localhost"),
        pytest.param(("0.0.0.0", 8000), True, id="unspecified"),  # noqa: S104
        pytest.param("/tmp/some.sock", True, id="unix-socket"),  # noqa: S108
        pytest.param(("opendata.dwd.de", 443), False, id="hostname"),
        pytest.param(("141.38.3.10", 443), False, id="address"),
    ],
)
def test_what_counts_as_this_machine(address: object, local: bool) -> None:  # noqa: FBT001
    """A hostname never resolves here, so anything that is not plainly local is refused."""
    assert _is_local_address(address) is local
