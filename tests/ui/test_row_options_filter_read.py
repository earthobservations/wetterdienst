# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A `filter` alone reads up to the stream limit and is held to `rows`, as a `first` is (GH-4436).

The stub of `row_options_stub` is three stations of 1,096 days, so that a request reads 3,288 rows (estimated) and about
3,036 readings exist. The limits are set small around these numbers to hold the boundaries: the read to the stream
limit, what is held to `rows`, what stops the walk ("so far"), and what a `sort` alone still is.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.ui.row_options_stub import DAYS, STATIONS, TMIN, oracle, serve
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.ui.limits import Limits, check_chosen_rows
from wetterdienst.ui.problems import ProblemError
from wetterdienst.ui.restapi import app

_BASE = {"provider": "dwd", "network": "observation", "parameters": TMIN, "timestamp": "2018/2020", "all": "true"}
_NAME = "temperature_air_min_2m"
#: the readings that a request of the stub reads, which the limit of a stream is held to
_READ = len(STATIONS) * DAYS


@pytest.fixture(autouse=True)
def _stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the stub network on every test of this module."""
    serve(monkeypatch)


def _rest(**params: Any) -> Any:  # noqa: ANN401
    return TestClient(app).get("/api/values", params={**_BASE, **params})


def _matching(limit: float) -> list[tuple[str, str, float]]:
    """Give the readings at or below `limit`, as the oracle has them: by station, by day."""
    return [
        (station, ts.date().isoformat(), value)
        for station in STATIONS
        for ts, value in oracle(station, _NAME)
        if value <= limit
    ]


def _of(values: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    return [(v["station_id"], v["date"][:10] if "date" in v else v["timestamp"][:10], v["value"]) for v in values]


def _rows(response: Any) -> list[tuple[str, str, float]]:  # noqa: ANN401
    return _of(response.json()["values"])


def _limits(monkeypatch: pytest.MonkeyPatch, rows: int, stream: int) -> None:
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", str(rows))
    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", str(stream))


def test_a_filter_alone_reads_what_the_rows_limit_refuses_and_sends_what_matched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3,288 rows are read under a `rows` of 1,000: the request that was refused at its start is answered."""
    _limits(monkeypatch, 1000, 10_000)
    assert _rest().status_code == 400  # no option: held to `rows` as it was
    response = _rest(filter="value<=-9")
    assert response.status_code == 200, response.text
    assert _rows(response) == _matching(-9)
    search = response.json()["metadata"]["search"]
    # all three series were read, whole: the readings searched are all of them
    assert search["totals"]["searched"] == sum(len(oracle(s, _NAME)) for s in STATIONS)
    assert search["totals"]["matched"] == len(_matching(-9))


def test_the_rows_that_match_are_held_to_rows_to_the_row_and_refused_so_far_not_at_the_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `rows` at the number that matched the answer is sent, one less and it is refused, and it says so far."""
    matched = len(_matching(-9))
    _limits(monkeypatch, matched, 10_000)
    assert _rest(filter="value<=-9").status_code == 200
    _limits(monkeypatch, matched - 1, 10_000)
    refused = _rest(filter="value<=-9")
    assert refused.status_code == 400, refused.text
    body = refused.json()
    assert body["limit"] == "rows"
    assert body["requested"] == matched
    assert f"chose {matched:,} rows so far" in body["detail"]


def test_a_filter_that_matches_everything_is_stopped_at_the_station_that_crosses_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first station has 1,012 readings: with `rows` at 1,000 the walk stops there, and the others are not read."""
    _limits(monkeypatch, 1000, 10_000)
    read: list[str] = []
    original = TimeseriesValues._hold  # noqa: SLF001

    def spy(self: TimeseriesValues, selection: Any, rows: int, cells: int, data: Any) -> Any:  # noqa: ANN401
        read.append(str(data[-1]["station_id"][0]))
        return original(self, selection, rows, cells, data)

    monkeypatch.setattr(TimeseriesValues, "_hold", spy)
    refused = _rest(filter="value<=20")
    assert refused.status_code == 400, refused.text
    body = refused.json()
    assert body["requested"] == len(oracle("00001", _NAME)) < _READ
    assert "so far" in body["detail"]
    assert read == ["00001"]
    # what helps is told, and a `first` is not among it: the request has none, and `first` needs a `sort`
    assert "Tighten the `filter`" in body["detail"]
    assert "`max_rows`" in body["detail"]
    assert "smaller `first`" not in body["detail"]


