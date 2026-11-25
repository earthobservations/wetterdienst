# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the row options must choose, worked out the slow way in plain Python (GH-4411).

The readings are a function of the station and the day (`row_options_stub`), so a loop for each rule of the words gives
the answer without polars, for the long shape and for the wide one (a row of each day of each station, whatever the
readings: the wide shape keeps the days that are missing).
"""

from __future__ import annotations

import datetime as dt
import operator
from typing import TYPE_CHECKING, Any

from tests.ui.row_options_stub import DAYS, FIRST_DAY, oracle

if TYPE_CHECKING:
    import polars as pl

_COMPARE = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
_PARTS = {
    "year": lambda ts: ts.year,
    "month": lambda ts: ts.month,
    "day": lambda ts: ts.day,
    "hour": lambda ts: ts.hour,
}
#: what the wide shape's one series is called here: it has no parameter column
WIDE = "wide"

#: cases of the long shape (what the words choose) and of the wide one (the calendar alone: it has no `value`)
LONG_CASES: list[dict[str, Any]] = [
    {"filter": "value<=-9"},
    {"filter": "value>=-5,value<=-4.5"},
    {"filter": "month=12|1|2,year!=2019", "sort": "value"},
    {"filter": "month=12,month=1"},
    {"filter": "value!=1.0"},
    {"sort": "-value"},
    {"sort": "value", "first": 1},
    {"sort": "-value", "first": 3},
    {"sort": "value", "first": 1, "by": "station_id,year"},
    {"sort": "value", "first": 1, "by": "year"},
    {"sort": "-value", "first": 2, "by": "none"},
    {"filter": "month=12,day=24", "sort": "-value", "first": 1, "by": "none"},
    {"filter": "value<0", "sort": "month,day", "first": 1, "by": "none"},
    {"sort": "-timestamp", "first": 1},
    {"sort": "month,-value", "first": 2, "by": "station_id,month"},
    {"filter": "value>100", "sort": "value", "first": 1},
    {"max_rows": 3},
    {"filter": "value<=-9", "max_rows": 7},
    {"sort": "value", "first": 1, "max_rows": 5},
    {"sort": "-value", "first": 2, "by": "year", "max_rows": 4},
    {"sort": "-value", "max_rows": 10},
]
WIDE_CASES: list[dict[str, Any]] = [
    {"filter": "month=2"},
    {"filter": "year=2019,month=12|1", "max_rows": 7},
    {"sort": "-day", "first": 1},
    {"sort": "month,-day", "first": 2, "by": "year"},
    {"sort": "-timestamp", "first": 1, "by": "none", "max_rows": 2},
    {"max_rows": 5},
    {"max_rows": 500},
    {"sort": "day", "max_rows": 9},
    {"filter": "day=1", "sort": "-year", "first": 1, "by": "month", "max_rows": 6},
    {"filter": "day>=30", "max_rows": 4},
]


def station_ids(count: int) -> list[str]:
    """Give the ids the stub serves for `count` stations."""
    return [f"{number:05d}" for number in range(1, count + 1)]


def _rows(parameters: list[str], stations: list[str], *, wide: bool) -> list[dict[str, Any]]:
    rows = []
    for station in stations:
        if wide:
            rows.extend(
                {
                    "station_id": station,
                    "parameter": WIDE,
                    "timestamp": FIRST_DAY + dt.timedelta(days=day),
                    "value": None,
                }
                for day in range(DAYS)
            )
            continue
        # the answer's own order: by station, by parameter name, by time
        for name in sorted(parameter.rsplit("/", 1)[1] for parameter in parameters):
            rows.extend(
                {"station_id": station, "parameter": name, "timestamp": ts, "value": value}
                for ts, value in oracle(station, name)
            )
    return rows


def expected(  # noqa: C901
    parameters: list[str],
    *,
    filter_: list[tuple[str, str, tuple[float, ...]]] = (),
    sort: list[tuple[str, bool]] = (),
    first: int | None = None,
    by: list[str] | None = None,
    max_rows: int | None = None,
    stations: int = 3,
    wide: bool = False,
) -> list[tuple[str, str, dt.datetime, float | None]]:
    """Work out the rows of the answer the slow way: a loop for each rule of the words."""

    def column(row: dict[str, Any], name: str) -> Any:  # noqa: ANN401
        return row[name] if name in ("value", "timestamp", "station_id") else _PARTS[name](row["timestamp"])

    def meets(row: dict[str, Any]) -> bool:
        for name, op, numbers in filter_:
            value = column(row, name)
            if op == "=":
                ok = any(value == n for n in numbers)
            elif op == "!=":
                ok = all(value != n for n in numbers)
            else:
                ok = _COMPARE[op](value, numbers[0])
            if not ok:
                return False
        return True

    rows = [row for row in _rows(parameters, station_ids(stations), wide=wide) if meets(row)]
    group_by = ["station_id"] if by is None else by
    if first is not None:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows:
            if all(column(row, name) is not None for name, _ in sort):
                groups.setdefault((row["parameter"], *(column(row, name) for name in group_by)), []).append(row)
        kept = []
        for members in groups.values():
            ordered = members
            for name, descending in reversed(sort):
                ordered = sorted(ordered, key=lambda r, n=name: column(r, n), reverse=descending)
            # a row is kept when fewer than `first` rows of its group sort strictly before it: the position of the
            # first row of its run of equal keys
            run_start = 0
            for index, row in enumerate(ordered):
                if index and any(column(row, name) != column(ordered[index - 1], name) for name, _ in sort):
                    run_start = index
                if run_start < first:
                    kept.append(row)
        rows = kept
    if sort:
        for name, descending in reversed([*sort, ("station_id", False), ("timestamp", False)]):
            rows = sorted(rows, key=lambda r, n=name: column(r, n), reverse=descending)
        rows = sorted(rows, key=lambda r: r["parameter"])
    if max_rows is not None:
        rows = rows[:max_rows]
    return [(r["station_id"], r["parameter"], r["timestamp"], r["value"]) for r in rows]


def same(got: list[Any], want: list[Any]) -> None:
    """Assert two lists of rows are equal, naming the first row that differs (a diff of thousands of rows is slow)."""
    assert len(got) == len(want), (len(got), len(want))
    for index, (left, right) in enumerate(zip(got, want, strict=True)):
        assert left == right, (index, left, right)


def got(frame: pl.DataFrame) -> list[tuple[str, str, dt.datetime, float | None]]:
    """Read the rows of a frame the way `expected` has them: a wide row has the one series and no value."""
    if "parameter" not in frame.columns:
        return [(r["station_id"], WIDE, r["timestamp"], None) for r in frame.iter_rows(named=True)]
    return [(r["station_id"], r["parameter"], r["timestamp"], r["value"]) for r in frame.iter_rows(named=True)]


def got_items(items: list[dict[str, Any]]) -> list[tuple[str, str, dt.datetime, float | None]]:
    """Read the rows of an answer's `values`, or the lines of a stream, the way `expected` has them."""
    out = []
    for item in items:
        stamp = dt.datetime.fromisoformat(item["timestamp"])
        if "parameter" in item:
            value = item["value"]
            out.append((item["station_id"], item["parameter"], stamp, None if value in (None, "") else float(value)))
        else:
            out.append((item["station_id"], WIDE, stamp, None))
    return out
