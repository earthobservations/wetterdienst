# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the guard that holds `-m "not remote"` to being offline."""

import socket

import pytest

from tests.conftest import _SOCKET_CONNECT, _is_local_address


def test_an_unmarked_test_cannot_reach_upstream() -> None:
    """The refusal names the address, so what is missing a marker is read off the failure."""
    with socket.socket() as sock, pytest.raises(OSError, match=r"network access blocked: \('example.org', 80\)"):
        sock.connect(("example.org", 80))


def test_the_refusal_says_what_to_do_about_it() -> None:
    """A test reaching upstream is either remote or written wrong, and the message says both."""
    with socket.socket() as sock, pytest.raises(OSError, match=r"pytest\.mark\.remote"):
        sock.connect_ex(("example.org", 80))


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
