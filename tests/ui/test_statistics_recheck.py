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
    assert (
        "The answer lists the first 20 of 21 series that have a group, in the order the stations were read" in message
    )
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


# ----------------------------------------------------------------------------------------------------------------
# S2, S4, S5: what the notes of a tool say
# ----------------------------------------------------------------------------------------------------------------


def test_the_note_of_per_station_does_not_claim_the_best_series(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without `per=none` the 20 series are the first read, and the note says so and where the ranking is."""
    serve(monkeypatch, count=50)
    answer = _tool(_PLAIN)
    message = _warning(answer, "answer-truncated") or ""
    assert "the first 20 of 50 series that have a group, in the order the stations were read" in message
    assert "`per=none` ranks across the stations" in message
    assert "best" not in message
    assert [s["station_id"] for s in answer["series"]] == [f"{n:05d}" for n in range(1, 21)]
    ranked = _tool({**_RANKED, "parameters": TMIN})
    assert "the series with the best groups" in (_warning(ranked, "answer-truncated") or "")


def test_the_incomplete_warning_of_a_cut_answer_counts_the_groups_it_still_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the cut the warning says how many of the incomplete groups are still in the answer."""
    serve(monkeypatch, count=6)
    options = {"aggregate": "count,mean", "by": "year,month,day"}
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 20_000)
    answer = _tool(options)
    shown = sum(len(s["groups"]) for s in answer["series"])
    whole_incomplete = answer["metadata"]["search"]["totals"]["groups_incomplete"]
    held = sum(1 for s in answer["series"] for g in s["groups"] if not g["complete"])
    assert 0 < held < whole_incomplete
    assert shown < answer["metadata"]["search"]["totals"]["groups"]
    message = _warning(answer, "incomplete-groups") or ""
    assert f"{whole_incomplete:,} groups have fewer values" in message
    assert f"({held:,} of them in this answer)" in message


def test_a_having_with_no_match_does_not_say_to_name_fewer_stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Series with no group because `having` kept none: the note says no group met it, nothing about stations."""
    serve(monkeypatch, count=30)
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 6_000)
    answer = _tool({**_PLAIN, "having": "count>1000"})
    message = _warning(answer, "answer-truncated") or ""
    assert "No group of the series left out met `having`" in message
    assert "fewer stations" not in message
    assert answer["series"] == []
    assert answer["metadata"]["search"]["totals"]["series"] == 30


# ----------------------------------------------------------------------------------------------------------------
# what mutants passed
# ----------------------------------------------------------------------------------------------------------------


def test_two_parameters_are_cut_by_rank_one_after_the_other(monkeypatch: pytest.MonkeyPatch) -> None:
    """(49) `max_rows=3` over two parameters keeps rank 1 of each and rank 2 of the first, not three of the first."""
    serve(monkeypatch, count=6)
    answer = _rest(
        parameters=_TWO, aggregate="max", by="year,month", sort="-max", first=5, per="none", max_rows=3
    ).json()
    groups = [(s["parameter"], g["rank"]) for s in answer["series"] for g in s["groups"]]
    assert sorted(rank for _, rank in groups) == [1, 1, 2]
    assert len({parameter for parameter, _ in groups}) == 2
    # the one that has the second rank is the one the answer lists first
    first = _rest(parameters=_TWO, aggregate="max", by="year,month", sort="-max", first=5, per="none").json()
    order = list(dict.fromkeys(s["parameter"] for s in first["series"]))
    assert (order[0], 2) in groups


def test_the_totals_of_the_series_a_tool_leaves_out_are_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """(79) 30 series, 20 listed: `searched`, `expected` and `gaps` are the sums of all 30, as REST gives them."""
    serve(monkeypatch, count=30)
    whole = _rest(**_PLAIN).json()["metadata"]["search"]["totals"]
    tool = _tool(_PLAIN)["metadata"]["search"]["totals"]
    assert {key: tool[key] for key in ("stations_read", "searched", "expected", "gaps", "series", "groups")} == {
        key: whole[key] for key in ("stations_read", "searched", "expected", "gaps", "series", "groups")
    }
    assert tool["series"] == 30
    assert tool["groups_returned"] == 60 < whole["groups_returned"] == 90


def test_a_series_left_with_no_group_by_a_cut_is_not_in_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """(80) A cut that ends in the third series leaves the others out; the totals still count all six."""
    serve(monkeypatch, count=6)
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 20_000)
    answer = _tool({"aggregate": "count,mean", "by": "year,month,day"})
    assert 0 < len(answer["series"]) < 6
    assert all(s["groups"] for s in answer["series"])
    assert answer["metadata"]["search"]["totals"]["series"] == 6
    assert answer["metadata"]["counts"]["stations"] == len({s["station_id"] for s in answer["series"]})


@pytest.mark.parametrize(("count", "status"), [(100, 200), (101, 400)])
def test_a_hundred_series_are_answered_and_a_hundred_and_one_refused(
    monkeypatch: pytest.MonkeyPatch, count: int, status: int
) -> None:
    """(83) The limit is 100 series: exactly 100 is no excess."""
    serve(monkeypatch, count=count)
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "1000")
    response = _rest(aggregate="count", by="year")
    assert response.status_code == status, response.text[:300]
    if status == 400:
        assert response.json()["limit"] in ("series", "stations")


def test_empty_year_start_and_max_missing_are_not_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """(88) `year_start=` and `max_missing=` are what a form sends for nothing: the answer of the defaults."""
    serve(monkeypatch, count=2)
    plain = _rest(aggregate="count,mean", by="year")
    empty = _rest(aggregate="count,mean", by="year", year_start="", max_missing="")
    assert (plain.status_code, empty.status_code) == (200, 200)
    assert empty.json()["series"] == plain.json()["series"]
    assert empty.json()["metadata"]["search"]["options"] == plain.json()["metadata"]["search"]["options"]


# ----------------------------------------------------------------------------------------------------------------
# the pilot: what the tool says it cannot do, and `max_missing` kept at 0 to rank
# ----------------------------------------------------------------------------------------------------------------


def _statistics_tool() -> Any:  # noqa: ANN401
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def read() -> Any:  # noqa: ANN401
        tools = await build_mcp_server(app).list_tools()
        return next(tool for tool in tools if tool.name == "statistics")

    return asyncio.run(read())


def test_the_tool_says_what_statistics_cannot_do_and_not_to_estimate_it() -> None:
    """Runs, moving windows, percentiles and medians are not in `statistics`: the description says so, briefly."""
    description = _statistics_tool().description
    assert (
        "cannot find runs (the longest dry spell), moving windows (the wettest 3 days), percentiles or medians"
        in description
    )
    assert "do not estimate" in description
    assert len(description) < 1_300


def test_the_instructions_say_it_too_within_the_cap() -> None:
    """One sentence of the server's instructions, which stay under 7,800 characters."""
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import INSTRUCTIONS  # noqa: PLC0415

    assert (
        "`statistics` has no runs (dry spells), moving windows, percentiles or medians: say so, do not estimate."
        in INSTRUCTIONS
    )
    assert len(INSTRUCTIONS) < 7_800


