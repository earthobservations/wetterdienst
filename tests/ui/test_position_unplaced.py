# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The warning `position-unplaced` is in the answers it concerns, and in no other (GH-3468).

The referential of `eaufrance/hubeau` lists the Blavet (J543211003) in Algeria, which no swap puts right, so the reader
gives it no position. The answer says so where the station is in it (selected by id, name or SQL, or the whole list)
or where a search by place had to leave it out (rank, distance, bounding box, and so interpolate and summarize,
which rank on a distance); a request for other stations, or for a resolution that does not hold it, is not told.

Offline: the stubs of the referential of `tests/provider/station_catalogue_stubs.py`, through the library, the command
line and REST.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.provider.station_catalogue_stubs import hubeau_request
from wetterdienst.provider.eaufrance.hubeau import HubeauRequest, api
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

CODE = "position-unplaced"
BLAVET = "J543211003"
PARIS = "F700000102"
# Neulliac (Morbihan) and Paris, the places to search by
NEAR_THE_BLAVET = {"latitude": 48.0, "longitude": -2.9}
NEAR_PARIS = {"latitude": 48.85, "longitude": 2.35}
BOX_AROUND_THE_BLAVET = {"left": -3.5, "bottom": 47.5, "right": -2.5, "top": 48.5}
BOX_AROUND_PARIS = {"left": 2.0, "bottom": 48.5, "right": 2.7, "top": 49.0}

#: what each selection asks for: the query of REST, and the same as the arguments of the library call
SELECTIONS: dict[str, dict[str, str]] = {
    "id of Paris": {"stations": PARIS},
    "id of the Blavet": {"stations": BLAVET},
    "name of Paris": {"name": "La Seine à Paris"},
    "name of the Blavet": {"name": "Le Blavet à Neulliac"},
    "sql of Paris": {"sql": f"station_id = '{PARIS}'"},
    "sql of the Blavet": {"sql": f"station_id = '{BLAVET}'"},
    "all": {"all": "true"},
    "rank near the Blavet": {**{k: str(v) for k, v in NEAR_THE_BLAVET.items()}, "rank": "2"},
    "rank near Paris": {**{k: str(v) for k, v in NEAR_PARIS.items()}, "rank": "2"},
    "distance near the Blavet": {**{k: str(v) for k, v in NEAR_THE_BLAVET.items()}, "distance": "50"},
    "distance near Paris": {**{k: str(v) for k, v in NEAR_PARIS.items()}, "distance": "50"},
    "bbox around the Blavet": {k: str(v) for k, v in BOX_AROUND_THE_BLAVET.items()},
    "bbox around Paris": {k: str(v) for k, v in BOX_AROUND_PARIS.items()},
}
#: the selections whose answer holds the Blavet, or that had to leave it out: every place search, as it is never
#: found by one
TOLD = {
    "id of the Blavet",
    "name of the Blavet",
    "sql of the Blavet",
    "all",
    "rank near the Blavet",
    "rank near Paris",
    "distance near the Blavet",
    "distance near Paris",
    "bbox around the Blavet",
    "bbox around Paris",
}
NOT_TOLD = set(SELECTIONS) - TOLD


@pytest.fixture(autouse=True)
def hubeau(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> HubeauRequest:  # noqa: ANN401
    """Serve the referential, and let every test be the process's first to tell a station without a position."""
    monkeypatch.setattr(api, "_reported_unplaced", set())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WD_RESTAPI_SQL", "true")
    begin_response()
    return hubeau_request(monkeypatch)


def _library(request: HubeauRequest, selection: dict[str, str]) -> None:
    """Make the selection on the library's request."""
    point = (float(selection["latitude"]), float(selection["longitude"])) if "latitude" in selection else None
    if "stations" in selection:
        request.filter_by_station_id(selection["stations"])
    elif "name" in selection:
        request.filter_by_name(selection["name"])
    elif "sql" in selection:
        request.filter_by_sql(selection["sql"])
    elif "all" in selection:
        request.all()
    elif point and "rank" in selection:
        request.filter_by_rank(point, int(selection["rank"]))
    elif point:
        request.filter_by_distance(point, float(selection["distance"]))
    else:
        request.filter_by_bbox(*(float(selection[key]) for key in ("left", "bottom", "right", "top")))


def _rest(**query: str) -> list[dict[str, str]]:
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/stations",
        params={"provider": "eaufrance", "network": "hubeau", "parameters": "5_minutes/data", **query},
    )
    assert response.status_code == 200, response.text
    return response.json()["metadata"]["warnings"]


