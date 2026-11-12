# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A tool's `values` and `stations` answer is cut to a size budget, with a note; no other surface is (GH-4022).

Claude Code saves a tool result of more than 50,000 characters to a file, so an unwindowed forecast (90,000 and more)
and a listing of every station of a bounding box (1.7 million) never reached the model. The tools' answers are cut to
`ANSWER_BUDGET` characters of what the client receives: at a timestamp for `values`, keeping the end nearest to now
(the start where the caller gave a window), and the first stations of the list for `stations`. The note is a warning
of the `metadata` block (`answer-truncated`) and, for the formats with no block, the `X-Wetterdienst-Truncated`
header, told in the sentence of the tool. The REST API, the command line and the library answer all of it.

Offline: the readers are stood in for with frames of the shape the core hands out.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from tests.ui.test_restapi import _values_result_of_shape
from wetterdienst.ui import restapi
from wetterdienst.ui.budget import ANSWER_BUDGET, answer_size
from wetterdienst.ui.mcp import _mark_tool_requests
from wetterdienst.util.datetime import parse_date_window

if TYPE_CHECKING:
    from wetterdienst.model.result import StationsResult, ValuesResult

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

_PARAMETERS = "daily/climate_summary/temperature_air_mean_2m,daily/precipitation_more/precipitation_amount"
_VALUES = {"provider": "dwd", "network": "observation", "parameters": _PARAMETERS, "stations": "01048"}
_STATIONS = {"provider": "dwd", "network": "observation", "parameters": "daily/climate_summary", "all": "true"}
_NOW = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)


def _tool_client() -> TestClient:
    """Make a client of the REST app as an MCP tool's request reaches it."""
    return TestClient(_mark_tool_requests(restapi.app), raise_server_exceptions=False)