def test_the_estimate_of_the_read_is_held_to_the_stream_limit_to_the_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """The estimate (3,288 rows) is checked against the limit of a stream, and the text says it is a read."""
    _limits(monkeypatch, 1000, _READ)
    assert _rest(filter="value<=-9").status_code == 200
    _limits(monkeypatch, 1000, _READ - 1)
    refused = _rest(filter="value<=-9")
    assert refused.status_code == 400, refused.text
    body = refused.json()
    assert body["limit"] == "stream_rows"
    assert body["requested"] == _READ
    assert f"would read about {_READ:,} rows, more than the {_READ - 1:,}" in body["detail"]
    assert "shorter `timestamp` window" in body["detail"]
    assert "stream" not in body["detail"].split("more than")[1].split(". ")[1]  # the advice is not to stream


def test_a_filter_is_refused_for_its_stations_as_any_request_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """The limit of stations is the same one: a read to the stream limit does not read more stations."""
    _limits(monkeypatch, 1000, 10_000)
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "2")
    refused = _rest(filter="value<=-9")
    assert refused.status_code == 400
    assert refused.json()["limit"] == "stations"


def test_a_limit_that_is_off_is_off_for_a_filter_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """0 switches a limit off: the stream limit for the read, the rows limit for what is held."""
    _limits(monkeypatch, 1000, 0)
    assert _rest(filter="value<=-9").status_code == 200
    _limits(monkeypatch, 0, 10_000)
    assert _rest(filter="value<=20").status_code == 200
    # a read is held to the larger of the two, so `rows` off is no limit on it, as for a body without a filter
    _limits(monkeypatch, 0, _READ - 1)
    assert _rest(filter="value<=20").status_code == 200
    assert _rest().status_code == 200


def test_a_sort_alone_is_held_to_rows_for_what_it_reads_and_a_filter_with_it_reads_the_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `sort` holds every row it reads, so it keeps today's limit; with a `filter` the rows matched are sorted."""
    _limits(monkeypatch, 1000, 10_000)
    refused = _rest(sort="-value")
    assert refused.status_code == 400
    assert refused.json()["limit"] == "rows"
    assert "add `first` or a `filter`" in refused.json()["detail"]
    ordered = _rest(sort="-value", filter="value<=-9")
    assert ordered.status_code == 200, ordered.text
    expected = sorted(_matching(-9), key=lambda row: (-row[2], row[0], row[1]))
    assert _rows(ordered) == expected
    # held to `rows` after the filter: the same boundary as for a filter alone
    _limits(monkeypatch, len(expected) - 1, 10_000)
    over = _rest(sort="-value", filter="value<=-9")
    assert over.status_code == 400
    assert "so far" in over.json()["detail"]
    assert "Tighten the `filter`" in over.json()["detail"]


