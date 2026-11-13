# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A test that meets a provider's rate limit is never rerun (GH-4053).

The suite reruns a remote test that fails with a transient network error (`--only-rerun ClientResponseError` and the
other names of `addopts`, twice, after 5 s). `--only-rerun` matches along the cause chain from pytest-rerunfailures
16.7, and the `ProviderRateLimitError` of a 429 has the 429's `ClientResponseError` as its cause: so it was rerun, and a
provider that had said to wait was asked again after 5 s, twice. `--rerun-except ProviderRateLimitError` takes it out.

The inner runs are real ones in a process of their own, given the options of the outer run (the ones of `addopts`), so
that what is held is the configuration of the suite and not a copy of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError

from tests.conftest import _rerun_will_retry
from wetterdienst.exceptions import DownloadError, ProviderRateLimitError

if TYPE_CHECKING:
    from _pytest.pytester import Pytester

_INNER = """
from pathlib import Path
from unittest.mock import MagicMock

from aiohttp import ClientResponseError

from wetterdienst.exceptions import DownloadError
from wetterdienst.util.network import rate_limited


def _status(status):
    return ClientResponseError(request_info=MagicMock(), history=(), status=status)


def _ran(name):
    path = Path(__file__).parent / f"{name}.count"
    path.write_text(path.read_text() + "x" if path.exists() else "x")


def test_rate_limited():
    _ran("rate_limited")
    raise rate_limited("https://example.org/x", 7) from _status(429)


def test_rate_limited_in_a_wrapper():
    _ran("wrapped")
    try:
        raise rate_limited("https://example.org/x", 7) from _status(429)
    except DownloadError as error:
        raise RuntimeError("the walk failed") from error


def test_the_429_alone():
    _ran("the_429")
    raise _status(429)


def test_a_server_error():
    _ran("server_error")
    raise DownloadError("https://example.org/x", "503") from _status(503)
"""


def _only_rerun(request: pytest.FixtureRequest) -> list[str]:
    patterns = request.config.getoption("only_rerun") or request.config.getini("only_rerun")
    assert patterns, "the suite reruns only what addopts names"
    return [argument for pattern in patterns for argument in ("--only-rerun", pattern)]


def _rerun_except(request: pytest.FixtureRequest) -> list[str]:
    patterns = request.config.getoption("rerun_except") or request.config.getini("rerun_except")
    return [argument for pattern in patterns for argument in ("--rerun-except", pattern)]


def _runs(pytester: Pytester, name: str) -> int:
    return len((pytester.path / f"{name}.count").read_text())


def test_a_rate_limit_error_is_not_rerun_and_a_server_error_is(
    pytester: Pytester, request: pytest.FixtureRequest
) -> None:
    """The suite's own options: the rate limit runs once, the 5xx three times (the run and its two reruns)."""
    pytester.makepyfile(test_inner=_INNER)

    result = pytester.runpytest_subprocess(
        "-p", "no:cacheprovider", "--reruns", "2", "--reruns-delay", "0", *_only_rerun(request), *_rerun_except(request)
    )

    assert result.ret != 0
    assert _runs(pytester, "rate_limited") == 1
    assert _runs(pytester, "wrapped") == 1
    # what the guard is not: a 5xx and the bare 429 are still the transient errors they were
    assert _runs(pytester, "server_error") == 3
    assert _runs(pytester, "the_429") == 3


def test_the_conftest_does_not_expect_a_rerun_of_a_rate_limit_error_with_a_429_cause(
    request: pytest.FixtureRequest,
) -> None:
    """The 429 as the cause is what `--only-rerun` matches; `--rerun-except` takes the error out, here as well."""
    if not request.config.pluginmanager.hasplugin("rerunfailures"):
        pytest.skip("the run does not rerun")
    from pytest_rerunfailures import get_reruns_count  # noqa: PLC0415 -- only there with the plugin

    if not get_reruns_count(request.node):
        pytest.skip("the run does not rerun")
    limited = ProviderRateLimitError("https://example.org/x", "limited", 7)
    limited.__cause__ = ClientResponseError(request_info=MagicMock(), history=(), status=429)
    server_error = DownloadError("https://example.org/x", "503")
    server_error.__cause__ = ClientResponseError(request_info=MagicMock(), history=(), status=503)

    assert _rerun_will_retry(request.node, limited) is False
    assert _rerun_will_retry(request.node, server_error) is True
