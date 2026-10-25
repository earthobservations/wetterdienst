# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures for tests."""

import errno
import ipaddress
import os
import platform
import re
import socket
import sys
import threading
import time
import warnings
from collections.abc import Collection, Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from wetterdienst import Info, Options, Settings
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.util.eccodes import bufr_is_available
from wetterdienst.util.network import _worth_retrying

IS_CI = bool(os.environ.get("CI"))
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"
IS_PYTHON_3_14 = sys.version_info[:2] == (3, 14)
BUFR_AVAILABLE = bufr_is_available()

info = Info()

#: the members of the `metadata` block that every JSON answer has, whatever was asked for
RESPONSE_METADATA_ALWAYS = frozenset(
    {"api_version", "schema_version", "retrieved_at", "provider", "producer", "request", "counts", "crs", "warnings"},
)
#: the members `with_metadata` adds to the block
RESPONSE_METADATA_HEAVY = frozenset({"parameters", "quality"})


def assert_response_metadata(block: dict, metadata: dict, *, with_metadata: bool = False) -> None:
    """Check the `metadata` block of an answer: its members, and the producer and provider it names.

    The block is always there; `with_metadata` adds the parameters and the quality flags to it. The
    `metadata` fixture holds the producer and the provider, the rest is read off the request.
    """
    assert set(block) == RESPONSE_METADATA_ALWAYS | (RESPONSE_METADATA_HEAVY if with_metadata else frozenset())
    assert block["producer"] == metadata["producer"]
    assert block["provider"] == metadata["provider"]


def is_no_such_option(output: str, option: str) -> bool:
    """Say whether click's output refuses an option it does not have, in the words of any click the floor allows.

    click 8.2.0 says `No such option: --x`, the releases after it `No such option '--x'`.
    """
    return f"No such option '{option}'" in output or f"No such option: {option}" in output


def is_html_document(output: str) -> bool:
    """Say whether an HTML export is a whole document rather than a fragment.

    plotly 7 leads the document with a doctype where 6.x began straight at ``<html>``, and the
    plotly floor allows either.
    """
    return output.lstrip().lower().startswith(("<!doctype html>", "<html>"))


def _is_server_fault(failure: Exception) -> bool:
    """Say whether a failure carries the status of a 5xx that is no `ClientResponseError`.

    AEMET reports its own faults as the `estado` of the envelope of an HTTP 200, and the reader raises
    that as a `DownloadError` caused by an error that holds the `estado` as `status` (GH-2965).
    """
    status = getattr(failure, "status", None)
    return isinstance(status, int) and status >= HTTPStatus.INTERNAL_SERVER_ERROR


#: Hosts that any machine running this suite reaches: where its dependencies came from.
_CONNECTIVITY_PROBES = (("pypi.org", 443), ("github.com", 443))
#: What a connection that a host did not take up fails with: it timed out, was refused or reset, or has no route
#: to the host (`EHOSTUNREACH`) or to its network (`ENETUNREACH`, what a runner reports for an address, an IPv6 one
#: say, that its interface has no route to). On Windows `errno` carries the Winsock codes (10060, 10061, ...), so
#: these are the same names there.
_UNANSWERED_ERRNOS = frozenset(
    {errno.ETIMEDOUT, errno.ECONNREFUSED, errno.ECONNRESET, errno.EHOSTUNREACH, errno.ENETUNREACH}
)
#: `ERROR_SEM_TIMEOUT`, "The semaphore timeout period has expired": how Windows reports a connect that timed out
#: through the overlapped I/O asyncio uses, as a plain `OSError` that no `errno` names.
_WINDOWS_SEMAPHORE_TIMEOUT = 121


def _runner_has_network() -> bool:
    """Say whether this machine can open a connection to hosts that are not the one under test."""
    for host, port in _CONNECTIVITY_PROBES:
        try:
            with socket.create_connection((host, port), timeout=5):
                return True
        except OSError:
            continue
    return False


def _host_did_not_answer(failure: BaseException | None) -> bool:
    """Say whether the `OSError` under a `NoInternetError` is a host that did not take up the connection.

    A timeout, a refusal, a reset or abort, or no route to the host or its network. Not a name that did not resolve
    (`socket.gaierror`): that is also what a decommissioned or misspelt host looks like, which this
    suite has to be able to fail on.

    A connection that was refused, reset or aborted is told by its class (`ConnectionError`) as well as by
    `errno`: asyncio raises a Windows `[WinError 64] The specified network name is no longer available` as a
    `ConnectionResetError`, and its `errno` (probably `EINVAL`, which CPython has no better mapping of that
    code for) is not `ECONNRESET`. That error failed three hubeau.eaufrance.fr tests as no outage (GH-2522).
    """
    if not isinstance(failure, OSError) or isinstance(failure, socket.gaierror):
        return False
    return (
        isinstance(failure, (TimeoutError, ConnectionError))
        or failure.errno in _UNANSWERED_ERRNOS
        or getattr(failure, "winerror", None) == _WINDOWS_SEMAPHORE_TIMEOUT
    )


