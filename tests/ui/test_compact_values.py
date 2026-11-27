# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The compact format of `values` over REST, the command line, Python and MCP (GH-4445).

One stub of a DWD network (`row_options_stub`) answers every surface. The text each makes is held to the JSON the REST
API answers for the same request (the rows and their flags, read by `tests/compact_reader.py`, which shares no code with
the writer), to the text of the other surfaces, and, over MCP, to the budget a tool's answer keeps to.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.compact_reader import differences, parse, readings_in_order, values
from tests.ui.row_options_stub import GUST, TMAX, TMIN, serve
from wetterdienst.io.formats import COMPACT_MEDIA_TYPE
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.budget import ANSWER_BUDGET
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app

if TYPE_CHECKING:
    from tests.compact_reader import Parsed

pytestmark = pytest.mark.usefixtures("_stub")

_BASE = {
    "provider": "dwd",
    "network": "observation",
    "parameters": f"{TMIN},{TMAX}",
    "timestamp": "2018-01-01/2018-01-20",
    "stations": "00001,00002",
}
_NOW = "2026-11-26T09:44:00+00:00"


@pytest.fixture
def _stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the stub network, and have every answer retrieved at one time, so that texts can be compared."""
    serve(monkeypatch)
    monkeypatch.setattr("wetterdienst.ui.response_metadata._retrieved_at", lambda: _NOW)


def _rest(fmt: str = "compact", **params: Any) -> Any:  # noqa: ANN401
    return TestClient(app).get("/api/values", params={**_BASE, "format": fmt, **params})


def _cli(*args: str) -> Any:  # noqa: ANN401
    result = CliRunner().invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            f"--parameters={_BASE['parameters']}",
            f"--timestamp={_BASE['timestamp']}",
            f"--stations={_BASE['stations']}",
            *args,
        ],
    )
    assert result.exit_code == 0, result.output
    return result


def _truth(rows: list[dict[str, Any]]) -> dict[tuple, tuple[float | None, str | None]]:
    """Read the rows of the JSON answer as the compact text must give them back."""
    return {
        (r["station_id"], r["resolution"], r["dataset"], r["parameter"], dt.datetime.fromisoformat(r["timestamp"])): (
            r["value"],
            r["quality_flags"],
        )
        for r in rows
    }


def _held_to_json(text: str, **params: Any) -> Parsed:  # noqa: ANN401
    """Read the compact text and hold its readings to those of the JSON answer of the same request."""
    parsed = parse(text)
    answer = _rest("json", **params).json()
    assert differences(values(parsed), _truth(answer["values"])) == []
    assert parsed.end == f"rows={answer['metadata']['counts']['rows']}"
    return parsed


# --- the REST route -----------------------------------------------------------------------------------------------


def test_the_rest_route_answers_one_body_in_its_own_media_type_with_the_headers_of_the_block() -> None:
    """The text is not streamed: one body with its length, the licence and the credit line in the headers too."""
    response = _rest()

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == f"{COMPACT_MEDIA_TYPE}; charset=utf-8"
    assert "transfer-encoding" not in response.headers
    assert int(response.headers["content-length"]) == len(response.content)
    assert response.headers["x-wetterdienst-license"] == "CC-BY-4.0"
    assert response.headers["x-wetterdienst-rows"] == "76"
    assert response.text.startswith("# wetterdienst-compact/1 values\n")
    assert response.text.endswith("# end rows=76\n")
    assert response.content.decode("utf-8") == response.text


def test_the_text_holds_the_readings_and_flags_of_the_json_and_the_stations() -> None:
    """Every reading of the JSON answer is in a table, with its flags, and nothing else is."""
    text = _rest().text

    parsed = _held_to_json(text)
    assert [t.heading for t in parsed.tables if t.heading.startswith(("stations", "values"))] == [
        "stations",
        "values daily/climate_summary station=00001",
        "values daily/climate_summary station=00002",
    ]
    assert [row[:2] for row in parsed.table("stations").rows] == [["00001", "Alpha"], ["00002", "Beta"]]
    table = parsed.table("values daily/climate_summary station=00001")
    assert table.columns == ["timestamp", "temperature_air_max_2m(°C)", "temperature_air_min_2m(°C)"]
    # the stub has gaps: 19 of the 20 days have a reading of the maximum, and so a row
    assert len(table.rows) == 19


def test_rest_cli_and_python_write_the_same_text() -> None:
    """The three surfaces render through one function: the same bytes for the same request."""
    rest = _rest().text
    cli_text = _cli("--format=compact").stdout
    request = DwdObservationRequest(
        parameters=[TMIN, TMAX],
        start=dt.datetime(2018, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2018, 1, 20, 23, 59, 59, 999999, tzinfo=dt.UTC),
    ).filter_by_station_id(["00001", "00002"])
    python = request.values().all().to_compact()

    assert cli_text == rest
    assert python == rest
    assert request.values().all().to_format("COMPACT") == rest


def test_with_metadata_adds_the_settings_and_the_tables_and_every_surface_agrees() -> None:
    """The units are in the column lines either way; `with_metadata` adds the settings, parameters and legend."""
    plain = _rest().text
    rich = _rest(with_metadata="true").text

    assert "# settings: " not in plain
    assert "## parameters" not in plain
    parsed = parse(rich)
    assert parsed.get("settings", "").startswith("humanize=true convert_units=true")
    assert "temperature=degree_celsius" in parsed.get("unit_targets", "")
    assert {row[1]: row[4] for row in parsed.table("parameters").rows} == {
        "temperature_air_max_2m": "°C",
        "temperature_air_min_2m": "°C",
    }
    # the stub's readings have QN 1 and a `suspect:relations` check: the legend tells those and no other kind
    assert [row[0] for row in parsed.table("quality_flags legend").rows] == [None, "suspect"]
    assert [row[:2] for row in parsed.table("quality_flags codes").rows] == [[None, "1"]]
    assert parsed.table("source quality flags").rows
    assert "documentation" not in parsed.table("quality_flags legend").columns
    # the descriptions of the parameters are what makes the block long: they are not in it
    assert "description" not in parsed.table("parameters").columns
    assert _cli("--format=compact", "--with-metadata").stdout == rich
    assert len(rich) < len(_rest("json", with_metadata="true").text) / 2


def test_row_options_are_searched_and_reported_and_the_rows_stay_in_the_order_of_the_answer() -> None:
    """`filter` and `sort` choose the rows: the header says what was searched, the order of the answer is kept."""
    params = {"filter": "value<-5", "sort": "-timestamp", "timestamp": "2018/2020"}
    text = _rest(**params).text

    parsed = _held_to_json(text, **params)
    assert parsed.get("search") == "filter=value<-5 sort=-timestamp"
    assert re.fullmatch(
        r"searched \d+ of \d+ expected, gaps \d+; matched \d+, returned \d+", parsed.get("search_totals", "")
    )
    series = parsed.table("search series")
    assert [row[0] for row in series.rows] == ["00001", "00001", "00002", "00002"]
    assert series.columns[:4] == ["station_id", "parameter", "first", "last"]
    tables = [t for t in parsed.tables if t.heading.startswith("values ")]
    # a sorted answer of several stations has a table for each parameter, with a station column: the order of the answer
    # over the stations is the ranking
    assert [t.heading for t in tables] == [
        "values daily/climate_summary parameter=temperature_air_max_2m",
        "values daily/climate_summary parameter=temperature_air_min_2m",
    ]
    for table in tables:
        assert table.columns[:2] == ["station_id", "timestamp"]
        assert len(table.columns) == 3
    # one parameter needs no word for it, and one station is in the heading
    one = parse(_rest(**{**params, "parameters": TMIN}).text)
    assert [t.heading for t in one.tables if t.heading.startswith("values ")] == ["values daily/climate_summary"]
    alone = parse(_rest(**{**params, "parameters": TMIN, "stations": "00001"}).text)
    assert [t.heading for t in alone.tables if t.heading.startswith("values ")] == [
        "values daily/climate_summary station=00001"
    ]


def _json_order(answer: dict[str, Any], parameter: str) -> list[tuple[str, dt.datetime]]:
    """Give the (station, timestamp) of the rows of one parameter in the order of the JSON answer."""
    return [
        (r["station_id"], dt.datetime.fromisoformat(r["timestamp"]))
        for r in answer["values"]
        if r["parameter"] == parameter
    ]


@pytest.mark.parametrize("parameters", [TMIN, f"{TMIN},{TMAX}"])
def test_a_ranking_over_stations_keeps_its_order_in_the_text(parameters: str) -> None:
    """`sort=-value&first=3&by=none`: the three highest of all stations are in the order the JSON has them."""
    params = {"parameters": parameters, "timestamp": "2018/2020", "sort": "-value", "first": 3, "by": "none"}
    text = _rest(**params).text
    answer = _rest("json", **params).json()

    parsed = _held_to_json(text, **params)

    readings = readings_in_order(parsed)
    assert len({station for station, *_ in readings}) == 2 or parameters == TMIN
    for parameter in parameters.split(","):
        name = parameter.rsplit("/", 1)[1]
        expected = _json_order(answer, name)
        assert expected
        assert [(who, moment) for who, _, _, column, moment in readings if column == name] == expected


def test_the_ranking_of_two_stations_is_not_one_table_a_station() -> None:
    """The rows of the two stations are interleaved by their value in one table, which a table each would split."""
    params = {"timestamp": "2018/2020", "sort": "-value", "first": 3, "by": "none", "parameters": TMIN}
    answer = _rest("json", **params).json()
    parsed = parse(_rest(**params).text)

    (table,) = [t for t in parsed.tables if t.heading.startswith("values ")]
    assert table.heading == "values daily/climate_summary"
    assert {row[0] for row in table.rows} == {"00001", "00002"}
    assert len(table.rows) == len(answer["values"])
    # the values are in descending order down the table, over both stations, as the answer ranks them
    numbers = [float(row[2] or "nan") for row in table.rows]
    assert numbers == sorted(numbers, reverse=True)


def test_the_readings_of_the_end_line_are_those_of_the_long_form_in_either_shape() -> None:
    """`# end rows=` counts readings, the rows of the long form: a null reading kept is one, its cell empty."""
    kept = _rest(drop_nulls="false")
    wide = _rest(shape="wide")
    counted = _rest("json", drop_nulls="false").json()["metadata"]["counts"]["rows"]

    def end(response: Any) -> str:  # noqa: ANN401
        return response.text.rsplit("\n", 2)[-2]

    assert counted == 80
    # the wide shape keeps the nulls as `drop_nulls=false` does, and counts the same readings
    assert end(kept) == end(wide) == "# end rows=80"
    assert end(_rest()) == "# end rows=76"
    cells = [
        cell for t in parse(_rest().text).tables if t.heading.startswith("values ") for r in t.rows for cell in r[1:]
    ]
    assert sum(cell is not None for cell in cells) == 76
    # the nulls of the kept answer are empty cells too: more readings than cells
    kept_cells = [
        cell for t in parse(kept.text).tables if t.heading.startswith("values ") for r in t.rows for cell in r[1:]
    ]
    assert sum(cell is not None for cell in kept_cells) == 76


def test_the_wide_shape_is_the_same_table_and_the_values_are_those_of_the_long_one() -> None:
    """`shape` does not apply to the text: a table has a column for each parameter in either shape."""
    long_ = parse(_rest(shape="long").text)
    wide = parse(_rest(shape="wide").text)

    assert [t.heading for t in wide.tables] == [t.heading for t in long_.tables]
    # the wide shape keeps the null readings (it has no `drop_nulls`), which the long shape drops: 4 of the 80 here
    assert (long_.end, wide.end) == ("rows=76", "rows=80")
    got = {k: v for k, v in values(wide).items() if v[0] is not None}
    want = {k: v for k, v in values(long_).items() if v[0] is not None}
    assert got == want
    assert len(want) == 76


def test_a_window_without_readings_is_an_answer_with_its_header_and_no_table() -> None:
    """An empty answer is a 200: no station is listed, nothing is a table, the end line counts none."""
    response = _rest(timestamp="2030-01-01/2030-01-03")

    assert response.status_code == 200
    parsed = parse(response.text)
    assert parsed.tables == []
    assert parsed.end == "rows=0"
    assert parsed.get("license") == "CC-BY-4.0 https://creativecommons.org/licenses/by/4.0/"
    assert response.text.endswith("\n\n# end rows=0\n")


def test_a_row_cap_holds_the_text_as_it_holds_every_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """The text is one body, held to `rows` as a json body is, and not streamed up to the larger `stream_rows`."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "10")
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "1000")

    compact = _rest()
    json_ = _rest("json")
    streamed = _rest("csv")

    assert compact.status_code == json_.status_code == 400
    assert compact.json()["type"] == json_.json()["type"]
    assert "more than the 10 this server sends as one answer" in compact.json()["detail"]
    assert streamed.status_code == 200


