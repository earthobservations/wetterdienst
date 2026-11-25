# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`statistics` over REST, MCP, the command line and Python (GH-4412).

One stub of a DWD network (`row_options_stub`) answers every surface, with readings a plain Python function gives, so
each surface is held to the same groups, to the same report of what was searched, to the same refusals, to the limits
of a request that reads a record, and to the cut of a tool's answer.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.model.statistics_oracle import Case, expected_series
from tests.model.statistics_stub import at, serve_custom
from tests.ui.row_options_stub import STATIONS, TMIN, oracle, serve
from wetterdienst.model.group_statistics import StatisticsRun
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app

_BASE = {"provider": "dwd", "network": "observation", "parameters": TMIN, "timestamp": "2018/2020", "all": "true"}
_NAME = "temperature_air_min_2m"
_READINGS = {station: {ts.date(): value for ts, value in oracle(station, _NAME)} for station in STATIONS}


@pytest.fixture(autouse=True)
def _stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the stub network on every test of this module."""
    serve(monkeypatch)


def _rest(**params: Any) -> Any:  # noqa: ANN401
    return TestClient(app).get("/api/v1/statistics", params={**_BASE, **params})


def _cli(*args: str) -> Any:  # noqa: ANN401
    return CliRunner().invoke(
        cli,
        [
            "statistics",
            "--provider=dwd",
            "--network=observation",
            f"--parameters={TMIN}",
            "--timestamp=2018/2020",
            "--all",
            *args,
        ],
    )


def _tool(arguments: dict[str, Any], name: str = "statistics") -> Any:  # noqa: ANN401
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    selection = {k: v for k, v in _BASE.items() if k != "all"}

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(app)) as client:
            return await client.call_tool(
                name, {**selection, "stations": "00001,00002,00003", **arguments}, raise_on_error=False
            )

    return asyncio.run(call())


def _python(aggregate: str, **options: Any) -> Any:  # noqa: ANN401
    request = DwdObservationRequest(
        parameters=[TMIN],
        start=dt.datetime(2018, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2020, 12, 31, 23, 59, 59, 999999, tzinfo=dt.UTC),
    ).all()
    return request.values().statistics(aggregate, **options)


def _groups(answer: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    return [(s["station_id"], s["groups"]) for s in answer["series"]]


def _structured(result: Any) -> dict[str, Any]:  # noqa: ANN401
    answer = result.structured_content
    return answer.get("result", answer)


def _warning(answer: dict[str, Any], code: str) -> str | None:
    return next((w["message"] for w in answer["metadata"]["warnings"] if w["code"] == code), None)


# ----------------------------------------------------------------------------------------------------------------
# the same answer on every surface
# ----------------------------------------------------------------------------------------------------------------

_REQUESTS = [
    pytest.param({"aggregate": "count", "by": "year", "filter": "value<0"}, id="frost days"),
    pytest.param(
        {"aggregate": "mean,min,max", "by": "year,month", "sort": "-mean", "first": 4}, id="warmest months first"
    ),
    pytest.param(
        {"aggregate": "sum,count", "by": "year", "filter": "month=12|1|2", "year_start": 12, "max_missing": 30},
        id="winters",
    ),
    pytest.param({"aggregate": "first,last", "by": "month", "having": "searched>0", "max_rows": 20}, id="capped"),
]


@pytest.mark.parametrize("options", _REQUESTS)
def test_every_surface_answers_the_same_groups(options: dict[str, Any]) -> None:
    """REST, the tool, the command line and Python give the same series and groups, and the oracle agrees."""
    response = _rest(**options)
    assert response.status_code == 200, response.text
    rest = response.json()

    tool = _tool(dict(options))
    assert not tool.is_error, tool.content
    assert _groups(_structured(tool)) == _groups(rest)

    flags = [f"--{k.replace('_', '-')}={v}" for k, v in options.items()]
    cli_result = _cli(*flags)
    assert cli_result.exit_code == 0, cli_result.output
    assert _groups(json.loads(cli_result.stdout)) == _groups(rest)

    python = _python(options["aggregate"], **{k: v for k, v in options.items() if k != "aggregate"})
    assert _groups({"series": python.series_dicts()}) == _groups(rest)
    assert python.search()["totals"] == rest["metadata"]["search"]["totals"]
    assert python.search()["options"] == rest["metadata"]["search"]["options"]


def test_rest_agrees_with_the_oracle_and_reports_what_was_searched() -> None:
    """The frost days of each year are what plain Python counts, and the report says how many days there were."""
    answer = _rest(aggregate="count,mean", by="year", filter="value<0").json()
    case = Case(
        aggregate="count,mean",
        by=("year",),
        window=(dt.date(2018, 1, 1), dt.date(2020, 12, 31)),
        value=lambda v: v < 0,
    )
    for series in answer["series"]:
        want = expected_series(_READINGS[series["station_id"]], case)
        assert [g["count"] for g in series["groups"]] == [g["count"] for g in want["groups"]]
        readings = _READINGS[series["station_id"]]
        assert series["searched"] == len(readings)
        assert series["expected"] == 1096
        assert series["gaps"] == 1096 - len(readings)
        assert series["first"] == min(readings).isoformat()
        assert series["last"] == max(readings).isoformat()
    search = answer["metadata"]["search"]
    assert search["totals"]["series"] == 3
    assert search["totals"]["groups"] == 9
    assert search["window"] == {
        "start": answer["metadata"]["request"]["start"],
        "end": answer["metadata"]["request"]["end"],
    }
    assert answer["metadata"]["counts"] == {"stations": 3, "rows": 9}
    assert list(search) == ["options", "window", "totals"]
    assert list(answer["series"][0]) == [
        "station_id",
        "name",
        "resolution",
        "dataset",
        "parameter",
        "unit",
        "first",
        "last",
        "searched",
        "expected",
        "gaps",
        "over_groups",
        "groups",
    ]
    assert list(answer["series"][0]["groups"][0]) == ["year", "count", "mean", "searched", "expected"]


def test_the_block_says_what_was_calculated() -> None:
    """The processing note says the numbers are calculated, the options are echoed with their defaults."""
    metadata = _rest(aggregate="max", by="month", first=2, sort="-max").json()["metadata"]
    assert "calculated per group" in metadata["processing_note"]
    assert metadata["search"]["options"] == {
        "aggregate": ["max"],
        "filter": None,
        "by": ["month"],
        "per": "station",
        "having": None,
        "sort": "-max",
        "first": 2,
        "year_start": 1,
        "max_missing": 0,
        "max_rows": None,
    }
    assert metadata["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert metadata["request"]["stations"] == {"filter": "all", "count": 3, "ids": list(STATIONS)}


# ----------------------------------------------------------------------------------------------------------------
# formats
# ----------------------------------------------------------------------------------------------------------------


def test_csv_is_a_row_per_group_with_the_block_in_the_headers() -> None:
    """The identity of the series first, then the columns of `by`, the aggregates and their dates."""
    response = _rest(aggregate="min,count", by="year", format="csv")
    assert response.status_code == 200
    lines = response.text.splitlines()
    assert lines[0] == "station_id,resolution,dataset,parameter,year,min,min_at,count,searched,expected"
    assert len(lines) == 1 + 9
    assert lines[1].startswith("00001,daily,climate_summary,temperature_air_min_2m,2018,")
    assert response.headers["X-Wetterdienst-Groups-Matched"] == "9"
    assert "X-Wetterdienst-Values-Searched" in response.headers
    assert response.headers["X-Wetterdienst-Rows"] == "9"
    assert "calculated per group" in response.headers["X-Wetterdienst-Processing"]


def test_ndjson_is_the_block_a_line_per_group_and_an_end_with_the_series_without_their_groups() -> None:
    """The block first, a line for each group, then the end."""
    response = _rest(aggregate="count", by="year", format="ndjson")
    lines = [json.loads(line) for line in response.text.splitlines()]
    assert "metadata" in lines[0]
    assert lines[1] == {
        "station_id": "00001",
        "resolution": "daily",
        "dataset": "climate_summary",
        "parameter": "temperature_air_min_2m",
        "year": 2018,
        "count": 337,
        "searched": 337,
        "expected": 365,
    }
    end = lines[-1]["end"]
    assert end["counts"] == {"stations": 3, "rows": 9}
    assert [s["station_id"] for s in end["series"]] == list(STATIONS)
    assert all("groups" not in s for s in end["series"])
    assert len(lines) == 1 + 9 + 1


# ----------------------------------------------------------------------------------------------------------------
# what is refused, and how
# ----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("options", "fragment"),
    [
        ({"aggregate": "median"}, "`median` is not a column of this option"),
        ({"aggregate": "count,count"}, "`count` is named twice"),
        ({"aggregate": "count,mean,sum,min,max,first"}, "6 aggregates, more than the 5 allowed"),
        ({"aggregate": "count", "by": "station_id"}, "never merged"),
        ({"aggregate": "count", "by": "decade"}, "`decade` is a group that is not available in this version"),
        ({"aggregate": "count", "filter": "value<0C"}, "something after the number"),
        ({"aggregate": "count", "filter": "temperature_air_min_2m<0"}, "not a column of this option"),
        ({"aggregate": "count", "having": "mean>3"}, "`mean` is not among the `aggregate` of this request"),
        ({"aggregate": "count", "sort": "-mean"}, "add it there first"),
        ({"aggregate": "count", "sort": "year"}, "`year` is not a group of this request"),
        ({"aggregate": "count", "first": 3}, "no `sort` is given"),
        ({"aggregate": "count", "per": "none"}, "no `first` is given"),
        ({"aggregate": "count", "year_start": 7}, "`by` has no `year`"),
        ({"aggregate": "count", "by": "year", "max_missing": 3}, "neither is asked for"),
    ],
)
def test_a_text_that_cannot_be_read_is_a_422_located_at_the_option(options: dict[str, Any], fragment: str) -> None:
    """Each refusal is a 422 `invalid-parameters` whose `errors` locate it at the option, with what to write."""
    response = _rest(**options)
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["type"].endswith("invalid-parameters")
    assert fragment in body["errors"][0]["msg"]
    assert body["errors"][0]["loc"][0] == "query"


@pytest.mark.parametrize(
    ("options", "fragment"),
    [
        ({"aggregate": "count", "by": "hour"}, "`hour` is finer than the daily values of `temperature_air_min_2m`"),
        ({"aggregate": "count", "filter": "hour=12"}, "Invalid `filter`: `hour` is finer than the daily values"),
    ],
)
def test_a_request_that_does_not_fit_the_series_is_a_400_that_says_what_to_change(
    options: dict[str, Any], fragment: str
) -> None:
    """Well written, and not for daily values: a 400, before a second station is read."""
    response = _rest(**options)
    assert response.status_code == 400, response.text
    assert fragment in response.json()["detail"]
    assert "finest column of daily data is `day`" in response.json()["detail"]


def test_a_sum_of_a_pressure_is_refused_with_the_allowed_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal names the aggregates the parameter allows (directions and codes: `test_group_statistics_rules`)."""
    readings = {at(2018, 1, day): 1000.0 + day for day in range(1, 29)}
    serve_custom(monkeypatch, {"00001": readings}, parameter="pressure_air_site_mean")
    response = _rest(parameters="daily/climate_summary/pressure_air_site_mean", aggregate="sum")
    assert response.status_code == 400, response.text
    assert "Allowed here: count, mean, min, max, first, last." in response.json()["detail"]
    assert "is no quantity" in response.json()["detail"]


