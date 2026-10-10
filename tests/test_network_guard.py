# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the guard that holds `-m "not remote"` to being offline."""

import os
import socket
from pathlib import Path

import aiohttp.resolver
import pytest

from tests.conftest import _SOCKET_CONNECT, NetworkAccessBlockedError, _is_local_address
from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import download_file, list_remote_files_fsspec

#: A name rather than an address, and one RFC 2606 reserves so that it resolves nowhere. An
#: address would take the tests below down the `connect` patch alone -- aiohttp and asyncio both
#: skip resolution for a literal -- and that patch is not on the path on Windows, where asyncio
#: connects through `_overlapped.ConnectEx`. So they would pass here and fail there, having first
#: waited out three real connect timeouts. Refused at the name, they ask the same question on every
#: platform, and nothing is sent: the guard answers before the resolver is called.
UNREACHABLE = "blocked.invalid"


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


def test_aiohttp_still_resolves_through_the_step_this_guards() -> None:
    """The name-level refusal only reaches aiohttp while aiohttp resolves through `getaddrinfo`.

    `DefaultResolver` is `AsyncResolver` the moment `aiodns` is merely importable -- it is
    aiohttp's usual speedups dependency and can arrive transitively without anyone asking for it --
    and `AsyncResolver` goes through c-ares, which this never sees. On Windows the `connect` patch
    is already off the path, so that day the whole download path is unguarded and the offline
    selection goes quietly green. Asserted rather than assumed, so the day it happens is a failure
    here and someone decides what to do, instead of the guard going missing.
    """
    assert aiohttp.resolver.DefaultResolver is aiohttp.resolver.ThreadedResolver


def test_resolving_a_name_off_this_machine_is_refused(blocked_network: list[object]) -> None:
    """The connect patch misses Windows, where asyncio connects through `_overlapped.ConnectEx`.

    Resolution is the step every platform shares, so it is refused here too and the guard holds on
    all three rather than going quietly green on one of them. It is also what names the host: a
    refusal at `connect` alone would say `('141.38.2.164', 443)`, aiohttp having resolved already.
    """
    with pytest.raises(NetworkAccessBlockedError, match=r"network access blocked: opendata\.dwd\.de"):
        socket.getaddrinfo("opendata.dwd.de", 443)
    assert blocked_network == [("opendata.dwd.de", 443)]


@pytest.mark.parametrize("resolver", ["gethostbyname", "gethostbyname_ex"])
def test_the_other_ways_in_to_the_resolver_are_refused_too(
    resolver: str,
    blocked_network: list[object],
) -> None:
    """`gethostbyname` is its own C entry point and never reaches `getaddrinfo`.

    A caller resolving that way would have the address in hand and could then connect by the path
    the connect patch does not see on Windows, which is what the name-level refusal is for.

    Looked up by name at call time, not passed in as the function: parametrising on the attribute
    captures it at collection, which is before the guard is installed, and the test then measures
    the unpatched one and passes whatever the guard does.
    """
    with pytest.raises(NetworkAccessBlockedError, match=r"network access blocked: opendata\.dwd\.de"):
        getattr(socket, resolver)("opendata.dwd.de")
    assert blocked_network == [("opendata.dwd.de", None)]


def test_resolving_a_name_given_as_bytes_is_refused_too(blocked_network: list[object]) -> None:
    """A bytes host is valid here, and asyncio hands it to the loop unchanged."""
    with pytest.raises(NetworkAccessBlockedError, match=r"network access blocked: opendata\.dwd\.de"):
        socket.getaddrinfo(b"opendata.dwd.de", 443)
    assert blocked_network == [("opendata.dwd.de", 443)]


def test_resolving_for_this_machine_is_not(blocked_network: list[object]) -> None:
    """`getaddrinfo(None, port)` is how a local server asks for something to bind to."""
    assert socket.getaddrinfo(None, 0)
    assert blocked_network == []


