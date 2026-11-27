# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`filter`, `sort`, `first` and `by` over REST, MCP, the command line and Python (GH-4411).

One stub of a DWD network (`row_options_stub`) answers every surface, with readings that a plain Python function gives
(`oracle`), so each surface is held to the same rows, to the report of what was searched, to the same refusals, and to
the limits: a request with `first` or a `filter` reads up to the stream limit, and holds what it chooses to the limit
of one body.
"""

from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace
from typing import Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.ui.row_options_stub import DAYS, GUST, STATIONS, TMIN, oracle, serve
from wetterdienst.model.row_selection import parse_row_selection
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app
from wetterdienst.util.datetime import format_timestamp

_BASE = {"provider": "dwd", "network": "observation", "parameters": TMIN, "timestamp": "2018/2020", "all": "true"}
_NAME = "temperature_air_min_2m"


@pytest.fixture(autouse=True)
def _stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the stub network on every test of this module."""
    serve(monkeypatch)


def _lowest(station: str) -> list[tuple[str, float]]:
    readings = oracle(station, _NAME)
    low = min(value for _, value in readings)
    return [(ts.date().isoformat(), value) for ts, value in readings if value == low]


def _rest(**params: Any) -> Any:  # noqa: ANN401
    return TestClient(app).get("/api/values", params={**_BASE, **params})


def _rows(answer: dict[str, Any]) -> list[tuple[str, str, float]]:
    return [
        (v["station_id"], v["date"][:10] if "date" in v else v["timestamp"][:10], v["value"]) for v in answer["values"]
    ]


def test_the_lowest_of_every_station_with_what_was_searched() -> None:
    """The lowest of every station with what was searched."""
    response = _rest(sort="value", first=1)
    assert response.status_code == 200, response.text
    answer = response.json()
    expected = [(station, day, value) for station in STATIONS for day, value in _lowest(station)]
    assert _rows(answer) == expected
    search = answer["metadata"]["search"]
    assert search["options"] == {"filter": None, "sort": "value", "first": 1, "by": None, "max_rows": None}
    request = answer["metadata"]["request"]
    assert search["window"] == {"start": request["start"], "end": request["end"]}
    assert search["series_omitted"] == 0
    assert [s["station_id"] for s in search["series"]] == list(STATIONS)
    for entry in search["series"]:
        readings = oracle(entry["station_id"], _NAME)
        assert entry["searched"] == len(readings)
        assert entry["expected"] == DAYS
        assert entry["gaps"] == DAYS - len(readings)
        assert entry["first"] == format_timestamp(readings[0][0])
        assert entry["last"] == format_timestamp(readings[-1][0])
        assert entry["matched"] == len(_lowest(entry["station_id"]))
    assert search["totals"]["matched"] == answer["metadata"]["counts"]["rows"] == len(expected)
    assert search["totals"]["searched"] < search["totals"]["expected"]  # the gaps are told, not hidden


def test_the_dates_of_a_series_come_before_its_counts_and_the_series_before_the_totals() -> None:
    """A reader sees from when to when a series was searched before it reads how many values that is."""
    search = _rest(sort="value", first=1).json()["metadata"]["search"]
    assert list(search) == ["options", "window", "series", "series_omitted", "totals"]
    assert list(search["series"][0]) == [
        "station_id",
        "name",
        "resolution",
        "dataset",
        "parameter",
        "first",
        "last",
        "searched",
        "expected",
        "gaps",
        "matched",
        "returned",
    ]


def test_a_window_that_begins_before_the_data_is_incomplete_in_the_report() -> None:
    """The request asks for 2017 as well, which the stations never had: expected counts it, the gaps do not."""
    search = _rest(sort="value", first=1, timestamp="2017/2020").json()["metadata"]["search"]
    entry = search["series"][0]
    assert entry["expected"] == DAYS + 365
    assert entry["gaps"] == DAYS - entry["searched"]
    assert entry["first"].startswith("2018-01-0")


def test_no_option_adds_no_member_to_the_block() -> None:
    """No option adds no member to the block."""
    answer = _rest().json()
    assert "search" not in answer["metadata"]


def test_the_search_is_reported_for_an_empty_answer() -> None:
    """The search is reported for an empty answer."""
    answer = _rest(filter="value>100").json()
    assert answer["values"] == []
    assert answer["metadata"]["counts"]["rows"] == 0
    assert answer["metadata"]["search"]["totals"]["matched"] == 0
    assert answer["metadata"]["search"]["totals"]["searched"] > 3000


