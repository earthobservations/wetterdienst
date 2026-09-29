# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the request models the CLI, REST API and MCP share."""

from typing import Any

import pytest
from pydantic import ValidationError

from wetterdienst.ui import core
from wetterdienst.ui.core import (
    HistoryRequest,
    InterpolationRequest,
    StationsRequest,
    SummaryRequest,
    ValuesRequest,
    get_interpolate,
    get_summarize,
)

_BASE = {"provider": "dwd", "network": "observation", "parameters": "daily/kl"}

_BBOX = {"left": 13.0, "bottom": 51.0, "right": 14.0, "top": 52.0}


@pytest.mark.parametrize("model", [StationsRequest, ValuesRequest])
@pytest.mark.parametrize(
    "selection",
    [
        {"all": True},
        {"station": "01048"},
        {"name": "Dresden"},
        # rank caps the fuzzy matches, which the REST API and MCP rely on
        {"name": "Dresden", "rank": 3},
        {"latitude": 51.0, "longitude": 13.7, "rank": 5},
        {"latitude": 51.0, "longitude": 13.7, "distance": 25},
        # a point on the equator and the prime meridian is a point, not a missing one
        {"latitude": 0.0, "longitude": 0.0, "rank": 5},
        _BBOX,
        {"sql": "region='Sachsen'"},
    ],
)
def test_station_selection_accepted(model: type[StationsRequest | ValuesRequest], selection: dict[str, Any]) -> None:
    """Test each station selection is accepted on its own."""
    model.model_validate({**_BASE, **selection})


@pytest.mark.parametrize("model", [StationsRequest, ValuesRequest, HistoryRequest])
@pytest.mark.parametrize("blank", ["", [""], ",", ["", " , "]])
def test_blank_station_selects_nothing(
    model: type[StationsRequest | ValuesRequest | HistoryRequest], blank: str | list[str]
) -> None:
    """Test a blank station id is no selection, so `all` beside it stands on its own.

    FastAPI reads an empty `station=` as `[""]`, which counted as a station selection and refused
    `all=true&station=` as two.
    """
    request = model.model_validate({**_BASE, "all": True, "station": blank})
    assert request.station is None


def test_station_ids_read_from_every_item() -> None:
    """Test station ids are read from a comma-separated string and from each item of a list."""
    request = StationsRequest.model_validate({**_BASE, "station": ["01048, ", "04411,00011"]})
    assert request.station == ["01048", "04411", "00011"]


def _errors(model: type[Any], values: dict[str, Any]) -> list[tuple[str, tuple, dict | None]]:
    """Return each error a model reports for values, as its type, location and context."""
    with pytest.raises(ValidationError) as info:
        model.model_validate(values)
    return [(error["type"], error["loc"], error.get("ctx")) for error in info.value.errors()]


_ONE_OF_SELECTIONS = {
    "one_of": [["all"], ["station"], ["name"], ["latitude", "longitude"], ["left", "bottom", "right", "top"], ["sql"]]
}


@pytest.mark.parametrize("model", [StationsRequest, ValuesRequest])
@pytest.mark.parametrize(
    ("selection", "errors"),
    [
        ({}, [("missing_one_of", (), _ONE_OF_SELECTIONS)]),
        # the REST API answered this for the station and dropped the name without a word
        (
            {"station": "01048", "name": "Hamburg"},
            [
                ("mutually_exclusive", ("station",), {"conflicts_with": ["name"]}),
                ("mutually_exclusive", ("name",), {"conflicts_with": ["station"]}),
            ],
        ),
        # a bounding box conflicts by the first side it gives
        (
            {"all": True, **_BBOX, "sql": "region='Sachsen'"},
            [
                ("mutually_exclusive", ("all",), {"conflicts_with": ["left", "sql"]}),
                ("mutually_exclusive", ("left",), {"conflicts_with": ["all", "sql"]}),
                ("mutually_exclusive", ("sql",), {"conflicts_with": ["all", "left"]}),
            ],
        ),
        ({"latitude": 51.0, "rank": 5}, [("missing_with", ("longitude",), {"required_with": ["latitude"]})]),
        (
            {"latitude": 51.0, "longitude": 13.7},
            [("missing_one_of", (), {"one_of": [["rank"], ["distance"]], "required_with": ["latitude", "longitude"]})],
        ),
        (
            {"latitude": 51.0, "longitude": 13.7, "rank": 5, "distance": 25},
            [
                ("mutually_exclusive", ("rank",), {"conflicts_with": ["distance"]}),
                ("mutually_exclusive", ("distance",), {"conflicts_with": ["rank"]}),
            ],
        ),
        (
            {"left": 13.0, "bottom": 51.0, "right": 14.0},
            [("missing_with", ("top",), {"required_with": ["left", "bottom", "right"]})],
        ),
        (
            {"station": "01048", "rank": 5},
            [("requires", ("rank",), {"requires": [["latitude", "longitude"], ["name"]]})],
        ),
        ({"name": "Dresden", "distance": 25}, [("requires", ("distance",), {"requires": [["latitude", "longitude"]]})]),
    ],
)
def test_station_selection_refused(
    model: type[StationsRequest | ValuesRequest],
    selection: dict[str, Any],
    errors: list[tuple[str, tuple, dict]],
) -> None:
    """Test a request making no station selection, or more than one, or half of one, is refused.

    Each error is located at the field it is about, as pydantic locates one field's error, so the
    REST API reports it at that query parameter and the CLI can name the option.
    """
    assert _errors(model, {**_BASE, **selection}) == errors


