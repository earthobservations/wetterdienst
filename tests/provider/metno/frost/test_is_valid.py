# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what `MetnoFrostRequest.is_valid()` makes of the answers to its probe (GH-2550)."""

from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from wetterdienst import Wetterdienst
from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.settings import Settings
from wetterdienst.util.network import PROBE_TIMEOUT_SECONDS, File

if TYPE_CHECKING:
    from pathlib import Path

LOGGER = "wetterdienst.provider.metno.frost.api"


def _answer(monkeypatch: pytest.MonkeyPatch, content: BytesIO | Exception, status: int) -> list[dict]:
    """Have the probe's download answer with `content` and `status`; return what it was called with."""
    calls: list[dict] = []

    def download_file(**kwargs: object) -> File:
        calls.append(kwargs)
        return File(url=str(kwargs["url"]), content=content, status=status)

    monkeypatch.setattr(frost_api, "download_file", download_file)
    return calls


@pytest.fixture(autouse=True)
def _client_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Give Frost a client ID and nothing else of the `WD_*` variables and `.env` of whoever runs the tests.

    A credential of another provider in the environment (AEMET's, say) would have `discover()` list
    it as configured, which these tests then read.
    """
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")


@pytest.mark.parametrize("status", [401, 403])
def test_is_valid_is_false_for_a_rejected_client_id(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """Frost's 401 and 403 are the answers that say the client ID is refused."""
    _answer(monkeypatch, Exception(f"{status}, message='Unauthorized'"), status)
    assert MetnoFrostRequest.is_valid() is False


def test_is_valid_is_true_for_an_accepted_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 with a body is the client ID accepted."""
    calls = _answer(monkeypatch, BytesIO(b"{}"), 200)
    assert MetnoFrostRequest.is_valid() is True
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("content", "status"),
    [
        (OSError("certificate verify failed"), 500),
        (NoInternetError("no route to host"), 503),
        (TimeoutError("timed out"), 408),
        (Exception("429, message='Too Many Requests'"), 429),
        (Exception("500, message='Internal Server Error'"), 500),
        (Exception("503, message='Service Unavailable'"), 503),
        (Exception("404, message='Not Found'"), 404),
    ],
    ids=["ssl", "no-network", "timeout", "429", "500", "503", "404"],
)
def test_is_valid_is_unknown_when_the_probe_could_not_tell(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, content: Exception, status: int
) -> None:
    """Any failure but a rejection says nothing about the client ID, so it is None, not False, and logged."""
    _answer(monkeypatch, content, status)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert MetnoFrostRequest.is_valid() is None
    assert [record.getMessage() for record in caplog.records if record.name == LOGGER] == [
        f"Could not check the Frost credentials (status {status}): {content}"
    ]


def test_is_valid_is_one_short_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe asks once and gives up after `PROBE_TIMEOUT_SECONDS`, not as long as a values request (GH-2564)."""
    calls = _answer(monkeypatch, BytesIO(b"{}"), 200)
    assert MetnoFrostRequest.is_valid() is True
    assert calls[0]["attempts"] == 1
    # an acceptance is cached for a minute, not an hour: a revoked client ID must not read True for an hour (GH-2750)
    assert calls[0]["ttl"] is CacheExpiry.ONE_MINUTE
    assert calls[0]["client_kwargs"]["timeout"].total == PROBE_TIMEOUT_SECONDS
    assert Settings().fsspec_client_kwargs["timeout"] > PROBE_TIMEOUT_SECONDS


def test_discover_does_not_probe_a_configured_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """The listing of providers has no `valid` for a configured client ID, which `is_valid()` checks (GH-2564)."""
    calls = _answer(monkeypatch, Exception("401"), 401)
    entry = Wetterdienst.discover()["metno"]["frost"]
    assert (entry["auth"], entry["configured"], "valid" in entry) == (True, True, False)
    assert calls == []
    assert Wetterdienst.is_valid(MetnoFrostRequest) is False