def test_a_filter_alone_streams_station_by_station_and_the_report_is_the_last_line() -> None:
    """A filter alone streams station by station and the report is the last line."""
    response = _rest(filter="value<=-9.5", format="ndjson")
    assert response.status_code == 200, response.text
    lines = [json.loads(line) for line in response.text.splitlines()]
    assert "search" not in lines[0]["metadata"]
    end = lines[-1]["end"]
    assert end["search"]["options"]["filter"] == "value<=-9.5"
    assert end["search"]["totals"]["matched"] == end["counts"]["rows"] == len(lines) - 2
    assert end["search"]["totals"]["series"] == 3


def test_sort_and_first_are_chosen_before_the_stream_begins_so_the_first_line_has_the_report() -> None:
    """Sort and first are chosen before the stream begins so the first line has the report."""
    response = _rest(sort="-value", first=2, by="none", format="ndjson")
    assert response.status_code == 200, response.text
    lines = [json.loads(line) for line in response.text.splitlines()]
    search = lines[0]["metadata"]["search"]
    assert search["totals"]["matched"] == len(lines) - 2
    assert lines[0]["metadata"]["counts"]["rows"] == len(lines) - 2
    values = [line["value"] for line in lines[1:-1]]
    assert values == sorted(values, reverse=True)
    assert lines[-1]["end"]["counts"]["rows"] == len(lines) - 2


def test_csv_carries_the_totals_in_headers() -> None:
    """Csv carries the totals in headers."""
    response = _rest(sort="value", first=1, format="csv")
    assert response.status_code == 200
    rows = response.text.splitlines()
    assert response.headers["x-wetterdienst-rows-matched"] == str(len(rows) - 1)
    assert int(response.headers["x-wetterdienst-values-searched"]) < int(
        response.headers["x-wetterdienst-values-expected"]
    )
    streamed = _rest(filter="value<=-9.5", format="csv")
    assert "x-wetterdienst-rows-matched" not in streamed.headers


def test_geojson_and_with_stations_answer_the_chosen_rows() -> None:
    """Geojson and with stations answer the chosen rows."""
    answer = _rest(sort="value", first=1, format="geojson").json()
    assert answer["metadata"]["search"]["totals"]["matched"] == sum(
        len(f["values"]) for f in answer["data"]["features"]
    )
    answer = _rest(sort="value", first=1, with_stations="true").json()
    assert [s["station_id"] for s in answer["stations"]] == list(STATIONS)
    # a station none of whose rows matched is not in the block, as for any other cut of the rows
    answer = _rest(filter="value<=-9.5,year=2018", stations="00001", with_stations="true", all="false").json()
    assert {s["station_id"] for s in answer["stations"]} <= {"00001"}


@pytest.mark.parametrize(
    ("params", "loc", "fragment"),
    [
        ({"filter": "value<="}, "filter", "position 8"),
        ({"filter": "value<=5x"}, "filter", "position 9"),
        ({"sort": "parameter"}, "sort", "`parameters`"),
        ({"by": "year"}, "by", "no `first` is given"),
        ({"first": 1}, "first", "no `sort` is given"),
        ({"first": 0, "sort": "value"}, "first", "outside the range"),
        ({"first": "many", "sort": "value"}, "first", "not a whole number"),
        ({"sort": "value", "first": 1, "by": "none,year"}, "by", "together with other columns"),
    ],
)
def test_a_text_that_cannot_be_read_is_a_422_located_at_the_option(
    params: dict[str, Any], loc: str, fragment: str
) -> None:
    """A text that cannot be read is a 422 located at the option."""
    response = _rest(**params)
    assert response.status_code == 422, response.text
    body = response.json()
    errors = body["errors"] if "errors" in body else body["detail"]
    assert errors[0]["loc"][-1] == loc, errors
    assert fragment in errors[0]["msg"], errors


def test_a_word_that_is_no_parameter_of_the_request_is_a_422_at_the_option_with_its_closest_names() -> None:
    """A name that the request does not have is refused once the request is known (GH-4419), as a text is: a 422."""
    response = _rest(filter="temperature<5")
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:invalid-parameters"
    detail = body["detail"]
    assert "`temperature` is not a column of this option" in detail
    assert "or a parameter of this request (temperature_air_min_2m)" in detail
    assert "Did you mean temperature_air_min_2m?" in detail
    assert body["errors"][0]["loc"] == ["query", "filter"]
    assert body["errors"][0]["input"] == "temperature<5"
    assert body["errors"][0]["type"] == "row_selection"
    unsorted = _rest(sort="temperatur").json()
    assert unsorted["errors"][0]["loc"] == ["query", "sort"]


