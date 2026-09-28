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


def test_an_unmarked_test_cannot_reach_upstream(blocked_network: list[object]) -> None:
    """The refusal names the address, so what is missing a marker is read off the failure."""
    with (
        socket.socket() as sock,
        pytest.raises(NetworkAccessBlockedError, match=r"network access blocked: \('example.org', 80\)"),
    ):
        sock.connect(("example.org", 80))
    assert blocked_network == [("example.org", 80)]


def test_the_refusal_says_what_to_do_about_it(blocked_network: list[object]) -> None:
    """A test reaching upstream is either remote or written wrong, and the message says both."""
    with socket.socket() as sock, pytest.raises(NetworkAccessBlockedError, match=r"pytest\.mark\.remote"):
        sock.connect_ex(("example.org", 80))
    assert blocked_network == [("example.org", 80)]


def test_the_refusal_is_not_an_oserror() -> None:
    """What the guard raises has to be outside everything the library degrades on.

    aiohttp turns an `OSError` from a connect into `ClientConnectorError`, which is the library's
    signal for being offline -- and being offline is a thing it answers rather than reports.
    """
    assert not issubclass(NetworkAccessBlockedError, OSError)


def test_a_blocked_listing_says_so_rather_than_coming_back_empty(blocked_network: list[object]) -> None:
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
    # more than one: the listing is wrapped in a stamina retry, which asks again before giving up
    assert set(blocked_network) == {(UNROUTABLE, 443)}


def test_a_blocked_download_says_so_rather_than_carrying_no_internet(
    tmp_path: Path,
    blocked_network: list[object],
) -> None:
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
    assert blocked_network == [(UNROUTABLE, 443)]


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
        # a dual-stack socket reports a v4 peer this way, and 3.12's `is_loopback` says False for it
        pytest.param(("::ffff:127.0.0.1", 8000, 0, 0), True, id="loopback-v4-mapped"),
        pytest.param(("opendata.dwd.de", 443), False, id="hostname"),
        pytest.param(("141.38.3.10", 443), False, id="address"),
        pytest.param(("::ffff:8.8.8.8", 443, 0, 0), False, id="address-v4-mapped"),
    ],
)
def test_what_counts_as_this_machine(address: object, local: bool) -> None:  # noqa: FBT001
    """A hostname never resolves here, so anything that is not plainly local is refused."""
    assert _is_local_address(address) is local


def _run_one(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
) -> pytest.RunResult:
    """Run one generated test under this guard, as its own session in its own process.

    A subprocess rather than a nested in-process session: the guard keeps what it refused in module
    state, which a nested session would share with the test running it.
    """
    monkeypatch.setenv("PYTHONPATH", str(pytestconfig.rootpath))
    pytester.makeconftest("pytest_plugins = ['tests.conftest']\n")
    pytester.makepyfile(body)
    return pytester.runpytest_subprocess("-p", "no:randomly", "-p", "no:cacheprovider")


def test_a_refusal_that_reaches_the_test_is_reported_once(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary missing-marker case: one failure naming the host, and no teardown error.

    The teardown check below cannot tell on its own that the refusal already ended the test, and
    reporting a second time would send a contributor hunting for an `except Exception` that is not
    there.
    """
    result = _run_one(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import socket

        def test_forgot_the_marker():
            socket.socket().connect(("example.org", 80))
        """,
    )
    result.assert_outcomes(failed=1, errors=0)
    result.stdout.fnmatch_lines(["*network access blocked: ('example.org', 80)*"])
    assert "did not reach the test" not in result.stdout.str()


def test_a_refusal_nobody_reported_still_fails_the_test(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller that degrades on `except Exception` postpones the failure rather than avoiding it.

    Several providers do exactly that, so the refusal reaching the test cannot be what the guard
    rests on.
    """
    result = _run_one(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import socket

        def test_swallows_the_refusal():
            try:
                socket.socket().connect(("example.org", 80))
            except Exception:  # noqa: BLE001 -- the degradation being imitated
                pass
        """,
    )
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*did not reach the test*"])