def test_a_sum_of_temperatures_is_in_degree_days() -> None:
    """The Hellmann number and the heating degree days: a sum of a daily temperature, `°Cd`."""
    series = _rest(aggregate="sum,mean", by="year").json()["series"][0]
    assert series["unit"] == "°C"
    assert series["units"] == {"sum": "°Cd"}


@pytest.mark.parametrize(
    ("name", "query"),
    [
        ("aggregate", "aggregate=count&aggregate=mean"),
        ("by", "aggregate=count&by=year&by=month"),
        ("filter", "aggregate=count&filter=value<0&filter=month=1"),
        ("having", "aggregate=count&having=count>1&having=count>2"),
        ("sort", "aggregate=count&sort=-count&sort=count"),
        ("first", "aggregate=count&sort=-count&first=1&first=2"),
        ("per", "aggregate=count&sort=-count&first=1&per=none&per=station"),
        ("max_rows", "aggregate=count&max_rows=1&max_rows=2"),
        ("year_start", "aggregate=count&by=year&year_start=7&year_start=8"),
        ("max_missing", "aggregate=mean&max_missing=1&max_missing=2"),
    ],
)
def test_an_option_given_twice_is_a_422(name: str, query: str) -> None:
    """The query would keep one of them and the answer would not say which."""
    response = TestClient(app).get(
        f"/api/v1/statistics?provider=dwd&network=observation&parameters={TMIN}&all=true&timestamp=2018/2020&{query}"
    )
    assert response.status_code == 422, response.text
    assert f"`{name}` is given 2 times" in response.json()["detail"]


