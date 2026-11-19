# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A station that KNMI's EDR API refuses is told as a file let go, not as a station with no values (GH-3928).

The API answers 400 for a station it does not know. The station is left out of the query, which is a request that was
turned down and no evidence that KNMI holds nothing for it: the answer carries `file-skipped` and not
`station-without-rows`, so a caller does not take the gap for a station without data.
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest
from aiohttp import ClientResponseError
from fastapi.testclient import TestClient

from tests.provider.knmi.observation.catalogue import locations_frame
from wetterdienst.provider.knmi.observation import api, edr
from wetterdienst.ui import restapi
from wetterdienst.util.network import File

STATIONS = ("06260", "06280", "06344")
PARAMS = {"provider": "knmi", "network": "observation", "parameters": "daily/data/temperature_air_mean_2m"}


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    """Keep the WD_* variables of whoever runs the tests out of the settings, and the cache in the test's directory."""
    import os  # noqa: PLC0415

    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(str(tmp_path))
    monkeypatch.setenv("WD_AUTH__KNMI_EDR", "key-for-test")
    monkeypatch.setenv("WD_CACHE_DISABLE", "true")


def _coverage(wsis: list[str]) -> bytes:
    times = ["2020-01-02T00:00:00Z", "2020-01-03T00:00:00Z", "2020-01-04T00:00:00Z"]
    coverages = [
        {
            "type": "Coverage",
            "domain": {"type": "Domain", "domainType": "PointSeries", "axes": {"t": {"values": times}}},
            "ranges": {
                "TG": {
                    "type": "NdArray",
                    "dataType": "float",
                    "axisNames": ["t"],
                    "shape": [3],
                    "values": [1.0, 2.0, 3.0],
                }
            },
            "eumetnet:locationId": wsi,
        }
        for wsi in wsis
    ]
    return json.dumps({"type": "CoverageCollection", "domainType": "PointSeries", "coverages": coverages}).encode()


def _serve(monkeypatch: pytest.MonkeyPatch, *, refused: set[str]) -> None:
    """Serve the list of three stations and an answer for each request, a 400 where it names a station of `refused`."""
    monkeypatch.setattr(api, "read_stations", lambda *_args: locations_frame(*STATIONS))

    def fetch(url: str, _settings: object, _ttl: object) -> File:
        wsis = urlsplit(url).path.rsplit("/", 1)[-1].split(",")
        if any(wsi.rsplit("-", 1)[-1] in refused for wsi in wsis):
            error = ClientResponseError(request_info=MagicMock(), history=(), status=400, message="Bad Request")
            return File(url=url, content=error, status=400)
        return File(url=url, content=BytesIO(_coverage(wsis)), status=200)

    monkeypatch.setattr(edr, "fetch", fetch)


def _values() -> dict:
    client = TestClient(restapi.app, raise_server_exceptions=False)
    response = client.get(
        "/api/values", params={**PARAMS, "stations": ",".join(STATIONS), "timestamp": "2020-01-01/2020-01-03"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_a_refused_station_is_told_as_a_file_let_go_and_not_as_a_station_without_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """06280 is refused (a 400): the answer holds the other two, and `file-skipped` names it."""
    _serve(monkeypatch, refused={"06280"})

    answer = _values()

    assert {row["station_id"] for row in answer["values"]} == {"06260", "06344"}
    warnings = answer["metadata"]["warnings"]
    codes = [warning["code"] for warning in warnings]
    assert "file-skipped" in codes
    assert "station-without-rows" not in codes
    skipped = next(warning for warning in warnings if warning["code"] == "file-skipped")
    assert skipped["stations"] == ["06280"]


def test_a_station_that_the_api_answers_with_no_data_is_still_a_station_without_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 404 is KNMI saying it has nothing, which is the other warning (and the one the refused station is not)."""
    _serve(monkeypatch, refused=set())
    original = edr.fetch

    def fetch(url: str, settings: object, ttl: object) -> File:
        if "06280" in url and "," not in urlsplit(url).path.rsplit("/", 1)[-1]:
            return File(url=url, content=FileNotFoundError("no data"), status=404)
        return original(url, settings, ttl)

    monkeypatch.setattr(edr, "fetch", fetch)
    monkeypatch.setattr(
        edr,
        "plan_requests",
        lambda _n, first, last, resolution, now, _parameters: [
            (chunk, 1)
            for chunk in edr._aligned(first, last, resolution, now)  # noqa: SLF001
        ],
    )

    answer = _values()

    codes = [warning["code"] for warning in answer["metadata"]["warnings"]]
    assert "station-without-rows" in codes
    assert "file-skipped" not in codes