def test_value_over_two_units_and_value_in_the_wide_shape_are_refused_as_a_400() -> None:
    """Value over two units and value in the wide shape are refused as a 400."""
    response = _rest(parameters=f"{TMIN},{GUST}", filter="value<=-2")
    assert response.status_code == 400, response.text
    assert "Name one parameter" in response.text
    response = _rest(shape="wide", sort="value", first=1)
    assert response.status_code == 400
    assert "wide" in response.text
    ok = _rest(parameters=f"{TMIN},{GUST}", sort="value", first=1)
    assert ok.status_code == 200, ok.text
    assert {v["parameter"] for v in ok.json()["values"]} == {"temperature_air_min_2m", "wind_gust_max"}


def test_a_request_with_first_reads_up_to_the_stream_limit_and_sends_up_to_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3 stations of 1096 days are 3288 rows to read: over a limit of 1000, under the stream limit."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "10000")
    refused = _rest()
    assert refused.status_code == 400
    assert refused.json()["limit"] == "rows"
    # a filter alone reads up to the stream limit too, and holds what matched to the limit (GH-4436)
    assert _rest(filter="value<=-9").status_code == 200
    chosen = _rest(sort="value", first=1)
    assert chosen.status_code == 200, chosen.text
    # what is sent is held to the limit of its kind: 1,100 rows chosen of a limit of 1,000
    over = _rest(sort="value", first=1000, by="station_id,month")
    assert over.status_code == 400, over.text
    assert "options chose" in over.text
    # the walk is stopped as the stations are read, not after the last one: the rows held when it stopped, so far
    assert re.search(r"chose [\d,]+ rows so far", over.text), over.text
    assert "at least" not in over.text
    # a stream that holds the rows (sort, first) is held to the same limit: it does not stream them
    streamed = _rest(sort="value", first=1000, by="station_id,month", format="ndjson")
    assert streamed.status_code == 400, streamed.text
    # one that does not hold them (a filter alone) streams under the stream limit
    assert _rest(filter="value>=-1000", format="ndjson").status_code == 200
    # the stream limit holds the read of a request with first, too
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "2000")
    assert _rest(sort="value", first=1).status_code == 400


def _cli(*args: str) -> Any:  # noqa: ANN401
    return CliRunner().invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            f"--parameters={TMIN}",
            "--timestamp=2018/2020",
            "--all",
            *args,
        ],
    )


def test_the_command_line_chooses_the_rows_and_says_what_it_searched() -> None:
    """The command line chooses the rows and says what it searched."""
    result = _cli("--sort=value", "--first=1")
    assert result.exit_code == 0, result.output
    answer = json.loads(result.stdout)
    assert _rows(answer) == [(s, d, v) for s in STATIONS for d, v in _lowest(s)]
    assert answer["metadata"]["search"]["totals"]["series"] == 3
    result = _cli("--filter=value<=-9.5,year=2019", "--sort=-timestamp", "--first=1", "--by=none", "--format=csv")
    assert result.exit_code == 0, result.output
    assert len(result.stdout.splitlines()) >= 2


@pytest.mark.parametrize(
    ("args", "fragment"),
    [
        (["--filter=value<="], "position 8"),
        (["--first=1"], "no `sort` is given"),
        (["--sort=value", "--first=0"], "outside the range"),
        (["--by=year"], "no `first` is given"),
    ],
)
def test_the_command_line_refuses_what_cannot_be_read_as_a_usage_error(args: list[str], fragment: str) -> None:
    """The command line refuses what cannot be read as a usage error."""
    result = _cli(*args)
    assert result.exit_code == 2, result.output
    assert fragment in result.output.replace("\n", " ") or fragment in result.output


def _tool(arguments: dict[str, Any]) -> Any:  # noqa: ANN401
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    selection = {k: v for k, v in _BASE.items() if k != "all"}

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(app)) as client:
            return await client.call_tool(
                "values",
                {**selection, "stations": "00001,00002,00003", "format": "json", **arguments},
                raise_on_error=False,
            )

    return asyncio.run(call())


