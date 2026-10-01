# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the request models the CLI, REST API and MCP share."""

import datetime as dt
from types import SimpleNamespace
from typing import Any

import polars as pl
import pytest
from pydantic import ValidationError

from wetterdienst.ui import core
from wetterdienst.ui.core import (
    HistoryRequest,
    InterpolationRequest,
    StationsRequest,
    StripesImageRequest,
    StripesValuesRequest,
    SummaryRequest,
    ValuesRequest,
    _get_stripes_data,
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


@pytest.mark.parametrize("model", [StripesValuesRequest, StripesImageRequest])
@pytest.mark.parametrize(
    ("given", "errors"),
    [
        ({"station": "01048"}, None),
        ({"name": "Dresden"}, None),
        ({"station": "01048", "start_year": 2000, "end_year": 2001}, None),
        ({}, [("missing_one_of", (), {"one_of": [["station"], ["name"]]})]),
        (
            {"station": "01048", "name": "Dresden"},
            [
                ("mutually_exclusive", ("station",), {"conflicts_with": ["name"]}),
                ("mutually_exclusive", ("name",), {"conflicts_with": ["station"]}),
            ],
        ),
        # a range ending where it starts holds one year, and stripes need two
        (
            {"station": "01048", "start_year": 2000, "end_year": 2000},
            [("greater_than_field", ("end_year",), {"field": "start_year", "gt": 2000})],
        ),
        ({"station": "01048", "name_threshold": 1.01}, [("less_than_equal", ("name_threshold",), {"le": 1.0})]),
    ],
)
def test_stripes_selection(
    model: type[StripesValuesRequest | StripesImageRequest],
    given: dict[str, Any],
    errors: list | None,
) -> None:
    """Test climate stripes are made for exactly one of a station or a name, over a range of years."""
    values = {"kind": "temperature", **given}
    if errors is None:
        model.model_validate(values)
        return
    assert _errors(model, values) == errors


def _stripes_of(monkeypatch: pytest.MonkeyPatch, values: dict[int, float | None]) -> None:
    """Serve these annual values, by year, as the one station any stripes request finds."""
    frame = pl.DataFrame(
        {
            "timestamp": [dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc) for year in values],
            "value": list(values.values()),
        },
        schema={"timestamp": pl.Datetime(time_zone="UTC"), "value": pl.Float64},
    )
    stations = SimpleNamespace(
        to_dict=lambda: {"stations": [{"station_id": "01048", "name": "Dresden-Klotzsche"}]},
        values=SimpleNamespace(all=lambda: SimpleNamespace(df=frame)),
    )
    request = SimpleNamespace(filter_by_station_id=lambda _station: stations)
    monkeypatch.setitem(core.CLIMATE_STRIPES_CONFIG["temperature"], "request", lambda _period: request)


def test_stripes_are_scaled_over_the_years_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the colours span the requested years, not the station's whole record (GH-2063).

    Scaled over 2000 to 2009 they left 2003 to 2005 in the middle of the colour map, a third of it
    between them, and `value_scaled` went nowhere near 0 or 1 over the years returned.
    """
    _stripes_of(monkeypatch, {year: float(year - 1999) for year in range(2000, 2010)})
    request = StripesValuesRequest(kind="temperature", station="01048", start_year=2003, end_year=2005)
    df = _get_stripes_data(request).df
    assert df.get_column("timestamp").dt.year().to_list() == [2003, 2004, 2005]
    assert df.get_column("value_scaled").to_list() == [1.0, 0.5, 0.0]


@pytest.mark.parametrize(
    ("values", "years"),
    [
        # no year of the station's record in the range: empty stripes, answered as valid
        ({2000: 1.0, 2001: 2.0}, (2090, 2095)),
        # one year with data, the rest missing: stripes of a single colour
        ({2000: 1.0, 2001: None, 2002: None}, (2000, 2002)),
    ],
)
def test_stripes_need_two_years_with_data(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[int, float | None],
    years: tuple[int, int],
) -> None:
    """Test a range holding fewer than two years with data is refused, not drawn (GH-2063)."""
    _stripes_of(monkeypatch, values)
    request = StripesValuesRequest(kind="temperature", station="01048", start_year=years[0], end_year=years[1])
    with pytest.raises(
        ValueError,
        match="At least two years with data are required to create climate stripes; station 01048 has data from 2000",
    ):
        _get_stripes_data(request)


def test_stripes_of_one_value_take_the_middle_of_the_map(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test years all of one value are scaled to 0.5, not divided by a range of zero into NaN."""
    _stripes_of(monkeypatch, {2019: 700.0, 2020: 700.0})
    df = _get_stripes_data(StripesValuesRequest(kind="temperature", station="01048")).df
    assert df.get_column("value_scaled").to_list() == [0.5, 0.5]


def test_stripes_start_and_end_at_a_year_with_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a start or end year in a gap of the record does not label the stripes with a year without data.

    A start year of 1991 in a record with no data from 1991 to 1994 kept four empty years in front of
    the first stripe, and the image was labelled 1991.
    """
    _stripes_of(monkeypatch, {1990: 1.0, 1991: None, 1992: None, 1993: None, 1994: None, 1995: 2.0, 1996: 3.0})
    request = StripesValuesRequest(kind="temperature", station="01048", start_year=1991, end_year=1999)
    df = _get_stripes_data(request).df
    assert df.get_column("timestamp").dt.year().to_list() == [1995, 1996]


@pytest.mark.parametrize(
    ("kind", "highest", "lowest"),
    [
        # warm is red, cool is blue
        ("temperature", "rgb(103,0,31)", "rgb(5,48,97)"),
        # wet is teal, dry is brown: reversed, the wettest year took brown (GH-2063)
        ("precipitation", "rgb(0,60,48)", "rgb(84,48,5)"),
    ],
)
def test_stripes_colour_the_highest_and_lowest_years_as_their_kind_reads(kind: str, highest: str, lowest: str) -> None:
    """Test the colour map puts each kind's highest year, scaled to 0, and its lowest, scaled to 1, at the right end."""
    # plotly is the `plotting` extra, which a stripes image needs and a stripes request does not
    colors = pytest.importorskip("plotly.colors")
    colours = colors.get_colorscale(core.CLIMATE_STRIPES_CONFIG[kind]["color_map"])
    assert (colours[0][1], colours[-1][1]) == (highest, lowest)


def test_stripes_match_a_name_as_stations_and_values_do() -> None:
    """Test climate stripes default to the name threshold of the other requests and the CLI (GH-2063)."""
    assert StripesValuesRequest(kind="temperature", name="Dresden").name_threshold == 0.8
    assert (
        StripesValuesRequest.model_fields["name_threshold"].default
        == StationsRequest.model_fields["name_threshold"].default
    )


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


def test_select_history_sections_keeps_station_id() -> None:
    """Test a history narrowed to some sections still names its station, first as in the history."""
    history = {
        "station_id": "01048",
        "name": {"station": [], "operator": []},
        "parameter": [],
        "device": [],
        "geography": [],
        "missing_data": {"summary": [], "periods": []},
    }
    selected = core.select_history_sections(history, {"missing_data"})
    assert list(selected.items()) == [("station_id", "01048"), ("missing_data", {"summary": [], "periods": []})]
