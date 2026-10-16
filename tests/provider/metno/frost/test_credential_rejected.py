# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A client ID that Frost refuses is a `CredentialRejectedError`, whose message never holds the ID (GH-2665)."""

from __future__ import annotations

import datetime as dt
import os
from typing import TYPE_CHECKING

import pytest

from wetterdienst.exceptions import (
    ConfigurationError,
    CredentialMissingError,
    CredentialRejectedError,
    WetterdienstError,
)
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from pathlib import Path

#: a client ID that no message, log line or answer may repeat
CLIENT_ID = "frost-client-id-4f9a"


def reject_client_id(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """Answer every download as Frost answers a client ID it refuses: the exception, with no body."""

    def download_file(*, url: str, **_kwargs: object) -> File:
        return File(url=url, content=OSError(f"{status}, message='Unauthorized'"), status=status)

    monkeypatch.setattr(frost_api, "download_file", download_file)


@pytest.fixture(autouse=True)
def _client_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Give Frost a client ID and nothing else of the `WD_*` variables and `.env` of whoever runs the tests."""
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WD_AUTH__METNO_FROST", CLIENT_ID)


@pytest.mark.parametrize("status", [401, 403])
def test_a_rejected_client_id_raises_credential_rejected_error(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """The stations of a request whose client ID Frost refuses raise the type, which names the setting and not the ID.

    Still a `PermissionError`, which is what it was, so that a caller that caught that still does.
    """
    reject_client_id(monkeypatch, status)
    request = MetnoFrostRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start=dt.datetime(2020, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2020, 1, 2, tzinfo=dt.UTC),
    )
    with pytest.raises(CredentialRejectedError, match=f"HTTP {status}") as excinfo:
        request.all()
    error = excinfo.value
    assert isinstance(error, (ConfigurationError, WetterdienstError, PermissionError))
    assert "WD_AUTH__METNO_FROST" in str(error)
    assert CLIENT_ID not in str(error)
    assert CLIENT_ID not in repr(error)


def test_a_rejected_client_id_is_not_a_missing_one() -> None:
    """Told apart from `CredentialMissingError`: a caller catching a missing key does not catch a refused one."""
    assert not issubclass(CredentialRejectedError, CredentialMissingError)
    assert not issubclass(CredentialMissingError, CredentialRejectedError)
