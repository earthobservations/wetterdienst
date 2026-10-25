# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the helper that skips a remote test whose upstream did not answer."""

import errno
import os
import socket
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError, ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

import wetterdienst.provider.rmi.observation.api as rmi_api
from tests import conftest
from tests.conftest import skip_if_upstream_problem, skip_if_upstream_unavailable
from wetterdienst.exceptions import CredentialRejectedError, DownloadError, NoInternetError
from wetterdienst.util.network import File


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(FSTimeoutError(), id="timeout"),
        pytest.param(_response_error(503), id="503"),
        pytest.param(ServerDisconnectedError(), id="dropped connection"),
    ],
)
def test_a_request_upstream_did_not_answer_skips_the_test(error: Exception) -> None:
    """Test that a timeout, a 5xx or a dropped connection says nothing about the data and skips."""
    with pytest.raises(pytest.skip.Exception, match="upstream did not answer"), skip_if_upstream_unavailable():
        raise error


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(AssertionError("listed twice"), id="assertion"),
        pytest.param(_response_error(400), id="400"),
        pytest.param(FileNotFoundError("https://hubeau.eaufrance.fr/api"), id="404"),
        pytest.param(ValueError("unparseable"), id="value"),
        pytest.param(
            CredentialRejectedError("AEMET rejected the request. Check that WD_AUTH__AEMET contains a valid API key."),
            id="credential rejected",
        ),
        pytest.param(_response_error(401), id="401"),
        pytest.param(_response_error(403), id="403"),
        pytest.param(DownloadError("https://example.invalid/file", "refused"), id="download error without a cause"),
    ],
)
def test_an_answer_upstream_gave_still_fails_the_test(error: Exception) -> None:
    """Test that an assertion, or a request upstream refused or could not find, is not skipped.

    A 400 or a 404 is upstream answering, and what it most likely says is that the request was
    built wrong -- which is exactly what a test of the provider exists to report.

    The skip is caught by name, so that a helper skipping these too fails this test rather than
    skipping it along with them.
    """
    raised: Exception | None = None
    try:
        with skip_if_upstream_unavailable():
            raise error  # noqa: TRY301 -- the helper under test is what catches it
    except pytest.skip.Exception:
        pytest.fail(f"{error!r} skipped the test")
    except Exception as caught:  # noqa: BLE001 -- compared below, whatever it is
        raised = caught

    assert raised is error


def test_skip_if_upstream_unavailable_decorates_a_test_function() -> None:
    """Test that the helper skips as a decorator too, which is how the remote tests wear it."""

    @skip_if_upstream_unavailable()
    def _remote_test() -> None:
        raise FSTimeoutError

    with pytest.raises(pytest.skip.Exception):
        _remote_test()


@pytest.mark.parametrize(
    ("cause", "skipped"),
    [
        pytest.param(FSTimeoutError(), True, id="timeout"),
        pytest.param(_response_error(503), True, id="503"),
        pytest.param(FileNotFoundError("https://hubeau.eaufrance.fr/api"), False, id="404"),
    ],
)
def test_a_download_error_is_told_by_the_failure_it_carries(cause: Exception, skipped: bool) -> None:  # noqa: FBT001
    """Test that a `DownloadError` skips or fails the test as its cause would (GH-2460).

    `File.raise_if_exception` raises it in place of the stored error, so a timeout that is raised
    through it must still read as upstream not answering.
    """
    error = DownloadError("https://example.invalid/file", "reason")
    error.__cause__ = cause

    if skipped:
        with pytest.raises(pytest.skip.Exception, match="upstream did not answer"), skip_if_upstream_unavailable():
            raise error
    else:
        with pytest.raises(DownloadError), skip_if_upstream_unavailable():
            raise error


