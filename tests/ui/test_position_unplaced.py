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
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.provider.station_catalogue_stubs import hubeau_request
from wetterdienst.provider.eaufrance.hubeau import HubeauRequest, api
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable

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
    """Test that `all()` and the filters record the warning for the answers that hold the Blavet or leave it out.

    A filter builds the list it selects among without telling it (`_stations_to_select_among`), so a request for
    other stations carries nothing, where `all()` holds the whole list and tells it.
    """
    _library(hubeau, SELECTIONS[selection])

    codes = [warning["code"] for warning in recorded_warnings()]
    assert codes == ([] if selection in NOT_TOLD else [CODE])


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


#: a window before the Blavet opened (2026-07-09): it cannot have a reading in it
BEFORE_IT_OPENED = {"timestamp": "2026-01-01"}
#: and one after
AFTER_IT_OPENED = {"timestamp": "2026-10-15"}
#: the selections by place or of the whole list, which a window can leave the station out of
WHOLE_LIST_OR_PLACE = [
    name for name in TOLD if name not in {"id of the Blavet", "name of the Blavet", "sql of the Blavet"}
]
#: and those that name the station, which are told whatever the window does to it
NAMING = ["id of the Blavet", "sql of the Blavet"]


@pytest.mark.parametrize("surface", [_rest, _cli])
@pytest.mark.parametrize("selection", WHOLE_LIST_OR_PLACE)
def test_a_window_that_leaves_the_station_out_of_a_listing_takes_the_warning_with_it(
    selection: str, surface: Callable[..., list[dict[str, str]]]
) -> None:
    """Test that a listing for a window before the Blavet opened, where it is not in the answer, has no warning."""
    assert surface(**SELECTIONS[selection], **BEFORE_IT_OPENED) == []
    assert [warning["code"] for warning in surface(**SELECTIONS[selection], **AFTER_IT_OPENED)] == [CODE]


@pytest.mark.parametrize("surface", [_rest, _cli])
def test_a_name_is_matched_among_the_stations_with_a_record_in_the_window(
    surface: Callable[..., list[dict[str, str]]],
) -> None:
    """Test that a name selects among the stations that can have a reading in the window (GH-3026), as for any station.

    The Blavet opened after a window before it, so it is not a candidate for the name and is not in the answer, nor
    told; after the opening it is.
    """
    assert surface(**SELECTIONS["name of the Blavet"], **BEFORE_IT_OPENED) == []
    assert [w["code"] for w in surface(**SELECTIONS["name of the Blavet"], **AFTER_IT_OPENED)] == [CODE]


@pytest.mark.parametrize("surface", [_rest, _cli])
@pytest.mark.parametrize("selection", NAMING)
def test_a_station_named_in_a_listing_is_told_whatever_the_window_does_to_it(
    selection: str, surface: Callable[..., list[dict[str, str]]]
) -> None:
    """Test that asking for the Blavet by id or SQL is told, though the window leaves it out of the answer."""
    warnings = surface(**SELECTIONS[selection], **BEFORE_IT_OPENED)

    assert [warning["code"] for warning in warnings] == [CODE]


def test_the_library_does_not_cut_to_a_window_so_it_tells_the_station(hubeau: HubeauRequest) -> None:
    """Test that `all()` of a request with a window holds the Blavet, as the library does not cut a listing to it."""
    request = HubeauRequest(
        parameters=[("5_minutes", "data")], start="2026-01-01", end="2026-01-02", settings=hubeau.settings
    )
    begin_response()

    assert BLAVET in request.all().df.get_column("station_id").to_list()
    assert [warning["code"] for warning in recorded_warnings()] == [CODE]


def test_the_values_of_a_whole_list_are_told_once(hubeau: HubeauRequest, caplog: pytest.LogCaptureFixture) -> None:
    """Test that `all().values().all()` carries the warning once, in the answer and in the log."""
    with caplog.at_level(logging.DEBUG, logger=api.log.name):
        stations = hubeau.all()
        stations.values().all()

    assert [warning["code"] for warning in recorded_warnings()] == [CODE]
    assert [record.levelname for record in caplog.records if "Hub'Eau lists" in record.getMessage()] == ["WARNING"]
