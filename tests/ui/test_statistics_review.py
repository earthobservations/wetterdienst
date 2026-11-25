# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The review of #4444 on the surfaces: `per=none` by rank, the series of an answer, the limits, the shape (GH-4412).

The stub of the row options serves the stations; each case is held to what plain Python makes of the same readings.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.ui.row_options_stub import GUST, STATIONS, TMIN, serve
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.restapi import app

_BASE = {"provider": "dwd", "network": "observation", "parameters": TMIN, "timestamp": "2018/2020", "all": "true"}


def _rest(**params: Any) -> Any:  # noqa: ANN401
    return TestClient(app).get("/api/v1/statistics", params={**_BASE, **params})


def _tool(arguments: dict[str, Any]) -> dict[str, Any]:
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(app)) as client:
            return await client.call_tool("statistics", {**_BASE, **arguments}, raise_on_error=False)

    result = asyncio.run(call())
    assert not result.is_error, result.content
    answer = result.structured_content
    return answer.get("result", answer)


def _flat(answer: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(s["station_id"], g) for s in answer["series"] for g in s["groups"]]


def _warning(answer: dict[str, Any], code: str) -> str | None:
    return next((w["message"] for w in answer["metadata"]["warnings"] if w["code"] == code), None)


_PER_NONE = {"aggregate": "max", "by": "year,month", "sort": "-max", "first": 5, "per": "none"}


def test_per_none_lists_the_series_by_their_best_rank_and_each_group_has_its_rank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The five highest months of 12 stations: ranks 1 to 5, series by their best, the others left out."""
    serve(monkeypatch, count=12)
    whole = _rest(aggregate="max", by="year,month").json()
    want = sorted(
        ((g["max"], g["year"], g["month"], s["station_id"]) for s in whole["series"] for g in s["groups"]),
        key=lambda x: (-x[0], x[1], x[2], x[3]),
    )[:5]
    answer = _rest(**_PER_NONE).json()
    got = [(g["max"], g["year"], g["month"], s["station_id"], g["rank"]) for s in answer["series"] for g in s["groups"]]
    assert sorted(got, key=lambda x: x[4]) == [(*w, rank) for rank, w in enumerate(want, start=1)]
    assert sorted(g["rank"] for _, g in _flat(answer)) == [1, 2, 3, 4, 5]
    firsts = [min(g["rank"] for g in s["groups"]) for s in answer["series"]]
    assert firsts == sorted(firsts)
    assert 0 < len(answer["series"]) <= 5
    assert all(s["groups"] for s in answer["series"])
    assert list(answer["series"][0]["groups"][0])[:3] == ["rank", "year", "month"]
    totals = answer["metadata"]["search"]["totals"]
    # the series that kept no group are not listed and the totals count them all
    assert totals["series"] == 12
    assert totals["groups_returned"] == 5
    assert totals["groups"] == 12 * 36
    assert answer["metadata"]["counts"] == {"stations": len(answer["series"]), "rows": 5}


def test_per_station_groups_have_no_rank_and_per_none_csv_and_ndjson_have_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rank` is the column of `per=none` alone, in front of the columns of `by`, in CSV and NDJSON as in JSON."""
    serve(monkeypatch, count=4)
    station = _rest(aggregate="max", by="year", sort="-max", first=2).json()
    assert "rank" not in station["series"][0]["groups"][0]
    csv = _rest(**{**_PER_NONE, "format": "csv"}).text.splitlines()
    assert csv[0] == "station_id,resolution,dataset,parameter,rank,year,month,max,max_at,searched,expected,complete"
    assert sorted(line.split(",")[4] for line in csv[1:]) == ["1", "2", "3", "4", "5"]
    nd = _rest(**{**_PER_NONE, "format": "ndjson"}).text.splitlines()
    assert sorted(json.loads(line)["rank"] for line in nd[1:-1]) == [1, 2, 3, 4, 5]


