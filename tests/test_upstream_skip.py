# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the helper that skips a remote test whose upstream did not answer."""

import os
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError, ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

import wetterdienst.provider.rmi.observation.api as rmi_api
from tests.conftest import skip_if_upstream_unavailable
from wetterdienst.exceptions import DownloadError
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
