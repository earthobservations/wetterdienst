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


# --- parameter names as columns (GH-4419) ---------------------------------------------------------------------------
# A name stands for the parameter's value at the timestamp of a row, and a row is a timestamp of a station, so two
# parameters of one station meet at one time. The same slow way: the readings of a day, side by side, in a dict.

#: the parameters of the stub: the two temperatures and the gust, by the names the answer gives them
T_MIN, T_MAX, GUST_MAX = "temperature_air_min_2m", "temperature_air_max_2m", "wind_gust_max"
_DATASET = "climate_summary"

#: cases of parameter names, over the three parameters of the stub; every name used is among them. Gusts reach 15 and
#: the minimum -10 to 20, so each condition holds on a share of the days
NAME_CASES: list[dict[str, Any]] = [
    {"filter": f"{T_MIN}<0,{GUST_MAX}>=10"},
    {"filter": f"{T_MIN}<0,{GUST_MAX}>=10,month=12|1|2"},
    {"filter": f"{GUST_MAX}>=14"},
    {"filter": f"{GUST_MAX}!=3.5"},
    {"filter": f"{GUST_MAX}=2.5|3|3.5,{T_MAX}>0"},
    {"filter": f"{T_MIN}<-100"},
    {"filter": f"{_DATASET}_{GUST_MAX}>=10,{_DATASET}_{T_MIN}<0"},
    {"filter": f"{T_MIN.upper()}<0,Month=12"},
    {"filter": f"{T_MIN}>=-5,{T_MIN}<=-4.5,{GUST_MAX}>=0"},
    {"sort": T_MIN, "first": 10},
    {"sort": f"-{GUST_MAX},{T_MIN}", "first": 3, "by": "station_id,year"},
    {"sort": T_MIN, "first": 5, "by": "none"},
    {"sort": f"-{GUST_MAX}", "first": 1},
    {"sort": f"-{GUST_MAX}", "first": 2, "by": "year"},
    {"filter": f"{T_MAX}>=19", "sort": "-timestamp", "first": 3},
    {"filter": f"{T_MIN}<-5", "sort": f"-{GUST_MAX}", "first": 2, "by": "year"},
    {"filter": f"{T_MIN}<0", "sort": "month,day", "first": 1, "by": "none"},
    {"filter": f"{T_MIN}<0", "sort": f"{T_MAX}", "first": 2, "by": "station_id,month"},
    {"sort": f"-{T_MIN}"},
    {"sort": f"{GUST_MAX},-timestamp"},
    {"sort": f"-{GUST_MAX},{T_MIN}"},
    {"filter": f"{T_MIN}<0,{GUST_MAX}>=10", "max_rows": 7},
    {"sort": T_MIN, "first": 10, "max_rows": 12},
    {"filter": f"{GUST_MAX}>=10", "sort": f"-{T_MIN}", "max_rows": 25},
    {"max_rows": 4, "filter": f"{T_MAX}>-100"},
]


def _canonical(name: str) -> str:
    """Give the name of a parameter as the oracle holds it: lower case, without the dataset it was written after."""
    return name.lower().removeprefix(f"{_DATASET}_")


def expected_names(  # noqa: C901
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
    """Work out the rows of an answer to a selection with parameter names, the slow way: a dict of readings a day."""
    shorts = sorted(parameter.rsplit("/", 1)[1] for parameter in parameters)

    def column(row: dict[str, Any], name: str) -> Any:  # noqa: ANN401
        if name in ("timestamp", "station_id"):
            return row[name]
        if name in _PARTS:
            return _PARTS[name](row["timestamp"])
        return row["values"][_canonical(name)]

    def meets(row: dict[str, Any]) -> bool:
        for name, op, numbers in filter_:
            value = column(row, name)
            if value is None:
                return False
            if op == "=":
                ok = any(value == n for n in numbers)
            elif op == "!=":
                ok = all(value != n for n in numbers)
            else:
                ok = _COMPARE[op](value, numbers[0])
            if not ok:
                return False
        return True

    stamps = []
    for station in station_ids(stations):
        readings = {short: dict(oracle(station, short)) for short in shorts}
        for day in range(DAYS):
            stamp = FIRST_DAY + dt.timedelta(days=day)
            values = {short: readings[short].get(stamp) for short in shorts}
            # a long frame has a timestamp where a parameter has a reading; a wide one keeps every day
            if wide or any(v is not None for v in values.values()):
                stamps.append({"station_id": station, "timestamp": stamp, "values": values})
    rows = [row for row in stamps if meets(row)]
    group_by = ["station_id"] if by is None else by
    if first is not None:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows:
            if all(column(row, name) is not None for name, _ in sort):
                groups.setdefault(tuple(column(row, name) for name in group_by), []).append(row)
        kept = []
        for members in groups.values():
            ordered = members
            for name, descending in reversed(sort):
                ordered = sorted(ordered, key=lambda r, n=name: column(r, n), reverse=descending)
            run_start = 0
            for index, row in enumerate(ordered):
                if index and any(column(row, name) != column(ordered[index - 1], name) for name, _ in sort):
                    run_start = index
                if run_start < first:
                    kept.append(row)
        rows = kept
    if sort:
        for name, descending in reversed([*sort, ("station_id", False), ("timestamp", False)]):
            present = [r for r in rows if column(r, name) is not None]
            absent = [r for r in rows if column(r, name) is None]
            rows = sorted(present, key=lambda r, n=name: column(r, n), reverse=descending) + absent
    else:
        rows = sorted(rows, key=lambda r: (r["station_id"], r["timestamp"]))
    out: list[tuple[str, str, dt.datetime, float | None]] = []
    if wide:
        out = [(r["station_id"], WIDE, r["timestamp"], None) for r in rows]
    else:
        for row in rows:
            out.extend(
                (row["station_id"], short, row["timestamp"], row["values"][short])
                for short in shorts
                if row["values"][short] is not None
            )
        if not sort:
            # as read: by station, then parameter, then time
            out.sort(key=lambda r: (r[0], r[1], r[2]))
    if max_rows is not None:
        out = out[:max_rows]
    return out