@pytest.mark.parametrize(
    ("status", "skipped"),
    [
        pytest.param(502, True, id="502 proxy error"),
        pytest.param(400, False, id="400 is an answer"),
    ],
)
def test_an_rmi_outage_met_by_the_station_reader_skips_the_remote_test(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    skipped: bool,  # noqa: FBT001
) -> None:
    """Test that a remote RMI test wearing the helper is skipped on a 502 from the WFS and fails on a 400 (GH-2522).

    The remote RMI tests raise a `DownloadError` from the station and value readers when the WFS does
    not answer. Run through the reader itself, with the download served an error, this pins that the
    cause `File.raise_if_exception` attaches is what the helper reads, and that only the outage is
    skipped: a 400 is not in `_worth_retrying` and still fails the test.
    """
    monkeypatch.setattr(
        rmi_api,
        "download_file",
        lambda *, url, **_: File(url=url, content=_response_error(status), status=status),
    )

    @skip_if_upstream_unavailable()
    def _remote_test() -> None:
        rmi_api.RmiObservationRequest(parameters=[("hourly", "data", "temperature_air_mean_2m")]).all()

    if skipped:
        with pytest.raises(pytest.skip.Exception, match="upstream did not answer"):
            _remote_test()
    else:
        with pytest.raises(DownloadError):
            _remote_test()


def _run_remote_tests(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
) -> pytest.RunResult:
    """Run generated tests under this suite's own conftest, as their own session in their own process."""
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(filter(None, [str(pytestconfig.rootpath), existing])))
    pytester.makeconftest("pytest_plugins = ['tests.conftest']\n")
    pytester.makepyfile(body)
    return pytester.runpytest_subprocess("-p", "no:randomly", "-p", "no:cacheprovider", "-rs")


def test_a_remote_test_that_a_rerun_would_pass_is_not_skipped_on_its_first_timeout(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the suite's reruns still get their attempts before an outage skips a test (GH-2522).

    `reruns` and `--only-rerun` are what pyproject.toml configures: a timeout is asked again twice,
    and a skip would have ended the test on the first.
    """
    pytester.makeini("[pytest]\nreruns = 2\naddopts = --only-rerun FSTimeoutError\n")
    result = _run_remote_tests(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import pytest
        from aiohttp import ServerDisconnectedError
        from fsspec.exceptions import FSTimeoutError
        from wetterdienst.exceptions import DownloadError

        attempts = {"flaky": 0, "down": 0, "dropped": 0, "downloaded": 0}

        @pytest.mark.remote
        def test_timeout_once():
            attempts["flaky"] += 1
            if attempts["flaky"] == 1:
                raise FSTimeoutError

        @pytest.mark.remote
        def test_timeout_every_time():
            attempts["down"] += 1
            raise FSTimeoutError

        @pytest.mark.remote
        def test_dropped_connection():
            # not among the errors that are rerun, so there is no second attempt to wait for
            attempts["dropped"] += 1
            raise ServerDisconnectedError

        @pytest.mark.remote
        def test_download_that_timed_out():
            # how a failed download arrives: the timeout is only the cause, and is what is rerun
            attempts["downloaded"] += 1
            raise DownloadError("https://example.invalid/file", "timed out") from FSTimeoutError()

        def test_zz_attempts():
            assert attempts == {"flaky": 2, "down": 3, "dropped": 1, "downloaded": 3}
        """,
    )
    result.assert_outcomes(passed=2, skipped=3)
    # the one that passed on its second try asked once more, and the two that never did twice more
    assert result.parseoutcomes()["rerun"] == 5


def test_a_remote_test_is_skipped_on_an_outage_without_wearing_the_helper(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the `remote` marker alone skips a test whose upstream did not answer (GH-2522)."""
    result = _run_remote_tests(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import pytest
        from aiohttp import ClientResponseError
        from unittest.mock import MagicMock
        from fsspec.exceptions import FSTimeoutError

        @pytest.mark.remote
        def test_timeout():
            raise FSTimeoutError

        @pytest.mark.remote
        def test_bad_gateway():
            raise ClientResponseError(request_info=MagicMock(), history=(), status=502)
        """,
    )
    result.assert_outcomes(skipped=2)
    result.stdout.fnmatch_lines(["*upstream did not answer*"])
    # named by the test, not by the conftest line every skip is raised from
    result.stdout.no_fnmatch_line("SKIPPED*conftest.py*")


