# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The budget of a tool's answer also holds for `interpolate`, `summarize`, `stripes_stations` and `with_metadata`.

`interpolate` and `summarize` answer a series of timestamps and are cut as `values` is (at a timestamp, with the
window of the note, the `timestamp` they require giving the start of the window to keep); the stripes' stations are a
list of stations and are cut as `stations` is. A `with_metadata` block that is more than the budget on its own is left
out of an answer of a rank, a distance or a name as well. The REST API, the command line and the library answer all of
it (GH-4024). Offline: the getters are stood in for with frames of the shape the core hands out.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import polars as pl
import pytest

from tests.ui.test_mcp_budget import (
    _STATIONS,
    _a_legend_of,
    _client_sees,
    _compact,
    _note_of,
    _received,
    _rest_client,
    _stations_of,
    _the_client_gets,
    _tool_client,
    _window_of,
)
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from tests.ui.test_restapi import _values_result_of_shape
from wetterdienst.model.result import InterpolatedValuesResult, StationsFilter, SummarizedValuesResult
from wetterdienst.ui import restapi
from wetterdienst.ui.budget import ANSWER_BUDGET

if TYPE_CHECKING:
    from wetterdienst.model.result import StationsResult

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

_START = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
_ESTIMATE = {
    "provider": "dwd",
    "network": "observation",
    "parameters": "daily/climate_summary/temperature_air_mean_2m,daily/precipitation_more/precipitation_amount",
    "latitude": 51.1,
    "longitude": 13.8,
    "timestamp": "2024",
}
_TOOLS = {
    "interpolate": ("get_interpolate", InterpolatedValuesResult),
    "summarize": ("get_summarize", SummarizedValuesResult),
}
_A_RANK = {k: v for k, v in _STATIONS.items() if k != "all"} | {"latitude": 51.1, "longitude": 13.8, "rank": 5}


def _estimate_of(tool: str, days: int) -> InterpolatedValuesResult | SummarizedValuesResult:
    """Give an estimate for two parameters over `days` daily timestamps from 2024-01-01, as the core does."""
    stations = _values_result_of_shape("long").stations
    # the stations an estimate lists say how far they stand from the point
    stations = replace(
        stations,
        df=stations.df.with_columns(
            pl.lit(5.83).alias("distance"), pl.lit(None, dtype=pl.Float64).alias("elevation_difference")
        ),
    )
    rows = []
    for dataset, parameter in (
        ("climate_summary", "temperature_air_mean_2m"),
        ("precipitation_more", "precipitation_amount"),
    ):
        for day in range(days):
            row: dict[str, Any] = {
                "station_id": "edf27153",
                "resolution": "daily",
                "dataset": dataset,
                "parameter": parameter,
                "timestamp": _START + dt.timedelta(days=day),
                "value": 10.0 + day / 10,
            }
            if tool == "interpolate":
                row |= {"distance_mean": 11.91, "taken_station_ids": ["01048"]}
            else:
                row |= {"distance": 5.83, "taken_station_id": "01048"}
            rows.append(row)
    df = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    return _TOOLS[tool][1](stations=stations, df=df, latlon=(51.1, 13.8))


def _stub(monkeypatch: pytest.MonkeyPatch, tool: str, result: Any) -> None:  # noqa: ANN401
    monkeypatch.setattr(restapi, _TOOLS[tool][0], lambda **_kwargs: result)


def _stub_stripes(monkeypatch: pytest.MonkeyPatch, result: StationsResult) -> None:
    monkeypatch.setattr(restapi, "_get_stripes_stations", lambda **_kwargs: result)


def _stub_a_rank(monkeypatch: pytest.MonkeyPatch, count: int) -> StationsResult:
    listing = replace(_stations_of(count), _stations_filter=StationsFilter.BY_RANK, _rank=None)
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: listing)
    return listing