def test_the_cli_refuses_nothing_it_lists_and_lists_the_text_for_values_alone() -> None:
    """`values` has `--format=compact`; `stations`, `interpolate` and `summarize` do not list it (and refuse it)."""
    for command, offered in (("values", True), ("stations", False), ("interpolate", False), ("summarize", False)):
        helped = CliRunner().invoke(cli, [command, "--help"]).output
        assert ("compact" in helped) is offered, command
        refused = CliRunner().invoke(cli, [command, "--provider=dwd", "--network=observation", "--format=compact"])
        assert ("Invalid value for '--format'" in refused.output) is (not offered), command


def test_the_openapi_document_offers_the_text_where_it_is_answered() -> None:
    """`values` lists `compact` and declares its media type; no other route lists it."""
    paths = app.openapi()["paths"]

    def formats(route: str) -> set[str]:
        parameters = {p["name"]: p for p in paths[route]["get"]["parameters"]}
        return set(parameters["format"]["schema"]["enum"])

    assert "compact" in formats("/api/v1/values")
    for route in ("/api/v1/stations", "/api/v1/interpolate", "/api/v1/summarize", "/api/v1/alerts"):
        assert "compact" not in formats(route), route
    assert COMPACT_MEDIA_TYPE in paths["/api/v1/values"]["get"]["responses"]["200"]["content"]
    assert COMPACT_MEDIA_TYPE not in paths["/api/v1/stations"]["get"]["responses"]["200"]["content"]