def test_a_remote_test_that_met_a_real_failure_still_fails(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that an assertion, a 4xx or a missing file fails a remote test, and an unmarked test never skips."""
    result = _run_remote_tests(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import pytest
        from aiohttp import ClientResponseError
        from unittest.mock import MagicMock
        from fsspec.exceptions import FSTimeoutError

        @pytest.mark.remote
        def test_assertion():
            assert [] == [1]

        @pytest.mark.remote
        def test_bad_request():
            raise ClientResponseError(request_info=MagicMock(), history=(), status=400)

        @pytest.mark.remote
        def test_not_found():
            raise FileNotFoundError("https://example.invalid/file")

        def test_unmarked_timeout():
            raise FSTimeoutError
        """,
    )
    result.assert_outcomes(failed=4, skipped=0)


def _no_internet(cause: OSError | None) -> NoInternetError:
    error = NoInternetError("No internet connection: could not reach https://api.example.invalid/items")
    error.__cause__ = cause
    return error


def _semaphore_timeout() -> OSError:
    """Build what Windows raises, which carries `winerror` where POSIX has no such member to construct it with."""
    error = OSError(errno.EINVAL, "The semaphore timeout period has expired")
    error.winerror = 121  # ty: ignore[unresolved-attribute]
    return error


def _network_name_deleted() -> OSError:
    """Build `[WinError 64]`: a `ConnectionResetError` whose `errno` is not `errno.ECONNRESET`.

    The class says what the number does not; `EINVAL` is, as far as is known, the number asyncio's error carries.
    """
    error = ConnectionResetError(errno.EINVAL, "The specified network name is no longer available")
    error.winerror = 64  # ty: ignore[unresolved-attribute]
    return error


_UNANSWERED = [
    pytest.param(TimeoutError(), id="timeout"),
    pytest.param(ConnectionRefusedError(errno.ECONNREFUSED, "refused"), id="refused"),
    pytest.param(ConnectionResetError(errno.ECONNRESET, "reset"), id="reset"),
    pytest.param(OSError(errno.EHOSTUNREACH, "no route to host"), id="no route"),
    # opendata.chmi.cz on macos-26-intel in the Tests run of main 39771397946: `[Network is unreachable]`
    pytest.param(OSError(errno.ENETUNREACH, "Network is unreachable"), id="network unreachable"),
    # how a Windows runner reports a connect that timed out, as the log of the failing eccc tests shows
    pytest.param(_semaphore_timeout(), id="windows semaphore timeout"),
    # hubeau.eaufrance.fr on windows-latest in the Tests runs of main 39625581086 and 39643833924
    pytest.param(_network_name_deleted(), id="windows network name no longer available"),
    pytest.param(ConnectionAbortedError(errno.EINVAL, "aborted"), id="aborted"),
]


@pytest.mark.parametrize("cause", _UNANSWERED)
def test_a_host_that_did_not_answer_skips_while_the_runner_has_network(
    monkeypatch: pytest.MonkeyPatch, cause: OSError
) -> None:
    """Test that a connection one host never took up skips the test when other hosts can be reached (GH-2522)."""
    monkeypatch.setattr(conftest, "_runner_has_network", lambda: True)
    with pytest.raises(pytest.skip.Exception, match="upstream did not answer"), skip_if_upstream_unavailable():
        raise _no_internet(cause)


@pytest.mark.parametrize("cause", _UNANSWERED)
def test_a_runner_that_has_lost_its_network_fails_the_test(monkeypatch: pytest.MonkeyPatch, cause: OSError) -> None:
    """Test that nothing skips when no other host can be reached either: that is no outage of one provider (GH-2640)."""
    monkeypatch.setattr(conftest, "_runner_has_network", lambda: False)
    with pytest.raises(NoInternetError), skip_if_upstream_unavailable():
        raise _no_internet(cause)


