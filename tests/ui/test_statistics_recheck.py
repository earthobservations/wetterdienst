# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The re-check of #4444 on the surfaces: the series a tool lists, its notes and totals, the block (GH-4412)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.ui.row_options_stub import GUST, TMIN, serve
from wetterdienst.ui.restapi import app

_BASE = {"provider": "dwd", "network": "observation", "parameters": TMIN, "timestamp": "2018/2020", "all": "true"}
_TWO = f"{TMIN},{GUST}"


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


def _warning(answer: dict[str, Any], code: str) -> str | None:
    return next((w["message"] for w in answer["metadata"]["warnings"] if w["code"] == code), None)


def _ids(answer: dict[str, Any]) -> list[tuple[str, str]]:
    return [(s["station_id"], s["parameter"]) for s in answer["series"]]


# ----------------------------------------------------------------------------------------------------------------
# R5: the 20 series of a tool are those with the best groups over all parameters
# ----------------------------------------------------------------------------------------------------------------

_RANKED = {"aggregate": "max", "by": "year,month", "sort": "-max", "first": 40, "per": "none"}


def test_the_tool_takes_the_twenty_series_by_rank_over_all_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two parameters of 12 stations are 24 series: 20 stay, the best by rank, and neither parameter is left whole."""
    serve(monkeypatch, count=12)
    whole = _rest(parameters=_TWO, **_RANKED).json()
    assert len(whole["series"]) > 20
    parameters = list(dict.fromkeys(s["parameter"] for s in whole["series"]))
    assert len(parameters) == 2
    # plain Python: the best rank of each series, the parameters in the order the answer lists them, then the listing
    held = [
        (min(g["rank"] for g in s["groups"]), parameters.index(s["parameter"]), n, (s["station_id"], s["parameter"]))
        for n, s in enumerate(whole["series"])
    ]
    want = {key for *_, key in sorted(held)[:20]}
    tool = _tool({"parameters": _TWO, **_RANKED})
    assert len(tool["series"]) == 20
    assert set(_ids(tool)) == want
    assert {p for _, p in _ids(tool)} == set(parameters)
    # in the order the answer lists them, which REST has
    listed = [key for key in _ids(whole) if key in want]
    assert _ids(tool) == listed


def test_a_parameter_is_not_dropped_whole_by_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first 20 series of the list would be one parameter's 12 and 8 of the other's; the cap is by rank."""
    serve(monkeypatch, count=12)
    tool = _tool({"parameters": _TWO, **_RANKED})
    counts = {p: sum(1 for _, q in _ids(tool) if q == p) for _, p in _ids(tool)}
    assert sum(counts.values()) == 20
    assert all(count >= 1 for count in counts.values())
    assert len(counts) == 2


# ----------------------------------------------------------------------------------------------------------------
# R8: what a tool says of its cut, and what its totals say
# ----------------------------------------------------------------------------------------------------------------

_PLAIN = {"aggregate": "count", "by": "year"}


def test_exactly_twenty_series_are_no_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """20 stations: all 20 series, no note; the 21st is the first that is cut, and the note says so."""
    serve(monkeypatch, count=20)
    answer = _tool(_PLAIN)
    assert len(answer["series"]) == 20
    assert _warning(answer, "answer-truncated") is None
    serve(monkeypatch, count=21)
    answer = _tool(_PLAIN)
    assert len(answer["series"]) == 20
    message = _warning(answer, "answer-truncated") or ""
    assert "The answer lists 20 of 21 series that have a group" in message
    assert "40,000" not in message


def test_the_totals_of_a_capped_tool_count_the_groups_it_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    """`groups_returned` is the groups of the 20 series; `series` and `groups` count all 30 searched."""
    serve(monkeypatch, count=30)
    answer = _tool(_PLAIN)
    totals = answer["metadata"]["search"]["totals"]
    shown = sum(len(s["groups"]) for s in answer["series"])
    assert shown == 60
    assert (totals["series"], totals["groups"], totals["groups_returned"]) == (30, 90, 60)
    assert answer["metadata"]["counts"]["rows"] == 60


def test_a_having_that_matches_nothing_is_no_series_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """30 series with no group at all say that, and not '0 of 30 series': nothing is capped, the totals count them."""
    serve(monkeypatch, count=30)
    answer = _tool({**_PLAIN, "having": "count>1000"})
    assert [s for s in answer["series"] if s["groups"]] == []
    message = _warning(answer, "answer-truncated") or ""
    assert "0 of" not in message
    assert "first 0" not in message
    totals = answer["metadata"]["search"]["totals"]
    assert (totals["series"], totals["groups_returned"]) == (30, 0)