def test_the_tool_chooses_the_rows_and_a_bad_text_is_a_tool_error_that_says_what_to_write() -> None:
    """The tool chooses the rows and a bad text is a tool error that says what to write."""
    result = _tool({"sort": "value", "first": 1})
    assert not result.is_error
    answer = result.structured_content
    answer = answer.get("result", answer)
    assert answer["metadata"]["search"]["totals"]["series"] == 3
    assert [(v["station_id"], v["value"]) for v in answer["values"]] == [
        (s, v) for s in STATIONS for _, v in _lowest(s)
    ]
    bad = _tool({"filter": "temperature<5"})
    assert bad.is_error
    message = json.dumps(bad.structured_content) + str(bad.content)
    assert "value, year, month, day, hour" in message


def test_a_cut_tool_answer_keeps_the_order_of_the_answer_and_says_how_many_matched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cut tool answer keeps the order of the answer and says how many matched."""
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 9000)
    result = _tool({"sort": "-value", "filter": "year=2019"})
    assert not result.is_error
    answer = result.structured_content
    answer = answer.get("result", answer)
    warning = next(w for w in answer["metadata"]["warnings"] if w["code"] == "answer-truncated")
    total = answer["metadata"]["search"]["totals"]["matched"]
    assert f"of {total:,} matched rows" in warning["message"]
    assert "sort=-value" in warning["message"]
    values = [v["value"] for v in answer["values"]]
    assert 0 < len(values) < total
    assert values == sorted(values, reverse=True)
    assert answer["metadata"]["counts"]["rows"] == len(values)
    # what is kept is the top of the whole order, not the start of the record
    every = _rest(filter="year=2019", sort="-value").json()["values"]
    assert [v["value"] for v in every[: len(values)]] == values


def test_the_tool_description_and_schema_name_the_options_in_few_characters() -> None:
    """The tool description and schema name the options in few characters."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def schema() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            return tools["values"].model_dump()

    tool = asyncio.run(schema())
    properties = tool["input_schema"]["properties"]
    for name in ("filter", "sort", "first", "by"):
        assert name in properties
    for name in ("filter", "sort", "by"):
        assert {"type": "string"} in properties[name]["anyOf"]
    assert "pattern" not in json.dumps(properties["filter"])
    added = sum(len(json.dumps(properties[name])) for name in ("filter", "sort", "first", "by"))
    assert "sort=value&first=1" in tool["description"]
    # 1,403 before a parameter's name became a column (GH-4419), which took 236 characters of the descriptions
    assert added < 1700, added


def _warning(answer: dict[str, Any], code: str) -> str | None:
    return next((w["message"] for w in answer["metadata"]["warnings"] if w["code"] == code), None)


def test_max_rows_cuts_the_answer_to_its_first_rows_and_says_how_many_matched() -> None:
    """Every row of every tie is matched; the answer holds the first of them, and the warning and report count all."""
    full = _rest(sort="value", first=1).json()
    capped = _rest(sort="value", first=1, max_rows=5).json()
    assert len(full["values"]) > 5
    assert capped["values"] == full["values"][:5]
    assert capped["metadata"]["counts"]["rows"] == 5
    totals = capped["metadata"]["search"]["totals"]
    assert (totals["matched"], totals["returned"]) == (len(full["values"]), 5)
    assert capped["metadata"]["search"]["options"]["max_rows"] == 5
    assert sum(entry["returned"] for entry in capped["metadata"]["search"]["series"]) == 5
    assert _warning(capped, "rows-capped").startswith(f"5 of {len(full['values'])} matched rows are returned")
    # a cap that cuts nothing says nothing
    uncut = _rest(sort="value", first=1, max_rows=10_000).json()
    assert _warning(uncut, "rows-capped") is None
    assert uncut["metadata"]["search"]["totals"]["returned"] == len(full["values"])


def test_max_rows_streams_to_its_rows_and_goes_on_counting() -> None:
    """A stream stops sending at the cap; the end line has the counts of all, the warning and the search."""
    lines = [json.loads(line) for line in _rest(filter="value<=-9", max_rows=4, format="ndjson").text.splitlines()]
    assert len(lines) - 2 == 4
    end = lines[-1]["end"]
    assert end["counts"]["rows"] == 4
    totals = end["search"]["totals"]
    assert totals["returned"] == 4
    assert totals["matched"] > 4
    assert totals["series"] == 3  # every station was read to the end
    assert any(w["code"] == "rows-capped" for w in end["warnings"])
    # a csv has no place for it: the rows are cut, and the headers are those known before the first row
    csv = _rest(filter="value<=-9", max_rows=4, format="csv")
    assert len(csv.text.splitlines()) - 1 == 4
    # a choice made before the stream begins has its report in the first line, and the cap in it
    first = json.loads(_rest(sort="value", first=1, max_rows=4, format="ndjson").text.splitlines()[0])
    assert first["metadata"]["search"]["totals"]["returned"] == 4
    assert any(w["code"] == "rows-capped" for w in first["metadata"]["warnings"])