def test_a_station_selection_is_exactly_one_of_the_slim_ones() -> None:
    """No selection, two selections and one `values` has and `statistics` does not (a box) are refused."""
    base = {k: v for k, v in _BASE.items() if k != "all"}
    client = TestClient(app)
    for params in (
        {},
        {"all": "true", "stations": "00001"},
        {"left": "9", "bottom": "53", "right": "11", "top": "54"},
        {"wmo_id": "10381"},
    ):
        response = client.get("/api/v1/statistics", params={**base, "aggregate": "count", **params})
        assert response.status_code == 422, (params, response.text)


def test_the_tool_says_what_to_write_in_a_tool_error() -> None:
    """A bad text is a tool error with the position and what is allowed."""
    bad = _tool({"aggregate": "mode"})
    assert bad.is_error
    message = json.dumps(bad.structured_content) + str(bad.content)
    assert "count, mean, sum, min, max, first, last" in message


# ----------------------------------------------------------------------------------------------------------------
# what the answer says it left out
# ----------------------------------------------------------------------------------------------------------------


def test_the_warnings_count_incomplete_groups_by_station_and_say_how_many_tie() -> None:
    """`incomplete-groups` sums the groups with gaps; `ties-not-shown` says how many more tie with the last shown."""
    answer = _rest(aggregate="mean", by="year").json()
    message = _warning(answer, "incomplete-groups")
    assert message is not None
    assert message.startswith("9 groups have fewer values than expected, at 00001 Alpha (3)")
    assert "`max_missing` is 0" in message
    assert answer["metadata"]["search"]["totals"]["groups_incomplete"] == 9
    ties = _rest(aggregate="count", by="year", filter="value<-100", sort="-count", first=1).json()
    # every station has three years of 0: one is shown, two tie
    assert _warning(ties, "ties-not-shown") == (
        "6 more groups tie with the last one shown (the same value of every `sort` column) and are not shown: "
        "`first` keeps exactly N, in the order of `by` and then of the station. Add a second `sort` column, or raise "
        "`first`."
    )
    assert [len(s["groups"]) for s in ties["series"]] == [1, 1, 1]