def _host_of(failure: NoInternetError) -> str | None:
    """Name the host a `NoInternetError` could not reach, from the URL its message gives."""
    found = re.search(r"could not reach (\S+)", str(failure))
    return urlsplit(found.group(1)).hostname if found else None


def _is_upstream_outage(error: Exception, unresolved_hosts: Collection[str] = ()) -> bool:
    """Say whether a failure is the upstream not answering, by the rule `skip_if_upstream_unavailable` states."""
    # a download raised through `File.raise_if_exception` carries the failure as its cause
    failure = error.__cause__ if isinstance(error, DownloadError) and error.__cause__ else error
    if isinstance(failure, NoInternetError):
        cause = failure.__cause__
        unanswered = _host_did_not_answer(cause) or (
            isinstance(cause, socket.gaierror) and _host_of(failure) in unresolved_hosts
        )
        return unanswered and _runner_has_network()
    return isinstance(failure, Exception) and (_worth_retrying(failure) or _is_server_fault(failure))


@contextmanager
def skip_if_upstream_unavailable(*, unresolved_hosts: Collection[str] = ()) -> Generator[None]:
    """Skip a remote test whose upstream did not answer, rather than fail it.

    For a test that asserts what upstream publishes, a request that timed out or met a 5xx says
    nothing either way, and failing on it reports a provider's bad few minutes as a regression here.

    The rule, in full. It skips on:

    - what `_worth_retrying` names -- a timeout, a dropped connection, a body cut off mid-read, a
      5xx -- which `download_file` asks twice, so a request made through it is skipped on only after
      its second attempt failed as well;
    - a 5xx that arrives as the status of an envelope rather than of the response (AEMET);
    - a `NoInternetError` whose connection timed out, was refused, reset or aborted, or had no route (a
      Windows runner's "semaphore timeout" and "network name is no longer available" included), *and*
      only while this machine can still connect to other hosts (`_runner_has_network`), so a runner
      that has lost its network is red and not a wall of skips (GH-2640).

    It does not skip on anything else, and in particular not on:

    - a 4xx. A 404 is upstream answering and the likelier cause is a URL built wrong, which is what
      such a test is there to catch; a 400 or a 429 the same. A 401 or a 403 is a credential
      refused, and a `CredentialRejectedError` is a CI configuration failure that has to stay red
      (a rejected AEMET key).
    - a name that does not resolve (`socket.gaierror`): a decommissioned or misspelt host looks just
      like it, and a test that never reaches its host proves nothing, so it fails. Except for a host
      named in ``unresolved_hosts``, whose name a runner's resolver is known to fail on while it
      resolves every other (`frost.met.no` on the macOS runners, GH-3252): that skips, again only while
      `_runner_has_network`. A test names such a host through the `resolver_fails` marker, for the
      platform it was seen on, so the same failure on the others still fails.
    - a TLS failure, an assertion, or any other exception: a wrong answer is not an outage.

    Usable as a decorator or around the calls that reach upstream.

    Every test marked `remote` is already run inside it (`pytest_runtest_call` below, GH-2522), so
    it is for a block that has to be skipped alone: one inside a test that catches what it raises,
    where the exception never reaches the hook.
    """
    try:
        yield
    except Exception as error:
        if _is_upstream_outage(error, unresolved_hosts):
            pytest.skip(f"upstream did not answer: {error!r}")
        raise


def skip_if_upstream_problem(response: Any) -> None:  # noqa: ANN401
    """Skip a remote test whose REST answer says that the data provider did not answer in time.

    The REST API turns a failed provider request into a problem before the exception can reach
    `skip_if_upstream_unavailable`, and documents which 5xx is the provider's. Only a 504 of kind
    `upstream-timeout` skips: the provider did not answer in time, which is what a timeout is for
    `skip_if_upstream_unavailable` too. Not skipped, each for a reason of its own:

    - a 504 `request-timeout`: this server gave up, which a request too large for it also does, and so does an
      image that a slow runner takes longer than 60 seconds to render (the image tests on the Intel macOS runners,
      3 to 10 seconds on a laptop): nothing in it says the provider was slow;
    - a 503 `upstream-unreachable`: it does not say why the connection failed, and a name that does
      not resolve (see `skip_if_upstream_unavailable`) is one;
    - a 502 `upstream-failed`: the provider sent what the parser did not expect, which can be our
      parser's defect;
    - a 503 `server-busy`, a 4xx (a credential refused among them) and a 500.
    """
    if response.status_code != HTTPStatus.GATEWAY_TIMEOUT:
        return
    try:
        kind = str(response.json().get("type", ""))
    except ValueError:
        return
    if kind.rsplit(":", 1)[-1] == "upstream-timeout":
        pytest.skip(f"upstream did not answer: HTTP {response.status_code} {kind}")


