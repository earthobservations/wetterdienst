# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Frost answers an outage with an exception and a refused client ID with the type that names it (GH-3022, GH-3018).

The request of a values read is served as a failure, against a stubbed upstream.
"""

from __future__ import annotations

import ssl
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientPayloadError, ClientResponseError, ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

from tests.provider.metno.frost.test_values_failures import _failed, _values
from wetterdienst.exceptions import CredentialRejectedError, DownloadError, NoInternetError
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

CLIENT_ID = "client-id"


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status)


def _outage(failure: Exception, status: int) -> Callable[[str], File]:
    return lambda url: File(url=url, content=failure, status=status)


@pytest.mark.parametrize(
    ("failure", "status"),
    [
        pytest.param(FSTimeoutError(), 408, id="timeout"),
        pytest.param(ServerDisconnectedError(), 500, id="dropped connection"),
        pytest.param(ClientPayloadError("body cut short"), 500, id="cut body"),
        pytest.param(_response_error(500), 500, id="500"),
        pytest.param(_response_error(503), 503, id="503"),
        pytest.param(ssl.SSLCertVerificationError("certificate verify failed"), 500, id="tls"),
    ],
)
def test_metno_frost_values_raise_a_download_error_for_a_request_that_did_not_answer(
    monkeypatch: pytest.MonkeyPatch, failure: Exception, status: int
) -> None:
    """A timeout, a dropped connection, a cut body, a 5xx or a TLS failure is raised, not read as no data (GH-3022)."""
    values, seen = _values(monkeypatch, _outage(failure, status))
    with pytest.raises(DownloadError) as raised:
        values.all()
    assert raised.value.__cause__ is failure
    assert raised.value.url == seen[-1].split("?", maxsplit=1)[0]
    assert "?" not in raised.value.url


def test_metno_frost_values_raise_no_internet_error_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """A connection that could not be made is the `NoInternetError` it was (GH-2640)."""
    offline = NoInternetError("no route to host")
    values, _seen = _values(monkeypatch, _outage(offline, 503))
    with pytest.raises(NoInternetError) as raised:
        values.all()
    assert raised.value is offline


@pytest.mark.parametrize("status", [401, 403])
def test_metno_frost_values_raise_credential_rejected_error_for_a_refused_client_id(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """A client ID that Frost refuses on a values request is the type that names the setting, never the ID (GH-3018).

    The catalogue is cached for a day, so an ID revoked after it was read is first met here.
    """
    values, _seen = _values(monkeypatch, lambda url: _failed(url, status))
    with pytest.raises(CredentialRejectedError, match=f"HTTP {status}") as raised:
        values.all()
    assert "WD_AUTH__METNO_FROST" in str(raised.value)
    assert CLIENT_ID not in str(raised.value)
    assert CLIENT_ID not in repr(raised.value)