def test_max_rows_cuts_per_none_by_rank_and_leaves_out_the_series_without_a_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`max_rows=2` keeps the groups of rank 1 and 2, wherever their stations were read."""
    serve(monkeypatch, count=12)
    full = _rest(**_PER_NONE).json()
    cut = _rest(**{**_PER_NONE, "max_rows": 2}).json()
    assert sorted(g["rank"] for _, g in _flat(cut)) == [1, 2]
    best = {g["rank"]: (s, g["max"]) for s, g in _flat(full)}
    assert {g["rank"]: (s, g["max"]) for s, g in _flat(cut)} == {1: best[1], 2: best[2]}
    assert "2 of 5 groups are returned" in (_warning(cut, "rows-capped") or "")
    assert "best by rank" in (_warning(cut, "rows-capped") or "")
    assert cut["metadata"]["search"]["totals"]["series"] == 12


def test_the_tool_cuts_per_none_by_rank(monkeypatch: pytest.MonkeyPatch) -> None:
    """Over the budget the tool keeps the groups of the first ranks, with the series that hold them."""
    serve(monkeypatch, count=12)
    options = {
        "aggregate": "mean",
        "by": "year,month",
        "sort": "-mean",
        "first": 300,
        "per": "none",
        "max_missing": 400,
    }
    whole = _rest(**options).json()
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 16000)
    answer = _tool(options)
    ranks = sorted(g["rank"] for _, g in _flat(answer))
    assert ranks == list(range(1, len(ranks) + 1))
    assert 0 < len(ranks) < len(_flat(whole))
    assert "answer-truncated" in {w["code"] for w in answer["metadata"]["warnings"]}
    totals = answer["metadata"]["search"]["totals"]
    assert totals["groups_returned"] == len(ranks) == answer["metadata"]["counts"]["rows"]
    assert {**totals, "groups_returned": 0} == {**whole["metadata"]["search"]["totals"], "groups_returned": 0}
    kept = {(s, g["rank"], g["mean"]) for s, g in _flat(answer)}
    assert kept <= {(s, g["rank"], g["mean"]) for s, g in _flat(whole)}


def test_a_request_of_more_series_than_an_answer_reports_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """60 stations of two parameters are 120 series, more than the 100: a 400 `series`, before a station is read."""
    serve(monkeypatch, count=60)
    response = _rest(parameters=f"{TMIN},{GUST}", aggregate="count")
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["type"].endswith("limit-exceeded")
    assert (body["limit"], body["maximum"], body["requested"]) == ("series", 100, 120)
    assert "This request has 120 series, more than the 100 an answer reports" in body["detail"]
    assert _rest(aggregate="count").status_code == 200


def test_a_tool_lists_20_series_and_says_the_totals_cover_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """30 stations: REST lists 30 series, the tool 20 with the note, and the totals count 30."""
    serve(monkeypatch, count=30)
    options = {"aggregate": "count", "by": "year"}
    rest = _rest(**options).json()
    tool = _tool(options)
    assert (len(rest["series"]), len(tool["series"])) == (30, 20)
    assert [s["station_id"] for s in tool["series"]] == [s["station_id"] for s in rest["series"]][:20]
    message = _warning(tool, "answer-truncated") or ""
    # a cap of series, not a cut to the 40,000 characters: it says which, and that every group of the 20 is there
    assert "The answer lists 20 of 30 series that have a group" in message
    assert "40,000" not in message
    assert tool["metadata"]["search"]["totals"]["series"] == 30
    assert tool["metadata"]["counts"]["rows"] == 60
    assert tool["metadata"]["search"]["totals"]["groups_returned"] == 60


def test_the_groups_limit_is_its_own_setting_and_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_RESTAPI_MAX_GROUPS` (50,000 by default) is `max_groups` of `/api/version`, and the 400 names `groups`."""
    assert TestClient(app).get("/api/v1/version").json()["limits"]["max_groups"] == 50_000
    monkeypatch.setenv("WD_RESTAPI_MAX_GROUPS", "7")
    assert TestClient(app).get("/api/v1/version").json()["limits"]["max_groups"] == 7
    serve(monkeypatch)
    # the rows limit of `values` does not hold the groups: only this one does
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1")
    refused = _rest(aggregate="count", by="year,month")
    assert refused.status_code == 400
    assert refused.json()["limit"] == "groups"
    assert refused.json()["maximum"] == 7
    monkeypatch.setenv("WD_RESTAPI_MAX_GROUPS", "0")
    assert _rest(aggregate="count", by="year,month").status_code == 200


def test_the_shape_is_long_whatever_the_server_says(monkeypatch: pytest.MonkeyPatch) -> None:
    """A server set to `WD_TS_SHAPE=wide` answers `statistics` all the same."""
    serve(monkeypatch)
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    response = _rest(aggregate="count", by="year")
    assert response.status_code == 200, response.text
    assert len(response.json()["series"]) == 3


def test_the_groups_header_of_a_json_answer_and_the_name_of_the_one_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    """`X-Wetterdienst-Groups-Matched` is on every format; the parameter's name is `value` on every surface."""
    serve(monkeypatch)
    response = _rest(aggregate="count", by="year", filter="temperature_air_min_2m<0")
    assert response.status_code == 200, response.text
    assert response.headers["X-Wetterdienst-Groups-Matched"] == "9"
    assert response.json()["metadata"]["search"]["options"]["filter"] == "value<0"
    other = _rest(aggregate="count", filter="wind_gust_max<0")
    assert other.status_code == 422
    assert other.json()["errors"][0]["loc"] == ["query", "filter"]


def test_a_held_result_gives_the_units_of_its_options(monkeypatch: pytest.MonkeyPatch) -> None:
    """In degrees Fahrenheit a sum of daily temperatures is `°F d`, as the held result's options say."""
    serve(monkeypatch)
    request = DwdObservationRequest(
        parameters=[TMIN],
        start=dt.datetime(2018, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC),
        options={"unit_targets": {"temperature": "degree_fahrenheit"}},
    ).all()
    held = request.values().all().statistics("sum,mean", by="year", max_missing=400)
    series = held.series_dicts()[0]
    assert series["unit"] == "°F"
    assert series["units"] == {"sum": "°F d"}
    streamed = request.values().statistics("sum,mean", by="year", max_missing=400)
    assert streamed.series_dicts() == held.series_dicts()
    assert STATIONS


def test_fifty_thousand_groups_are_written_in_the_time_of_a_polars_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    """A series of 140 years by day is 51,000 groups: JSON and CSV and NDJSON are made from frames, not row by row."""
    import time  # noqa: PLC0415

    from tests.model.statistics_stub import daily, serve_custom  # noqa: PLC0415

    serve_custom(
        monkeypatch, {"00001": daily(dt.date(1880, 1, 1), [1.0] * 51_000)}, parameter="temperature_air_mean_2m"
    )
    request = DwdObservationRequest(
        parameters=["daily/climate_summary/temperature_air_mean_2m"],
        start=dt.datetime(1880, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2019, 12, 31, tzinfo=dt.UTC),
    ).all()
    result = request.values().statistics("count,mean,max", by="year,month,day", max_missing=400)
    started = time.perf_counter()
    result.to_json()
    csv = result.to_csv()
    nd = result.to_ndjson()
    assert time.perf_counter() - started < 3.0
    assert len(csv.splitlines()) == 1 + result.totals()["groups_returned"]
    assert len(nd.splitlines()) == 1 + result.totals()["groups_returned"]