def test_resolving_a_local_name_is_not(blocked_network: list[object]) -> None:
    """The local-server fixtures resolve `localhost`, and xdist's workers are reached by name too."""
    assert socket.getaddrinfo("localhost", 0)
    assert blocked_network == []


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
            url=f"https://{UNREACHABLE}/some/directory/",
            settings=Settings(),
            cache_expiry=CacheExpiry.METAINDEX,
        )
    # more than one: the listing is wrapped in a stamina retry, which asks again before giving up
    assert set(blocked_network) == {(UNREACHABLE, 443)}


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
            url=f"https://{UNREACHABLE}/some/file.csv",
            cache_dir=tmp_path,
            ttl=CacheExpiry.NO_CACHE,
        )
    # the set, as above: this path is retried too, and how many times is `_worth_retrying_download`'s
    # business rather than this test's -- what it asserts is that nothing but this was reached
    assert set(blocked_network) == {(UNREACHABLE, 443)}


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
        pytest.param((b"127.0.0.1", 8000), True, id="loopback-v4-bytes"),
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
    # prepended rather than set: an environment that already has one (tox, conda, some CI images)
    # needs to keep it, or the generated conftest's `pytest_plugins` may not import
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(filter(None, [str(pytestconfig.rootpath), existing])))
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
    assert "Neither the setup nor the call phase reported it" not in result.stdout.str()


def test_a_refusal_in_a_fixture_is_reported_once(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fixture that downloads something is an ordinary thing to write, and reaches the runner too.

    The phase differs, not the diagnosis, so the teardown check has to stay quiet here as well.
    """
    result = _run_one(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import socket

        import pytest

        @pytest.fixture
        def needs_net():
            socket.socket().connect(("example.org", 80))
            yield

        def test_forgot_the_marker(needs_net):
            pass
        """,
    )
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*network access blocked: ('example.org', 80)*"])
    assert "Neither the setup nor the call phase reported it" not in result.stdout.str()


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
    result.stdout.fnmatch_lines(["*Neither the setup nor the call phase reported it*"])


def test_a_refusal_a_provider_reraised_is_reported_once(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catching the refusal and raising your own `from` it still puts it in the traceback.

    Several providers do that rather than let the original through, and a reader sees the cause
    either way, so the teardown check must not report a second time for it.
    """
    result = _run_one(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import socket

        def test_provider_reraises():
            try:
                socket.socket().connect(("example.org", 80))
            except Exception as exc:
                raise RuntimeError("could not read the index") from exc
        """,
    )
    result.assert_outcomes(failed=1, errors=0)
    assert "Neither the setup nor the call phase reported it" not in result.stdout.str()


def test_the_teardown_check_stands_down_where_remote_tests_are_running_too(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What the guard records is per process, so a mixed run cannot say whose a refusal was.

    A thread an earlier `remote` test left running reaches the socket while some unmarked test is
    current, and the record would make it that test's. Failing a correct test is worse than missing
    a swallowed refusal, and the refusal itself is raised in either run, so only the offline
    selection -- which has no `remote` test to leave anything behind, and is the one CI gates on --
    carries the check.
    """
    result = _run_one(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import socket

        import pytest

        def test_swallows_the_refusal():
            try:
                socket.socket().connect(("example.org", 80))
            except Exception:  # noqa: BLE001
                pass

        @pytest.mark.remote
        def test_a_remote_neighbour():
            pass
        """,
    )
    result.assert_outcomes(passed=2, errors=0)


def test_a_refusal_inside_an_exception_group_is_reported_once(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Several connections refused at once arrive as a group, and the refusal in it is still seen.

    An `asyncio` gather or task group raises the refusals together, so the teardown check has to
    look inside the group, or it reports a second time for a refusal the reader already has.
    """
    result = _run_one(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import socket

        def test_a_group_of_connections():
            errors = []
            for _ in range(2):
                try:
                    socket.socket().connect(("example.org", 80))
                except Exception as exc:
                    errors.append(exc)
            raise ExceptionGroup("could not read the indexes", errors)
        """,
    )
    result.assert_outcomes(failed=1, errors=0)
    assert "Neither the setup nor the call phase reported it" not in result.stdout.str()
