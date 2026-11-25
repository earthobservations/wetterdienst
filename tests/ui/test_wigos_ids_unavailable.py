# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The warning `wigos-ids-unavailable` reaches the warnings of a REST answer for the stations (GH-4074).

The stations of `fmi/observation` get their `wigos_id` from WMO's register OSCAR. Where it cannot be reached they come
back without, and the answer says why: a caller of the REST API cannot read the log of the server.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.provider.station_catalogue_stubs import _fmi
from wetterdienst.exceptions import NoInternetError
from wetterdienst.model import oscar
from wetterdienst.model.oscar import WIGOS_IDS_UNAVAILABLE
from wetterdienst.ui import restapi
from wetterdienst.util.network import File

_STATIONS = {"provider": "fmi", "network": "observation", "parameters": "hourly/data", "all": "true"}


@pytest.fixture
def client() -> TestClient:
    """Make a client of the app."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def test_the_stations_come_back_with_the_warning_where_oscar_cannot_be_reached(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """A connection that cannot be made to `oscar.wmo.int` costs the `wigos_id` and not the stations."""
    _fmi(monkeypatch)  # the catalogue of FMI, served; the register is served by the stub of the conftest
    reached = client.get("/api/stations", params=_STATIONS)
    assert reached.status_code == 200
    assert [w["code"] for w in reached.json()["metadata"]["warnings"]] == []
    assert {s["wigos_id"] for s in reached.json()["stations"]} >= {"0-246-0-100907"}

    def unreachable(*, url: str, **_: object) -> File:
        return File(url=url, content=NoInternetError("No internet connection: could not reach oscar.wmo.int"), status=0)

    monkeypatch.setattr(oscar, "download_file", unreachable)
    oscar.forget_registers()
    answer = client.get("/api/stations", params=_STATIONS)

    assert answer.status_code == 200
    body = answer.json()
    assert {s["station_id"] for s in body["stations"]} >= {"100539", "100907"}
    assert {s["wigos_id"] for s in body["stations"]} == {None}
    (warning,) = [w for w in body["metadata"]["warnings"] if w["code"] == WIGOS_IDS_UNAVAILABLE]
    assert "oscar.wmo.int" in warning["message"]
    assert "fmi/observation" in warning["message"]