# --- MCP ----------------------------------------------------------------------------------------------------------


def _call(tool: str, arguments: dict[str, Any]) -> Any:  # noqa: ANN401
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(app)) as client:
            return await client.call_tool(tool, arguments, raise_on_error=False)

    return asyncio.run(call())


def _tool_arguments(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    return {**_BASE, **extra}


def test_a_tool_answers_the_text_without_a_format_and_json_when_asked_with_the_body_twice_and_no_sentence() -> None:
    """The default of the tool is the text (GH-4445): the content and the structured content; `format=json` is JSON."""
    default = _call("values", _tool_arguments())
    text = _call("values", _tool_arguments(format="compact"))
    as_json = _call("values", _tool_arguments(format="json"))

    assert not default.is_error, default.content
    assert not text.is_error, text.content
    assert default.content[0].text == default.structured_content["result"] == _rest().text
    assert default.structured_content == text.structured_content
    assert text.content[0].text == text.structured_content["result"] == _rest().text
    assert "The answer is" not in text.structured_content["result"]
    assert text.meta["wetterdienst"]["license"] == "CC-BY-4.0"
    assert not as_json.is_error, as_json.content
    assert as_json.structured_content["result"]["values"]


def test_rest_and_the_cli_keep_json_as_the_default_of_values() -> None:
    """Only the tool changed its default: a request without `format` is JSON everywhere else."""
    response = TestClient(app).get("/api/values", params=_BASE)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["values"]
    assert json.loads(_cli().output)["values"]


def test_a_default_answer_of_a_tool_is_cut_as_one_that_asks_for_the_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """The budget and the cut read the format the route answered in, which is the same with or without the name."""
    _big(monkeypatch)
    arguments = _tool_arguments(timestamp="2018/2020", stations="00001,00002,00003")

    default = _call("values", arguments)
    named = _call("values", {**arguments, "format": "compact"})

    assert not default.is_error, default.content
    assert default.structured_content == named.structured_content
    assert default.content[0].text == named.content[0].text
    parsed = parse(default.content[0].text)
    assert [code for code, _ in parsed.warnings() if code == "answer-truncated"] == ["answer-truncated"]
    assert _size(default.content[0].text) <= ANSWER_BUDGET


def _big(monkeypatch: pytest.MonkeyPatch, count: int = 3) -> None:
    """Serve `count` stations with every parameter of the dataset: a window of years is far over the budget."""
    serve(monkeypatch, count, every_parameter=True)
    monkeypatch.setattr("wetterdienst.ui.response_metadata._retrieved_at", lambda: _NOW)


def _size(text: str) -> int:
    """Count what a client receives of a text: the JSON of the structured content `{"result": text}`."""
    return len(json.dumps({"result": text}, separators=(",", ":"), ensure_ascii=False))


def test_a_long_answer_is_cut_to_whole_timestamps_within_the_budget_and_says_how_to_go_on() -> None:
    """The budget counts `{"result": text}`: the cut keeps whole timestamps, and holds more than the JSON does."""
    arguments = _tool_arguments(format="compact", timestamp="2018/2020", stations="00001,00002,00003")
    uncut = TestClient(app).get("/api/values", params=arguments)
    assert _size(uncut.text) > ANSWER_BUDGET + 10_000

    result = _call("values", arguments)

    assert not result.is_error, result.content
    text = result.content[0].text
    assert result.structured_content["result"] == text
    assert ANSWER_BUDGET - 3000 < _size(text) <= ANSWER_BUDGET
    parsed = parse(text)
    [(_, note)] = [w for w in parsed.warnings() if w[0] == "answer-truncated"]
    assert note.startswith(f"The answer was cut to stay within {ANSWER_BUDGET:,} characters: ")
    # the next window, to be asked as it is, and no word of csv or of the wide shape: this answer is smaller than both
    assert re.search(r"ask again with `timestamp=20\d\d-\d\d-\d\dT00:00:00\+00:00/2020`", note)
    assert "csv" not in note
    assert "shape" not in note
    assert "narrow the `timestamp` window or ask for fewer parameters" in note
    # every table ends on the same timestamp, which is whole: the cut is at a timestamp for every series
    tables = [t for t in parsed.tables if t.heading.startswith("values ")]
    assert len(tables) == 3
    assert len({t.rows[-1][0] for t in tables}) == 1
    assert all(len(row) == len(t.columns) for t in tables for row in t.rows)
    kept = len(tables[0].rows)
    assert all(len(t.rows) == kept for t in tables)
    assert parsed.end == f"rows={kept * 3 * 2}"
    # more timestamps than the JSON of the same budget holds
    json_answer = _call("values", {**arguments, "format": "json"})
    assert kept > len({v["timestamp"] for v in json_answer.structured_content["result"]["values"]}) * 2
    assert "`timestamp=" in note


@pytest.mark.parametrize("parameters", [2, 3, 5])
def test_a_timestamp_over_the_budget_by_itself_is_cut_after_whole_series(
    monkeypatch: pytest.MonkeyPatch, parameters: int
) -> None:
    """Many stations at one timestamp: the stations that fit are kept with every cell they have, none is cut through.

    The rows of the answer are a station's parameters one after the other, so a cut at a count of rows would end inside
    a station for most counts: the table of that station would lack a column, which reads as a reading it has not.
    """
    from tests.ui.test_mcp_budget import _stub_values, _tool_client  # noqa: PLC0415
    from tests.ui.test_restapi import _values_result_of_shape  # noqa: PLC0415

    names = [
        "temperature_air_mean_2m",
        "temperature_air_max_2m",
        "temperature_air_min_2m",
        "wind_gust_max",
        "snow_depth",
    ]
    stamp = dt.datetime(2026, 1, 2, tzinfo=dt.UTC)
    rows = [
        {
            "station_id": f"{i:05d}",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": name,
            "timestamp": stamp + dt.timedelta(days=day),
            "value": 1.5,
            "quality_flags": None,
        }
        for day in range(2)
        for i in range(600)
        for name in names[:parameters]
    ]
    base = _values_result_of_shape("long")
    frame = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    _stub_values(monkeypatch, replace(base, df=frame))
    arguments = {
        **_BASE,
        "stations": "01048",
        "format": "compact",
        "parameters": ",".join(f"daily/climate_summary/{n}" for n in names[:parameters]),
    }

    response = _tool_client().get("/api/values", params=arguments)

    assert response.status_code == 200, response.text
    text = response.text
    assert _size(text) <= ANSWER_BUDGET
    parsed = parse(text)
    note = dict(parsed.warnings())["answer-truncated"]
    assert "alone holds" in note
    assert "csv" not in note
    tables = [t for t in parsed.tables if t.heading.startswith("values ")]
    assert 0 < len(tables) < 600
    for table in tables:
        # a cell is empty for a gap of the source, never because the cut went through the series
        assert len(table.rows) == 1
        assert len(table.columns) == 1 + parameters
        assert all(cell == "1.5" for cell in table.rows[0][1:])
    assert parsed.end == f"rows={parameters * len(tables)}"
    # the first timestamp, in part: the second is left out whole
    assert {t.rows[0][0] for t in tables} == {"2026-01-02"}


def test_no_budget_cuts_a_timestamp_through_the_cells_of_a_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whatever the budget, the stations kept have every cell: a cut at a count of rows would end inside one.

    A cell costs a few characters and a station's table a hundred, so the budget that fits the most rows ends inside a
    station only for a few budgets of a hundred: they are all tried here, on a small answer.
    """
    from tests.ui.test_mcp_budget import _stub_values, _tool_client  # noqa: PLC0415
    from tests.ui.test_restapi import _values_result_of_shape  # noqa: PLC0415

    names = ["temperature_air_mean_2m", "temperature_air_max_2m", "temperature_air_min_2m", "wind_gust_max"]
    rows = [
        {
            "station_id": f"{i:05d}",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": name,
            "timestamp": dt.datetime(2026, 1, 2 + day, tzinfo=dt.UTC),
            "value": 1.5,
            "quality_flags": None,
        }
        for day in range(2)
        for name in names
        for i in range(60)
    ]
    base = _values_result_of_shape("long")
    frame = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    _stub_values(monkeypatch, replace(base, df=frame))
    arguments = {
        **_BASE,
        "stations": "01048",
        "format": "compact",
        "parameters": ",".join(f"daily/climate_summary/{n}" for n in names),
    }
    kept = set()

    for budget in range(2600, 2800, 4):
        monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", budget)
        response = _tool_client().get("/api/values", params=arguments)

        assert response.status_code == 200, response.text
        tables = [t for t in parse(response.text).tables if t.heading.startswith("values ")]
        assert tables, budget
        assert all(len(t.columns) == 1 + len(names) and len(t.rows) == 1 for t in tables), budget
        kept.add(len(tables))
    # the budgets did cut at different stations: the loop covered more than one cut
    assert len(kept) > 1


def test_the_size_a_tool_is_held_to_is_the_structured_content_as_the_client_gets_it() -> None:
    """`{"result": text}` as compact JSON: no sentence in front of a compact text, which the sentence of a csv has."""
    from wetterdienst.ui.mcp import structured_size  # noqa: PLC0415

    body = '# wetterdienst-compact/1 values\n# provider: "x"\nü\n'
    headers = {"x-wetterdienst-license": "CC-BY-4.0"}

    assert structured_size(COMPACT_MEDIA_TYPE, body, headers) == len(
        json.dumps({"result": body}, ensure_ascii=False, separators=(",", ":"))
    )
    assert structured_size("text/csv", body, headers) > structured_size(COMPACT_MEDIA_TYPE, body, headers) + 100


def test_the_note_of_a_cut_json_answer_still_offers_csv_with_the_wide_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """The advice is left out of the text's note only: the note of the JSON answer is as it was."""
    _big(monkeypatch)
    arguments = _tool_arguments(timestamp="2018/2020", stations="00001,00002,00003", format="json")

    result = _call("values", arguments)

    [warning] = [
        w for w in result.structured_content["result"]["metadata"]["warnings"] if w["code"] == "answer-truncated"
    ]
    assert "`format=csv` with `shape=wide`" in warning["message"]


def test_the_values_tool_describes_the_text_in_a_sentence_and_the_instructions_stay_under_their_limit() -> None:
    """The description of the tool says what the text is; the instructions have one sentence of it, under 7,800."""
    from wetterdienst.ui.mcp import INSTRUCTIONS  # noqa: PLC0415

    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def listed() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            return {tool.name: tool for tool in await client.list_tools()}

    tools = asyncio.run(listed())
    assert "pass format=json for the JSON" in tools["values"].description
    assert tools["values"].input_schema["properties"]["format"]["default"] == "compact"
    assert "Default of this tool: compact" in tools["values"].input_schema["properties"]["format"]["description"]
    assert tools["stations"].input_schema["properties"]["format"]["default"] == "json"
    assert "compact text by default" in INSTRUCTIONS
    assert 'format="json"' in INSTRUCTIONS
    assert "compact" not in tools["stations"].description
    assert "compact" not in tools["stations"].input_schema["properties"]["format"]["description"]
    assert INSTRUCTIONS.count("compact") == 1
    assert len(INSTRUCTIONS) < 7800
    # a model is never offered a chart, the charts being REST's alone
    assert "chart" not in tools["values"].input_schema["properties"]["format"]["description"].lower()


def test_the_gust_column_has_nulls_where_the_source_has_none() -> None:
    """A third parameter with gaps of its own: the empty cells are the gaps, which the JSON has no rows for."""
    params = {"parameters": f"{TMIN},{GUST}", "timestamp": "2018-01-01/2018-02-28"}
    text = _rest(**params).text

    parsed = _held_to_json(text, **params)
    table = parsed.table("values daily/climate_summary station=00001")
    gust = table.columns.index("wind_gust_max(m/s)")
    assert any(row[gust] is None for row in table.rows)