def test_max_missing_says_to_keep_it_0_to_rank_on_every_surface() -> None:
    """The option's text, in the tool's schema and the REST document: keep it 0 to rank."""
    schema = _statistics_tool().parameters["properties"]["max_missing"]
    text = schema["description"]
    assert "Keep it 0 to rank; raise it only for a gap you accept" in text
    assert "gaps-allowed" in text
    document = TestClient(app).get("/openapi.json").json()
    route = next(p for p in document["paths"].values() if "statistics" in p.get("get", {}).get("operationId", ""))
    option = next(q for q in route["get"]["parameters"] if q["name"] == "max_missing")
    assert option["description"] == text


def test_a_group_with_gaps_is_warned_of_on_rest_and_in_the_tool_and_not_at_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`max_missing=400` lets every incomplete year of the stub in: REST and the tool say so; the default does not."""
    serve(monkeypatch, count=3)
    options = {"aggregate": "mean", "by": "year", "sort": "-mean"}
    quiet = _rest(**options).json()
    assert _warning(quiet, "gaps-allowed") is None
    answer = _rest(**options, max_missing=400).json()
    message = _warning(answer, "gaps-allowed") or ""
    lacking = sum(
        g["expected"] - g["searched"] for s in answer["series"] for g in s["groups"] if g["expected"] > g["searched"]
    )
    assert message.startswith("9 groups lack up to ")
    assert f"({lacking:,} in all) and are ranked because `max_missing` is 400" in message
    assert _warning(_tool({**options, "max_missing": 400}), "gaps-allowed") == message
    assert _warning(_tool(options), "gaps-allowed") is None


def test_the_warning_of_a_cut_tool_answer_counts_the_groups_it_still_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cut to the budget, the answer's `gaps-allowed` counts the groups left in it that lack values and have some."""
    serve(monkeypatch, count=6)
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 20_000)
    answer = _tool({"aggregate": "mean", "by": "year,month", "max_missing": 400})
    held = [
        g["expected"] - g["searched"]
        for s in answer["series"]
        for g in s["groups"]
        if g["searched"] and g["expected"] > g["searched"]
    ]
    message = _warning(answer, "gaps-allowed") or ""
    assert held
    assert message.startswith(f"{len(held):,} groups lack up to {max(held):,} values ({sum(held):,} in all)")
    assert sum(len(s["groups"]) for s in answer["series"]) < answer["metadata"]["search"]["totals"]["groups"]


def test_the_warning_is_dropped_from_a_cut_that_holds_no_such_group(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the first groups of the cut are kept: where none lacks a value the warning is not told."""
    serve(monkeypatch, count=6)
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 6_000)
    answer = _tool({"aggregate": "mean", "by": "year,month,day", "max_missing": 400, "having": "searched=1"})
    assert all(g["expected"] == g["searched"] for s in answer["series"] for g in s["groups"])
    assert _warning(answer, "gaps-allowed") is None
    assert _warning(answer, "answer-truncated") is not None