@pytest.mark.parametrize("value", ["0", "-1", "10001", "many", "1.5"])
def test_max_rows_that_cannot_be_read_is_a_422_at_the_option(value: str) -> None:
    """The count is a whole number from 1 to 10,000, and the error is located at the option."""
    response = _rest(max_rows=value)
    assert response.status_code == 422, response.text
    errors = response.json()["errors"]
    assert errors[0]["loc"][-1] == "max_rows"
    assert "max_rows" in errors[0]["msg"]


@pytest.mark.parametrize("name", ["limit", "offset"])
def test_limit_and_offset_are_told_where_to_look(name: str) -> None:
    """They never were options: the answer names `max_rows`, on REST, in the tool and on the command line."""
    response = _rest(**{name: 5})
    assert response.status_code == 422
    assert "max_rows" in response.text
    assert "was renamed" not in response.text
    result = _tool({name: 5})
    assert result.is_error
    assert "max_rows" in json.dumps(result.structured_content) + str(result.content)
    cli = _cli(f"--{name}=5")
    assert cli.exit_code == 2
    assert f"--{name} is not an option of values" in cli.output.replace("\n", " ")
    assert "--max-rows" in cli.output


def test_max_rows_does_not_raise_the_read_limit_and_first_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """What is read is bounded as it was: a short answer from a long read needs `first`."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "10000")
    assert _rest(max_rows=5).status_code == 400
    assert _rest(sort="value", max_rows=5).status_code == 400
    capped = _rest(sort="value", first=1, max_rows=5)
    assert capped.status_code == 200, capped.text
    # and the rows a `first` chooses are held to `rows` after the cap: many ties are no refusal when it cuts them
    many = _rest(sort="value", first=1000, by="station_id,month", max_rows=50)
    assert many.status_code == 200, many.text
    assert len(many.json()["values"]) == 50


def test_the_command_line_takes_max_rows() -> None:
    """`--max-rows` cuts the answer, and the report counts all."""
    result = _cli("--sort=value", "--first=1", "--max-rows=3")
    assert result.exit_code == 0, result.output
    answer = json.loads(result.stdout)
    assert len(answer["values"]) == 3
    assert answer["metadata"]["search"]["totals"]["returned"] == 3
    assert _warning(answer, "rows-capped") is not None
    assert _cli("--max-rows=0").exit_code == 2


def test_a_tool_answer_cut_by_max_rows_and_by_the_budget_reads_sensibly(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rows-capped` says how many of how many matched are returned; `answer-truncated` counts what max_rows left."""
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 6000)
    result = _tool({"sort": "-value", "filter": "year=2019", "max_rows": 400})
    assert not result.is_error
    answer = result.structured_content
    answer = answer.get("result", answer)
    capped = _warning(answer, "rows-capped")
    truncated = _warning(answer, "answer-truncated")
    matched = answer["metadata"]["search"]["totals"]["matched"]
    assert capped.startswith(f"400 of {matched:,} matched rows are returned")
    assert f"of the 400 rows returned ({matched:,} matched; `max_rows` is 400)" in truncated
    assert answer["metadata"]["search"]["totals"]["returned"] == 400
    assert 0 < len(answer["values"]) < 400


