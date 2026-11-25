# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parameter names as columns of `filter` and `sort`, held to the slow working-out on every surface (GH-4419).

The stub network of `row_options_stub` has three parameters that miss days of their own, so a day one has and another
lacks is a day a condition on both is not met. The oracle (`row_options_oracle.expected_names`) keeps the readings of a
day side by side in a dict and answers without polars, for the reader (`all`, `query`), the result (`selected_rows`)
and the REST API (json, csv, ndjson), long and wide, with the held rows chosen again at 1, 2, 5 and 20 cells.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.ui.row_options_oracle import NAME_CASES, expected_names, got, got_items, same
from tests.ui.row_options_stub import GUST, TMAX, TMIN, serve
from wetterdienst.model.row_selection import parse_row_selection
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.restapi import app

_BASE = {"provider": "dwd", "network": "observation", "timestamp": "2018/2020", "all": "true"}
_THREE = [TMIN, TMAX, GUST]


def _want(parameters: list[str], rows: dict[str, Any], stations: int, *, wide: bool) -> list[Any]:
    selection = parse_row_selection(**rows)
    assert selection is not None
    return expected_names(
        parameters,
        filter_=[(c.column, c.operator, c.values) for c in selection.conditions],
        sort=[(k.column, k.descending) for k in selection.sort],
        first=selection.first,
        by=None if selection.by is None else list(selection.by),
        max_rows=selection.max_rows,
        stations=stations,
        wide=wide,
    )


def _cases(parameters: list[str]) -> list[dict[str, Any]]:
    """Give the cases whose names are among the parameters asked for."""
    asked = {p.rsplit("/", 1)[1] for p in parameters}
    return [
        rows
        for rows in NAME_CASES
        if "temperature_air_max_2m" in asked or "temperature_air_max_2m" not in str(rows).lower()
    ]


def _reader(parameters: list[str], *, wide: bool) -> Any:  # noqa: ANN401
    options = {"shape": "wide"} if wide else {}
    return DwdObservationRequest(parameters=parameters, start="2018-01-01", end="2020-12-31", options=options)


def _rest(parameters: list[str], rows: dict[str, Any], fmt: str, *, wide: bool) -> Any:  # noqa: ANN401
    params = {**_BASE, "parameters": ",".join(parameters), "format": fmt, **rows}
    if wide:
        params["shape"] = "wide"
    response = TestClient(app).get("/api/values", params=params)
    assert response.status_code == 200, response.text
    return response


def _csv_rows(text: str) -> list[dict[str, Any]]:
    return [{k: (v if v != "" else None) for k, v in row.items()} for row in csv.DictReader(io.StringIO(text))]


@pytest.fixture(autouse=True)
def _compaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Choose the held rows again as soon as there is something to choose from: the walk is bounded at every step."""
    monkeypatch.setattr(TimeseriesValues, "_COMPACT_CELLS", 5)


@pytest.mark.parametrize("wide", [False, True], ids=["long", "wide"])
@pytest.mark.parametrize("parameters", [[TMIN, GUST], _THREE], ids=["two parameters", "three parameters"])
def test_the_reader_the_result_and_every_format_choose_what_the_oracle_does(
    monkeypatch: pytest.MonkeyPatch, parameters: list[str], *, wide: bool
) -> None:
    """The reader, the result's method and the REST formats give the rows the working-out gives, case by case."""
    serve(monkeypatch, 3)
    request = _reader(parameters, wide=wide)
    whole = request.all().values().all()
    cases = _cases(parameters)
    assert len(cases) > 15
    for rows in cases:
        want = _want(parameters, rows, 3, wide=wide)
        label = (wide, parameters, rows)
        same(got(request.all().values().all(**rows).df), want)
        same(got(whole.selected_rows(**rows).df), want)
        same(got_items(_rest(parameters, rows, "json", wide=wide).json()["values"]), want)
        lines = [json.loads(line) for line in _rest(parameters, rows, "ndjson", wide=wide).text.splitlines()]
        same(got_items(lines[1:-1]), want)
        assert lines[-1]["end"]["counts"]["rows"] == len(want), label
        csv_text = _rest(parameters, rows, "csv", wide=wide).text
        assert len(_csv_rows(csv_text)) == len(want), label
        totals = _rest(parameters, rows, "json", wide=wide).json()["metadata"]["search"]["totals"]
        assert totals["returned"] == len(want), label
        assert totals["matched"] >= len(want), label


