# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A download that failed and was let go is no reason to say the source holds nothing (GH-3539).

Five providers log a download that failed and answer with what they have: the Frost discovery that was refused
(429), an AEMET chunk, the road weather files withdrawn since the listing, a KNMI timestamp that is not there, an SMHI
parameter file that was refused. What is missing then may be missing for that, and `parameter-without-rows` would tell
a caller the opposite of what a retry would find: it is not told. A file that is not there (404) is the source's
answer, and is still told. Each failure is made as the network layer makes it (`_failed_file`), as the stubs of the
providers' own tests hand a `File` over directly.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError

from tests.conftest import BUFR_AVAILABLE
from tests.provider.dwd.road.test_api import _stub_downloads, _stub_stations
from tests.provider.knmi.observation.test_api import _daily_values, _serve_knmi
from tests.provider.metno.frost.test_values_failures import _failed as _metno_404
from tests.provider.metno.frost.test_values_failures import _values as _metno_values
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


def _refused(url: str, status: int = 429) -> File:
    """Give a download the source refused, as the network layer hands it back."""
    error = ClientResponseError(request_info=MagicMock(), history=(), status=status, message="refused")
    file = _failed_file(url, error)
    assert file is not None
    assert file.status == status
    return file


def _told() -> list[dict[str, Any]]:
    """Give the warnings of `parameter-without-rows` that the request being served has recorded."""
    return [warning for warning in recorded_warnings() if warning["code"] == CODE]


def test_a_refused_download_is_noted_and_a_missing_file_is_not() -> None:
    """The network layer notes every failure but a 404, which is the answer of a source that has no such file."""
    from wetterdienst.util.response_warnings import downloads_failed  # noqa: PLC0415

    begin_response()
    before = downloads_failed()
    _failed_file("https://example.org/a", FileNotFoundError("not there"))
    assert downloads_failed() == before
    _refused("https://example.org/b", 404)
    assert downloads_failed() == before
    _refused("https://example.org/c", 429)
    _failed_file("https://example.org/d", TimeoutError())
    assert downloads_failed() == before + 2


# met.no Frost: the discovery of the time series was refused (GH-2494)


@pytest.mark.parametrize(("refused", "told"), [(False, 1), (True, 0)], ids=["no time series", "discovery refused"])
def test_frost_values_say_nothing_of_a_discovery_that_was_refused(
    monkeypatch: pytest.MonkeyPatch, *, refused: bool, told: int
) -> None:
    """A 404 for the available time series is Frost's answer for none; a 429 for them is a failure."""

    def observations(url: str) -> File:
        return _refused(url) if refused and "availableTimeSeries" in url else _metno_404(url, 404)

    values, _seen = _metno_values(monkeypatch, observations)
    begin_response()
    assert values.all().df.is_empty()
    assert len(_told()) == told
    if told:
        assert _told()[0]["stations"] == ["SN18700"]


# AEMET: a chunk that failed is skipped


@pytest.mark.parametrize(("status", "told"), [(404, 1), (400, 0)], ids=["no data for the chunk", "chunk failed"])
def test_aemet_values_say_nothing_of_a_chunk_that_failed(
    monkeypatch: pytest.MonkeyPatch, status: int, told: int
) -> None:
    """A 404 is AEMET answering that it has no data for the chunk; any other 4xx is a request that failed."""
    from tests.provider.aemet.observation.test_api import MADRID_RETIRO, _values  # noqa: PLC0415

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
        ]
    ).encode("latin-1")
    fetch = aemet_api._fetch_datos  # noqa: SLF001

    def serving(url: str, settings: Settings, ttl: Any) -> bytes | Exception:  # noqa: ANN401
        return stations if "todasestaciones" in url else fetch(url, settings, ttl)

    monkeypatch.setattr(aemet_api, "_fetch_datos", serving)
    monkeypatch.setattr(aemet_api, "_download_with_rate_limit_retry", lambda url, *_a, **_k: _refused(url, status))
    begin_response()
    assert _values("daily", years=1).is_empty()
    assert len(_told()) == told


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
    """Files that arrived and hold no reading are no failure: the station has none of the parameter, and it is told."""
    _stub_downloads(monkeypatch, [BytesIO(b"x" * 142), BytesIO(b"x" * 142)])
    begin_response()
    assert _stub_stations().values().all().df.is_empty()
    assert [warning["stations"] for warning in _told()] == [["A006"]]


# KNMI: a timestamp that is not there


def test_knmi_values_say_nothing_of_a_timestamp_that_is_not_there(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file KNMI answers for with a 404 is skipped with a warning of its own, and the answer around it is a gap."""
    _serve_knmi(monkeypatch, tmp_path, FileNotFoundError("not published"))
    begin_response()
    assert _daily_values(days=2).is_empty()
    assert _told() == []


# SMHI: a parameter file that was refused


@pytest.mark.parametrize(
    ("serving", "told"),
    [
        pytest.param(lambda url: _failed_file(url, FileNotFoundError("not found")), 1, id="not reported"),
        pytest.param(lambda url: _refused(url, 403), 0, id="refused"),
    ],
)
def test_smhi_values_say_nothing_of_a_file_that_was_refused(
    monkeypatch: pytest.MonkeyPatch,
    serving: Callable[[str], File],
    told: int,
) -> None:
    """A 404 is SMHI answering that the station does not report the parameter; a refusal is a failure."""

    def download_files(urls: list[str], **_: object) -> list[File]:
        body = json.dumps({"station": [_STATION]}).encode()
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    monkeypatch.setattr(smhi_api, "download_file", lambda url, **_: serving(url))
    begin_response()
    assert _smhi_request().values().all().df.is_empty()
    assert len(_told()) == told


def test_a_failure_in_a_thread_of_download_files_is_noted_for_the_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`download_files` downloads in threads, which have no context of their own: what they note is the caller's."""
    from wetterdienst.util import network  # noqa: PLC0415
    from wetterdienst.util.response_warnings import downloads_failed  # noqa: PLC0415

    monkeypatch.setattr(network, "download_file", lambda url, **_: _refused(url))
    begin_response()
    before = downloads_failed()

    files = network.download_files(["https://example.org/a", "https://example.org/b"], cache_dir=tmp_path)

    assert [file.status for file in files] == [429, 429]
    assert downloads_failed() == before + 2
