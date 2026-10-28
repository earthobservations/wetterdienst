# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A file the provider let go is no evidence that the source holds nothing (GH-3539).

Providers log a file they gave up on and answer with the others: a refused download, an AEMET chunk, the road weather
files withdrawn since the listing, a KNMI timestamp that is not there, an SMHI parameter file that was refused, an FMI
exception report with HTTP 200. The station whose file was let go is not counted by `parameter-without-rows`
(`note_skipped_download`), and the other stations are. An answer that says there is nothing (a 404 for a station that
does not report the parameter, Frost's 412, an AEMET `estado` of 404), and a download that failed and was made again
with success, are the source's answer and are still told. One test per family of providers, with the control that is
the answer of the source.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError

from tests.conftest import BUFR_AVAILABLE
from tests.provider.aemet.observation.test_api import BARCELONA, MADRID_RETIRO, _values
from tests.provider.dwd.road.test_api import _stub_downloads, _stub_stations
from tests.provider.fmi.observation.test_values_frames import _EXCEPTION_REPORT, _collection
from tests.provider.fmi.observation.test_values_frames import _serve as _serve_fmi
from tests.provider.fmi.observation.test_values_frames import _values as _fmi_values
from tests.provider.knmi.observation.test_api import _daily_values, _serve_knmi
from tests.provider.metno.frost.test_values_failures import _failed as _frost_answer
from tests.provider.metno.frost.test_values_failures import _values as _frost_values
from tests.provider.smhi.observation.test_api_download_failure import _STATION
from tests.provider.smhi.observation.test_api_download_failure import _request as _smhi_request
from wetterdienst.provider.aemet.observation import api as aemet_api
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File, _failed_file
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from wetterdienst import Settings

CODE = "parameter-without-rows"


def _told() -> list[dict[str, Any]]:
    """Give the warnings of `parameter-without-rows` that the request being served has recorded."""
    return [warning for warning in recorded_warnings() if warning["code"] == CODE]


def _refused(url: str, status: int = 429) -> File:
    """Give a download the source refused, as the network layer hands it back."""
    error = ClientResponseError(request_info=MagicMock(), history=(), status=status, message="refused")
    file = _failed_file(url, error)
    assert file is not None
    return file


# met.no Frost: a 412 is Frost's answer for none, a refusal is a file let go


@pytest.mark.parametrize(
    ("status", "told"),
    [(412, True), (404, True), (429, False), (500, False)],
    ids=["412 is no data", "404 is no data", "429 refused", "500 failed"],
)
def test_frost_values_say_nothing_of_a_discovery_that_failed(
    monkeypatch: pytest.MonkeyPatch, status: int, *, told: bool
) -> None:
    """Frost answers 412 or 404 for the available time series when there are none; anything else is let go."""

    def observations(url: str) -> File:
        return _frost_answer(url, status) if "availableTimeSeries" in url else _frost_answer(url, 404)

    values, _seen = _frost_values(monkeypatch, observations)
    begin_response()
    assert values.all().df.is_empty()
    assert [warning["stations"] for warning in _told()] == ([["SN18700"]] if told else [])


# AEMET: a chunk that failed is skipped; one that AEMET answered for with "no data" is the answer


def _aemet_serving(monkeypatch: pytest.MonkeyPatch, answer: Callable[[str], File]) -> None:
    """Serve the station list as two stations, and every request for values as `answer` says."""
    stations = json.dumps(
        [
            {
                "indicativo": MADRID_RETIRO,
                "nombre": "MADRID, RETIRO",
                "provincia": "MADRID",
                "altitud": "667",
                "latitud": "402941N",
                "longitud": "34041W",
            },
            {
                "indicativo": BARCELONA,
                "nombre": "BARCELONA AEROPUERTO",
                "provincia": "BARCELONA",
                "altitud": "4",
                "latitud": "412258N",
                "longitud": "020412E",
            },
        ]
    ).encode("latin-1")
    fetch = aemet_api._fetch_datos  # noqa: SLF001
    retry = aemet_api._download_with_rate_limit_retry  # noqa: SLF001

    def fetching(url: str, settings: Settings, ttl: object) -> bytes | Exception:
        return stations if "todasestaciones" in url else fetch(url, settings, ttl)  # ty: ignore[invalid-argument-type]

    def downloading(url: str, settings: Settings, ttl: object, **_kwargs: object) -> File:
        # the retry is the provider's own, with no time to wait between attempts
        return retry(url, settings, ttl, wait_initial=0.001, wait_max=0.001, max_retries=2)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(aemet_api, "_fetch_datos", fetching)
    monkeypatch.setattr(aemet_api, "_download_with_rate_limit_retry", downloading)
    monkeypatch.setattr(aemet_api, "download_file", lambda url, **_kwargs: answer(url))


def _envelope(url: str, estado: int, **extra: str) -> File:
    body = json.dumps({"estado": estado, "descripcion": "the answer", **extra}).encode()
    return File(url=url, content=BytesIO(body), status=200)


_AEMET_KINDS = [
    pytest.param(lambda url: _refused(url, 400), False, id="400"),
    pytest.param(lambda url: File(url=url, content=BytesIO(b"<html>maintenance</html>"), status=200), False, id="html"),
    pytest.param(lambda url: _envelope(url, 400), False, id="estado 400 in a 200"),
    pytest.param(lambda url: _envelope(url, 404), True, id="estado 404 is no data"),
    pytest.param(lambda url: _failed_file(url, FileNotFoundError(url)), True, id="404 is no data"),
]


@pytest.mark.parametrize(("answer", "told"), _AEMET_KINDS)
def test_aemet_values_say_nothing_of_a_chunk_that_was_let_go(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[str], File], *, told: bool
) -> None:
    """A chunk that failed, or whose body is no answer (a page, an `estado` that is an error), is let go."""
    _aemet_serving(monkeypatch, answer)
    begin_response()
    assert _values("daily", years=1).is_empty()
    assert len(_told()) == (1 if told else 0)