#: Frost's name on the macOS runners (GH-3252): their resolver answers SERVFAIL for `frost.met.no`, a CNAME into
#: another DNSSEC-signed zone, while it resolves `api.met.no` and every other host of the run. Linux and Windows
#: resolve it in the same runs, so a host that is really gone still fails there.
FROST_RESOLVER_ON_MACOS = pytest.mark.resolver_fails("frost.met.no", platform="darwin")


def _unresolved_hosts_of(item: pytest.Item) -> tuple[str, ...]:
    """Read the hosts a test's `resolver_fails` marker names, on the platform the marker is meant for.

    ``@pytest.mark.resolver_fails("frost.met.no", platform="darwin")``: a `sys.platform` that is not the
    one given leaves the list empty. Without ``platform`` the hosts apply everywhere.
    """
    hosts: list[str] = []
    for marker in item.iter_markers("resolver_fails"):
        platform_name = marker.kwargs.get("platform")
        if platform_name is None or sys.platform == platform_name:
            hosts.extend(marker.args)
    return tuple(hosts)


def _rerun_will_retry(item: pytest.Item, error: BaseException) -> bool:
    """Say whether pytest-rerunfailures is going to run this test again because of ``error``.

    It reruns a failure while the attempts for it last, and with ``--only-rerun`` only one that
    names the patterns -- matched, as it does, against the type and message of the error and of
    whatever it was raised from or while handling. A skip is not a failure, so a test that skipped
    on a timeout would never be asked a second time.

    Only the global ``reruns`` and ``--only-rerun`` (option or ini) are modelled, which is all this
    suite sets: not the ``flaky`` marker's own ``only_rerun``, ``rerun_except`` or ``condition``.
    """
    if not item.config.pluginmanager.hasplugin("rerunfailures"):
        return False
    from pytest_rerunfailures import get_reruns_count  # noqa: PLC0415 -- only there with the plugin

    if getattr(item, "execution_count", 1) > (get_reruns_count(item) or 0):
        return False
    patterns = item.config.getoption("only_rerun") or item.config.getini("only_rerun")
    if not patterns:
        return True
    seen: set[int] = set()
    chained: BaseException | None = error
    while chained is not None and id(chained) not in seen:
        seen.add(id(chained))
        if any(re.search(pattern, f"{type(chained).__name__}: {chained}") for pattern in patterns):
            return True
        chained = chained.__cause__ or (None if chained.__suppress_context__ else chained.__context__)
    return False


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None]:
    """Run a `remote` test inside `skip_if_upstream_unavailable`, so an outage skips it (GH-2522).

    A remote test asserts what an upstream publishes, and failing it on a timeout or a 5xx reports
    that upstream's bad few minutes as a regression here. Done for every `remote` test rather than
    decorated onto each, because that is what the marker says -- the test needs the internet -- and
    a decorator left off one is how most of the suite came to fail on outages. The classification
    is the helper's, so a 404, a 4xx or an assertion still fails the test.

    An error that pytest-rerunfailures is going to retry is left to it, and skipped only once the
    attempts are used up: this suite reruns a timeout or a 5xx twice, and a test that passes on the
    second try should still pass rather than skip.

    Not applied to the setup phase: a fixture that downloads and meets an outage still errors.
    Nor does it reach a test that goes through the CLI or the REST API, which turn a failed request
    into an exit code or a response before the exception can get here.
    """
    if item.get_closest_marker("remote") is None:
        return (yield)
    try:
        return (yield)
    except Exception as error:
        if _rerun_will_retry(item, error):
            raise
        try:
            with skip_if_upstream_unavailable(unresolved_hosts=_unresolved_hosts_of(item)):
                raise
        except pytest.skip.Exception as skipped:
            # reported at the test, as a skip from a fixture is, rather than at the line above, which
            # would merge the skips of every test into one `-rs` line that names none of them
            skipped._use_item_location = True  # noqa: SLF001
            raise


@pytest.fixture(autouse=True, scope="session")
def _worker_unique_cache_dir(tmp_path_factory: pytest.TempPathFactory, worker_id: str) -> None:
    """Give each pytest-xdist worker its own cache directory.

    Multiple workers writing to the same fsspec cache metadata file
    concurrently causes PermissionError (WinError 5) on Windows because
    os.replace() fails when the destination file is held open by another
    process. A per-worker directory eliminates that race entirely.

    The WD_CACHE_DIR env-var is honoured by pydantic-settings at
    Settings() instantiation time, so it takes effect for every Settings()
    created during the session.
    """
    cache = tmp_path_factory.mktemp(f"wd-cache-{worker_id}", numbered=False)
    os.environ["WD_CACHE_DIR"] = str(cache)
    yield
    del os.environ["WD_CACHE_DIR"]