def _rest_client() -> TestClient:
    """Make a client of the REST app as any other caller reaches it."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _values_of(start: dt.datetime, hours: int, *, step: dt.timedelta = dt.timedelta(hours=1)) -> ValuesResult:
    """Give the values of one station and two parameters, `hours` timestamps from `start`, long as the core does."""
    base = _values_result_of_shape("long")
    rows = [
        {
            "station_id": "01048",
            "resolution": "daily",
            "dataset": dataset,
            "parameter": parameter,
            "timestamp": start + step * hour,
            "value": 10.0 + hour / 10,
            "quality_flags": None,
        }
        for dataset, parameter in (
            ("climate_summary", "temperature_air_mean_2m"),
            ("precipitation_more", "precipitation_amount"),
        )
        for hour in range(hours)
    ]
    df = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    return replace(base, df=df)


def _stub_values(monkeypatch: pytest.MonkeyPatch, result: ValuesResult) -> None:
    monkeypatch.setattr(restapi, "get_values", lambda **_kwargs: result)


def _stations_of(count: int, *, with_umlaut: bool = False) -> StationsResult:
    """Give a listing of `count` stations of one dataset, as a bounding box or `all` selects them."""
    base = _values_result_of_shape("long").stations
    one = base.df.filter(pl.col("dataset") == "climate_summary")
    frame = pl.concat(
        [
            one.with_columns(
                pl.lit(f"{i:05d}").alias("station_id"),
                pl.lit(f"Fuhlsbüttel-{i}" if with_umlaut else f"Station {i}").alias("name"),
            )
            for i in range(count)
        ]
    )
    return replace(base, df=frame, _df_all=frame)


def _stub_stations(monkeypatch: pytest.MonkeyPatch, result: StationsResult) -> None:
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: result)


def _compact(text: str) -> int:
    """Count the characters of the JSON a client receives: FastMCP hands the parsed answer on compact."""
    return len(json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False))


def _note_of(answer: dict[str, Any]) -> str:
    notes = [w["message"] for w in answer["metadata"]["warnings"] if w["code"] == "answer-truncated"]
    assert len(notes) == 1
    return notes[0]


def _window_of(note: str) -> tuple[str, str]:
    """Read the `timestamp=<a>/<b>` of a note."""
    start, end = re.search(r"`timestamp=([^/`]+)/([^`]+)`", note).groups()  # ty: ignore[unresolved-attribute]
    return start, end


def _timestamps(answer: dict[str, Any]) -> list[str]:
    return sorted({value["timestamp"] for value in answer["values"]})


# --- values -------------------------------------------------------------------------------------------------------


def test_a_forecast_without_a_window_keeps_its_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """The timestamps are ahead of now: the earliest are kept, whole, and the note continues where the answer stops."""
    result = _values_of(_NOW + dt.timedelta(hours=1), 240)
    _stub_values(monkeypatch, result)

    response = _tool_client().get("/api/values", params=_VALUES)

    assert response.status_code == 200
    assert _compact(response.text) <= ANSWER_BUDGET
    answer = response.json()
    stamps = _timestamps(answer)
    assert 0 < len(stamps) < 240
    # the start of the forecast, every timestamp whole (a row for each of the two parameters)
    assert dt.datetime.fromisoformat(stamps[0]) == _NOW + dt.timedelta(hours=1)
    assert len(answer["values"]) == 2 * len(stamps)
    note = _note_of(answer)
    assert f"{len(answer['values']):,} of 480 rows" in note
    # the next window starts at the first timestamp left out and ends with the last of the forecast
    first, last = _window_of(note)
    assert dt.datetime.fromisoformat(first) == _NOW + dt.timedelta(hours=1 + len(stamps))
    assert dt.datetime.fromisoformat(last) == _NOW + dt.timedelta(hours=240)
    assert answer["metadata"]["counts"]["rows"] == len(answer["values"])
    assert response.headers["x-wetterdienst-warnings"] == "answer-truncated"


def test_a_record_without_a_window_keeps_its_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `recent` series ends near now: the latest timestamps are kept and the note names the earlier part."""
    result = _values_of(_NOW - dt.timedelta(hours=600), 600)
    _stub_values(monkeypatch, result)

    answer = _tool_client().get("/api/values", params=_VALUES).json()

    stamps = _timestamps(answer)
    assert 0 < len(stamps) < 600
    assert dt.datetime.fromisoformat(stamps[-1]) == _NOW - dt.timedelta(hours=1)
    note = _note_of(answer)
    first, last = _window_of(note)
    assert dt.datetime.fromisoformat(first) == _NOW - dt.timedelta(hours=600)
    assert dt.datetime.fromisoformat(last) == dt.datetime.fromisoformat(stamps[0]) - dt.timedelta(hours=1)
    assert "earlier part" in note


def test_a_window_keeps_its_start_and_the_next_window_continues_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a `timestamp` the start is kept whatever is nearer to now; the window of the note ends where theirs does."""
    start = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    result = _values_of(start, 700)
    _stub_values(monkeypatch, result)

    answer = _tool_client().get("/api/values", params={**_VALUES, "timestamp": "2026-01-01/2026-01-30"}).json()

    stamps = _timestamps(answer)
    assert dt.datetime.fromisoformat(stamps[0]) == start
    first, last = _window_of(_note_of(answer))
    assert dt.datetime.fromisoformat(first) == start + dt.timedelta(hours=len(stamps))
    # the end the caller gave, as they wrote it, which the tool reads as it read theirs
    assert last == "2026-01-30"
    # a window the tool accepts: it parses, as the endpoint parses the halves of an interval
    assert parse_date_window(first)[0] == start + dt.timedelta(hours=len(stamps))
    assert parse_date_window(last)[1].date() == dt.date(2026, 1, 30)


def test_a_window_without_a_closing_date_ends_where_the_answer_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single date is a window of its own, and the next one ends with it."""
    result = _values_of(dt.datetime(2026, 1, 1, tzinfo=dt.UTC), 700)
    _stub_values(monkeypatch, result)

    answer = _tool_client().get("/api/values", params={**_VALUES, "timestamp": "2026-01"}).json()

    assert _window_of(_note_of(answer))[1] == "2026-01"