@pytest.mark.parametrize(
    "cause",
    [
        pytest.param(socket.gaierror(8, "nodename nor servname provided, or not known"), id="name does not resolve"),
        pytest.param(OSError(errno.ENOENT, "something else"), id="other os error"),
        pytest.param(None, id="no cause"),
    ],
)
def test_a_connection_failure_that_is_not_an_unanswered_host_fails_the_test(
    monkeypatch: pytest.MonkeyPatch, cause: OSError | None
) -> None:
    """Test that a name that does not resolve fails even on a runner with network: a dead or misspelt host looks so."""
    monkeypatch.setattr(conftest, "_runner_has_network", lambda: True)
    with pytest.raises(NoInternetError), skip_if_upstream_unavailable():
        raise _no_internet(cause)


def _no_internet_at(host: str, cause: OSError | None) -> NoInternetError:
    error = NoInternetError(
        f"No internet connection: could not reach https://{host}/sources/v0.jsonld (Cannot connect)"
    )
    error.__cause__ = cause
    return error


_FROST = "frost.met.no"
_API = "api.met.no"
_UNRESOLVED = socket.gaierror(8, "nodename nor servname provided, or not known")


def test_a_name_that_does_not_resolve_skips_when_the_host_is_named_and_the_runner_has_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a host named in `unresolved_hosts` skips on a failed lookup, as frost.met.no on macOS (GH-3252)."""
    monkeypatch.setattr(conftest, "_runner_has_network", lambda: True)
    with (
        pytest.raises(pytest.skip.Exception, match="upstream did not answer"),
        skip_if_upstream_unavailable(unresolved_hosts=("frost.met.no",)),
    ):
        raise _no_internet_at(_FROST, _UNRESOLVED)


def test_a_failed_lookup_through_a_download_error_skips_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the named host is told through a `DownloadError` as well, the way the cause is read for any outage."""
    monkeypatch.setattr(conftest, "_runner_has_network", lambda: True)
    download_error = DownloadError("https://frost.met.no/sources/v0.jsonld", "no connection")
    download_error.__cause__ = _no_internet_at("frost.met.no", _UNRESOLVED)
    with (
        pytest.raises(pytest.skip.Exception, match="upstream did not answer"),
        skip_if_upstream_unavailable(unresolved_hosts=("frost.met.no",)),
    ):
        raise download_error


def test_a_name_that_does_not_resolve_still_fails_for_any_other_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that naming one host leaves a dead or misspelt other one red, and the unnamed default as well."""
    monkeypatch.setattr(conftest, "_runner_has_network", lambda: True)
    with pytest.raises(NoInternetError), skip_if_upstream_unavailable(unresolved_hosts=("frost.met.no",)):
        raise _no_internet_at(_API, _UNRESOLVED)
    with pytest.raises(NoInternetError), skip_if_upstream_unavailable():
        raise _no_internet_at(_FROST, _UNRESOLVED)


def test_a_named_host_that_does_not_resolve_fails_on_a_runner_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a runner that lost its network is no resolver quirk of one host: the test stays red (GH-2640)."""
    monkeypatch.setattr(conftest, "_runner_has_network", lambda: False)
    with pytest.raises(NoInternetError), skip_if_upstream_unavailable(unresolved_hosts=("frost.met.no",)):
        raise _no_internet_at(_FROST, _UNRESOLVED)


def test_a_resolver_marker_applies_to_the_platform_it_names(pytester: pytest.Pytester) -> None:
    """Test that `resolver_fails` hands the hosts on its platform, and none on another."""
    pytester.makepyfile(
        test_markers="""
        import sys
        import pytest

        @pytest.mark.resolver_fails("frost.met.no", platform=sys.platform)
        def test_here(): ...

        @pytest.mark.resolver_fails("frost.met.no", platform="not-" + sys.platform)
        def test_elsewhere(): ...

        @pytest.mark.resolver_fails("api.met.no")
        def test_everywhere(): ...
        """
    )
    items = pytester.getitems(pytester.path / "test_markers.py")
    assert {item.name: conftest._unresolved_hosts_of(item) for item in items} == {  # noqa: SLF001
        "test_here": ("frost.met.no",),
        "test_elsewhere": (),
        "test_everywhere": ("api.met.no",),
    }