# --- interpolate and summarize ------------------------------------------------------------------------------------


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_an_estimate_over_the_budget_keeps_the_start_of_its_window(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """A year is cut at a timestamp, whole, from the start of the window; the note continues the window to its end."""
    _stub(monkeypatch, tool, _estimate_of(tool, 366))

    response = _tool_client().get(f"/api/{tool}", params=_ESTIMATE)

    assert response.status_code == 200
    assert _compact(response.text) <= ANSWER_BUDGET
    answer = response.json()
    stamps = sorted({value["timestamp"] for value in answer["values"]})
    assert 0 < len(stamps) < 366
    assert dt.datetime.fromisoformat(stamps[0]) == _START
    # every timestamp whole: a row for each of the two parameters
    assert len(answer["values"]) == 2 * len(stamps)
    note = _note_of(answer)
    assert f"{len(answer['values']):,} of 732 rows are returned" in note
    first, last = _window_of(note)
    assert dt.datetime.fromisoformat(first) == _START + dt.timedelta(days=len(stamps))
    # the window the caller gave, which the tool read as a year
    assert last == "2024"
    assert answer["metadata"]["counts"]["rows"] == len(answer["values"])
    assert response.headers["x-wetterdienst-warnings"] == "answer-truncated"


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_the_note_of_an_estimate_does_not_offer_the_wide_shape(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """They have no `shape`: the note names the window, fewer parameters and the CSV, which is about half the size."""
    _stub(monkeypatch, tool, _estimate_of(tool, 366))

    note = _note_of(_tool_client().get(f"/api/{tool}", params=_ESTIMATE).json())

    assert "shape" not in note
    assert "narrow the `timestamp` window, ask for fewer parameters, or use `format=csv`, which is about half" in note
    csv = _tool_client().get(f"/api/{tool}", params={**_ESTIMATE, "format": "csv"})
    told = unquote(csv.headers["x-wetterdienst-truncated"])
    assert told.endswith("To get less at a time, narrow the `timestamp` window or ask for fewer parameters.")
    assert "shape" not in told


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
def test_every_data_format_of_an_estimate_is_within_the_budget(
    monkeypatch: pytest.MonkeyPatch, tool: str, fmt: str
) -> None:
    """What a client receives of each format, with `with_metadata` and the stations, is within the budget."""
    _stub(monkeypatch, tool, _estimate_of(tool, 900))
    arguments = {**_ESTIMATE, "format": fmt, "with_metadata": True, "with_stations": True}

    result = _client_sees(tool, arguments)

    assert not result.is_error, result.content
    structured = result.structured_content
    seen = structured["result"]
    assert ANSWER_BUDGET - 2_500 < _received(result) <= ANSWER_BUDGET
    if fmt == "csv":
        assert result.meta["wetterdienst"]["warnings"] == ["answer-truncated"]
        assert "Truncated: The answer was cut to stay within 40,000 characters" in seen
    else:
        assert any(w["code"] == "answer-truncated" for w in structured["result"]["metadata"]["warnings"])


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_the_stations_of_a_cut_estimate_are_those_of_the_rows_left(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """The estimate lists the stations its rows came from: a station only the rows that were cut used is not listed."""
    result = _estimate_of(tool, 366)
    stations = result.stations
    ghost = stations.df.filter(pl.col("station_id") == "01048").with_columns(pl.lit("99999").alias("station_id"))
    # the last day alone is made from the station 99999, which the cut leaves out
    column = "taken_station_ids" if tool == "interpolate" else "taken_station_id"
    taken = pl.lit(["99999"]) if tool == "interpolate" else pl.lit("99999")
    df = result.df.with_columns(
        pl.when(pl.col("timestamp") == _START + dt.timedelta(days=365))
        .then(taken)
        .otherwise(pl.col(column))
        .alias(column)
    )
    wide = replace(result, df=df, stations=replace(stations, df=pl.concat([stations.df, ghost])))
    _stub(monkeypatch, tool, wide)

    answer = _tool_client().get(f"/api/{tool}", params={**_ESTIMATE, "with_stations": True}).json()

    assert {station["station_id"] for station in answer["stations"]} == {"01048"}
    assert answer["metadata"]["counts"]["stations"] == 1


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_an_estimate_within_the_budget_is_left_as_it_is(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """Nothing is cut or noted where the answer fits."""
    _stub(monkeypatch, tool, _estimate_of(tool, 30))

    response = _tool_client().get(f"/api/{tool}", params=_ESTIMATE)

    answer = response.json()
    assert len(answer["values"]) == 60
    assert answer["metadata"]["warnings"] == []
    assert "x-wetterdienst-truncated" not in response.headers


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_the_block_of_an_estimate_that_is_over_the_budget_is_left_out(
    monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    """A `with_metadata` block of 45,000 characters is dropped from the estimate, as it is from `values`."""
    monkeypatch.setattr("wetterdienst.ui.response_metadata.quality_legend", lambda *_: _a_legend_of(45_000))
    _stub(monkeypatch, tool, _estimate_of(tool, 366))

    answer, size = _the_client_gets(_client_sees(tool, {**_ESTIMATE, "with_metadata": True}))

    assert ANSWER_BUDGET - 1_500 < size <= ANSWER_BUDGET
    assert "quality" not in answer["metadata"]
    note = _note_of(answer)
    assert re.match(r"The `with_metadata` block \(4\d,\d{3} characters\) was left out to stay within 40,000 ", note)
    assert 1 < len(answer["values"]) < 732


# --- the stripes' stations ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
def test_the_stripes_stations_are_cut_to_the_first_that_fit(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """The list has no selection: its first stations are kept, and the note says to name a place for the stripes."""
    _stub_stripes(monkeypatch, _stations_of(700, with_umlaut=True))

    response = _tool_client().get("/api/stripes/stations", params={"kind": "precipitation", "format": fmt})

    assert response.status_code == 200
    note = unquote(response.headers["x-wetterdienst-truncated"])
    assert "the first " in note
    assert "700 stations have data for the precipitation stripes" in note
    assert "give the station's name (often its town's) as `name` to `stripes_values` or `stripes_image`" in note
    assert "sample of the area" not in note
    assert "latitude, longitude and `rank` or `distance`" not in note
    assert "active=true" not in note
    if fmt == "csv":
        assert 0 < len(response.text.splitlines()) - 1 < 700
        assert len(response.text) <= ANSWER_BUDGET
        return
    body = response.json()
    assert _note_of(body) == note
    assert body["metadata"]["provider"]["name_english"] == "German Weather Service"
    assert _compact(response.text) <= ANSWER_BUDGET
    if fmt == "json":
        kept = [station["station_id"] for station in body["stations"]]
        assert 0 < len(kept) < 700
        assert kept == [f"{i:05d}" for i in range(len(kept))]
        assert body["metadata"]["counts"]["stations"] == len(kept)
    else:
        assert 0 < len(body["data"]["features"]) < 700


def test_the_stripes_note_says_what_active_does_for_the_whole_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """With `active=false` the note names `active=true`, which narrows the list to the stations that still report."""
    _stub_stripes(monkeypatch, _stations_of(700))

    note = _note_of(_tool_client().get("/api/stripes/stations", params={"kind": "temperature", "active": False}).json())

    assert "`active=true` lists only the stations that still report." in note
    assert "have data for the temperature stripes" in note


def test_what_a_client_receives_of_the_stripes_stations_is_within_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON and CSV (with its sentence), as the client receives them."""
    _stub_stripes(monkeypatch, _stations_of(700, with_umlaut=True))

    for fmt in ("json", "csv"):
        result = _client_sees("stripes_stations", {"kind": "temperature", "format": fmt})
        assert ANSWER_BUDGET - 1_500 < _received(result) <= ANSWER_BUDGET, fmt


def test_the_stripes_stations_within_the_budget_are_left_as_they_are(monkeypatch: pytest.MonkeyPatch) -> None:
    """A short list is no cut."""
    _stub_stripes(monkeypatch, _stations_of(20))

    response = _tool_client().get("/api/stripes/stations", params={"kind": "temperature"})

    assert len(response.json()["stations"]) == 20
    assert response.json()["metadata"]["warnings"] == []
    assert "x-wetterdienst-truncated" not in response.headers


# --- `with_metadata` of a few stations ----------------------------------------------------------------------------


@pytest.mark.parametrize("count", [5, 1])
def test_the_block_over_the_budget_is_left_out_of_a_few_stations(monkeypatch: pytest.MonkeyPatch, count: int) -> None:
    """A rank asks for a few stations and a single station is one: their rows stay, the block that overflows goes."""
    monkeypatch.setattr("wetterdienst.ui.response_metadata.quality_legend", lambda *_: _a_legend_of(45_000))
    listing = _stub_a_rank(monkeypatch, count)

    answer, size = _the_client_gets(_client_sees("stations", {**_A_RANK, "with_metadata": True}))

    assert size <= ANSWER_BUDGET
    assert len(answer["stations"]) == listing.df.height
    assert "quality" not in answer["metadata"]
    note = _note_of(answer)
    assert note.startswith("The `with_metadata` block (")
    assert "was left out to stay within 40,000 characters; read units with `coverage` or `glossary`." in note
    assert "stations are returned" not in note


def test_a_few_stations_with_a_block_that_fits_are_left_as_they_are(monkeypatch: pytest.MonkeyPatch) -> None:
    """The usual `with_metadata` of a rank is well within the budget: it stays, with no note."""
    _stub_a_rank(monkeypatch, 5)

    answer, _ = _the_client_gets(_client_sees("stations", {**_A_RANK, "with_metadata": True}))

    assert "parameters" in answer["metadata"]
    assert answer["metadata"]["warnings"] == []


# --- the other surfaces -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
def test_the_rest_api_answers_all_of_an_estimate_and_of_the_stripes_stations(
    monkeypatch: pytest.MonkeyPatch, tool: str, fmt: str
) -> None:
    """The same requests, not from a tool, come back whole: no note, no header; the budget is not even asked."""

    def never(*_args: object, **_kwargs: object) -> None:
        msg = "the budget is for a tool's request alone"
        raise AssertionError(msg)

    monkeypatch.setattr(restapi, "fit_values", never)
    monkeypatch.setattr(restapi, "fit_stations", never)
    _stub(monkeypatch, tool, _estimate_of(tool, 900))

    response = _rest_client().get(f"/api/{tool}", params={**_ESTIMATE, "format": fmt})

    assert response.status_code == 200
    assert len(response.text) > ANSWER_BUDGET
    assert "x-wetterdienst-truncated" not in response.headers
    assert "answer-truncated" not in response.headers.get("x-wetterdienst-warnings", "")
    assert "answer-truncated" not in response.text
    if fmt == "json":
        assert len(response.json()["values"]) == 1800

    _stub_stripes(monkeypatch, _stations_of(700))
    listed = _rest_client().get("/api/stripes/stations", params={"kind": "temperature", "format": fmt})
    assert listed.status_code == 200
    assert len(listed.text) > ANSWER_BUDGET
    assert "x-wetterdienst-truncated" not in listed.headers
    assert "answer-truncated" not in listed.text
    if fmt == "json":
        assert len(listed.json()["stations"]) == 700


def test_the_rest_answer_of_a_few_stations_with_a_big_block_is_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    """The block that a tool would lose is in the REST answer, which is never cut."""
    monkeypatch.setattr("wetterdienst.ui.response_metadata.quality_legend", lambda *_: _a_legend_of(45_000))
    _stub_a_rank(monkeypatch, 5)

    response = _rest_client().get("/api/stations", params={**_A_RANK, "with_metadata": True})

    assert len(response.text) > ANSWER_BUDGET
    assert "quality" in response.json()["metadata"]
    assert response.json()["metadata"]["warnings"] == []


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_python_answers_all_of_an_estimate(tool: str) -> None:
    """A result in Python is whole whatever its size."""
    result = _estimate_of(tool, 900)

    assert len(json.loads(result.to_json())["values"]) == 1800
    assert len(result.to_csv().splitlines()) - 1 == 1800