def test_the_wide_shape_counts_rows_of_the_frame_in_the_totals_and_the_warning() -> None:
    """A wide row holds every parameter: five rows sent are five, not five for each parameter."""
    response = _rest(
        parameters=f"{TMIN},daily/climate_summary/temperature_air_max_2m",
        shape="wide",
        filter="month=2",
        max_rows=5,
        all="true",
    )
    assert response.status_code == 200, response.text
    answer = response.json()
    totals = answer["metadata"]["search"]["totals"]
    frame_rows = 3 * (29 + 28 + 28)  # the days of February, 2018 to 2020, of three stations: a row each
    assert totals["returned"] == answer["metadata"]["counts"]["rows"] == 5
    assert totals["matched"] == frame_rows
    assert _warning(answer, "rows-capped").startswith(f"5 of {frame_rows} matched rows are returned")
    assert response.headers["x-wetterdienst-rows-matched"] == str(frame_rows)
    csv = _rest(
        parameters=f"{TMIN},daily/climate_summary/temperature_air_max_2m",
        shape="wide",
        sort="-day",
        first=1,
        max_rows=2,
        format="csv",
    )
    assert csv.status_code == 200, csv.text
    assert int(csv.headers["x-wetterdienst-rows-matched"]) >= 2
    assert len(csv.text.splitlines()) - 1 == 2


def test_a_station_whose_values_are_all_missing_is_read_and_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """It has no series to list: the totals say it was read, and with the nulls kept its window is all missing."""
    serve(monkeypatch, 3, missing=("00002",))
    totals = _rest(sort="value", first=1).json()["metadata"]["search"]["totals"]
    assert (totals["stations_read"], totals["stations_with_values"], totals["series"]) == (3, 2, 2)
    kept = _rest(sort="value", first=1, drop_nulls="false").json()["metadata"]["search"]
    entry = next(e for e in kept["series"] if e["station_id"] == "00002")
    assert (entry["searched"], entry["first"], entry["last"], entry["matched"]) == (0, None, None, 0)
    assert entry["expected"] == DAYS  # the window of the request, all of it missing
    # with the nulls kept the station has a series, with nothing searched: it has no value, so it is not counted
    assert kept["totals"]["stations_with_values"] == 2
    assert kept["totals"]["stations_read"] == 3


def test_each_series_names_its_station_and_a_tool_lists_only_a_few(monkeypatch: pytest.MonkeyPatch) -> None:
    """Over REST a hundred series are listed with their names; a tool lists twenty, and the totals count all."""
    serve(monkeypatch, 100)
    answer = _rest(sort="value", first=1, max_rows=10).json()
    search = answer["metadata"]["search"]
    assert [e["name"] for e in search["series"][:3]] == ["Alpha", "Beta", "Gamma"]
    assert search["series"][50]["name"] == "Station 00051"
    assert (len(search["series"]), search["series_omitted"], search["totals"]["series"]) == (100, 0, 100)
    assert len(json.dumps(search)) < 40_000  # what a hundred stations take of a REST answer, which has no budget
    result = _tool(
        {"sort": "value", "first": 1, "max_rows": 10, "stations": ",".join(f"{n:05d}" for n in range(1, 101))}
    )
    assert not result.is_error
    tool = result.structured_content
    tool = tool.get("result", tool)
    listed = tool["metadata"]["search"]
    assert len(listed["series"]) == 20
    assert listed["series_omitted"] == 80
    assert listed["totals"]["series"] == 100
    assert len(json.dumps(tool)) < 40_000