@pytest.mark.parametrize(
    ("selection", "message"),
    [
        (
            {},
            (
                "Exactly one of all, station, name, (latitude and longitude), (left, bottom, right and top) or sql "
                "is required"
            ),
        ),
        ({"station": "01048", "name": "Hamburg"}, "Cannot be combined with name"),
        ({"latitude": 51.0, "rank": 5}, "Field required with latitude"),
        (
            {"latitude": 51.0, "longitude": 13.7},
            "Exactly one of rank or distance is required with latitude and longitude",
        ),
        ({"station": "01048", "rank": 5}, "Requires (latitude and longitude) or name"),
    ],
)
def test_station_selection_message(selection: dict[str, Any], message: str) -> None:
    """Test the first error's message is worded as pydantic words its own, naming the fields."""
    with pytest.raises(ValidationError) as info:
        StationsRequest.model_validate({**_BASE, **selection})
    assert info.value.errors()[0]["msg"] == message


@pytest.mark.parametrize(
    ("selection", "errors"),
    [
        ({"all": True}, None),
        ({"station": "01048"}, None),
        ({}, [("missing_one_of", (), {"one_of": [["all"], ["station"]]})]),
        (
            {"all": True, "station": "01048"},
            [
                ("mutually_exclusive", ("all",), {"conflicts_with": ["station"]}),
                ("mutually_exclusive", ("station",), {"conflicts_with": ["all"]}),
            ],
        ),
    ],
)
def test_history_station_selection(selection: dict[str, Any], errors: list | None) -> None:
    """Test a history request selects its stations by exactly one of all or station."""
    if errors is None:
        HistoryRequest.model_validate({**_BASE, **selection})
        return
    assert _errors(HistoryRequest, {**_BASE, **selection}) == errors


@pytest.mark.parametrize("model", [InterpolationRequest, SummaryRequest])
@pytest.mark.parametrize(
    ("reference", "errors"),
    [
        ({"station": "01048"}, None),
        ({"latitude": 51.0, "longitude": 13.7}, None),
        ({"latitude": 0.0, "longitude": 0.0}, None),
        ({}, [("missing_one_of", (), {"one_of": [["station"], ["latitude", "longitude"]]})]),
        (
            {"station": "01048", "latitude": 51.0, "longitude": 13.7},
            [
                ("mutually_exclusive", ("station",), {"conflicts_with": ["latitude"]}),
                ("mutually_exclusive", ("latitude",), {"conflicts_with": ["station"]}),
            ],
        ),
        ({"latitude": 51.0}, [("missing_with", ("longitude",), {"required_with": ["latitude"]})]),
    ],
)
def test_reference_point(
    model: type[InterpolationRequest | SummaryRequest],
    reference: dict[str, Any],
    errors: list | None,
) -> None:
    """Test an interpolation or summary is made for exactly one of a station or a point."""
    values = {**_BASE, "date": "2020-06-30", **reference}
    if errors is None:
        model.model_validate(values)
        return
    assert _errors(model, values) == errors


class _Recorder:
    """Stand in for a request, recording which estimate it was asked for."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def interpolate(self, latlon: tuple[float, float], elevation: float | None) -> None:  # noqa: ARG002
        self.calls.append(("point", latlon))

    def interpolate_by_station_id(self, station_id: str, elevation: float | None) -> None:  # noqa: ARG002
        self.calls.append(("station", station_id))

    summarize = interpolate
    summarize_by_station_id = interpolate_by_station_id


@pytest.mark.parametrize(
    ("get", "model"),
    [(get_interpolate, InterpolationRequest), (get_summarize, SummaryRequest)],
)
def test_point_on_the_equator_is_a_point(
    monkeypatch: pytest.MonkeyPatch,
    get: Any,  # noqa: ANN401
    model: type[InterpolationRequest | SummaryRequest],
) -> None:
    """Test latitude 0 or longitude 0 is estimated for as a point.

    Both getters tested the coordinates for truth, so a point on the equator or the prime meridian
    was taken for no point at all and fell through to the station branch.
    """
    recorder = _Recorder()
    monkeypatch.setattr(core, "_get_stations_request", lambda **_: recorder)
    request = model.model_validate({**_BASE, "date": "2020-06-30", "latitude": 0.0, "longitude": 8.97})
    get(api=None, request=request, settings=None)
    assert recorder.calls == [("point", (0.0, 8.97))]