def test_a_sort_with_a_first_keeps_the_advice_it_had(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request with a `first` is told to make it smaller, as it was."""
    _limits(monkeypatch, 500, 10_000)
    refused = _rest(sort="value", first=1000, by="station_id,month", filter="value<=20")
    assert refused.status_code == 400, refused.text
    assert "smaller `first`" in refused.json()["detail"]


@pytest.mark.parametrize("fmt", ["csv", "ndjson"])
def test_a_filter_alone_in_a_stream_reads_up_to_the_stream_limit_and_is_not_held(
    monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """A stream sends rows as they are read: what matches is not held to `rows`, the read to the stream limit."""
    _limits(monkeypatch, 1000, 10_000)
    everything = _rest(filter="value<=20", format=fmt)
    assert everything.status_code == 200, everything.text
    count = sum(len(oracle(s, _NAME)) for s in STATIONS)
    lines = everything.text.splitlines()
    assert len(lines) == (count + 2 if fmt == "ndjson" else count + 1)
    # and the read is held to the stream limit to the row
    _limits(monkeypatch, 1000, _READ - 1)
    refused = _rest(filter="value<=20", format=fmt)
    assert refused.status_code == 400
    assert refused.json()["limit"] == "stream_rows"
    assert "would read about" in refused.json()["detail"]


def test_a_stream_that_sorts_a_filter_holds_what_matched_and_a_csv_is_the_same_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`sort` with a `filter` holds the rows before the first line, so they are held to `rows` in a stream too."""
    _limits(monkeypatch, 1000, 10_000)
    expected = sorted(_matching(-9), key=lambda row: (row[2], row[0], row[1]))
    lines = [json.loads(line) for line in _rest(sort="value", filter="value<=-9", format="ndjson").text.splitlines()]
    assert _of(lines[1:-1]) == expected
    csv = _rest(sort="value", filter="value<=-9", format="csv")
    assert csv.status_code == 200
    assert len(csv.text.splitlines()) == len(expected) + 1
    # more than `rows` matched is refused before a line goes out
    for fmt in ("ndjson", "csv"):
        refused = _rest(sort="value", filter="value<=20", format=fmt)
        assert refused.status_code == 400, refused.text
        assert "so far" in refused.json()["detail"]


def test_max_rows_bounds_what_is_held_and_a_filter_that_matches_everything_is_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `max_rows` the rows held are the rows of the answer, whatever matched; the count is of all."""
    _limits(monkeypatch, 1000, 10_000)
    held: list[int] = []
    original = TimeseriesValues._hold  # noqa: SLF001

    def spy(self: TimeseriesValues, selection: Any, rows: int, cells: int, data: Any) -> Any:  # noqa: ANN401
        result = original(self, selection, rows, cells, data)
        held.append(result[0])
        return result

    monkeypatch.setattr(TimeseriesValues, "_hold", spy)
    capped = _rest(filter="value<=20", max_rows=5)
    assert capped.status_code == 200, capped.text
    answer = capped.json()
    assert len(answer["values"]) == 5
    assert answer["values"][0]["station_id"] == "00001"  # the first rows as they are read
    assert answer["metadata"]["search"]["totals"]["matched"] == sum(len(oracle(s, _NAME)) for s in STATIONS)
    assert max(held) <= 5
    held.clear()
    top = _rest(filter="value<=20", sort="-value", max_rows=5)
    assert top.status_code == 200, top.text
    best = sorted(_matching(20), key=lambda row: (-row[2], row[0], row[1]))[:5]
    assert _rows(top) == best
    assert max(held) <= 10  # cut to `max_rows` whenever twice that
    # the ones without a filter do not read more than they did
    assert _rest(sort="-value", max_rows=5).status_code == 400
    assert _rest(max_rows=5).status_code == 400


def test_a_filter_with_a_first_is_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `filter` with `first` and `sort` reads to the stream limit and holds its rows to `rows`, unchanged."""
    _limits(monkeypatch, 1000, 10_000)
    response = _rest(filter="value<=20", sort="value", first=1)
    assert response.status_code == 200, response.text
    assert len(response.json()["values"]) >= 3


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


def test_a_tool_reads_the_record_for_a_filter_and_is_told_in_its_words_when_it_is_too_much(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tool is answered where it was refused, and the refusals that remain name what works through a tool."""
    _limits(monkeypatch, 1000, 10_000)
    answered = _tool({"filter": "value<=-9"})
    assert not answered.is_error, answered.content
    answer = answered.structured_content
    answer = answer.get("result", answer)
    assert _of(answer["values"]) == _matching(-9)
    # too many matched: the text names a `filter` and `max_rows`, not a stream
    over = _tool({"filter": "value<=20"})
    assert over.is_error
    message = str(over.content)
    assert "so far" in message
    assert "Tighten the `filter`" in message
    assert "ndjson" not in message
    # a read over the stream limit: shorter window, fewer parameters or stations
    _limits(monkeypatch, 1000, 1000)
    big = _tool({"filter": "value<=-9"})
    assert big.is_error
    assert "would read about" in str(big.content)
    assert "ndjson" not in str(big.content)
    # a `sort` alone is told to add `first` or a `filter`
    _limits(monkeypatch, 1000, 10_000)
    sort = _tool({"sort": "value"})
    assert sort.is_error
    assert "add `first` or a `filter`" in str(sort.content)


def test_a_tool_answer_of_a_filter_is_still_cut_to_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cut of the answer is the same: the first rows in the answer's order, and how many matched."""
    _limits(monkeypatch, 5000, 10_000)
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 9000)
    result = _tool({"filter": "value<=20"})
    assert not result.is_error, result.content
    answer = result.structured_content
    answer = answer.get("result", answer)
    warning = next(w for w in answer["metadata"]["warnings"] if w["code"] == "answer-truncated")
    total = answer["metadata"]["search"]["totals"]["matched"]
    assert f"of {total:,} matched rows" in warning["message"]
    assert len(answer["values"]) < total


def test_the_command_line_has_no_limit_and_a_filter_alone_is_as_it_was() -> None:
    """The library and the command line hold nothing: a filter alone is applied per station, and nothing refuses it."""
    from click.testing import CliRunner  # noqa: PLC0415

    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    result = CliRunner().invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            f"--parameters={TMIN}",
            "--timestamp=2018/2020",
            "--all",
            "--filter=value<=20",
            "--format=csv",
        ],
    )
    assert result.exit_code == 0, result.output
    assert re.search(r"00001", result.output)


