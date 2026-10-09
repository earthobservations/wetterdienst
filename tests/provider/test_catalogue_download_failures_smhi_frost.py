# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A failed download of the SMHI and Frost station catalogues is raised, not read as no stations (GH-2599).

The same rule as for the other catalogues (GH-2519): each is a required file, so a timeout, a 5xx or a 404 raises a
`DownloadError`, and `NoInternetError` stays quiet. Frost keeps its `PermissionError` for a 401 or 403, and SMHI
raises for the failure of any one parameter's station list rather than answering with the stations of the others.
"""

import json
import logging
from io import BytesIO
from typing import Any

import polars as pl
import pytest

from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.provider.smhi.observation.metadata import SmhiObservationMetadata
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

FAILURES = [
    pytest.param(TimeoutError(), 408, id="timeout"),
    pytest.param(OSError("503 Service Unavailable"), 503, id="server-error"),
    pytest.param(FileNotFoundError("404 Not Found"), 404, id="not-found"),
]

SMHI_STATIONS = {
    "station": [
        {"id": 1, "from": 0, "to": 1_700_000_000_000, "latitude": 1.0, "longitude": 2.0, "height": 3.0, "name": "A"},
    ],
}


def _request(request_class: type, **attributes: object) -> Any:  # noqa: ANN401
    """Build a request that holds only what the catalogue under test reads off `self`."""
    request = object.__new__(request_class)
    request.settings = Settings(cache_disable=True)
    for name, value in attributes.items():
        setattr(request, name, value)
    return request


def _frost() -> Any:  # noqa: ANN401
    return _request(frost_api.MetnoFrostRequest)._all()  # noqa: SLF001


def _smhi() -> Any:  # noqa: ANN401
    parameters = SmhiObservationMetadata["hourly"].datasets[0].parameters[:2]
    return _request(smhi_api.SmhiObservationRequest, parameters=parameters)._all()  # noqa: SLF001


def _ok(url: str, payload: dict) -> File:
    return File(url=url, content=BytesIO(json.dumps(payload).encode()), status=200)


def _serve_frost(monkeypatch: pytest.MonkeyPatch, error: Exception, status: int) -> None:
    monkeypatch.setattr(frost_api, "download_file", lambda *, url, **_: File(url=url, content=error, status=status))


def _serve_smhi(monkeypatch: pytest.MonkeyPatch, errors: dict[int, tuple[Exception, int]]) -> None:
    """Answer the station lists with the stations, bar the lists at the given positions, which fail."""

    def download_files(*, urls: list[str], **_: object) -> list[File]:
        return [
            File(url=url, content=errors[i][0], status=errors[i][1]) if i in errors else _ok(url, SMHI_STATIONS)
            for i, url in enumerate(urls)
        ]

    monkeypatch.setattr(smhi_api, "download_files", download_files)


@pytest.mark.parametrize(("error", "status"), FAILURES)
def test_frost_failed_catalogue_download_is_raised(
    monkeypatch: pytest.MonkeyPatch, error: Exception, status: int
) -> None:
    """A timeout, a 5xx or a 404 on the sources raises, where it read as a network without stations."""
    _serve_frost(monkeypatch, error, status)

    with pytest.raises(DownloadError) as excinfo:
        _frost()

    assert excinfo.value.__cause__ is error


@pytest.mark.parametrize("status", [401, 403])
def test_frost_rejected_credentials_keep_the_permission_error(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """A 401 or 403 is still the `PermissionError` naming the credential, not a `DownloadError`."""
    _serve_frost(monkeypatch, OSError(f"{status} rejected"), status)

    with pytest.raises(PermissionError, match=str(status)):
        _frost()


def test_frost_no_connection_at_all_stays_quiet(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A `NoInternetError` gives no stations and no warning, so working offline still returns empty."""
    _serve_frost(monkeypatch, NoInternetError("offline"), 503)
    caplog.set_level(logging.WARNING)

    assert _frost().collect().is_empty()
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


@pytest.mark.parametrize(("error", "status"), FAILURES)
@pytest.mark.parametrize("failing", [0, 1])
def test_smhi_failed_station_list_download_is_raised(
    monkeypatch: pytest.MonkeyPatch, error: Exception, status: int, failing: int
) -> None:
    """The failure of either parameter's station list raises, instead of answering with the other's stations."""
    _serve_smhi(monkeypatch, {failing: (error, status)})

    with pytest.raises(DownloadError) as excinfo:
        _smhi()

    assert excinfo.value.__cause__ is error


def test_smhi_station_lists_that_all_arrive_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control for the failures above: the same stubs without a failure give the stations."""
    _serve_smhi(monkeypatch, {})

    assert _smhi().collect()["station_id"].to_list() == ["1"]


@pytest.mark.parametrize("failing", [{0, 1}, {1}])
def test_smhi_no_connection_at_all_stays_quiet(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, failing: set[int]
) -> None:
    """A `NoInternetError` gives no stations and no warning, whether it hit every list or only one."""
    _serve_smhi(monkeypatch, {i: (NoInternetError("offline"), 503) for i in failing})
    caplog.set_level(logging.WARNING)

    result = _smhi()

    assert isinstance(result, pl.LazyFrame)
    assert result.collect().is_empty()
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
