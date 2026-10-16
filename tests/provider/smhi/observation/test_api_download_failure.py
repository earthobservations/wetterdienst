# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what SMHI values answer when a download fails (GH-2965)."""

import json
import logging
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientPayloadError, ClientResponseError, ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

from tests.conftest import skip_if_upstream_unavailable
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File

_STATION = {
    "id": 98230,
    "name": "Stockholm-Observatoriekullen A",
    "latitude": 59.3417,
    "longitude": 18.0549,
    "height": 43.133,
    "from": 1738368000000,
    "to": 1791727200000,
}
_CORRECTED_ARCHIVE = (
    "Från Datum Tid (UTC);Till Datum Tid (UTC);Representativt dygn;Lufttemperatur;Kvalitet\n"
    "2025-03-29 00:00:01;2025-03-30 00:00:00;2025-03-29;8.8;Y\n"
)


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status)


def _failing(monkeypatch: pytest.MonkeyPatch, failure: Exception, *, archive: bool = False) -> list[str]:
    """Serve the station list, and every values file as `failure`, the corrected archive as a file if asked.

    Returns the values urls requested.
    """
    requested: list[str] = []

    def download_files(urls: list[str], **_: object) -> list[File]:
        body = json.dumps({"station": [_STATION]}).encode()
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    def download_file(url: str, **_: object) -> File:
        requested.append(url)
        if archive and "corrected-archive" in url:
            return File(url=url, content=BytesIO(_CORRECTED_ARCHIVE.encode()), status=200)
        return File(url=url, content=failure, status=getattr(failure, "status", 500))

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    monkeypatch.setattr(smhi_api, "download_file", download_file)
    return requested


def _request() -> SmhiObservationRequest:
    return SmhiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start="2025-03-29",
        end="2025-03-29",
        settings=Settings(cache_disable=True),
    ).filter_by_station_id("98230")


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(FSTimeoutError(), id="timeout"),
        pytest.param(ServerDisconnectedError(), id="dropped connection"),
        pytest.param(ClientPayloadError("body cut short"), id="cut body"),
        pytest.param(_response_error(500), id="500"),
        pytest.param(_response_error(503), id="503"),
    ],
)
@pytest.mark.parametrize("archive", [False, True], ids=["nothing-read", "archive-read-latest-failed"])
def test_smhi_values_raise_a_download_error_for_a_download_that_did_not_answer(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    archive: bool,  # noqa: FBT001
) -> None:
    """A timeout, a dropped connection, a cut body or a 5xx is raised, whatever was read before it.

    Answering the corrected archive alone, or nothing, would read as a station without data (or as the whole
    series) for an SMHI that did not answer.
    """
    _failing(monkeypatch, failure, archive=archive)
    with pytest.raises(DownloadError) as raised:
        _request().values().all()
    assert raised.value.__cause__ is failure
    assert "/parameter/2/station/98230/period/" in raised.value.url


def test_smhi_values_raise_no_internet_error_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed connection is still the `NoInternetError` it was (GH-2640)."""
    offline = NoInternetError("no route to host")
    requested = _failing(monkeypatch, offline)
    with pytest.raises(NoInternetError) as raised:
        _request().values().all()
    assert raised.value is offline
    assert len(requested) == 1


def test_smhi_values_keep_the_empty_result_for_a_station_without_the_parameter(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A 404 is SMHI answering that the station does not report the parameter: an empty frame, no warning."""
    requested = _failing(monkeypatch, FileNotFoundError("not found"))
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.smhi"):
        df = _request().values().all().df
    assert df.is_empty()
    assert len(requested) == 2
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_smhi_values_keep_the_empty_result_for_an_answer_that_is_a_refusal(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A 4xx other than a 404 is an answer: an empty frame, with the warning it had."""
    _failing(monkeypatch, _response_error(403))
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.smhi"):
        df = _request().values().all().df
    assert df.is_empty()
    assert [record for record in caplog.records if record.levelno == logging.WARNING]


@pytest.mark.parametrize(
    ("failure", "skipped"),
    [
        pytest.param(FSTimeoutError(), True, id="timeout"),
        pytest.param(_response_error(502), True, id="502"),
        pytest.param(FileNotFoundError("not found"), False, id="404 is an answer"),
    ],
)
def test_smhi_outage_met_by_the_values_reader_skips_the_remote_test(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    skipped: bool,  # noqa: FBT001
) -> None:
    """A remote SMHI test is skipped on an outage of the values, which used to reach it as an empty frame."""
    _failing(monkeypatch, failure)

    @skip_if_upstream_unavailable()
    def _remote_test() -> None:
        assert not _request().values().all().df.is_empty()

    with pytest.raises(pytest.skip.Exception if skipped else AssertionError):
        _remote_test()