def test_max_rows_cuts_the_answer_in_its_order_and_says_so() -> None:
    """The first groups of the answer, series by series, and a `rows-capped` of how many of how many."""
    whole = _rest(aggregate="count", by="year").json()
    cut = _rest(aggregate="count", by="year", max_rows=4).json()
    assert [len(s["groups"]) for s in cut["series"]] == [3, 1, 0]
    flat = [g for s in whole["series"] for g in s["groups"]]
    assert [g for s in cut["series"] for g in s["groups"]] == flat[:4]
    assert "4 of 9 groups are returned" in (_warning(cut, "rows-capped") or "")
    assert cut["metadata"]["search"]["totals"]["groups_matched"] == 9
    assert cut["metadata"]["search"]["totals"]["groups_returned"] == 4


def test_per_none_ranks_across_the_stations_of_a_parameter() -> None:
    """The three warmest months of all stations together, each series holding its share of them."""
    every = _rest(aggregate="max", by="year,month").json()
    flat = sorted(
        ((g["max"], g["year"], g["month"], s["station_id"]) for s in every["series"] for g in s["groups"]),
        key=lambda x: (-x[0], x[1], x[2], x[3]),
    )
    top = _rest(aggregate="max", by="year,month", sort="-max", first=3, per="none").json()
    shown = sorted(
        ((g["max"], g["year"], g["month"], s["station_id"]) for s in top["series"] for g in s["groups"]),
        key=lambda x: (-x[0], x[1], x[2], x[3]),
    )
    assert shown == flat[:3]
    assert sum(len(s["groups"]) for s in top["series"]) == 3


# ----------------------------------------------------------------------------------------------------------------
# the cut of a tool's answer
# ----------------------------------------------------------------------------------------------------------------


