# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The warning `positions-unavailable` is in the answer of a search by place on a network without positions (GH-4088).

DWD gives the 27 regions of its pollen forecast no position (`dwd/pollen`, which declares
`stations_have_positions = False`), so a search by `rank`, `distance` or a bounding box, and an estimate by a point,
answers empty. The warning says why and names the way to find them, by name or id; a search by name or id, by SQL and
the whole list carry none. A network whose stations have a position never has it.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from fastapi.testclient import TestClient

from wetterdienst import Settings, Wetterdienst
from wetterdienst.provider.dwd.pollen import DwdPollenRequest
from wetterdienst.ui import restapi
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

CODE = "positions-unavailable"
POINT = (50.0, 10.0)

#: what each search by place asks for: the arguments of the library call, and the query of REST
BY_PLACE: dict[str, dict[str, str]] = {
    "rank": {"latitude": "50", "longitude": "10", "rank": "3"},
    "distance": {"latitude": "50", "longitude": "10", "distance": "100"},
    "bbox": {"left": "5.8", "bottom": "47.2", "right": "15.1", "top": "55.1"},
}
#: the searches that find the stations, and the whole list
BY_NAME_OR_ID: dict[str, dict[str, str]] = {
    "id": {"stations": "124"},
    "name": {"name": "Mainfranken"},
    "sql": {"sql": "region = 'Hessen'"},
    "all": {"all": "true"},
}


@pytest.fixture(autouse=True)
def _response(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:  # noqa: ANN401
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WD_RESTAPI_SQL", "true")
    begin_response()


def _request() -> DwdPollenRequest:
    return DwdPollenRequest(parameters=[("daily", "data")], settings=Settings(cache_disable=True))


def _codes() -> list[str]:
    return [warning["code"] for warning in recorded_warnings()]


def _library(request: DwdPollenRequest, selection: dict[str, str]) -> None:
    if "stations" in selection:
        request.filter_by_station_id(selection["stations"])
    elif "name" in selection:
        request.filter_by_name(selection["name"])
    elif "sql" in selection:
        request.filter_by_sql(selection["sql"])
    elif "all" in selection:
        request.all()
    elif "rank" in selection:
        request.filter_by_rank(POINT, int(selection["rank"]))
    elif "distance" in selection:
        request.filter_by_distance(POINT, float(selection["distance"]))
    else:
        request.filter_by_bbox(*(float(selection[key]) for key in ("left", "bottom", "right", "top")))


def _rest(path: str = "/api/stations", **query: str) -> dict[str, Any]:
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        path, params={"provider": "dwd", "network": "pollen", "parameters": "daily/data", **query}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("search", BY_PLACE)
def test_the_library_tells_a_search_by_place_that_the_stations_have_no_position(search: str) -> None:
    """`filter_by_rank`, `filter_by_distance` and `filter_by_bbox` answer empty and record the warning, once."""
    request = _request()
    _library(request, BY_PLACE[search])
    assert _codes() == [CODE]
    message = recorded_warnings()[0]["message"]
    assert "dwd/pollen" in message
    assert "no position" in message
    assert "`name`" in message
    assert "`stations`" in message
    assert "filter_by_name" in message
    assert "filter_by_station_id" in message


@pytest.mark.parametrize("search", BY_NAME_OR_ID)
def test_the_library_tells_nothing_to_a_search_by_name_or_id(search: str) -> None:
    """The stations are found by name, id and SQL, and listed by `all()`: no warning, as they are not left out."""
    _library(_request(), BY_NAME_OR_ID[search])
    assert _codes() == []


@pytest.mark.parametrize("search", BY_PLACE)
def test_rest_tells_a_search_by_place_that_the_stations_have_no_position(search: str) -> None:
    """The answer is empty and its `metadata.warnings` has the code, with the way to find the stations."""
    answer = _rest(**BY_PLACE[search])
    assert answer["stations"] == []
    (warning,) = [w for w in answer["metadata"]["warnings"] if w["code"] == CODE]
    assert "dwd/pollen" in warning["message"]
    assert "`name`" in warning["message"]
    assert "`stations`" in warning["message"]
    assert [w["code"] for w in answer["metadata"]["warnings"]] == [CODE]


@pytest.mark.parametrize("search", BY_NAME_OR_ID)
def test_rest_tells_nothing_to_a_search_by_name_or_id(search: str) -> None:
    """The stations come back, with none of the warning."""
    answer = _rest(**BY_NAME_OR_ID[search])
    assert answer["stations"]
    if search == "name":
        # the part-region's name alone finds that part-region first, not another one of Bayern (GH-4207)
        assert answer["stations"][0]["station_id"] == "124"
    assert CODE not in [w["code"] for w in answer["metadata"].get("warnings", [])]


@pytest.mark.parametrize("path", ["/api/interpolate", "/api/summarize"])
def test_rest_tells_an_estimate_by_a_point_that_the_stations_have_no_position(path: str) -> None:
    """`interpolate` and `summarize` rank the stations by a distance, so they are told as a search by place is."""
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        path,
        params={
            "provider": "dwd",
            "network": "pollen",
            "parameters": "daily/data/pollen_load_birch",
            "latitude": "50",
            "longitude": "10",
            "timestamp": "2026-11-18",
        },
    )
    assert CODE in response.text, response.text


@pytest.mark.parametrize(
    ("provider", "network"), [("dwd", "observation"), ("dwd", "mosmix"), ("dwd", "poi"), ("eaufrance", "hubeau")]
)
def test_a_network_whose_stations_have_a_position_never_has_the_flag_down(provider: str, network: str) -> None:
    """The flag is down for a network that declares it and for none other."""
    assert Wetterdienst.resolve(provider, network).stations_have_positions is True
    assert DwdPollenRequest.stations_have_positions is False


@pytest.mark.parametrize("estimate", ["interpolate", "summarize"])
def test_the_library_tells_an_estimate_by_a_point_that_the_stations_have_no_position(estimate: str) -> None:
    """The library's `interpolate` and `summarize` by a point rank by a distance and record the warning as well."""
    request = DwdPollenRequest(
        parameters=[("daily", "data", "pollen_load_birch")],
        start=dt.datetime(2026, 11, 17, tzinfo=dt.UTC),
        end=dt.datetime(2026, 11, 19, tzinfo=dt.UTC),
        settings=Settings(cache_disable=True),
    )
    getattr(request, estimate)(POINT)
    assert CODE in _codes()