def test_one_timestamp_over_the_budget_is_cut_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only where a single timestamp is more than the budget are its rows cut, and the note says so."""
    base = _values_result_of_shape("long")
    stamp = _NOW + dt.timedelta(hours=1)
    # 600 stations at one timestamp: about 150,000 characters of rows that no window can split
    rows = [
        {
            "station_id": f"{i:05d}",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": stamp + dt.timedelta(hours=hour),
            "value": 1.5,
            "quality_flags": None,
        }
        for hour in range(2)
        for i in range(600)
    ]
    df = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    _stub_values(monkeypatch, replace(base, df=df))

    response = _tool_client().get("/api/values", params=_VALUES)

    answer = response.json()
    assert _compact(response.text) <= ANSWER_BUDGET
    # the first timestamp, in part: the second is left out whole
    assert [dt.datetime.fromisoformat(t) for t in _timestamps(answer)] == [stamp]
    kept = len(answer["values"])
    assert 0 < kept < 600
    note = _note_of(answer)
    assert "alone holds 600 rows" in note
    assert f"only the first {kept:,} of them" in note
    assert "cannot split a timestamp" in note
    assert answer["metadata"]["counts"]["rows"] == kept


def test_a_single_timestamp_of_a_record_keeps_the_latest_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cut through, a record keeps the rows of its latest timestamp, the end that is nearest to now."""
    base = _values_result_of_shape("long")
    rows = [
        {
            "station_id": f"{i:05d}",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": _NOW - dt.timedelta(days=day),
            "value": 1.5,
            "quality_flags": None,
        }
        for day in (3, 1)
        for i in range(600)
    ]
    df = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    _stub_values(monkeypatch, replace(base, df=df))

    answer = _tool_client().get("/api/values", params=_VALUES).json()

    assert [dt.datetime.fromisoformat(t) for t in _timestamps(answer)] == [_NOW - dt.timedelta(days=1)]
    note = _note_of(answer)
    assert "only the first" in note
    # the earlier timestamp is what a window reaches
    assert dt.datetime.fromisoformat(_window_of(note)[0]) == _NOW - dt.timedelta(days=3)