def test_a_remote_test_with_a_resolver_marker_skips_on_its_failed_lookup(
    pytester: pytest.Pytester,
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the hook hands the marker's hosts to the helper: the named host skips, another and an unmarked fail."""
    result = _run_remote_tests(
        pytester,
        pytestconfig,
        monkeypatch,
        """
        import socket
        import pytest
        from tests import conftest
        from wetterdienst.exceptions import NoInternetError

        conftest._runner_has_network = lambda: True

        def lookup_failed(host):
            error = NoInternetError(f"No internet connection: could not reach https://{host}/x (Cannot connect)")
            error.__cause__ = socket.gaierror(8, "nodename nor servname provided, or not known")
            return error

        @pytest.mark.remote
        @pytest.mark.resolver_fails("frost.met.no")
        def test_named():
            raise lookup_failed("frost.met.no")

        @pytest.mark.remote
        @pytest.mark.resolver_fails("frost.met.no")
        def test_other_host():
            raise lookup_failed("api.met.no")

        @pytest.mark.remote
        def test_unmarked():
            raise lookup_failed("frost.met.no")
        """,
    )
    result.assert_outcomes(skipped=1, failed=2)


def test_the_connectivity_probe_is_true_if_any_host_takes_a_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the probe tries each host, and is false only when none can be connected to."""
    tried: list[tuple[str, int]] = []

    def refuse_first(address: tuple[str, int], timeout: float) -> MagicMock:  # noqa: ARG001
        tried.append(address)
        if len(tried) == 1:
            raise OSError
        return MagicMock()

    monkeypatch.setattr(conftest.socket, "create_connection", refuse_first)
    assert conftest._runner_has_network() is True  # noqa: SLF001
    assert len(tried) == 2

    def refuse_all(address: tuple[str, int], timeout: float) -> MagicMock:  # noqa: ARG001
        raise OSError

    monkeypatch.setattr(conftest.socket, "create_connection", refuse_all)
    assert conftest._runner_has_network() is False  # noqa: SLF001


def _problem_response(status: int, kind: str) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = {"type": f"urn:wetterdienst:problem:{kind}", "status": status}
    return response


def test_a_rest_answer_of_a_provider_that_timed_out_skips_the_test() -> None:
    """Test that a 504 `upstream-timeout` skips, as a timeout does where the library is called directly."""
    with pytest.raises(pytest.skip.Exception, match="upstream did not answer"):
        skip_if_upstream_problem(_problem_response(504, "upstream-timeout"))


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        pytest.param(200, "ok", id="200"),
        pytest.param(504, "request-timeout", id="the server gave up"),
        pytest.param(503, "upstream-unreachable", id="not told why the connection failed"),
        pytest.param(503, "server-busy", id="busy"),
        pytest.param(502, "upstream-failed", id="the parser may be at fault"),
        pytest.param(501, "credential-missing", id="credential"),
        pytest.param(500, "internal-error", id="our defect"),
        pytest.param(404, "not-found", id="404"),
    ],
)
def test_any_other_rest_answer_is_left_to_the_test(status: int, kind: str) -> None:
    """Test that only a provider's timeout skips: every other status is for the test's own assertion."""
    skip_if_upstream_problem(_problem_response(status, kind))


def test_a_rest_answer_that_is_not_json_is_left_to_the_test() -> None:
    """Test that a 504 with a body that is no problem (a proxy's page) is not read as the provider's timeout."""
    response = MagicMock()
    response.status_code = 504
    response.json.side_effect = ValueError("not json")
    skip_if_upstream_problem(response)