def test_a_cut_tool_answer_keeps_the_order_of_the_answer_and_says_how_many_groups_there_are(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first K of M groups in the order of the answer, the totals and the statistics over the groups of all."""
    options = {"aggregate": "mean,min,max", "by": "year,month"}
    whole = _rest(**options).json()
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 12000)
    result = _tool(options)
    assert not result.is_error
    answer = _structured(result)
    total = sum(len(s["groups"]) for s in whole["series"])
    shown = sum(len(s["groups"]) for s in answer["series"])
    assert 0 < shown < total
    message = _warning(answer, "answer-truncated") or ""
    assert f"the first {shown:,} of {total:,} groups" in message
    assert "`metadata.search.totals` and `over_groups` cover all" in message
    flat = [g for s in whole["series"] for g in s["groups"]]
    assert [g for s in answer["series"] for g in s["groups"]] == flat[:shown]
    assert answer["metadata"]["counts"]["rows"] == shown
    assert answer["metadata"]["search"]["totals"] == whole["metadata"]["search"]["totals"]
    kept = {s["station_id"]: s["over_groups"] for s in answer["series"]}
    assert all(kept[s["station_id"]] == s["over_groups"] for s in whole["series"] if s["station_id"] in kept)


def test_the_tool_leaves_a_small_answer_as_it_is() -> None:
    """Nothing is cut where the answer fits, and nothing is added to its warnings."""
    answer = _structured(_tool({"aggregate": "count", "by": "year"}))
    assert _warning(answer, "answer-truncated") is None
    assert sum(len(s["groups"]) for s in answer["series"]) == 9


def test_the_tool_definition_is_short() -> None:
    """The description and the input schema of the tool, which every client holds in its context."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def tools() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            return {tool.name: tool.model_dump() for tool in await client.list_tools()}

    found = asyncio.run(tools())
    tool = found["statistics"]
    size = len(tool["description"]) + len(json.dumps(tool["input_schema"], separators=(",", ":"), ensure_ascii=False))
    assert size < 7800, size
    assert tool["title"] == "Count, average or add up values per year, month, day or hour"
    properties = tool["input_schema"]["properties"]
    assert "aggregate" in tool["input_schema"]["required"]
    for name in (
        "left",
        "bottom",
        "right",
        "top",
        "wmo_id",
        "wigos_id",
        "icao_id",
        "shape",
        "humanize",
        "with_metadata",
    ):
        assert name not in properties
    assert "values" in tool["description"]
    assert size < len(found["values"]["description"]) + len(json.dumps(found["values"]["input_schema"])) / 2


# ----------------------------------------------------------------------------------------------------------------
# limits, and what is held
# ----------------------------------------------------------------------------------------------------------------


def test_more_groups_than_may_be_held_are_refused_as_soon_as_a_station_makes_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The limit of an answer (`rows`) holds the groups: refused at the station that exceeds it, not after the last."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "40")
    read: list[str] = []
    original = StatisticsRun.add_station

    def counting(self: StatisticsRun, df: Any, searched: Any) -> None:  # noqa: ANN401
        read.append(str(df.get_column("station_id")[0]))
        original(self, df, searched)

    monkeypatch.setattr(StatisticsRun, "add_station", counting)
    response = _rest(aggregate="count", by="year,month")
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["type"].endswith("limit-exceeded")
    assert (body["limit"], body["maximum"]) == ("rows", 40)
    assert "groups so far" in body["detail"]
    assert "Drop a column of `by`" in body["detail"]
    # 36 groups a station: the second station makes 72
    assert read == ["00001", "00002"]


def test_a_record_may_be_read_under_the_stream_limit_but_not_over_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The readings are held to the limit of a stream, as a request with `first` is, whatever the format."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    ok = _rest(aggregate="count", by="year")
    assert ok.status_code == 200, ok.text
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "1000")
    refused = _rest(aggregate="count", by="year")
    assert refused.status_code == 400, refused.text
    assert refused.json()["type"].endswith("limit-exceeded")
    assert refused.json()["limit"] == "stream_rows"


def test_the_stations_limit_holds_as_for_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """More stations than the server allows are refused before any is read."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "2")
    response = _rest(aggregate="count")
    assert response.status_code == 400
    assert response.json()["limit"] == "stations"


def test_each_station_is_reduced_before_the_next_is_read_and_its_rows_are_let_go(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The walk is a stream: read, reduce, read, reduce; the frame of a station is gone once its groups are made."""
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415

    events: list[str] = []
    collect = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001
    add = StatisticsRun.add_station

    def reading(self: Any, station_id: str, parameter_or_dataset: Any) -> Any:  # noqa: ANN401
        events.append(f"read {station_id}")
        return collect(self, station_id, parameter_or_dataset)

    def adding(self: StatisticsRun, df: Any, searched: Any) -> None:  # noqa: ANN401
        events.append(f"add {df.get_column('station_id')[0]}")
        add(self, df, searched)

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", reading)
    monkeypatch.setattr(StatisticsRun, "add_station", adding)
    result = _python("count", by="year")
    assert events == ["read 00001", "add 00001", "read 00002", "add 00002", "read 00003", "add 00003"]
    # what the run holds are the groups: a few columns of a few rows, not the readings of a station
    for series in result.series:
        assert series.frame.height == 3
        assert set(series.frame.columns) == {"year", "count", "searched", "expected", "_incomplete"}


def test_the_walk_stops_between_stations_when_the_answer_is_given_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check of the walk of `values` is the walk of `statistics` too: the work ends between two stations."""
    from wetterdienst.util import cancellation  # noqa: PLC0415

    calls = {"n": 0}

    def cancelled() -> None:
        calls["n"] += 1
        if calls["n"] > 1:
            raise cancellation.WorkAbandoned

    monkeypatch.setattr("wetterdienst.model.values.check_cancelled", cancelled)
    with pytest.raises(cancellation.WorkAbandoned):
        _python("count", by="year")
    assert calls["n"] == 2