def test_an_answer_within_the_budget_is_left_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is cut or noted where the answer fits."""
    _stub_values(monkeypatch, _values_of(_NOW, 12))

    response = _tool_client().get("/api/values", params=_VALUES)

    answer = response.json()
    assert len(answer["values"]) == 24
    assert answer["metadata"]["warnings"] == []
    assert "x-wetterdienst-truncated" not in response.headers


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv", "ndjson"])
def test_every_data_format_is_held_to_the_budget(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """JSON, GeoJSON, CSV and NDJSON each come back within the budget of what a client receives, with the note."""
    _stub_values(monkeypatch, _values_of(_NOW + dt.timedelta(hours=1), 900))

    response = _tool_client().get("/api/values", params={**_VALUES, "format": fmt})

    assert response.status_code == 200
    note = unquote(response.headers["x-wetterdienst-truncated"])
    assert "answer was cut to stay within 40,000 characters" in note
    assert response.headers["x-wetterdienst-warnings"] == "answer-truncated"
    if fmt in ("json", "geojson"):
        body = response.json()
        assert _note_of(body) == note
        assert _compact(response.text) <= ANSWER_BUDGET
        rows = (
            len(body["values"])
            if fmt == "json"
            else sum(len(feature["values"]) for feature in body["data"]["features"])
        )
        assert body["metadata"]["counts"]["rows"] == rows
        return
    if fmt == "csv":
        # a CSV has no block, so its note is in no row of it
        assert "answer was cut" not in response.text
        assert response.text.splitlines()[0].startswith("station_id")
        assert len(response.text.splitlines()) - 1 == int(response.headers["x-wetterdienst-rows"])
    else:
        lines = [json.loads(line) for line in response.text.splitlines()]
        assert _note_of(lines[0]) == note
        assert lines[-1]["end"]["counts"]["rows"] == len(lines) - 2


def _client_sees(tool: str, arguments: dict[str, Any]) -> Any:  # noqa: ANN401
    """Call a tool of the real server in process and give the result a client receives."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as client:
            return await client.call_tool(tool, arguments, raise_on_error=False)

    return asyncio.run(call())


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv", "ndjson"])
@pytest.mark.parametrize("with_metadata", [False, True])
def test_what_the_client_receives_is_within_the_budget(
    monkeypatch: pytest.MonkeyPatch, fmt: str, *, with_metadata: bool
) -> None:
    """The budget holds for the structured content of the tool result, `with_metadata` and the sentence included.

    For JSON that is the answer as FastMCP hands it on, compact; for CSV and NDJSON the sentence of the tool (the
    licence, the processing note, the warnings and the note itself) and the body.
    """
    _stub_values(monkeypatch, _values_of(_NOW + dt.timedelta(hours=1), 900))
    arguments = {**_VALUES, "format": fmt, "with_metadata": with_metadata}

    result = _client_sees("values", arguments)

    assert not result.is_error, result.content
    structured = result.structured_content
    seen = (
        structured["result"]
        if fmt in ("csv", "ndjson")
        else json.dumps(structured, separators=(",", ":"), ensure_ascii=False)
    )
    assert ANSWER_BUDGET - 1_500 < len(seen) <= ANSWER_BUDGET
    if fmt in ("csv", "ndjson"):
        # the sentence tells the note in words, and the body is below it
        assert "Truncated: The answer was cut to stay within 40,000 characters" in seen
        assert result.meta["wetterdienst"]["warnings"] == ["answer-truncated"]
        assert result.meta["wetterdienst"]["truncated"].startswith("The answer was cut")
    else:
        assert any(w["code"] == "answer-truncated" for w in structured["result"]["metadata"]["warnings"])


def test_the_size_counted_is_what_the_client_gets_of_the_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """`answer_size` of a JSON body is the length of the compact JSON a client receives, with an escape or not."""
    _stub_values(monkeypatch, _values_of(_NOW, 1))
    body = {"metadata": {}, "values": [{"name": "Fuhlsbüttel"}]}
    escaped = json.dumps(body)
    request = type("Request", (), {"format": "json", "pretty": False})()
    wrapped = len(json.dumps({"result": body}, separators=(",", ":"), ensure_ascii=False))
    assert answer_size(escaped, request, None) == wrapped  # ty: ignore[invalid-argument-type]
    pretty = type("Request", (), {"format": "json", "pretty": True})()
    assert answer_size(json.dumps(body, indent=4), pretty, None) == answer_size(escaped, request, None)  # ty: ignore[invalid-argument-type]