def _is_local_address(address: object) -> bool:
    """Say whether a socket address points at this machine.

    Anything that is not an ``(host, port)`` tuple - a unix socket path, most notably - is local by
    definition. pytest-xdist talks to its workers over loopback, so loopback stays open.
    """
    if not isinstance(address, tuple) or not address:
        return True
    # decoded the way `_guarded_getaddrinfo` decodes, not `str()`: a bytes host is valid at
    # `connect` too, and `str(b"127.0.0.1")` is `"b'127.0.0.1'"`, which matches no loopback and
    # would refuse a legitimate local connection
    first = address[0]
    host = os.fsdecode(first) if isinstance(first, (str, bytes)) else str(first)
    host = host.lower()  # names are case-insensitive, and Windows tooling likes to shout them
    if host in {"", "localhost"} or host.endswith(".localhost"):
        return True
    try:
        parsed = ipaddress.ip_address(host)
    except ValueError:
        return False
    # a dual-stack socket reports a v4 peer as `::ffff:127.0.0.1`, and whether `is_loopback` looks
    # through that mapping has moved about between interpreters -- 3.12 answers False where 3.11,
    # 3.13 and 3.14 answer True, and all four are in the CI matrix. Unwrapped here so the
    # answer is the same on all of them. The mapped address is asked the same question, so a mapped
    # `::ffff:8.8.8.8` stays refused
    parsed = getattr(parsed, "ipv4_mapped", None) or parsed
    return parsed.is_loopback or parsed.is_unspecified


_SOCKET_CONNECT = socket.socket.connect
_SOCKET_CONNECT_EX = socket.socket.connect_ex
_SOCKET_GETADDRINFO = socket.getaddrinfo
_SOCKET_GETHOSTBYNAME = socket.gethostbyname
_SOCKET_GETHOSTBYNAME_EX = socket.gethostbyname_ex


def _refuse_name(host: Any, port: Any) -> None:  # noqa: ANN401
    """Refuse a name that is not on this machine, and record it.

    Refused at resolution as well as at `connect`, because this is the step every platform shares.
    The connect patch still holds for a synchronous `socket.connect` on Windows; what it does not
    see there is asyncio, whose `ProactorEventLoop` goes through `_overlapped.ConnectEx` -- which
    is the library's whole download path, so without this `-m "not remote"` would be green on
    Windows for a test that fails everywhere else. Nothing resolves a host it is not about to talk
    to.

    It is also what puts the name in the message. aiohttp resolves before it connects, so a refusal
    at `connect` alone would say `('141.38.2.164', 443)` and leave the reader to work out whose
    server that is; refused at the name, it says `opendata.dwd.de`.

    The host is decoded rather than asked whether it is a `str`: bytes are valid here and asyncio's
    `_ensure_resolved` hands them to the loop unchanged. Anything that is neither -- `None`, which
    is how a local server asks for something to bind to -- is left alone without being asked about,
    there being no name in it to refuse.
    """
    name = os.fsdecode(host) if isinstance(host, (str, bytes)) else None
    if name is not None and not _is_local_address((name, port)):
        msg = (
            f"network access blocked: {name}. A test that reaches the internet needs "
            f"@pytest.mark.remote, or has to be rewritten to work without the network."
        )
        _GUARD_STATE["refused"].append((name, port))
        raise NetworkAccessBlockedError(msg)


def _guarded_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    """Resolve, once the name has been allowed."""
    _refuse_name(host, port)
    return _SOCKET_GETADDRINFO(host, port, *args, **kwargs)


def _guarded_gethostbyname(host: Any) -> Any:  # noqa: ANN401
    """Guard the other way in: a separate C entry point that never reaches `getaddrinfo`.

    Nothing in the tree resolves this way -- aiohttp's `ThreadedResolver` goes through
    `loop.getaddrinfo` -- but a caller that did would have had a name resolved and could then
    connect by a path the connect patch does not see on Windows, which is the hole the name-level
    refusal exists to close.
    """
    _refuse_name(host, None)
    return _SOCKET_GETHOSTBYNAME(host)


def _guarded_gethostbyname_ex(host: Any) -> Any:  # noqa: ANN401
    """As `_guarded_gethostbyname`, for the form that answers with aliases and a list."""
    _refuse_name(host, None)
    return _SOCKET_GETHOSTBYNAME_EX(host)


