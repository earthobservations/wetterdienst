# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The warning `positions-unavailable` is in the answer of a search by place on a network without positions (GH-4088).

DWD gives the 27 regions of its pollen forecast no position (`dwd/pollen`, which declares
`stations_have_positions = False`), so a search by `rank`, `distance` or a bounding box, and an estimate by a point,
answers empty. The warning says why and names the way to find them, by name or id; a search by name or id, by SQL and
the whole list carry none. A network whose stations have a position never has it.

A dataset of a network that has positions can have none: `dwd/derived`'s `monthly/climate_correction_factor`, whose
stations are the postal codes (`datasets_without_positions`, GH-4206).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import polars as pl
import pytest
from fastapi.testclient import TestClient

from wetterdienst import Settings, Wetterdienst
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as derived_api
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
    "sql": {"sql": "region = 'Hessen'"},  # the library's and the command line's only
    "all": {"all": "true"},
}


@pytest.fixture(autouse=True)
def _response(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:  # noqa: ANN401
    monkeypatch.chdir(tmp_path)
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


@pytest.mark.parametrize("search", [name for name in BY_NAME_OR_ID if name != "sql"])
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


# the dataset of a network that has positions that has none: `dwd/derived`'s correction factor (GH-4206)

DERIVED_CODE_MESSAGE = "dwd/derived monthly/climate_correction_factor"


def _derived(*parameters: tuple[str, ...]) -> DwdDerivedRequest:
    return DwdDerivedRequest(parameters=list(parameters), settings=Settings(cache_disable=True))


@pytest.fixture
def _derived_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the directory listing of the correction factor, the one thing its stations read from the network.

    Its stations are the 100000 postal codes, generated, with no position: the files of the technical datasets only
    decide the values.
    """
    monkeypatch.setattr(
        derived_api,
        "create_file_index_for_climate_derived",
        lambda *_args, **_kwargs: pl.LazyFrame({"station_id": []}, schema={"station_id": pl.String}),
    )


@pytest.mark.usefixtures("_derived_listing")
@pytest.mark.parametrize("search", BY_PLACE)
def test_the_library_tells_a_search_by_place_on_the_correction_factor(search: str) -> None:
    """The postal codes are found by id and none by place, so the search says why it found no station, once."""
    request = _derived(("monthly", "climate_correction_factor"))
    _library(request, BY_PLACE[search])
    assert _codes() == [CODE]
    message = recorded_warnings()[0]["message"]
    assert DERIVED_CODE_MESSAGE in message
    assert "no position" in message
    # the postal codes have no name, so a search by name is no way to find them
    assert "`name`" not in message
    assert "filter_by_name" not in message
    assert "`stations`" in message
    assert "filter_by_station_id" in message


@pytest.mark.usefixtures("_derived_listing")
@pytest.mark.parametrize("selection", [{"stations": "48151"}, {"all": "true"}])
def test_the_library_tells_nothing_to_a_search_by_id_on_the_correction_factor(selection: dict[str, str]) -> None:
    """The postal codes are listed and found by id: no warning, as they are not left out."""
    _library(_derived(("monthly", "climate_correction_factor")), selection)
    assert _codes() == []


@pytest.mark.parametrize(
    "parameters",
    [
        [("monthly", "heating_degreedays")],
        [("monthly", "cooling_degreehours_13")],
        [("hourly", "radiation_global")],
        [("hourly", "sunshine_duration")],
        [("daily", "soil")],
        [("monthly", "soil")],
    ],
)
def test_the_other_datasets_of_derived_have_positions_and_are_told_nothing(parameters: list[tuple[str, str]]) -> None:
    """Their lists (`KL_Monatswerte`, `fg_duett`, `sd_duett`, `stations_list_soil`) carry a latitude and longitude."""
    _derived(*parameters)._warn_no_positions()  # noqa: SLF001
    assert _codes() == []


@pytest.fixture
def _derived_with_heating(monkeypatch: pytest.MonkeyPatch, _derived_listing: None) -> None:
    """Serve the station list of the heating degree days with two stations that have a position."""
    meta = derived_api.create_meta_index_for_climate_derived

    def create(dataset: Any, settings: Settings) -> pl.LazyFrame:  # noqa: ANN401
        if dataset.name == "heating_degreedays":
            return pl.LazyFrame(
                {
                    "station_id": ["00044", "00073"],
                    "latitude": [52.9336, 48.6159],
                    "longitude": [8.2370, 13.0506],
                    "elevation": [44.0, 340.0],
                    "name": ["Großenkneten", "Aldersbach-Kriestorf"],
                    "region": ["Niedersachsen", "Bayern"],
                }
            )
        return meta(dataset, settings)

    monkeypatch.setattr(derived_api, "create_meta_index_for_climate_derived", create)


@pytest.mark.usefixtures("_derived_with_heating")
@pytest.mark.parametrize("search", BY_PLACE)
def test_a_request_of_the_correction_factor_among_other_datasets_finds_the_others_and_names_it_alone(
    search: str,
) -> None:
    """The stations of the heating degree days are found by place; the warning is for the dataset that has none."""
    request = _derived(("monthly", "heating_degreedays"), ("monthly", "climate_correction_factor"))
    _library(request, BY_PLACE[search])
    (warning,) = recorded_warnings()
    assert warning["code"] == CODE
    assert DERIVED_CODE_MESSAGE in warning["message"]
    assert "heating_degreedays" not in warning["message"]
    # the warning is about the codes alone, which have no name: the id is the way to find them
    assert "`name`" not in warning["message"]
    assert "`stations`" in warning["message"]


@pytest.mark.usefixtures("_derived_with_heating")
def test_the_stations_of_the_other_datasets_are_found_by_place() -> None:
    """The warning is no empty answer: the two stations of the heating degree days are ranked, none of the codes."""
    request = _derived(("monthly", "heating_degreedays"), ("monthly", "climate_correction_factor"))
    result = request.filter_by_rank(POINT, 5)
    assert set(result.df["dataset"]) == {"heating_degreedays"}
    assert sorted(result.df["station_id"]) == ["00044", "00073"]
    assert _codes() == [CODE]


def test_the_datasets_without_positions_are_declared_by_derived_alone() -> None:
    """The flag of the network stays up for `dwd/derived`, and no other network declares a dataset without positions."""
    assert DwdDerivedRequest.stations_have_positions is True
    assert DwdDerivedRequest.datasets_without_positions == {"monthly/climate_correction_factor"}
    assert DwdDerivedRequest.datasets_without_names == {"monthly/climate_correction_factor"}
    for provider, network in [("dwd", "observation"), ("dwd", "mosmix"), ("dwd", "poi"), ("eaufrance", "hubeau")]:
        assert Wetterdienst.resolve(provider, network).datasets_without_positions == frozenset()


@pytest.mark.usefixtures("_derived_listing")
def test_rest_tells_a_search_by_place_on_the_correction_factor() -> None:
    """The answer is empty and its `metadata.warnings` has the code, as for the pollen regions."""
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "derived",
            "parameters": "monthly/climate_correction_factor",
            **BY_PLACE["rank"],
        },
    )
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["stations"] == []
    (warning,) = [w for w in answer["metadata"]["warnings"] if w["code"] == CODE]
    assert DERIVED_CODE_MESSAGE in warning["message"]


@pytest.mark.usefixtures("_derived_listing")
@pytest.mark.parametrize("estimate", ["interpolate", "summarize"])
def test_the_library_tells_an_estimate_by_a_point_on_the_correction_factor(estimate: str) -> None:
    """Whatever the estimate does with a parameter that is not interpolated, it ranks by a distance first."""
    request = DwdDerivedRequest(
        parameters=[("monthly", "climate_correction_factor", "climate_correction_factor")],
        start=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2026, 3, 1, tzinfo=dt.UTC),
        settings=Settings(cache_disable=True),
    )
    getattr(request, estimate)(POINT)
    assert CODE in _codes()