def test_a_case_is_a_case_when_it_answers_rows_and_when_it_answers_none() -> None:
    """The table has cases that choose rows and cases that choose none: neither is vacuous (oracle only)."""
    sizes = [len(_want(_THREE, rows, 3, wide=False)) for rows in NAME_CASES]
    assert sum(1 for size in sizes if size > 20) > 10
    assert sizes[NAME_CASES.index({"filter": "temperature_air_min_2m<-100"})] == 0


@pytest.mark.parametrize("wide", [False, True], ids=["long", "wide"])
def test_query_gives_the_stations_their_own_choice_where_the_groups_stay_in_a_station(
    monkeypatch: pytest.MonkeyPatch, *, wide: bool
) -> None:
    """`query` yields a station's rows chosen as `all` chooses them, for every case that stays in the station."""
    serve(monkeypatch, 3)
    request = _reader(_THREE, wide=wide)
    for rows in NAME_CASES:
        selection = parse_row_selection(**rows)
        assert selection is not None
        if not selection.per_station or selection.max_rows is not None:
            continue
        pieces = [r.df for r in request.all().values().query(**rows)]
        mine = [row for piece in pieces for row in got(piece)]
        same(sorted(mine), sorted(_want(_THREE, rows, 3, wide=wide)))


@pytest.mark.parametrize("compact", [1, 2, 5, 20])
@pytest.mark.parametrize("stations", [1, 2, 3, 6])
@pytest.mark.parametrize("wide", [False, True], ids=["long", "wide"])
def test_the_groups_over_stations_hold_for_every_count_of_stations_and_every_bound(
    monkeypatch: pytest.MonkeyPatch, stations: int, compact: int, *, wide: bool
) -> None:
    """One to six stations, the held rows chosen again at 1, 2, 5 and 20 cells: the same rows as the working-out."""
    serve(monkeypatch, stations)
    monkeypatch.setattr(TimeseriesValues, "_COMPACT_CELLS", compact)
    request = _reader(_THREE, wide=wide)
    for rows in NAME_CASES:
        same(got(request.all().values().all(**rows).df), _want(_THREE, rows, stations, wide=wide))