class NetworkAccessBlockedError(Exception):
    """Raised in place of a connection an unmarked test tried to open.

    Deliberately not an `OSError`. aiohttp turns any `OSError` from a connect into
    `ClientConnectorError`, which the library reports as `NoInternetError` (GH-2640). A guard that
    raised `OSError` was therefore read as being offline: the test failed as `NoInternetError`,
    which reads like a lost connection and not like a missing marker, or -- where a provider
    degrades on it -- passed while testing nothing. Deriving straight from `Exception` puts this
    outside that conversion, so the missing marker is what the failure says.

    Not a `BaseException`, which would escape more: fsspec's `sync()` carries a result back from
    the loop thread through `except Exception`, and anything outside that is dropped for a `None`
    return rather than re-raised.

    Being an `Exception` does leave it catchable by the handful of call sites that degrade on a
    bare `except Exception` -- `provider/dwd/dmo/api.py` and `Wetterdienst.is_valid`
    among them. `_block_network` therefore also fails the test at teardown for a refusal that
    never reached it, so swallowing one postpones the failure rather than avoiding it.
    """


#: What the guard refused during the current test, and whether the test said it meant to provoke
#: one. Read at teardown, because a refusal a caller swallowed has to fail the test all the same.
_GUARD_STATE: dict[str, Any] = {"refused": [], "expected": False, "alone": False}


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Note whether this run is the offline selection, or the whole suite with `remote` in it.

    Last, because deselecting on `-m` is itself done in this hook: asked any earlier, `items` still
    holds the `remote` tests that `-m "not remote"` is about to take out, and every run looks mixed.

    The teardown check below only runs for the former, and what makes that safe is not merely that
    the offline selection has no `remote` test in it. What the guard records is per process, not
    per test, so a connection made by a thread that outlives the test that started it is charged to
    whichever test is current. In a mixed run that happens: a `remote` test opens real sockets, one
    of them times out, and fsspec cancels nothing -- this suite carries `--only-rerun
    FSTimeoutError` because it sees them -- so the attempt can land on an innocent unmarked test and
    fail it at teardown. In the offline selection it cannot: every non-local name and address is
    refused before any I/O, so no socket to one is ever opened, nothing can be waiting on one, and
    there is no attempt left over to arrive late. Failing a correct test is worse than missing a
    swallowed refusal, so the check is kept for the run where it cannot do that -- which is the run
    the CI job gates on -- and the refusal itself, raised either way, covers the rest.
    """
    _GUARD_STATE["alone"] = not any(item.get_closest_marker("remote") for item in items)


#: Whether the refusal is what ended the test itself. Set from the report hook below, because a
#: fixture's teardown cannot see how the call phase went, and the teardown check would otherwise
#: report a second time -- saying a caller swallowed it -- on the run where it plainly did not.
_REFUSAL_ENDED_TEST = pytest.StashKey[bool]()


def _carries_refusal(exception: BaseException, seen: frozenset[int] = frozenset()) -> bool:
    """Say whether the refusal is anywhere in what a phase raised.

    Not just the exception itself: a provider that catches it and raises its own `from exc` has
    still put it in the traceback, where a reader sees it, so the teardown check below must not
    report it a second time. Groups are walked too, an `asyncio` gather being the way several
    connections arrive at once.
    """
    if id(exception) in seen:
        return False
    if isinstance(exception, NetworkAccessBlockedError):
        return True
    seen = seen | {id(exception)}
    nested: tuple[BaseException | None, ...] = (exception.__cause__, exception.__context__)
    if isinstance(exception, BaseExceptionGroup):
        nested = (*nested, *exception.exceptions)
    return any(one is not None and _carries_refusal(one, seen) for one in nested)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Note whether the guard's refusal is what ended this phase.

    Setup as well as the call: a fixture that downloads something is an ordinary thing to write,
    and the refusal reaches the runner from there just as plainly. Accumulated rather than
    assigned, so the later phase does not answer for the earlier one. A refusal raised in another
    fixture's *teardown* is still reported twice -- that report is made after `_block_network` has
    already run its check, so there is nothing for the check to read.

    Only where the phase actually failed, so the stash does not claim a refusal was reported when
    `xfail` turned it into a green xfail instead. That does not rescue the `xfail` case -- see the
    fixture below -- it only keeps this from saying something untrue about it.
    """
    report = yield
    if call.when in {"setup", "call"}:
        ended = call.excinfo is not None and _carries_refusal(call.excinfo.value) and report.outcome == "failed"
        item.stash[_REFUSAL_ENDED_TEST] = item.stash.get(_REFUSAL_ENDED_TEST, default=False) or ended
    return report


