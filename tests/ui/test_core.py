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


@pytest.mark.parametrize("model", [StationsRequest, ValuesRequest])
@pytest.mark.parametrize(
    ("selection", "message"),
    [
        ({}, "Select stations by exactly one of all, station, name, latitude/longitude, left/bottom/right/top, sql"),
        # the REST API answered this for the station and dropped the name without a word
        ({"station": "01048", "name": "Hamburg"}, "(got station, name)"),
        ({"all": True, "sql": "region='Sachsen'"}, "(got all, sql)"),
        ({"latitude": 51.0, "rank": 5}, "latitude and longitude go together"),
        ({"latitude": 51.0, "longitude": 13.7}, "latitude/longitude take exactly one of rank or distance"),
        (
            {"latitude": 51.0, "longitude": 13.7, "rank": 5, "distance": 25},
            "latitude/longitude take exactly one of rank or distance",
        ),
        ({"left": 13.0, "bottom": 51.0, "right": 14.0}, "left, bottom, right and top go together"),
        ({"station": "01048", "rank": 5}, "rank applies to latitude/longitude or name"),
        ({"name": "Dresden", "distance": 25}, "distance applies to latitude/longitude"),
    ],
)
def test_station_selection_refused(
    model: type[StationsRequest | ValuesRequest],
    selection: dict[str, Any],
    message: str,
) -> None:
    """Test a request making no station selection, or more than one, or half of one, is refused."""
    with pytest.raises(ValidationError, match=message.replace("(", r"\(").replace(")", r"\)")):
        model.model_validate({**_BASE, **selection})


def test_station_selection_spelled_as_given() -> None:
    """Test the rules name each field as the validation context spells it, the field itself otherwise.

    The CLI passes its options, so its user reads `--station` where the REST API's reads `station`.
    """
    selection = {**_BASE, "station": "01048", "rank": 5}
    names = {"station": "--station", "rank": "--rank", "latitude": "--latitude", "longitude": "--longitude"}
    with pytest.raises(ValidationError, match="--rank applies to --latitude/--longitude or name"):
        StationsRequest.model_validate(selection, context={"field_names": names})
    with pytest.raises(ValidationError, match="Value error, rank applies to latitude/longitude or name"):
        StationsRequest.model_validate(selection)


@pytest.mark.parametrize(
    ("selection", "accepted"),
    [
        ({"all": True}, True),
        ({"station": "01048"}, True),
        ({}, False),
        ({"all": True, "station": "01048"}, False),
    ],
)
def test_history_station_selection(selection: dict[str, Any], *, accepted: bool) -> None:
    """Test a history request selects its stations by exactly one of all or station."""
    if accepted:
        HistoryRequest.model_validate({**_BASE, **selection})
        return
    with pytest.raises(ValidationError, match="Select stations by exactly one of all or station"):
        HistoryRequest.model_validate({**_BASE, **selection})


@pytest.mark.parametrize("model", [InterpolationRequest, SummaryRequest])
@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ({"station": "01048"}, None),
        ({"latitude": 51.0, "longitude": 13.7}, None),
        ({"latitude": 0.0, "longitude": 0.0}, None),
        ({}, "Give exactly one of station or latitude/longitude"),
        (
            {"station": "01048", "latitude": 51.0, "longitude": 13.7},
            "Give exactly one of station or latitude/longitude",
        ),
        ({"latitude": 51.0}, "latitude and longitude go together"),
    ],
)
def test_reference_point(
    model: type[InterpolationRequest | SummaryRequest],
    reference: dict[str, Any],
    message: str | None,
) -> None:
    """Test an interpolation or summary is made for exactly one of a station or a point."""
    values = {**_BASE, "date": "2020-06-30", **reference}
    if message is None:
        model.model_validate(values)
        return
    with pytest.raises(ValidationError, match=message):
        model.model_validate(values)


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
