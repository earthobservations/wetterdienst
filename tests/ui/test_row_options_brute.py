# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every way of asking for the rows is held to the slow working-out of them, on every surface, in both shapes (GH-4411).

One table of options (`row_options_oracle`), the stub network of `row_options_stub`, and the same rows from the
reader (`all`, `query`), the result (`selected_rows`) and the REST API (json, csv, ndjson), long and wide, with the held
rows chosen again at one cell, at two, at five and at twenty (`_COMPACT_CELLS`), over one to six stations.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.ui.row_options_oracle import LONG_CASES, WIDE_CASES, expected, got, got_items, same
from tests.ui.row_options_stub import TMAX, TMIN, serve
from wetterdienst.model.row_selection import parse_row_selection
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.restapi import app

_BASE = {"provider": "dwd", "network": "observation", "timestamp": "2018/2020", "all": "true"}
_TWO = [TMIN, TMAX]


def _want(parameters: list[str], rows: dict[str, Any], stations: int, *, wide: bool) -> list[Any]:
    selection = parse_row_selection(**rows)
    assert selection is not None
    return expected(
        parameters,
        filter_=[(c.column, c.operator, c.values) for c in selection.conditions],
        sort=[(k.column, k.descending) for k in selection.sort],
        first=selection.first,
        by=None if selection.by is None else list(selection.by),
        max_rows=selection.max_rows,
        stations=stations,
        wide=wide,
    )


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
@pytest.mark.parametrize("parameters", [[TMIN], _TWO], ids=["one parameter", "two parameters"])
def test_the_reader_the_result_and_every_format_choose_what_the_oracle_does(
    monkeypatch: pytest.MonkeyPatch, parameters: list[str], *, wide: bool
) -> None:
    """The reader, the result's method and the REST formats give the rows the slow working-out gives, case by case."""
    serve(monkeypatch, 3)
    request = _reader(parameters, wide=wide)
    whole = request.all().values().all()
    for rows in WIDE_CASES if wide else LONG_CASES:
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
        assert [r["station_id"] for r in _csv_rows(csv_text)] == [w[0] for w in want], label
        # the report counts the frame's rows in the totals, wide or long, and the cap says what it cut
        totals = _rest(parameters, rows, "json", wide=wide).json()["metadata"]["search"]["totals"]
        assert totals["returned"] == len(want), label
        assert totals["matched"] >= len(want), label


@pytest.mark.parametrize("wide", [False, True], ids=["long", "wide"])
def test_query_gives_the_stations_their_own_choice_where_the_groups_stay_in_a_station(
    monkeypatch: pytest.MonkeyPatch, *, wide: bool
) -> None:
    """`query` yields a station's rows chosen as `all` chooses them, for every case that stays in the station."""
    serve(monkeypatch, 3)
    request = _reader([TMIN], wide=wide)
    for rows in WIDE_CASES if wide else LONG_CASES:
        selection = parse_row_selection(**rows)
        assert selection is not None
        if not selection.per_station or selection.max_rows is not None:
            continue  # the cap of the whole, and groups over stations, are `all`'s
        pieces = [r.df for r in request.all().values().query(**rows)]
        mine = [row for piece in pieces for row in got(piece)]
        same(sorted(mine), sorted(_want([TMIN], rows, 3, wide=wide)))


@pytest.mark.parametrize("compact", [1, 2, 5, 20])
@pytest.mark.parametrize("stations", [1, 2, 3, 6])
@pytest.mark.parametrize("wide", [False, True], ids=["long", "wide"])
def test_the_cap_and_the_groups_over_stations_hold_for_every_count_of_stations_and_every_bound(
    monkeypatch: pytest.MonkeyPatch, stations: int, compact: int, *, wide: bool
) -> None:
    """One to six stations, the held rows chosen again at 1, 2, 5 and 20 cells: the same rows as the working-out."""
    serve(monkeypatch, stations)
    monkeypatch.setattr(TimeseriesValues, "_COMPACT_CELLS", compact)
    request = _reader(_TWO, wide=wide)
    for rows in WIDE_CASES if wide else LONG_CASES:
        want = _want(_TWO, rows, stations, wide=wide)
        same(got(request.all().values().all(**rows).df), want)
    # the cases that were the bug: a cap without a sort, over a wide frame, where the frames are counted in cells
    for cap in (1, 2, 5, 7, 500, 5000):
        rows = {"max_rows": cap}
        want = _want(_TWO, rows, stations, wide=wide)
        same(got(request.all().values().all(**rows).df), want)
        assert len(want) == min(cap, stations * 1096) if wide else len(want) <= cap


def test_the_report_of_a_wide_stream_counts_the_frame_and_knows_the_stations_it_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wide stream's `end` line has the rows of the frame, the same warning as the body, and `stations_read`."""
    serve(monkeypatch, 3)
    for rows in ({"filter": "day=1", "max_rows": 5}, {"max_rows": 5}):
        lines = [json.loads(x) for x in _rest(_TWO, rows, "ndjson", wide=True).text.splitlines()]
        end = lines[-1]["end"]
        totals = end["search"]["totals"]
        body = _rest(_TWO, rows, "json", wide=True).json()["metadata"]
        assert totals == body["search"]["totals"]
        assert totals["returned"] == 5
        assert totals["stations_read"] == 3
        warning = next(w["message"] for w in end["warnings"] if w["code"] == "rows-capped")
        assert warning == next(w["message"] for w in body["warnings"] if w["code"] == "rows-capped")
        assert warning.startswith(f"5 of {totals['matched']:,} matched rows are returned")
    nothing = [
        json.loads(x)
        for x in _rest(_TWO, {"filter": "month=2,month=3", "max_rows": 3}, "ndjson", wide=True).text.splitlines()
    ]
    assert nothing[-1]["end"]["search"]["totals"]["stations_read"] == 3
    assert nothing[-1]["end"]["search"]["totals"]["matched"] == 0


def test_a_cut_stream_and_the_station_names_are_read_once_for_the_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    """The names of the stations are read once for a walk, not for each station."""
    serve(monkeypatch, 6)
    calls = []
    from wetterdienst.model import values as module  # noqa: PLC0415

    original = module.station_names
    monkeypatch.setattr(module, "station_names", lambda frame: (calls.append(1), original(frame))[1])
    _reader([TMIN], wide=False).all().values().all(sort="value", first=1)
    assert len(calls) == 1
