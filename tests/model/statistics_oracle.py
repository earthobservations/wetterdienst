# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What `statistics` must answer, worked out in plain Python over the readings of a stub (GH-4412).

The oracle shares no line with `model/group_statistics.py` and no library with it: dates, dictionaries and loops. It
writes the rules of the completeness (`docs/usage/restapi.md`, "Statistics") as a person would work them by hand: the
cells of a group are the days of its period that pass the time conditions, `searched` the days with a value among them,
the aggregates are of the days that also meet the value conditions.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

ONE_DAY = dt.timedelta(days=1)


@dataclass(frozen=True)
class Case:
    """One request of the matrix: the texts the options are written as and the predicates they mean."""

    aggregate: str
    by: tuple[str, ...] = ()
    filter: str | None = None
    year_start: int = 1
    max_missing: int = 0
    window: tuple[dt.date | None, dt.date | None] = (None, None)
    #: the time conditions as predicates of a day and the value conditions as predicates of a reading
    #: a predicate of a day and of the year it is named by (the season's, with `year_start`)
    time: Callable[[dt.date, int], bool] = lambda _d, _y: True
    value: Callable[[float], bool] = lambda _v: True
    now: dt.datetime = field(default_factory=lambda: dt.datetime(2100, 1, 1, tzinfo=dt.UTC))

    def timestamp(self) -> str | None:
        """Write the window as the `timestamp` option."""
        first, last = self.window
        if first is None and last is None:
            return None
        return f"{first.isoformat()}/{last.isoformat()}" if first and last else (first or last).isoformat()


def season_year(day: dt.date, year_start: int) -> int:
    """Name a day's year by the year its season ends in."""
    return day.year + (1 if year_start > 1 and day.month >= year_start else 0)


def season_start(year: int, year_start: int) -> dt.date:
    """Give the first day of the season a year names."""
    return dt.date(year if year_start == 1 else year - 1, year_start, 1)


def season_end(year: int, year_start: int) -> dt.date:
    """Give the last day of the season a year names."""
    if year_start == 1:
        return dt.date(year, 12, 31)
    return dt.date(year, year_start, 1) - ONE_DAY


def _key(day: dt.date, by: Sequence[str], year_start: int) -> tuple[int, ...]:
    parts = {"year": season_year(day, year_start), "month": day.month, "day": day.day}
    return tuple(parts[column] for column in by)


def _days(low: dt.date, high: dt.date) -> list[dt.date]:
    return [low + dt.timedelta(days=n) for n in range((high - low).days + 1)] if low <= high else []


def period(case: Case, first: dt.date | None, last: dt.date | None) -> tuple[dt.date, dt.date] | None:
    """Give the days a series is counted over, by the rule of its group's period (None for no cell at all)."""
    w0, w1 = case.window
    today = case.now.date()
    if "year" in case.by:
        low_at, high_at = (w0, w1 or today) if w0 is not None else (first, last)
        if low_at is None or high_at is None:
            return None
        low = season_start(season_year(low_at, case.year_start), case.year_start)
        high = season_end(season_year(high_at, case.year_start), case.year_start)
        # a season or a year is whole: the window does not cut it, so a group it cuts is incomplete
        return (low, high) if low <= high else None
    latest = today - ONE_DAY
    has_window = w0 is not None and w0 <= latest
    if first is None or last is None:
        return (w0, min(w1 or latest, latest)) if has_window and w0 is not None else None
    low, high = first, last
    if has_window and w0 is not None:
        low = min(w0, first)
        high = max(min(w1 or latest, latest), last)
    return low, high


def expected_series(readings: Mapping[dt.date, float], case: Case) -> dict[str, Any]:  # noqa: C901
    """Work the groups of one series out: {"groups": rows in key order, "total", "not_listed", "usable..."}."""
    w0, w1 = case.window
    # the walk cuts a station's readings to the window before anything is counted
    readings = {d: v for d, v in readings.items() if (w0 is None or d >= w0) and (w1 is None or d <= w1)}
    present = sorted(readings)
    first = present[0] if present else None
    last = present[-1] if present else None
    bounds = period(case, first, last)
    cells: dict[tuple[int, ...], list[dt.date]] = {}
    if bounds is not None:
        for day in _days(*bounds):
            if case.time(day, season_year(day, case.year_start)):
                cells.setdefault(_key(day, case.by, case.year_start), []).append(day)
    # a period that has not begun is no group
    cells = {
        key: days for key, days in cells.items() if dt.datetime(*days[0].timetuple()[:3], tzinfo=dt.UTC) <= case.now
    }
    # a value outside every cell makes its group's expectation unknown; the stub's values lie inside its window
    groups = []
    total = len(cells)
    not_listed = 0
    for key in sorted(cells):
        days = cells[key]
        seen = [day for day in days if day in readings]
        counted = [day for day in seen if case.value(readings[day])]
        searched, expected = len(seen), len(days)
        if searched == 0 and first is not None and last is not None and (days[-1] < first or days[0] > last):
            not_listed += 1
            continue
        if first is None:
            not_listed += 1
            continue
        incomplete = expected - searched > case.max_missing
        row: dict[str, Any] = dict(zip(case.by, key, strict=True))
        values = [readings[day] for day in counted]
        low = min(values) if values else None
        high = max(values) if values else None
        for name in (a.strip() for a in case.aggregate.split(",")):
            if name == "count":
                row["count"] = None if searched == 0 else len(counted)
            elif name == "mean":
                row["mean"] = None if searched == 0 or incomplete or not values else sum(values) / len(values)
            elif name == "sum":
                row["sum"] = None if searched == 0 or incomplete else (sum(values) if values else 0.0)
            elif name in ("min", "max"):
                row[name] = low if name == "min" else high
                at = next((d for d in counted if readings[d] == row[name]), None) if values else None
                row[f"{name}_at"] = at.isoformat() if at else None
            elif name == "earliest":
                row["earliest"] = values[0] if values else None
                row["earliest_at"] = counted[0].isoformat() if counted else None
            elif name == "latest":
                row["latest"] = values[-1] if values else None
                row["latest_at"] = counted[-1].isoformat() if counted else None
        row["searched"] = searched
        row["expected"] = expected
        row["complete"] = not incomplete
        row["_incomplete"] = incomplete
        groups.append(row)
    return {"groups": groups, "total": total, "not_listed": not_listed, "first": first, "last": last}


def over_groups(groups: Sequence[Mapping[str, Any]], name: str, total: int) -> dict[str, Any]:
    """Give the statistics over the groups of one aggregate: the complete groups that have a value."""
    usable = [g[name] for g in groups if not g["_incomplete"] and g.get(name) is not None]
    return {
        "groups": total,
        "usable": len(usable),
        "min": min(usable) if usable else None,
        "max": max(usable) if usable else None,
        "mean": sum(usable) / len(usable) if usable else None,
    }
