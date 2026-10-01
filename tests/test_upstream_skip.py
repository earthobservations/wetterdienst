# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the helper that skips a remote test whose upstream did not answer."""

from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError
from fsspec.exceptions import FSTimeoutError

from tests.conftest import skip_if_upstream_unavailable


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(FSTimeoutError(), id="timeout"),
        pytest.param(_response_error(503), id="503"),
        pytest.param(FileNotFoundError("https://hubeau.eaufrance.fr/api"), id="404"),
    ],
)
def test_a_request_upstream_did_not_answer_skips_the_test(error: Exception) -> None:
    """Test that a timeout, a 5xx or a missing file says nothing about the data and skips."""
    with pytest.raises(pytest.skip.Exception, match="upstream did not answer"), skip_if_upstream_unavailable():
        raise error


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(AssertionError("listed twice"), id="assertion"),
        pytest.param(_response_error(400), id="400"),
        pytest.param(ValueError("unparseable"), id="value"),
    ],
)
def test_an_answer_upstream_gave_still_fails_the_test(error: Exception) -> None:
    """Test that an assertion, or a request upstream refused as malformed, is not skipped.

    A 400 is upstream answering, and what it says is that the request was built wrong -- which is
    exactly what a test of the provider exists to report.

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