def _cli(**query: str) -> list[dict[str, str]]:
    result = CliRunner().invoke(
        cli,
        [
            "stations",
            "--provider=eaufrance",
            "--network=hubeau",
            "--parameters=5_minutes/data",
            "--with-metadata=true",
            *(f"--{key}={value}" for key, value in query.items()),
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["metadata"]["warnings"]


@pytest.mark.parametrize("selection", SELECTIONS)
def test_the_library_tells_the_station_where_it_concerns_the_answer(selection: str, hubeau: HubeauRequest) -> None:
    """Test that a filter records the warning for the answers that hold the Blavet or leave it out, and no other.

    `all()` is the list the filters select among and tells nothing; `get_stations` tells it for an answer that is the
    list, which the REST and command line tests below hold.
    """
    _library(hubeau, SELECTIONS[selection])

    codes = [warning["code"] for warning in recorded_warnings()]
    assert codes == ([] if selection in NOT_TOLD or selection == "all" else [CODE])


@pytest.mark.parametrize("selection", SELECTIONS)
def test_rest_tells_the_station_where_it_concerns_the_answer(selection: str) -> None:
    """Test that the `metadata` of a REST answer carries the warning for the selections that concern the Blavet."""
    warnings = _rest(**SELECTIONS[selection])

    assert [warning["code"] for warning in warnings] == ([CODE] if selection in TOLD else [])
    if selection in TOLD:
        assert warnings[0]["message"].endswith(f"The referential wrote {BLAVET} raw:35.108562837,0.840483401.")


@pytest.mark.parametrize("selection", SELECTIONS)
def test_the_command_line_tells_the_station_as_rest_does(selection: str) -> None:
    """Test that `stations --with-metadata` carries the same warnings as REST for each selection."""
    assert _cli(**SELECTIONS[selection]) == _rest(**SELECTIONS[selection])


def test_a_resolution_that_does_not_hold_the_station_is_not_told() -> None:
    """Test that the whole list, or a place search, of a resolution without the Blavet carries no warning."""
    for query in ({"all": "true"}, NEAR_THE_BLAVET | {"rank": "2"}, BOX_AROUND_THE_BLAVET):
        text = {key: str(value) for key, value in query.items()}
        response = TestClient(restapi.app, raise_server_exceptions=False).get(
            "/api/stations",
            params={"provider": "eaufrance", "network": "hubeau", "parameters": "hourly/data", **text},
        )
        assert response.status_code == 200, response.text
        assert response.json()["metadata"]["warnings"] == [], query


def test_the_copy_an_estimate_reads_through_tells_the_stations_the_request_listed(hubeau: HubeauRequest) -> None:
    """Test that `interpolate` and `summarize`, which rank on a copy of the request, tell what the request listed."""
    all_ = hubeau.all()
    begin_response()

    copy.copy(hubeau).filter_by_distance((48.84, 2.37), 50, df_all=all_.df)

    assert [warning["code"] for warning in recorded_warnings()] == [CODE]


def test_a_warning_is_logged_once_by_the_process_and_recorded_for_every_answer(
    hubeau: HubeauRequest, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a library caller finds the warning once in its log, and the answer of each request holds it."""
    with caplog.at_level(logging.DEBUG, logger=api.log.name):
        for _ in range(3):
            begin_response()
            hubeau.filter_by_station_id(BLAVET)
            assert [warning["code"] for warning in recorded_warnings()] == [CODE]

    shown = [record.levelname for record in caplog.records if "Hub'Eau lists" in record.getMessage()]
    assert shown == ["WARNING", "DEBUG", "DEBUG"]


def test_stations_that_are_not_among_the_ids_are_not_named(hubeau: HubeauRequest) -> None:
    """Test that the hook tells only the stations among the ids it is given."""
    hubeau.all()
    begin_response()

    hubeau._warn_unplaced([PARIS, "O919001001"])  # noqa: SLF001
    hubeau._warn_unplaced([])  # noqa: SLF001
    assert recorded_warnings() == []

    hubeau._warn_unplaced([PARIS, BLAVET])  # noqa: SLF001
    assert [warning["code"] for warning in recorded_warnings()] == [CODE]