def test_the_streamed_answer_is_the_station_by_station_choice_of_the_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A filter of names streams: each station is answered as it is read, and the `end` line has the whole report."""
    serve(monkeypatch, 3)
    rows = {"filter": "temperature_air_min_2m<0,wind_gust_max>=10"}
    lines = [json.loads(x) for x in _rest(_THREE, rows, "ndjson", wide=False).text.splitlines()]
    body = _rest(_THREE, rows, "json", wide=False).json()
    assert lines[-1]["end"]["search"]["totals"] == body["metadata"]["search"]["totals"]
    same(got_items(lines[1:-1]), got_items(body["values"]))
    series = {(s["station_id"], s["parameter"]): s for s in body["metadata"]["search"]["series"]}
    days = {station: series[(station, "temperature_air_min_2m")]["matched"] for station in ("00001", "00002", "00003")}
    # both named parameters have a value on every matched day: their matched counts are the days
    assert days == {s: series[(s, "wind_gust_max")]["matched"] for s in days}
    # the third parameter's rows are those of the same days, where it has a value
    assert all(series[(s, "temperature_air_max_2m")]["matched"] <= days[s] for s in days)


_FROST = {
    "filter": "temperature_air_min_2m<0,wind_gust_max>=10",
    "sort": "-wind_gust_max",
    "first": 4,
    "by": "station_id",
}


def _cli(*args: str) -> Any:  # noqa: ANN401
    from click.testing import CliRunner  # noqa: PLC0415

    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    return CliRunner().invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            f"--parameters={','.join(_THREE)}",
            "--timestamp=2018/2020",
            "--all",
            *args,
        ],
    )


def _tool(arguments: dict[str, Any]) -> Any:  # noqa: ANN401
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    selection = {k: v for k, v in _BASE.items() if k != "all"}

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(app)) as client:
            return await client.call_tool(
                "values",
                {**selection, "parameters": ",".join(_THREE), "stations": "00001,00002,00003", **arguments},
                raise_on_error=False,
            )

    return asyncio.run(call())


def test_python_rest_the_command_line_and_the_tool_give_the_same_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one selection of the issue, on the four surfaces: the frost with gusts, strongest first."""
    serve(monkeypatch, 3)
    want = _want(_THREE, _FROST, 3, wide=False)
    assert len(want) > 20
    same(got(_reader(_THREE, wide=False).all().values().all(**_FROST).df), want)
    same(got_items(_rest(_THREE, _FROST, "json", wide=False).json()["values"]), want)
    result = _cli(
        f"--filter={_FROST['filter']}", f"--sort={_FROST['sort']}", f"--first={_FROST['first']}", f"--by={_FROST['by']}"
    )
    assert result.exit_code == 0, result.output
    same(got_items(json.loads(result.stdout)["values"]), want)
    tool = _tool(_FROST)
    assert not tool.is_error
    answer = tool.structured_content
    same(got_items(answer.get("result", answer)["values"]), want)


def test_a_name_that_is_none_is_refused_on_every_surface_with_the_names_the_request_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same refusal: a 400 on REST, a usage error on the command line, a tool error, a `ValueError` in Python."""
    serve(monkeypatch, 3)
    text = "temperature_air_min_2<0"
    with pytest.raises(ValueError, match="Did you mean temperature_air_min_2m"):
        _reader(_THREE, wide=False).all().values().all(filter=text)
    response = TestClient(app).get("/api/values", params={**_BASE, "parameters": ",".join(_THREE), "filter": text})
    assert response.status_code == 400
    assert "Did you mean temperature_air_min_2m" in response.json()["detail"]
    cli = _cli(f"--filter={text}")
    assert cli.exit_code == 2, cli.output
    assert "Did you mean temperature_air_min_2m" in cli.output.replace("\n", " ")
    tool = _tool({"filter": text})
    assert tool.is_error
    assert "Did you mean temperature_air_min_2m" in json.dumps(tool.structured_content) + str(tool.content)


def test_value_beside_a_name_and_names_over_two_resolutions_are_a_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refusal of a well-written selection that does not fit the request, and before any station is read."""
    serve(monkeypatch, 3)
    params = {**_BASE, "parameters": ",".join(_THREE)}
    response = TestClient(app).get("/api/values", params={**params, "filter": "value<0,wind_gust_max>=10"})
    assert response.status_code == 400
    assert "`value` and a parameter's name are in one selection" in response.json()["detail"]
    mixed = f"{TMIN},hourly/temperature_air/temperature_air_2m"
    response = TestClient(app).get(
        "/api/values", params={**_BASE, "parameters": mixed, "filter": "temperature_air_min_2m<0"}
    )
    assert response.status_code == 400, response.text
    assert "has 2 (daily, hourly)" in response.json()["detail"]