def test_a_series_report_that_is_the_budget_goes_before_the_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Where the report alone fills the budget, its series are left out, with the totals kept, before a row is cut."""
    serve(monkeypatch, 100)
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 4000)
    result = _tool(
        {"sort": "value", "first": 1, "max_rows": 6, "stations": ",".join(f"{n:05d}" for n in range(1, 101))}
    )
    answer = result.structured_content
    answer = answer.get("result", answer)
    search = answer["metadata"]["search"]
    assert search["series"] == []
    assert search["series_omitted"] == 100
    assert search["totals"]["series"] == 100
    assert 1 <= len(answer["values"]) <= 6  # the series went and the rows that fit stayed
    note = _warning(answer, "rows-capped")
    assert note is not None


def test_a_note_never_advises_what_cannot_make_fewer_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """With `first=1` and `max_rows=1` there is no smaller one to ask for."""
    from wetterdienst.ui.budget import _rows_note  # noqa: PLC0415

    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 3000)
    result = _tool({"sort": "-value", "first": 1})
    answer = result.structured_content
    answer = answer.get("result", answer)
    truncated = _warning(answer, "answer-truncated") or ""
    assert truncated, answer["metadata"]["warnings"]
    assert "smaller `first`" not in truncated
    assert "`max_rows`" in truncated
    # and where a `first` above 1 or a `max_rows` is given, the note names it to make smaller
    taken = SimpleNamespace(
        series=SimpleNamespace(height=1, get_column=lambda _name: SimpleNamespace(sum=lambda: 10)),
        selection=parse_row_selection(sort="value", first=5, max_rows=9),
        matched_total=30,
    )
    note = _rows_note(result=SimpleNamespace(search=taken), kept=4, total=9, lead="", honest=False)
    assert "a smaller `first`, a smaller `max_rows`, a `filter`, or fewer parameters and stations" in note


def test_a_sort_without_first_is_told_that_a_stream_does_not_help(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `sort` holds every row it reads, so the refusal says to add `first` or drop `sort`, not to stream."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    for params in ({"sort": "value"}, {"sort": "value", "format": "csv"}, {"sort": "value", "format": "ndjson"}):
        response = _rest(**params)
        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "add `first`" in detail
        assert "drop `sort`" in detail
        assert "ndjson" not in detail
    # a request without `sort` is told to stream, as it was
    assert "format=ndjson" in _rest().json()["detail"]


def test_a_repeated_row_option_is_refused_and_not_silently_one_of_them() -> None:
    """A second `filter` is a 422 that says to join the conditions with a comma; so for `sort` and `by`."""
    for name, extra in (("filter", "month=1"), ("sort", "-value"), ("by", "year")):
        params = {**_BASE, "sort": "value", "first": 1, "filter": "value<0", "by": "station_id"}
        query = "&".join([f"{key}={value}" for key, value in params.items()] + [f"{name}={extra}"]).replace("<", "%3C")
        response = TestClient(app).get(f"/api/values?{query}")
        assert response.status_code == 422, response.text
        errors = response.json()["errors"]
        assert errors[0]["loc"] == ["query", name]
        assert "given 2 times" in errors[0]["msg"]
    assert "comma" in response.text or "one value" in response.text


def test_a_repeated_option_on_the_command_line_is_a_usage_error() -> None:
    """Click would keep the last of two: the command says to join the conditions with a comma."""
    result = _cli("--filter=value<0", "--filter=month=1")
    assert result.exit_code == 2, result.output
    assert "--filter is given 2 times" in result.output
    assert "comma" in result.output
    assert _cli("--sort=value", "--sort=-value", "--first=1").exit_code == 2


def test_a_tool_csv_carries_what_was_searched_in_its_sentence() -> None:
    """A CSV has no block: the three headers are in the sentence that stands for it."""
    result = _tool({"sort": "value", "first": 1, "format": "csv"})
    assert not result.is_error
    content = json.dumps(result.structured_content)
    assert "Searched:" in content
    assert "values of" in content
    assert "rows matched the options" in content


def test_spanning_groups_that_tie_over_many_stations_are_refused_so_far(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every station's lowest value ties: 100 stations of 16 rows are more than the limit, and none are held."""
    serve(monkeypatch, 100)
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "1000000")
    refused = _rest(sort="value", first=1, by="none", max_rows=1)
    assert refused.status_code == 400, refused.text
    assert re.search(r"chose [\d,]+ rows so far", refused.text), refused.text
    assert "add `timestamp` to `sort`" in refused.text
    # a calendar column breaks the tie where it means something: one row for each year of each station is 300 rows
    ok = _rest(sort="value,timestamp", first=1, by="year", max_rows=5)
    assert ok.status_code == 200, ok.text


def test_a_choice_with_max_rows_over_many_stations_is_no_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every station keeps up to `max_rows` rows and the rows held are cut to the answer, so 60 stations are fine."""
    serve(monkeypatch, 60)
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1500")
    response = _rest(sort="-value", first=1000, by="station_id,month", max_rows=1000)
    assert response.status_code == 200, response.text
    answer = response.json()
    assert len(answer["values"]) == 1000
    assert answer["metadata"]["search"]["totals"]["matched"] > 1500


def test_a_wide_request_that_chooses_rows_is_answered_where_the_plain_one_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """The read of a wide request with `first` is estimated as the plain wide request is, in rows: not refused more."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "5000")
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "7000")
    both = f"{TMIN},daily/climate_summary/temperature_air_max_2m"
    # 3 stations x 1,096 days: 3,288 wide rows, 6,576 cells. The plain request is answered, and so is one with `first`
    assert _rest(parameters=both, shape="wide").status_code == 200
    assert _rest(parameters=both, shape="wide", sort="-day", first=1).status_code == 200
    # the read of one with `first` is held to the larger of the two limits, in rows as for the plain request: a stream
    # limit below `rows` does not refuse what the plain request is answered (GH-4436)
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "3000")
    assert _rest(parameters=both, shape="wide", sort="-day", first=1).status_code == 200
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "3000")
    assert _rest(parameters=both, shape="wide", sort="-day", first=1).status_code == 400