# --- stations -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv", "ndjson"])
def test_every_station_of_a_bounding_box_or_all_is_cut_to_the_first_that_fit(
    monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """`all` and a bounding box keep the first stations in list order, and the note says how many match."""
    _stub_stations(monkeypatch, _stations_of(700, with_umlaut=True))
    bbox = {**{k: v for k, v in _STATIONS.items() if k != "all"}, "left": 0, "bottom": 0, "right": 90, "top": 90}

    for params in (_STATIONS, bbox):
        response = _tool_client().get("/api/stations", params={**params, "format": fmt})

        assert response.status_code == 200
        note = unquote(response.headers["x-wetterdienst-truncated"])
        assert (
            "of 700 stations are returned, in list order. 700 stations match; narrow with latitude, longitude and"
            in note
        )
        assert "`rank` or `distance`, or `name`" in note
        if fmt == "json":
            body = response.json()
            kept = [station["station_id"] for station in body["stations"]]
            assert 0 < len(kept) < 700
            assert kept == [f"{i:05d}" for i in range(len(kept))]
            assert _note_of(body) == note
            assert body["metadata"]["counts"]["stations"] == len(kept)
            assert len(json.dumps(body, separators=(",", ":"), ensure_ascii=False)) <= ANSWER_BUDGET
        elif fmt == "geojson":
            body = response.json()
            assert 0 < len(body["data"]["features"]) < 700
            assert _note_of(body) == note
        elif fmt == "csv":
            assert "answer was cut" not in response.text
            assert 0 < len(response.text.splitlines()) - 1 < 700
        else:
            lines = [json.loads(line) for line in response.text.splitlines()]
            assert _note_of(lines[0]) == note


def test_the_stations_of_a_client_are_within_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """What a client receives of a stations listing, CSV with its sentence and JSON, is within the budget."""
    _stub_stations(monkeypatch, _stations_of(700, with_umlaut=True))

    for fmt in ("json", "csv"):
        result = _client_sees("stations", {**_STATIONS, "format": fmt})
        structured = result.structured_content
        seen = (
            structured["result"] if fmt == "csv" else json.dumps(structured, separators=(",", ":"), ensure_ascii=False)
        )
        assert ANSWER_BUDGET - 1_500 < len(seen) <= ANSWER_BUDGET, fmt


@pytest.mark.parametrize(
    "selection",
    [
        {"name": "Station", "rank": 700},
        {"latitude": 51.1, "longitude": 13.8, "rank": 700},
        {"latitude": 51.1, "longitude": 13.8, "distance": 5000},
    ],
)
def test_a_rank_a_distance_or_a_name_is_not_cut(monkeypatch: pytest.MonkeyPatch, selection: dict[str, Any]) -> None:
    """They ask for a few stations: nothing is cut, however many come back, and nothing is noted."""
    from wetterdienst.model.result import StationsFilter  # noqa: PLC0415

    kind = (
        StationsFilter.BY_NAME
        if "name" in selection and "rank" not in selection
        else StationsFilter.BY_RANK
        if "rank" in selection
        else StationsFilter.BY_DISTANCE
    )
    listing = replace(_stations_of(700), _stations_filter=kind, _rank=None)
    _stub_stations(monkeypatch, listing)
    params = {k: v for k, v in _STATIONS.items() if k != "all"} | {
        key: value for key, value in selection.items() if key != "rank" or "name" not in selection
    }
    if kind is StationsFilter.BY_NAME:
        params = {k: v for k, v in params.items() if k != "rank"}

    response = _tool_client().get("/api/stations", params=params)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["stations"]) == 700
    assert body["metadata"]["warnings"] == []
    assert "x-wetterdienst-truncated" not in response.headers