def test_a_name_works_in_the_wide_shape_where_value_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented use of 0.197.0: conditions on the parameters' columns of the wide row."""
    serve(monkeypatch, 3)
    rows = {"filter": "temperature_air_min_2m<0,wind_gust_max>=10"}
    answer = _rest(_THREE, rows, "json", wide=True).json()
    assert {"temperature_air_min_2m", "wind_gust_max"} <= set(answer["values"][0])
    assert all(v["temperature_air_min_2m"] < 0 and v["wind_gust_max"] >= 10 for v in answer["values"])
    refused = TestClient(app).get(
        "/api/values",
        params={**_BASE, "parameters": ",".join(_THREE), "shape": "wide", "filter": "value<0"},
    )
    assert refused.status_code == 400
    assert "Name the parameter instead" in refused.json()["detail"]


def test_the_tool_describes_names_in_few_characters() -> None:
    """The description of the tool says that a name is a column, in a sentence; the schema grows by a few words."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def schema() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            return tools["values"].model_dump()

    tool = asyncio.run(schema())
    assert "temperature_air_min_2m<0,wind_gust_max>=17.2" in tool["description"]
    properties = tool["input_schema"]["properties"]
    assert "requested parameter's name" in properties["filter"]["description"]
    assert "requested parameter's name" in properties["sort"]["description"]


def test_a_name_is_the_name_the_answer_writes_and_its_number_is_in_the_unit_the_answer_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `humanize=false` a name is the source's (`tnk`); with a unit target the number is in that unit."""
    serve(monkeypatch, 3)
    parameters = [TMIN, GUST]
    celsius = _reader(parameters, wide=False).all().values().all(filter="temperature_air_min_2m<0,wind_gust_max>=10")
    stamps = sorted({(r["station_id"], r["timestamp"]) for r in celsius.df.iter_rows(named=True)})
    assert len(stamps) > 20
    # the source's own names: tnk and fx
    own = DwdObservationRequest(
        parameters=parameters, start="2018-01-01", end="2020-12-31", options={"humanize": False}
    )
    raw = own.all().values().all(filter="tnk<0,fx>=10")
    assert sorted({(r["station_id"], r["timestamp"]) for r in raw.df.iter_rows(named=True)}) == stamps
    assert set(raw.df.get_column("parameter")) == {"tnk", "fx"}
    # a humanised name is no name of that request, and the refusal says which names it has
    with pytest.raises(ValueError, match=r"or a parameter of this request \(tnk, fx\)"):
        own.all().values().all(filter="temperature_air_min_2m<0")
    # degrees Fahrenheit: -0 degrees Celsius is 32; the same days, in the number the answer writes
    fahrenheit = DwdObservationRequest(
        parameters=parameters,
        start="2018-01-01",
        end="2020-12-31",
        options={"unit_targets": {"temperature": "degree_fahrenheit"}},
    )
    shown = fahrenheit.all().values().all(filter="temperature_air_min_2m<32,wind_gust_max>=10")
    assert sorted({(r["station_id"], r["timestamp"]) for r in shown.df.iter_rows(named=True)}) == stamps
    values = shown.df.filter(pl.col("parameter") == "temperature_air_min_2m").get_column("value")
    assert 0 < values.max() < 32


def test_a_request_of_several_stations_with_a_rank_reads_the_stations_it_would_without_the_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Names change which rows come back, never which stations are read (`rank` and `skip_empty` count first)."""
    serve(monkeypatch, 3, missing=("00002",))
    request = DwdObservationRequest(parameters=[TMIN, GUST], start="2018-01-01", end="2020-12-31")
    plain = request.filter_by_rank((53.5, 10.0), 2).values().all()
    named = request.filter_by_rank((53.5, 10.0), 2).values().all(filter="temperature_air_min_2m<-100")
    assert named.df.is_empty()
    assert named.search is not None
    # the station without a reading is passed over by the rank, which reads on to a third: as without the names
    totals = named.search.to_dict()["totals"]
    assert (totals["stations_read"], totals["stations_with_values"]) == (3, 2)
    assert sorted(plain.df.get_column("station_id").unique()) == ["00001", "00003"]