def test_a_stream_limit_below_rows_does_not_refuse_what_the_plain_request_is_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read is held to the larger of `rows` and `stream_rows`: `first` shares this line, `statistics` does not."""
    _limits(monkeypatch, 5000, 1000)
    assert _rest().status_code == 200  # 3,288 rows of a body under `rows`
    assert _rest(filter="value<=-9").status_code == 200
    assert _rest(sort="value", first=1).status_code == 200
    _limits(monkeypatch, 3000, 1000)
    refused = _rest(filter="value<=-9")
    assert refused.status_code == 400
    body = refused.json()
    assert (body["limit"], body["maximum"], body["requested"]) == ("rows", 3000, _READ)
    # `statistics` reads under `stream_rows` alone: a limit of a stream below `rows` refuses it at that limit
    _limits(monkeypatch, 5000, 1000)
    statistics = TestClient(app).get("/api/statistics", params={**_BASE, "aggregate": "count", "by": "year"})
    assert statistics.status_code == 400, statistics.text
    assert statistics.json()["limit"] == "stream_rows"
    assert statistics.json()["maximum"] == 1000
    # and where the stream limit is the larger it is the one named, to the row
    _limits(monkeypatch, 1000, _READ - 1)
    assert _rest(filter="value<=-9").json()["limit"] == "stream_rows"


def test_the_texts_of_the_read_refusal_are_the_same_for_rest_and_a_tool_and_name_no_sort_it_has_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read is told a narrower request, whatever it has: a `filter` (or a `first`) is not told to drop a `sort`."""
    _limits(monkeypatch, 1000, 1000)
    head = f"This request would read about {_READ:,} rows, more than the 1,000 this server reads for one request."
    narrow = "Ask for a shorter `timestamp` window, fewer `parameters` or fewer stations."
    assert _rest(filter="value<=-9").json()["detail"] == f"{head} {narrow}"
    assert _rest(filter="value<=-9", sort="value").json()["detail"] == f"{head} {narrow}"
    assert _rest(sort="value", first=1).json()["detail"] == f"{head} {narrow}"
    for arguments in ({"filter": "value<=-9"}, {"filter": "value<=-9", "sort": "value"}, {"sort": "value", "first": 1}):
        result = _tool(arguments)
        assert result.is_error
        message = str(result.content)
        assert f"{head} {narrow}" in message
        assert "drop `sort`" not in message
    # a `sort` alone is the one that is told to drop it
    assert "drop `sort`" in _rest(sort="value").json()["detail"]


def test_a_max_rows_above_rows_is_asked_to_be_smaller_and_is_not_a_walk_stopped_so_far(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`max_rows` of 2,000 over a `rows` of 1,000 holds 2,000 rows, which is told at the end, not so far."""
    _limits(monkeypatch, 1000, 10_000)
    refused = _rest(filter="value<=20", max_rows=2000)
    assert refused.status_code == 400, refused.text
    detail = refused.json()["detail"]
    assert "so far" not in detail
    assert f"chose {2000:,} rows," in detail
    assert "Tighten the `filter`" in detail
    assert "smaller `max_rows`" in detail
    assert "cut the answer with `max_rows`" not in detail
    # one that is cut to `rows` is answered
    assert _rest(filter="value<=20", max_rows=1000).status_code == 200


def test_the_refusal_of_the_rows_chosen_names_a_stream_over_rest_only_and_what_the_request_has_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `filter` alone is told it can stream (REST), a tool never; a `sort` that is given is not asked for again."""
    _limits(monkeypatch, 1000, 10_000)
    stream = "Or stream it: `format=ndjson` and `format=csv` send the rows as they are read and hold none."
    alone = _rest(filter="value<=20").json()["detail"]
    assert alone.endswith(stream)
    assert "add `sort` and `first` to keep the first rows of each station" in alone
    tool = str(_tool({"filter": "value<=20"}).content)
    assert "Tighten the `filter`" in tool
    assert "stream" not in tool
    assert "ndjson" not in tool
    # with a `sort` a stream holds the rows too: nothing to say about one, and `first` only is asked for
    sorted_ = _rest(filter="value<=20", sort="value").json()["detail"]
    assert "stream" not in sorted_
    assert "add `first` to keep the first rows of each station" in sorted_
    assert "add `sort`" not in sorted_
    # the stream is not offered where the limit of a stream is no more than `rows`
    limits = Limits(max_stations=0, max_rows=1000, max_stream_rows=1000, max_groups=0, timeout=0, max_concurrent=0)
    with pytest.raises(ProblemError) as error:
        check_chosen_rows(2000, limits, first=False)
    assert "stream" not in str(error.value)


def test_a_filter_that_matches_more_than_rows_is_told_it_can_stream_where_the_stream_limit_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `stream_rows` at 0 the refusal of the rows chosen ends with the stream sentence, and a tool's does not."""
    _limits(monkeypatch, 1000, 0)
    detail = _rest(filter="value<=20").json()["detail"]
    assert "so far" in detail
    assert detail.endswith(
        "Or stream it: `format=ndjson` and `format=csv` send the rows as they are read and hold none."
    )
    assert "stream" not in str(_tool({"filter": "value<=20"}).content)