def test_the_series_without_a_group_do_not_count_toward_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `having` that keeps the groups of 5 of 30 stations lists those 5, with no word of a cap."""
    serve(monkeypatch, count=30)
    whole = _rest(**_PLAIN, having="count>=364").json()
    holding = [s for s in whole["series"] if s["groups"]]
    answer = _tool({**_PLAIN, "having": "count>=364"})
    assert [s["station_id"] for s in answer["series"] if s["groups"]] == [s["station_id"] for s in holding][:20]
    if len(holding) <= 20:
        message = _warning(answer, "answer-truncated") or ""
        assert "of 30 series" not in message


def test_a_series_with_no_group_stays_in_a_tool_answer_that_fits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Where the answer fits and has 20 series or fewer, it is REST's answer unchanged, empty series included."""
    serve(monkeypatch, count=5)
    rest = _rest(**_PLAIN, having="count>=364").json()
    tool = _tool({**_PLAIN, "having": "count>=364"})
    assert tool["series"] == rest["series"]
    assert _warning(tool, "answer-truncated") is None


def test_a_cut_tool_answer_says_how_many_of_how_many(monkeypatch: pytest.MonkeyPatch) -> None:
    """Over the budget: the first K of M groups, the totals of all, and `groups_returned` is K."""
    serve(monkeypatch, count=6)
    options = {"aggregate": "count,mean", "by": "year,month,day"}
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 40_000)
    whole = _rest(**options).json()
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 20_000)
    answer = _tool(options)
    shown = sum(len(s["groups"]) for s in answer["series"])
    total = sum(len(s["groups"]) for s in whole["series"])
    assert 0 < shown < total
    assert f"the first {shown:,} of {total:,} groups" in (_warning(answer, "answer-truncated") or "")
    totals = answer["metadata"]["search"]["totals"]
    assert totals["groups_returned"] == shown == answer["metadata"]["counts"]["rows"]
    assert totals["groups"] == whole["metadata"]["search"]["totals"]["groups"]


# ----------------------------------------------------------------------------------------------------------------
# the block: the stations of `per=none`, the header of a CSV, the rows cap
# ----------------------------------------------------------------------------------------------------------------


def test_the_stations_of_the_request_are_those_searched_under_per_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """`first=1` over 12 stations lists one series, but 12 stations were searched: `request.stations` says 12."""
    serve(monkeypatch, count=12)
    answer = _rest(aggregate="max", by="year", sort="-max", first=1, per="none").json()
    assert len(answer["series"]) == 1
    stations = answer["metadata"]["request"]["stations"]
    assert stations["count"] == 12
    assert len(stations["ids"]) == 12
    assert answer["metadata"]["counts"]["stations"] == 1
    assert answer["metadata"]["search"]["totals"]["series"] == 12


def test_a_csv_answer_carries_the_groups_matched_in_a_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CSV has no block: the groups matched travel as `X-Wetterdienst-Groups-Matched`, with the values searched."""
    serve(monkeypatch, count=3)
    response = _rest(aggregate="count", by="year", having="count>=364", format="csv")
    assert response.status_code == 200
    json = _rest(aggregate="count", by="year", having="count>=364").json()
    matched = json["metadata"]["search"]["totals"]["groups_matched"]
    assert response.headers["X-Wetterdienst-Groups-Matched"] == str(matched)
    assert response.headers["X-Wetterdienst-Values-Searched"] == str(json["metadata"]["search"]["totals"]["searched"])
    assert matched < json["metadata"]["search"]["totals"]["groups"]


@pytest.mark.parametrize(("cap", "capped"), [(10, False), (9, False), (8, True), (1, True)])
def test_rows_capped_is_told_only_when_groups_are_cut(monkeypatch: pytest.MonkeyPatch, cap: int, capped: bool) -> None:  # noqa: FBT001
    """3 stations x 3 years are 9 groups: `max_rows=9` cuts nothing, and says nothing."""
    serve(monkeypatch, count=3)
    answer = _rest(aggregate="count", by="year", max_rows=cap).json()
    shown = sum(len(s["groups"]) for s in answer["series"])
    assert shown == min(cap, 9)
    assert (_warning(answer, "rows-capped") is not None) is capped


def test_complete_is_a_boolean_in_every_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """`complete` is true or false in the JSON and a column of true and false in the CSV, never 1 and 0."""
    serve(monkeypatch, count=2)
    answer = _rest(aggregate="count,mean", by="year").json()
    flags = [g["complete"] for s in answer["series"] for g in s["groups"]]
    assert flags
    assert all(isinstance(flag, bool) for flag in flags)
    csv = _rest(aggregate="count,mean", by="year", format="csv").text.splitlines()
    header = csv[0].split(",")
    column = header.index("complete")
    assert {line.split(",")[column] for line in csv[1:]} <= {"true", "false"}
    assert len(csv) == 1 + len(flags)