# --- the other surfaces -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv", "ndjson"])
def test_the_rest_api_answers_all_of_it(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """The same requests, not from a tool, come back whole: no note, no header, every row and station."""
    from tests.ui.test_restapi import _stub_stream  # noqa: PLC0415

    result = _values_of(_NOW + dt.timedelta(hours=1), 900)
    _stub_values(monkeypatch, result)
    _stub_stream(monkeypatch, [result])
    response = _rest_client().get("/api/values", params={**_VALUES, "format": fmt})

    assert response.status_code == 200
    assert len(response.text) > ANSWER_BUDGET
    assert "x-wetterdienst-truncated" not in response.headers
    assert "answer-truncated" not in response.headers.get("x-wetterdienst-warnings", "")
    assert "answer-truncated" not in response.text
    if fmt == "json":
        assert len(response.json()["values"]) == 1800

    _stub_stations(monkeypatch, _stations_of(700))
    listed = _rest_client().get("/api/stations", params={**_STATIONS, "format": fmt})

    assert listed.status_code == 200
    assert "x-wetterdienst-truncated" not in listed.headers
    assert "answer-truncated" not in listed.text
    if fmt == "json":
        assert len(listed.json()["stations"]) == 700


def test_python_and_the_cli_answer_all_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A result in Python is whole, and the command line, which never imports the budget, writes every row."""
    result = _values_of(_NOW + dt.timedelta(hours=1), 900)
    assert len(json.loads(result.to_json())["values"]) == 1800
    assert len(result.to_csv().splitlines()) - 1 == 1800
    # the command line prints through its own readers: a stub of them answers 1800 rows, which the CLI writes whole
    from click.testing import CliRunner  # noqa: PLC0415

    from wetterdienst.ui import cli as cli_module  # noqa: PLC0415

    monkeypatch.setattr(cli_module, "get_values", lambda **_kwargs: result)
    output = CliRunner().invoke(
        cli_module.cli,
        ["values", "--provider", "dwd", "--network", "observation", "--parameters", _PARAMETERS, "--stations", "01048"],
    )
    assert output.exit_code == 0, output.output
    assert len(json.loads(output.output)["values"]) == 1800
    assert "answer-truncated" not in output.output


# --- the note and the header --------------------------------------------------------------------------------------


def test_the_note_says_what_is_returned_what_is_left_and_how_to_narrow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rows kept and total, the range, the next window, and the three ways to ask for less."""
    _stub_values(monkeypatch, _values_of(_NOW + dt.timedelta(hours=1), 900))

    note = _note_of(_tool_client().get("/api/values", params=_VALUES).json())

    assert re.search(r"\d[\d,]* of 1,800 rows are returned, from \S+ to \S+ \(\d+ of 900 timestamps;", note)
    assert "ask again with `timestamp=" in note
    assert "narrow the `timestamp` window" in note
    assert "fewer parameters" in note
    assert "`format=csv` with `shape=wide`" in note
    # it holds no coordinates of the request, and the server logs none of it
    assert "latitude" not in note
    assert "51.1" not in note


def test_the_header_and_the_sentence_carry_the_note_of_a_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """`X-Wetterdienst-Truncated` carries the note, percent-encoded as the others are, and the sentence tells it."""
    _stub_values(monkeypatch, _values_of(_NOW + dt.timedelta(hours=1), 900))

    response = _tool_client().get("/api/values", params={**_VALUES, "format": "csv"})

    header = response.headers["x-wetterdienst-truncated"]
    assert header.isascii()
    assert unquote(header).startswith("The answer was cut to stay within 40,000 characters: ")
    result = _client_sees("values", {**_VALUES, "format": "csv"})
    assert f"Truncated: {unquote(header)[:60]}" in result.structured_content["result"]


# --- what the model is told ---------------------------------------------------------------------------------------


def test_the_instructions_window_their_values_examples_and_say_of_the_budget() -> None:
    """No example of `values` reads a whole record, and the instructions tell the cut, its warning and csv with wide."""
    from wetterdienst.ui.mcp import INSTRUCTIONS  # noqa: PLC0415

    calls = re.findall(r"values\((.*?)\)", INSTRUCTIONS, flags=re.DOTALL)
    assert len(calls) == 2
    for call in calls:
        assert 'timestamp="' in call
        assert "periods" not in call
    flat = " ".join(INSTRUCTIONS.split())
    assert "cut to 40,000 characters" in flat
    assert "`answer-truncated`" in flat
    assert 'format="csv" with shape="wide"' in flat
    assert len(INSTRUCTIONS) < 7800


def test_the_values_tool_recommends_a_window_and_the_rest_document_does_not() -> None:
    """The tool's description has the sentence, which only the tool has: the REST document stays as it was."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def listed() -> dict[str, str]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return {tool.name: tool.description or "" for tool in await client.list_tools()}

    descriptions = asyncio.run(listed())
    advice = "Give a `timestamp` window: an answer is cut to 40,000 characters; for a long series use format=csv"
    assert descriptions["values"].rstrip().endswith("shape=wide.")
    assert advice in descriptions["values"]
    assert advice not in descriptions["stations"]
    paths = restapi.app.openapi()["paths"]
    routes = [path for path in paths if path.endswith("/values")]
    assert routes
    assert all("40,000" not in paths[path]["get"]["description"] for path in routes)