def test_aemet_values_tell_of_a_chunk_that_failed_and_then_came_without_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download that failed and was made again with success is no file let go: its answer is the source's."""
    calls: list[str] = []

    def answer(url: str) -> File:
        calls.append(url)
        # the first try of each request fails, the second is AEMET's answer that it has no data
        return _refused(url, 503) if calls.count(url) == 1 else _envelope(url, 404)

    _aemet_serving(monkeypatch, answer)
    begin_response()
    assert _values("daily", years=1).is_empty()
    assert len(_told()) == 1
    assert any(calls.count(url) == 2 for url in calls)


def test_aemet_values_name_the_station_that_was_not_let_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """One station's chunk fails and the other's is AEMET's answer of no data: the warning names the other."""
    _aemet_serving(
        monkeypatch,
        lambda url: _refused(url, 400) if f"/{MADRID_RETIRO}" in url else _envelope(url, 404),
    )
    begin_response()
    assert _values("daily", years=1, station_ids=(MADRID_RETIRO, BARCELONA)).is_empty()
    assert [warning["stations"] for warning in _told()] == [[BARCELONA]]


# dwd/road: the files withdrawn since the listing


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_road_weather_says_nothing_of_files_withdrawn_since_the_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404 there is a gap in the window (DWD removed the file), which the provider logs and answers around."""
    _stub_downloads(monkeypatch, [FileNotFoundError("x"), FileNotFoundError("x")], status=404)
    begin_response()
    assert _stub_stations().values().all().df.is_empty()
    assert _told() == []


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_road_weather_tells_of_files_that_hold_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files that arrived and hold no reading are no file let go: the station has none of the parameter."""
    _stub_downloads(monkeypatch, [BytesIO(b"x" * 142), BytesIO(b"x" * 142)])
    begin_response()
    assert _stub_stations().values().all().df.is_empty()
    assert [warning["stations"] for warning in _told()] == [["A006"]]


# KNMI: a timestamp that is not there


def test_knmi_values_say_nothing_of_a_timestamp_that_is_not_there(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file KNMI answers for with a 404 is a moment it does not have, which the provider skips and warns of."""
    _serve_knmi(monkeypatch, tmp_path, FileNotFoundError("not published"))
    begin_response()
    assert _daily_values(days=2).is_empty()
    assert _told() == []


# SMHI: a parameter file that was refused


@pytest.mark.parametrize(
    ("serving", "told"),
    [
        pytest.param(lambda url: _failed_file(url, FileNotFoundError("not found")), True, id="not reported"),
        pytest.param(lambda url: _refused(url, 403), False, id="refused"),
    ],
)
def test_smhi_values_say_nothing_of_a_file_that_was_refused(
    monkeypatch: pytest.MonkeyPatch, serving: Callable[[str], File], *, told: bool
) -> None:
    """A 404 is SMHI answering that the station does not report the parameter; a refusal is a file let go."""

    def download_files(urls: list[str], **_: object) -> list[File]:
        body = json.dumps({"station": [_STATION]}).encode()
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    monkeypatch.setattr(smhi_api, "download_file", lambda url, **_: serving(url))
    begin_response()
    assert _smhi_request().values().all().df.is_empty()
    assert len(_told()) == (1 if told else 0)


# FMI: an exception report is answered with HTTP 200


@pytest.mark.parametrize(
    ("answer", "told"),
    [
        pytest.param(_EXCEPTION_REPORT, False, id="exception report"),
        pytest.param(_collection(), True, id="empty collection"),
    ],
)
def test_fmi_values_say_nothing_of_an_exception_report(
    monkeypatch: pytest.MonkeyPatch, answer: bytes, *, told: bool
) -> None:
    """FMI answers 200 for an error as well as for a station that reports nothing; only the second is told."""
    import datetime as dt  # noqa: PLC0415

    _serve_fmi(monkeypatch, answer)
    begin_response()
    start = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
    assert _fmi_values("hourly", start, start + dt.timedelta(hours=1)).is_empty()
    assert len(_told()) == (1 if told else 0)
