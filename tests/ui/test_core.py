# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the request models the CLI, REST API and MCP share."""

import datetime as dt
from types import SimpleNamespace
from typing import Any

import polars as pl
import pytest
from pydantic import ValidationError

from wetterdienst.exceptions import ApiNotFoundError
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
    resolve_network,
)

_BASE = {"provider": "dwd", "network": "observation", "parameters": "daily/kl"}

_BBOX = {"left": 13.0, "bottom": 51.0, "right": 14.0, "top": 52.0}


@pytest.mark.parametrize("model", [StationsRequest, ValuesRequest])
@pytest.mark.parametrize(
    "selection",
    [
        {"all": True},
        {"stations": "01048"},
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

    FastAPI reads an empty `stations=` as `[""]`, which counted as a station selection and refused
    `all=true&station=` as two.
    """
    request = model.model_validate({**_BASE, "all": True, "stations": blank})
    assert request.stations is None


def test_station_ids_read_from_every_item() -> None:
    """Test station ids are read from a comma-separated string and from each item of a list."""
    request = StationsRequest.model_validate({**_BASE, "stations": ["01048, ", "04411,00011"]})
    assert request.stations == ["01048", "04411", "00011"]


def _errors(model: type[Any], values: dict[str, Any]) -> list[tuple[str, tuple, dict | None]]:
    """Return each error a model reports for values, as its type, location and context."""
    with pytest.raises(ValidationError) as info:
        model.model_validate(values)
    return [(error["type"], error["loc"], error.get("ctx")) for error in info.value.errors()]


_ONE_OF_RANK_OR_DISTANCE = {"one_of": [["rank"], ["distance"]]}
_ONE_OF_SELECTIONS = {
    "one_of": [["all"], ["stations"], ["name"], ["latitude", "longitude"], ["left", "bottom", "right", "top"], ["sql"]]
}


@pytest.mark.parametrize("model", [StationsRequest, ValuesRequest])
@pytest.mark.parametrize(
    ("selection", "errors"),
    [
        ({}, [("missing_one_of", (), _ONE_OF_SELECTIONS)]),
        # the REST API answered this for the station and dropped the name without a word
        (
            {"stations": "01048", "name": "Hamburg"},
            [
                ("mutually_exclusive", ("stations",), {"conflicts_with": ["name"], **_ONE_OF_SELECTIONS}),
                ("mutually_exclusive", ("name",), {"conflicts_with": ["stations"], **_ONE_OF_SELECTIONS}),
            ],
        ),
        # a bounding box conflicts by the first side it gives
        (
            {"all": True, **_BBOX, "sql": "region='Sachsen'"},
            [
                ("mutually_exclusive", ("all",), {"conflicts_with": ["left", "sql"], **_ONE_OF_SELECTIONS}),
                ("mutually_exclusive", ("left",), {"conflicts_with": ["all", "sql"], **_ONE_OF_SELECTIONS}),
                ("mutually_exclusive", ("sql",), {"conflicts_with": ["all", "left"], **_ONE_OF_SELECTIONS}),
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
                ("mutually_exclusive", ("rank",), {"conflicts_with": ["distance"], **_ONE_OF_RANK_OR_DISTANCE}),
                ("mutually_exclusive", ("distance",), {"conflicts_with": ["rank"], **_ONE_OF_RANK_OR_DISTANCE}),
            ],
        ),
        (
            {"left": 13.0, "bottom": 51.0, "right": 14.0},
            [("missing_with", ("top",), {"required_with": ["left", "bottom", "right"]})],
        ),
        (
            {"stations": "01048", "rank": 5},
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
                "Exactly one of all, stations, name, (latitude and longitude), (left, bottom, right and top) or sql "
                "is required"
            ),
        ),
        (
            {"stations": "01048", "name": "Hamburg"},
            (
                "Cannot be combined with name, give exactly one of all, stations, name, (latitude and longitude), "
                "(left, bottom, right and top) or sql"
            ),
        ),
        ({"latitude": 51.0, "rank": 5}, "Field required with latitude"),
        (
            {"latitude": 51.0, "longitude": 13.7},
            "Exactly one of rank or distance is required with latitude and longitude",
        ),
        ({"stations": "01048", "rank": 5}, "Requires (latitude and longitude) or name"),
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
        ({"stations": "01048"}, None),
        ({}, [("missing_one_of", (), {"one_of": [["all"], ["stations"]]})]),
        (
            {"all": True, "stations": "01048"},
            [
                ("mutually_exclusive", ("all",), {"conflicts_with": ["stations"], "one_of": [["all"], ["stations"]]}),
                ("mutually_exclusive", ("stations",), {"conflicts_with": ["all"], "one_of": [["all"], ["stations"]]}),
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
                (
                    "mutually_exclusive",
                    ("station",),
                    {"conflicts_with": ["latitude"], "one_of": [["station"], ["latitude", "longitude"]]},
                ),
                (
                    "mutually_exclusive",
                    ("latitude",),
                    {"conflicts_with": ["station"], "one_of": [["station"], ["latitude", "longitude"]]},
                ),
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
    values = {**_BASE, "timestamp": "2020-06-30", **reference}
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
                ("mutually_exclusive", ("station",), {"conflicts_with": ["name"], "one_of": [["station"], ["name"]]}),
                ("mutually_exclusive", ("name",), {"conflicts_with": ["station"], "one_of": [["station"], ["name"]]}),
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
    from wetterdienst.model.unit import UnitConverter  # noqa: PLC0415

    frame = pl.DataFrame(
        {
            "timestamp": [dt.datetime(year, 1, 1, tzinfo=dt.UTC) for year in values],
            "value": list(values.values()),
        },
        schema={"timestamp": pl.Datetime(time_zone="UTC"), "value": pl.Float64},
    )
    # read with the parameter and options of the real request, which the metadata names the unit by
    real = core._get_stripes_temperature_request()  # noqa: SLF001
    # as the values build theirs
    unit_converter = UnitConverter()
    unit_converter.update_targets(real.options.unit_targets)
    stations = SimpleNamespace(
        to_dict=lambda: {"stations": [{"station_id": "01048", "name": "Dresden-Klotzsche"}]},
        values=lambda: SimpleNamespace(all=lambda: SimpleNamespace(df=frame), unit_converter=unit_converter),
        parameters=real.parameters,
        options=real.options,
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
    request = model.model_validate({**_BASE, "timestamp": "2020-06-30", "latitude": 0.0, "longitude": 8.97})
    get(api=None, request=request, settings=None)
    assert recorder.calls == [("point", (0.0, 8.97))]


@pytest.mark.parametrize("model", [StationsRequest, ValuesRequest])
def test_swsmos_issue_is_forwarded(model: type[StationsRequest | ValuesRequest]) -> None:
    """Test the issue asked of dwd/swsmos reaches its request rather than reading the latest run (GH-2299)."""
    from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415

    request = model.model_validate(
        {
            "provider": "dwd",
            "network": "swsmos",
            "parameters": "hourly/data",
            "stations": "A006",
            "issue": "2026-10-01T11:00",
        },
    )
    stations_request = core._get_stations_request(  # noqa: SLF001
        api=DwdSwsmosRequest,
        request=request,
        timestamp=None,
        settings=Settings(),
    )
    assert stations_request.issue == dt.datetime(2026, 10, 1, 11, tzinfo=dt.UTC)


def test_swsmos_without_issue_reads_the_latest_run() -> None:
    """Test a dwd/swsmos request without an issue still targets the latest run (GH-2299)."""
    from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.swsmos.api import DwdForecastDate  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415

    request = ValuesRequest.model_validate(
        {"provider": "dwd", "network": "swsmos", "parameters": "hourly/data", "stations": "A006"},
    )
    stations_request = core._get_stations_request(  # noqa: SLF001
        api=DwdSwsmosRequest,
        request=request,
        timestamp=None,
        settings=Settings(),
    )
    assert stations_request.issue is DwdForecastDate.LATEST


def test_get_issues_lists_the_swsmos_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test dwd/swsmos lists its runs as UTC ISO strings, whatever the station (GH-2319)."""
    from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest, api  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [
            f"{api._BASE_URL}/swsmos_LATEST_opendata.csv.bz2",  # noqa: SLF001
            f"{api._BASE_URL}/swsmos_20261004060000_opendata.csv.bz2",  # noqa: SLF001
            f"{api._BASE_URL}/swsmos_20261004050000_opendata.csv.bz2",  # noqa: SLF001
        ],
    )
    request = core.IssuesRequest.model_validate({"provider": "dwd", "network": "swsmos", "station": "A006"})

    assert core.get_issues(api=DwdSwsmosRequest, request=request, settings=Settings()) == [
        "2026-10-04T05:00:00.000000+00:00",
        "2026-10-04T06:00:00.000000+00:00",
    ]


@pytest.mark.parametrize("option", [{"dataset": "icon"}, {"lead_time": "long"}])
def test_get_issues_refuses_dmo_options_for_swsmos(option: dict[str, str]) -> None:
    """Test a DMO-only option asked of dwd/swsmos is refused, as for MOSMIX, rather than ignored (GH-2319)."""
    from wetterdienst.exceptions import InvalidEnumerationError  # noqa: PLC0415
    from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415

    request = core.IssuesRequest.model_validate(
        {"provider": "dwd", "network": "swsmos", "station": "A006", **option},
    )

    with pytest.raises(InvalidEnumerationError, match="applies to DWD DMO only"):
        core.get_issues(api=DwdSwsmosRequest, request=request, settings=Settings())


@pytest.mark.parametrize(
    "environment", [{"WD_TS_SHAPE": "wide"}, {"WD_TS_SKIP_EMPTY": "true"}], ids=["wide", "skip_empty"]
)
@pytest.mark.parametrize(
    ("kind", "dataset", "name_original"),
    [("temperature", "climate_summary", "ja_tt"), ("precipitation", "precipitation_more", "ja_rr")],
)
def test_stripes_read_the_whole_record_long_whatever_the_environment_says(
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str],
    kind: str,
    dataset: str,
    name_original: str,
) -> None:
    """Test the environment leaves the stripes a station's whole record, in a `value` column (GH-2348).

    The stripes requests take their settings from the environment. A wide frame has no `value`
    column, so `WD_TS_SHAPE=wide` raised `ColumnNotFoundError`, and `WD_TS_SKIP_EMPTY=true` dropped
    a station with gaps in its record, which left no years to draw. The station list and the
    station's one download are stubbed, so the dropping of nulls, the skipping and the shaping all
    still run and nothing leaves the machine.
    """
    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415

    # two years of five missing, well below the 0.95 `skip_threshold` asks for by default
    values = [1.0, None, None, 4.0, 5.0]
    years = list(range(2000, 2000 + len(values)))
    stations = pl.DataFrame(
        [
            {
                "resolution": "annual",
                "dataset": dataset,
                "station_id": "01048",
                "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
                "end_timestamp": dt.datetime(2025, 12, 31, tzinfo=dt.UTC),
                "latitude": 51.1278,
                "longitude": 13.7543,
                "elevation": 228.0,
                "name": "Dresden-Klotzsche",
                "state": "Sachsen",
            },
        ],
    )

    def _all(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(request=self, df=stations, df_all=stations, stations_filter=StationsFilter.ALL)

    def _collect_station_parameter_or_dataset(
        self: DwdObservationValues,  # noqa: ARG001
        station_id: str,
        parameter_or_dataset: object,  # noqa: ARG001
    ) -> pl.DataFrame:
        # as the source has them: named by its codes, the missing years as nulls
        return pl.DataFrame(
            [
                {
                    "station_id": station_id,
                    "resolution": "annual",
                    "dataset": dataset,
                    "parameter": name_original,
                    "timestamp": dt.datetime(year, 1, 1, tzinfo=dt.UTC),
                    "value": value,
                    "quality_flags": "10",
                }
                for year, value in zip(years, values, strict=True)
            ],
            schema_overrides={"value": pl.Float64},
        )

    for name, setting in environment.items():
        monkeypatch.setenv(name, setting)
    monkeypatch.setattr(DwdObservationRequest, "all", _all)
    monkeypatch.setattr(
        DwdObservationValues, "_collect_station_parameter_or_dataset", _collect_station_parameter_or_dataset
    )
    df = _get_stripes_data(StripesValuesRequest(kind=kind, station="01048")).df
    assert df.get_column("timestamp").dt.year().to_list() == years
    assert df.get_column("value").to_list() == values


def test_stripes_of_a_station_that_returns_no_rows_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a listed station whose values come back without rows is refused, not upsampled (GH-2369).

    The values drop a station whose collected frame is empty, so one whose data file is missing left
    an empty frame, and `upsample` raised `ComputeError` ("cannot determine upsample boundaries")
    rather than the refusal a station with only null values gets. The station list is stubbed, and
    the station's one download returns the bare frame DWD's values return for a file that is not
    there, so the values' own empty frame is what reaches the stripes.
    """
    from wetterdienst.exceptions import NotEnoughDataError  # noqa: PLC0415
    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415

    stations = pl.DataFrame(
        [
            {
                "resolution": "annual",
                "dataset": "climate_summary",
                "station_id": "01048",
                "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
                "end_timestamp": dt.datetime(2025, 12, 31, tzinfo=dt.UTC),
                "latitude": 51.1278,
                "longitude": 13.7543,
                "elevation": 228.0,
                "name": "Dresden-Klotzsche",
                "state": "Sachsen",
            },
        ],
    )

    def _all(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(request=self, df=stations, df_all=stations, stations_filter=StationsFilter.ALL)

    monkeypatch.setattr(DwdObservationRequest, "all", _all)
    monkeypatch.setattr(
        DwdObservationValues, "_collect_station_parameter_or_dataset", lambda *_args, **_kwargs: pl.DataFrame()
    )
    with pytest.raises(
        NotEnoughDataError,
        match="At least two years with data are required to create climate stripes; station 01048 has data for no year",
    ):
        _get_stripes_data(StripesValuesRequest(kind="temperature", station="01048"))


@pytest.mark.parametrize("model", [ValuesRequest, InterpolationRequest, SummaryRequest])
def test_date_is_refused_naming_timestamp(model: type[ValuesRequest | InterpolationRequest | SummaryRequest]) -> None:
    """Test `date`, renamed to `timestamp`, is refused by naming it, not as an extra input (GH-2438)."""
    station = "stations" if model is ValuesRequest else "station"
    with pytest.raises(ValidationError) as error:
        model.model_validate({**_BASE, station: "01048", "date": "2020-06-30"})
    assert error.value.errors(include_url=False) == [
        {
            "type": "renamed",
            "loc": ("date",),
            "msg": "date was renamed to timestamp",
            "input": "2020-06-30",
            "ctx": {"renamed_to": "timestamp"},
        }
    ]


@pytest.mark.parametrize(
    ("model", "old", "new"),
    [
        (model, old, new)
        for model in (StationsRequest, ValuesRequest, HistoryRequest)
        for old, new in (("station", "stations"), ("parameter", "parameters"), ("period", "periods"))
        # a history request takes no periods, so there the singular is an input it does not know
        if new in model.model_fields
    ],
)
def test_a_list_by_its_singular_name_is_refused_naming_the_plural(
    model: type[StationsRequest | ValuesRequest | HistoryRequest], old: str, new: str
) -> None:
    """Test a parameter that takes a list is plural, and the singular is refused naming it (GH-2561)."""
    given = {key: value for key, value in {**_BASE, "all": True}.items() if key != new}
    with pytest.raises(ValidationError) as error:
        model.model_validate({**given, old: "x"})
    assert [(e["type"], e["loc"], e["msg"]) for e in error.value.errors(include_url=False)] == [
        ("renamed", (old,), f"{old} was renamed to {new}")
    ]


@pytest.mark.parametrize("model", [InterpolationRequest, SummaryRequest, core.IssuesRequest, StripesValuesRequest])
def test_the_one_station_a_request_takes_is_not_a_renamed_list(model: type) -> None:
    """Test `station` is the name of a single station, which the requests that take one go on to accept (GH-2561)."""
    given = {"kind": "temperature"} if model is StripesValuesRequest else {**_BASE, "timestamp": "2020-06-30"}
    if model is core.IssuesRequest:
        given = {"provider": "dwd", "network": "mosmix"}
    assert model.model_validate({**given, "station": "01048"}).station == "01048"
    with pytest.raises(ValidationError) as error:
        model.model_validate({**given, "stations": "01048"})
    types = [e["type"] for e in error.value.errors(include_url=False)]
    assert "extra_forbidden" in types
    assert "renamed" not in types


@pytest.mark.parametrize(
    ("old", "new"),
    [("resolution", "resolutions"), ("dataset", "datasets")],
)
def test_coverage_refuses_the_singular_of_its_lists_naming_the_plural(old: str, new: str) -> None:
    """Test the resolutions and datasets of a coverage are plural, and the singular is refused naming them (GH-2561)."""
    with pytest.raises(ValidationError) as error:
        core.CoverageRequest.model_validate({"provider": "dwd", "network": "observation", old: "x"})
    assert [(e["type"], e["loc"], e["msg"]) for e in error.value.errors(include_url=False)] == [
        ("renamed", (old,), f"{old} was renamed to {new}")
    ]


# what each class of `exceptions.py` is answered with, by name so that a class added to the module
# has to be given its status here (GH-2634)
_STATUS_OF = {
    "ApiNotFoundError": 404,
    "BufrReaderMissingError": 501,
    "ConfigurationError": 501,
    "CredentialMissingError": 501,
    "CredentialRejectedError": 501,
    "DateRequiredError": 400,
    "DownloadError": 502,
    "ExportRefusedError": 500,
    "ImageTooLargeError": 400,
    "InvalidBoundingBoxError": 400,
    "InvalidEnumerationError": 400,
    "InvalidParameterError": 400,
    "InvalidTimeIntervalError": 400,
    "IssueNotFoundError": 404,
    "LocationOutOfRangeError": 400,
    "MetadataNotFoundError": 404,
    "MetaFileFormatError": 502,
    "MetaFileNotFoundError": 502,
    "MissingDependencyError": 501,
    "MissingTimeIntervalError": 400,
    "NoInternetError": 503,
    "NoParametersFoundError": 400,
    "NoPeriodsFoundError": 400,
    "NoStationsWithElevationError": 400,
    "NotEnoughDataError": 400,
    "NotFoundError": 404,
    "ParameterNotCarriedError": 400,
    "ProductFileNotFoundError": 502,
    "ProviderNotFoundError": 404,
    "RequestError": 400,
    "ReversedTimeIntervalError": 400,
    "StartDateEndDateError": 400,
    "StationNotFoundError": 404,
    "UpstreamError": 502,
    "WetterdienstError": 500,
}


def _exception_classes() -> list[type[BaseException]]:
    import inspect  # noqa: PLC0415

    from wetterdienst import exceptions  # noqa: PLC0415

    return [
        cls
        for _, cls in inspect.getmembers(exceptions, inspect.isclass)
        if cls.__module__ == exceptions.__name__ and issubclass(cls, BaseException)
    ]


def test_every_exception_class_is_classified() -> None:
    """Each class of `exceptions.py` has a status above, and `failure_status` gives it that one (GH-2634).

    The REST API, the command line and the MCP tools ask `failure_status` instead of keeping a list of
    the refusals, so a class that is not in the table above was never decided on.
    """
    classes = {cls.__name__: cls for cls in _exception_classes()}
    assert sorted(classes) == sorted(_STATUS_OF)
    for name, cls in classes.items():
        assert core.failure_status(cls.__new__(cls)) == _STATUS_OF[name], name


def test_an_upstream_failure_after_a_timeout_is_a_504() -> None:
    """A provider that did not answer in time is a 504, found in the chain of causes; a dropped connection a 502."""
    from aiohttp import ClientPayloadError, ServerTimeoutError  # noqa: PLC0415
    from fsspec.exceptions import FSTimeoutError  # noqa: PLC0415

    from wetterdienst.exceptions import DownloadError  # noqa: PLC0415

    for cause in (TimeoutError(), ServerTimeoutError(), FSTimeoutError()):
        error = DownloadError("https://example.org/file", "timed out")
        error.__cause__ = cause
        assert core.failure_status(error) == 504, type(cause)
    # through one more link, as a provider that wraps the download's failure in its own
    outer = DownloadError("https://example.org/other", "wrapped")
    inner = DownloadError("https://example.org/file", "timed out")
    inner.__cause__ = TimeoutError()
    outer.__cause__ = inner
    assert core.failure_status(outer) == 504
    dropped = DownloadError("https://example.org/file", "dropped")
    dropped.__cause__ = ClientPayloadError()
    assert core.failure_status(dropped) == 502
    assert core.failure_status(DownloadError("https://example.org/file", "no cause")) == 502

    # a timeout the failure was merely raised while handling is not its cause
    def raised_in_a_handler() -> None:
        try:
            raise TimeoutError  # noqa: TRY301
        except TimeoutError:
            url = "https://example.org/file"
            raise DownloadError(url, "raised in a handler") from None

    with pytest.raises(DownloadError) as raised:
        raised_in_a_handler()
    assert core.failure_status(raised.value) == 502


def test_an_unclassified_wetterdienst_error_is_a_server_error() -> None:
    """A class derived from the root alone, whoever adds it, is answered as the server's error (GH-2634)."""
    from wetterdienst.exceptions import WetterdienstError  # noqa: PLC0415

    class UnplacedError(WetterdienstError):
        """An exception nobody has given a kind."""

    assert core.failure_status(UnplacedError("x")) == 500
    assert not core._is_caller_refusal(UnplacedError("x"), SimpleNamespace())  # noqa: SLF001


def test_failures_the_library_does_not_name_are_server_errors() -> None:
    """A defect or the failure of a library underneath is a 500, whatever its built-in class (GH-2634)."""
    for error in (ValueError("x"), KeyError("x"), IndexError("x"), OSError("x"), RuntimeError("x")):
        assert core.failure_status(error) == 500
    # a date at the edge of what a datetime holds is the request's
    assert core.failure_status(OverflowError("date value out of range")) == 400


def test_a_refusal_is_told_by_its_class_and_not_by_the_class_it_also_is() -> None:
    """A `ValueError` of the library's is a refusal by being a `RequestError`; one that is not, is not."""
    from wetterdienst.exceptions import (  # noqa: PLC0415
        CredentialMissingError,
        CredentialRejectedError,
        InvalidEnumerationError,
        MetaFileFormatError,
    )

    request = SimpleNamespace()
    # both are `ValueError`s; one is the caller's to fix, one is a file in a layout the parser does not expect
    assert core._is_caller_refusal(InvalidEnumerationError("x"), request)  # noqa: SLF001
    assert not core._is_caller_refusal(MetaFileFormatError("x"), request)  # noqa: SLF001
    # a missing credential is the deployment's lack: neither a refusal nor a defect
    assert not core._is_caller_refusal(CredentialMissingError("x"), request)  # noqa: SLF001
    # and so is a rejected one, though it is a `PermissionError`
    assert not core._is_caller_refusal(CredentialRejectedError("x"), request)  # noqa: SLF001


@pytest.mark.parametrize(
    ("provider", "network", "name"),
    [
        ("dwd", "observation", "DwdObservationRequest"),
        ("dwd", "radar", "DwdRadarValues"),
        ("dwd", "alerts", "DwdWeatherAlertRequest"),
    ],
)
def test_resolve_network_gives_the_class_of_either_kind_of_network(provider: str, network: str, name: str) -> None:
    """The surfaces take a standalone network by name too: `coverage`, `auth` and `issues` answer for it (GH-3045)."""
    assert resolve_network(provider, network).__name__ == name


def test_resolve_network_refuses_a_network_that_does_not_exist() -> None:
    """A network that is not in the registry is the `ApiNotFoundError` the surfaces answer with a 404 (GH-3045)."""
    with pytest.raises(ApiNotFoundError, match=r"No API available for provider foo and network bar\."):
        resolve_network("foo", "bar")