def _guarded(original: Any) -> Any:  # noqa: ANN401
    """Wrap a socket connect method so that it refuses anything not on this machine."""

    def wrapper(self: socket.socket, address: object, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if not _is_local_address(address):
            msg = (
                f"network access blocked: {address}. A test that reaches the internet needs "
                f"@pytest.mark.remote, or has to be rewritten to work without the network."
            )
            _GUARD_STATE["refused"].append(address)
            raise NetworkAccessBlockedError(msg)
        return original(self, address, *args, **kwargs)

    return wrapper


@pytest.fixture
def blocked_network() -> list[object]:
    """Say that this test provokes the guard on purpose, and hand it what was refused.

    Without it a refusal fails the test at teardown even where nothing propagated, which is the
    point of the teardown check. Requested after the autouse fixture has armed it, so the flag is
    set between that fixture's setup and its teardown.
    """
    _GUARD_STATE["expected"] = True
    return _GUARD_STATE["refused"]


#: how long the Chrome of the image tests may take to start and draw a first figure, in seconds
_KALEIDO_START_TIMEOUT = 300


def _draw_a_figure() -> None:
    """Draw an empty figure to PNG, which does not return before Chrome is up."""
    import plotly.graph_objects as go  # noqa: PLC0415 -- only the image tests need it

    go.Figure().to_image(format="png")


def _kaleido_server_of(kaleido: Any) -> Any:  # noqa: ANN401
    """Give the global server of an imported `kaleido` module, None where this release has none to reach.

    kaleido 1.0.0, the lowest the `plotting` extra allows, has no `start_sync_server`, and the server object of
    the releases that have one is a private attribute (`_global_server`): a release that lacks any part of what
    `_serve_kaleido` calls is not given a server, and its tests render as they did before GH-3250.
    """
    server = getattr(kaleido, "_global_server", None)
    if server is None or not all(
        callable(getattr(kaleido, name, None)) for name in ("start_sync_server", "stop_sync_server", "calc_fig_sync")
    ):
        return None
    return server


def _kaleido_to_start() -> tuple[Any, Any] | None:
    """Give the `kaleido` module and its server, or None where nothing is to be started.

    That is: kaleido or plotly is not installed, this release of kaleido has no server to reach, or a one-shot render
    fails (Chrome is missing), which the tests that draw an image say for themselves.
    """
    try:
        import kaleido  # noqa: PLC0415 -- optional, and only the image tests need it

        server = _kaleido_server_of(kaleido)
        if server is None:
            return None
        _draw_a_figure()  # one-shot: raises at once where Chrome is missing, which the server would not
    except Exception:  # noqa: BLE001 -- the tests that draw an image say what is wrong, this only warms up
        return None
    return kaleido, server


def _serve_kaleido() -> Generator[None]:
    """Run the body of `_kaleido_server`, kept out of the fixture so that a test can drive it."""
    started = _kaleido_to_start()
    if started is None:
        yield
        return
    kaleido, server = started
    import plotly.io as pio  # noqa: PLC0415 -- only the image tests need it

    # what plotly would hand a one-shot render (the request header of the map tiles); None is kaleido's default
    # (the older plotly, 6.1.1 among them, has no `headers` default)
    kaleido.start_sync_server(
        headers=getattr(pio.defaults, "headers", None),
        plotlyjs=getattr(pio.defaults, "plotlyjs", None),
        mathjax=getattr(pio.defaults, "mathjax", None),
        silence_warnings=True,
    )
    # the thread of the server, which kaleido offers no way to ask whether it is alive; None counts as alive
    thread = getattr(server, "_thread", None)

    def server_is_alive() -> bool:
        return thread is None or thread.is_alive()

    failures: list[BaseException] = []

    def warm_up() -> None:
        try:
            with warnings.catch_warnings():  # the kopts that plotly hands a server, which ignores them
                warnings.filterwarnings("ignore", message="The kopts argument is ignored", category=UserWarning)
                _draw_a_figure()
        except BaseException as error:  # noqa: BLE001 -- handed to the fixture, which fails with it
            failures.append(error)

    drawn = threading.Thread(target=warm_up, daemon=True)
    lock, calc_fig_sync = threading.Lock(), kaleido.calc_fig_sync

    def calc_fig_one_at_a_time(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        with lock:
            return calc_fig_sync(*args, **kwargs)

    try:
        drawn.start()
        deadline = time.monotonic() + _KALEIDO_START_TIMEOUT
        # a server whose thread died (Chrome failed to start) never answers: ask for it as well as for the figure
        while drawn.is_alive() and server_is_alive() and time.monotonic() < deadline:
            drawn.join(1)
        if drawn.is_alive():
            pytest.fail(
                f"the Chrome of kaleido did not draw a first figure: its server thread is "
                f"{'alive' if server_is_alive() else 'dead'} after at most {_KALEIDO_START_TIMEOUT} seconds"
            )
        if failures:
            pytest.fail(f"the Chrome of kaleido failed to draw a first figure: {failures[0]!r}")
        kaleido.calc_fig_sync = calc_fig_one_at_a_time
        yield
    finally:
        kaleido.calc_fig_sync = calc_fig_sync
        if drawn.is_alive():
            # the server is stuck or dead and its queue is never read: have kaleido take the one-shot path again,
            # and its exit hook (which joins the thread without a timeout) do nothing
            server._initialized = False  # noqa: SLF001
        else:
            kaleido.stop_sync_server(silence_warnings=True)


@pytest.fixture(scope="session")
def _kaleido_server() -> Generator[None]:
    """Start the Chrome of kaleido once, before the first image of the session is drawn (GH-3250).

    Without it every `fig.to_image` starts a Chrome of its own and stops it again. On the Intel macOS runners
    that start took so long that the REST API gave up on the request after its 60 seconds (`request-timeout`),
    the log showing Chrome's updater and `choreographer` lines right before: the render is slow there, not the
    provider, and a test that waits for a request is no place to measure it. Here the start is paid for outside
    any timed request, and the images after it are drawn by the Chrome that is up. The request timeout, which
    other tests hold the REST API to, is left as it is.

    Where kaleido, plotly or Chrome are not there, a release of kaleido has no server to start (1.0.0, which the
    lowest-versions job installs), or a first figure fails, nothing is started and the image tests find out for
    themselves as they did before. A server that dies or does not come up while it starts fails the tests with
    that said, rather than leaving each of them waiting on a server that never answers.

    kaleido's server hands every caller the next result of one queue, so two renders at once could swap their
    images: a REST request that gave up after its timeout leaves its render running, and the next test would
    queue behind it. `calc_fig_sync` is therefore called under a lock for the session.
    """
    yield from _serve_kaleido()


@pytest.fixture(autouse=True)
def _kaleido_for_image_tests(request: pytest.FixtureRequest) -> Generator[None]:
    """Give a remote test that draws an image the Chrome of `_kaleido_server`.

    Picked by the name, as the image tests are named for it (`test_..._image`, `test_index_examples[...image...]`),
    and only for those that reach the provider: the others draw no image, or draw one with kaleido stubbed.
    """
    if not (request.node.get_closest_marker("remote") and "image" in request.node.name):
        yield
        return
    request.getfixturevalue("_kaleido_server")
    with warnings.catch_warnings():
        # plotly hands kaleido its `kopts` (request headers), which a running server says it ignores
        warnings.filterwarnings("ignore", message="The kopts argument is ignored", category=UserWarning)
        yield


@pytest.fixture(autouse=True)
def _block_network(request: pytest.FixtureRequest) -> Generator[None]:
    """Refuse non-local socket connections for every test not marked ``remote``.

    ``-m "not remote"`` is documented as the offline selection, so nothing it selects may reach
    upstream. Without this guard an unmarked test that downloads something passes on a warm cache
    and fails on a cold one, which reads like a regression rather than a missing marker.

    The patching is done by hand rather than through ``monkeypatch``, because an autouse fixture
    requesting ``monkeypatch`` would pull it ahead of the module-level fixtures that expect to be
    torn down first.

    Three things it does not cover, all of which would let a connection through rather than refuse
    one wrongly. This is function-scoped and fixtures are set up widest first, so a connection made
    at import time, or by any fixture scoped above `function` -- package, module and class as much
    as session -- happens before it is in place, and is not recorded for the check below either. It
    patches `socket.connect`, which on Windows is not the path asyncio's `ProactorEventLoop` takes
    -- that connects through `_overlapped.ConnectEx`. And it only sees a connection being opened:
    fsspec keeps one filesystem instance per key, and with it one aiohttp session and its
    keep-alive pool, for the life of the worker, so an unmarked test asking for a url a `remote`
    test has just fetched can be served over a connection that is already up. Name resolution goes
    out regardless.

    And a fourth, which is pytest rather than this guard: a non-strict `@pytest.mark.xfail` absorbs
    everything a test can report, the teardown check below included -- a bare `pytest.fail()` in a
    fixture's teardown comes back as a second xfail and the run stays green. So a test that is both
    unmarked and `xfail` can reach upstream and say nothing, and no check made per test can change
    that. `test_benchmarks` was the one in the tree; it is marked now.

    So this holds the suite to its own claim; it is not a sandbox.
    """
    # cleared rather than rebound, so a reference `blocked_network` handed out stays the live one,
    # and before the `remote` return below rather than after it: a marked test that asked for
    # `blocked_network` would otherwise be handed the last unmarked test's refusals as its own
    _GUARD_STATE["refused"].clear()
    _GUARD_STATE["expected"] = False
    # pytest-rerunfailures hands the same `Item` to every attempt, so a retry would otherwise read
    # the first attempt's answer and skip the check
    request.node.stash[_REFUSAL_ENDED_TEST] = False
    if request.node.get_closest_marker("remote"):
        yield
        return
    socket.socket.connect = _guarded(_SOCKET_CONNECT)
    socket.socket.connect_ex = _guarded(_SOCKET_CONNECT_EX)
    socket.getaddrinfo = _guarded_getaddrinfo
    socket.gethostbyname = _guarded_gethostbyname
    socket.gethostbyname_ex = _guarded_gethostbyname_ex
    try:
        yield
    finally:
        socket.socket.connect = _SOCKET_CONNECT
        socket.socket.connect_ex = _SOCKET_CONNECT_EX
        socket.getaddrinfo = _SOCKET_GETADDRINFO
        socket.gethostbyname = _SOCKET_GETHOSTBYNAME
        socket.gethostbyname_ex = _SOCKET_GETHOSTBYNAME_EX
        refused = list(_GUARD_STATE["refused"])
        reported = request.node.stash.get(_REFUSAL_ENDED_TEST, default=False)
        if refused and not _GUARD_STATE["expected"] and not reported and _GUARD_STATE["alone"]:
            # usually something between the socket and the test caught it -- `list_remote_files_
            # fsspec` and `download_file` no longer do, but several providers degrade on a bare
            # `except Exception` -- and a refusal nobody reported is the vacuous pass this guard
            # exists to stop. Not always, though: a refusal raised in another fixture's teardown
            # is reported after this runs, and saying it was swallowed would send the reader
            # looking for an `except Exception` that is not there. So this says what is known
            pytest.fail(
                f"network access blocked: {refused}. A test that reaches the internet needs "
                f"@pytest.mark.remote, or has to be rewritten to work without the network. "
                f"Neither the setup nor the call phase reported it, so it was either caught on "
                f"the way or raised during teardown.",
            )


@pytest.fixture
def default_settings() -> Settings:
    """Provide default settings."""
    return Settings()


@pytest.fixture
def options_drop_nulls_false() -> Options:
    """Provide no drop nulls options."""
    return Options(drop_nulls=False)


@pytest.fixture
def options_convert_units_false() -> Options:
    """Provide no unit conversion options."""
    return Options(convert_units=False)


# True options
@pytest.fixture
def options_skip_empty_true() -> Options:
    """Provide skip empty options."""
    return Options(skip_empty=True)


# False options
@pytest.fixture
def options_humanize_false_drop_nulls_false() -> Options:
    """Provide no humanize and no drop nulls options."""
    return Options(humanize=False, drop_nulls=False)


@pytest.fixture
def options_humanize_false_convert_units_false() -> Options:
    """Provide no humanize and no unit conversion options."""
    return Options(humanize=False, convert_units=False)


@pytest.fixture
def options_humanize_false_convert_units_false_wide_shape() -> Options:
    """Provide wide shape, no humanize and no unit conversion options."""
    return Options(shape="wide", humanize=False, convert_units=False)


@pytest.fixture
def options_humanize_false_wide_shape() -> Options:
    """Provide wide shape and no humanize options."""
    return Options(shape="wide", humanize=False)


@pytest.fixture
def options_convert_units_false_wide_shape() -> Options:
    """Provide wide shape and no unit conversion options."""
    return Options(shape="wide", convert_units=False)


@pytest.fixture
def options_wide_shape() -> Options:
    """Provide wide shape options."""
    return Options(shape="wide")


@pytest.fixture
def metadata() -> dict:
    """Provide metadata."""
    return {
        "producer": {
            "doi": "10.5281/zenodo.3960624",
            "name": "wetterdienst",
            "version": info.version,
            "repository": "https://github.com/earthobservations/wetterdienst",
            "documentation": "https://wetterdienst.readthedocs.io",
        },
        "provider": {
            "attribution": "Source: Deutscher Wetterdienst",
            "copyright": "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
            "country": "Germany",
            "license": {
                "spdx_id": "CC-BY-4.0",
                "name": "Creative Commons Attribution 4.0 International",
                "url": "https://creativecommons.org/licenses/by/4.0/",
            },
            "name_english": "German Weather Service",
            "name_local": "Deutscher Wetterdienst",
            "url": "https://opendata.dwd.de/climate_environment/CDC/",
        },
    }


@pytest.fixture
def _no_client_kwargs_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep client kwargs set in the developer's environment or a `.env` file out of a test.

    `Settings` merges them into its default `fsspec_client_kwargs`, so a test comparing against
    those defaults would otherwise depend on the machine it runs on.
    """
    for name in os.environ:
        if name.upper().startswith("WD_FSSPEC_CLIENT_KWARGS"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