def test_the_final_check_is_the_net_for_rows_that_piled_up_between_two_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Held 13 rows with a limit of 10, though no choice again found more than 9: only the whole answer is checked.

    Station A has 8 days, B has 4 of which 3 are A's and lower, so choosing again after B leaves 9 (under the limit) and
    the next choice is at 18; C has 4 new days, so the walk ends with 13 and the check of the answer refuses it.
    """
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415

    serve(monkeypatch, 3)
    days = {"00001": [1, 2, 3, 4, 5, 6, 7, 8], "00002": [6, 7, 8, 20], "00003": [21, 22, 23, 24]}
    level = {"00001": 10.0, "00002": 5.0, "00003": 7.0}

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> Any:  # noqa: ANN401, ARG001
        import datetime as dt  # noqa: PLC0415

        import polars as pl  # noqa: PLC0415

        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        name = next(p.name_original for p in dataset if p.name == "temperature_air_min_2m")
        stamps = [dt.datetime(2018, 1, day, tzinfo=dt.UTC) for day in days[station_id]]
        return pl.DataFrame(
            {
                "timestamp": stamps,
                "parameter": [name] * len(stamps),
                "value": [level[station_id]] * len(stamps),
                "quality_flags": ["1"] * len(stamps),
                "resolution": ["daily"] * len(stamps),
                "dataset": [dataset.name] * len(stamps),
            },
            schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "10")
    response = _rest(sort="value", first=1, by="year,month,day", timestamp="2018")
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["requested"] == 13
    assert "so far" not in body["detail"]  # the walk never held more than the limit at a choice: the answer did
    # with a limit of 13 the same request is answered with those 13 rows
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "13")
    assert len(_rest(sort="value", first=1, by="year,month,day", timestamp="2018").json()["values"]) == 13


def test_a_tool_that_sorts_too_much_is_told_to_add_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool is refused in its own words: a shorter window, fewer parameters, add `first`, or drop `sort`."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    result = _tool({"sort": "value"})
    assert result.is_error
    message = str(result.content)
    assert "add `first`" in message
    assert "drop `sort`" in message
    assert "ndjson" not in message


def test_a_repeated_number_is_refused_with_a_hint_to_give_one() -> None:
    """`first` and `max_rows` twice are a 422 or a usage error that says one number, not columns joined by commas."""
    query = "&".join(f"{k}={v}" for k, v in {**_BASE, "sort": "value", "first": 1, "max_rows": 2}.items())
    for name in ("first", "max_rows"):
        response = TestClient(app).get(f"/api/values?{query}&{name}=9")
        assert response.status_code == 422, response.text
        message = response.json()["errors"][0]["msg"]
        assert f"give one number to `{name}`" in message
        assert "columns" not in message
    for args in (["--sort=value", "--first=1", "--first=5"], ["--max-rows=1", "--max-rows=2"]):
        result = _cli(*args)
        assert result.exit_code == 2, result.output
        assert "give one number" in result.output


def test_the_limit_of_the_choice_again_is_in_rows_whatever_the_width_of_the_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wide choice of 10,000 rows of 14 parameters or more is answered with a limit of 12,000: cells are no rows.

    10 stations of 1,000 days, wide, with `by=none` (the groups span stations, so the held rows are chosen again as
    soon as their cells reach the limit): a station alone is 14,000 cells and 1,000 rows, and the answer is 10,000 rows.
    """
    serve(monkeypatch, 10, every_parameter=True)
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "12000")
    window = {"timestamp": "2018-01-01/2020-09-26", "parameters": "daily/climate_summary", "shape": "wide"}
    response = _rest(sort="timestamp", first=10000, by="none", **window)
    assert response.status_code == 200, response.text
    answer = response.json()
    assert len(answer["values"]) == 10_000
    assert answer["metadata"]["search"]["totals"]["returned"] == 10_000
    width = len([key for key in answer["values"][0] if not key.endswith("_quality_flags")]) - 4  # the keys of the row
    assert width >= 13  # a station is over 12,000 cells: the cells are over the limit at the first choice again
    # and one row more than the limit is refused, as rows
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "9999")
    assert _rest(sort="timestamp", first=10000, by="none", **window).status_code == 400
