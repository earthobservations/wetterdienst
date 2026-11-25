# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`statistics` against a plain-Python oracle, over every combination of the options that matters (GH-4412).

The stub of the row options (`tests/ui/row_options_stub.py`) serves three stations with a daily record of three years,
each with gaps and many equal values, and `statistics_oracle` works out what each request must answer from the same
readings with dates, dictionaries and loops. A request is a `Case`: the texts of the options and, beside them, what they
mean as predicates; the matrix is years, months, days, seasons (`year_start`), filters, windows that cut the first and
the last group, windows wider than the record (groups that are no rows), `max_missing` and a clock that makes the
running year incomplete.
"""

from __future__ import annotations

import datetime as dt
import itertools
import random
from typing import TYPE_CHECKING, Any

import pytest

from tests.model.statistics_oracle import Case, expected_series, over_groups
from tests.model.statistics_stub import at, serve_custom
from tests.ui.row_options_stub import STATIONS, TMIN, oracle
from wetterdienst.model import group_statistics
from wetterdienst.provider.dwd.observation import DwdObservationRequest

if TYPE_CHECKING:
    from collections.abc import Callable

    from wetterdienst.model.group_statistics import StatisticsResult

_NAME = "temperature_air_min_2m"
_READINGS = {station: {ts.date(): value for ts, value in oracle(station, _NAME)} for station in STATIONS}
_FILTERS: dict[str | None, tuple[Callable[[dt.date, int], bool], Callable[[float], bool]]] = {
    None: (lambda _d, _y: True, lambda _v: True),
    "value<0": (lambda _d, _y: True, lambda v: v < 0),
    "month=12|1|2": (lambda d, _y: d.month in (12, 1, 2), lambda _v: True),
    "month=12|1|2,value<=-5": (lambda d, _y: d.month in (12, 1, 2), lambda v: v <= -5),
    "day=1|15,value>=0": (lambda d, _y: d.day in (1, 15), lambda v: v >= 0),
    "year=2019,value!=0": (lambda _d, y: y == 2019, lambda v: v != 0),
    "month!=2,month!=3,value>-100": (lambda d, _y: d.month not in (2, 3), lambda _v: True),
    "value>1000": (lambda _d, _y: True, lambda v: v > 1000),
}
_WINDOWS = {
    "years": (dt.date(2018, 1, 1), dt.date(2020, 12, 31)),
    "cuts": (dt.date(2018, 3, 15), dt.date(2020, 9, 10)),
    "wider": (dt.date(2017, 1, 1), dt.date(2021, 12, 31)),
    "none": (None, None),
}
_NOWS = {
    "past": dt.datetime(2100, 1, 1, tzinfo=dt.UTC),
    "running": dt.datetime(2020, 7, 1, 12, tzinfo=dt.UTC),
}
_AGGREGATES = ("count,mean,sum,min,max", "earliest,latest,count,mean")
_BY = ((), ("year",), ("month",), ("year", "month"), ("day",), ("month", "day"), ("year", "month", "day"))


def _matrix() -> list[Case]:
    cases = []
    for aggregate, by, text, window, now, missing in itertools.product(
        _AGGREGATES, _BY, _FILTERS, _WINDOWS, _NOWS, (0, 7, 400)
    ):
        starts = (1, 7, 12) if "year" in by else (1,)
        for year_start in starts:
            time, value = _FILTERS[text]
            cases.append(
                Case(
                    aggregate=aggregate,
                    by=by,
                    filter=text,
                    year_start=year_start,
                    max_missing=missing,
                    window=_WINDOWS[window],
                    time=time,
                    value=value,
                    now=_NOWS[now],
                )
            )
    return random.Random(4412).sample(cases, 250)  # noqa: S311


def _readings(case: Case) -> dict[str, dict[dt.date, float]]:
    """Give the readings the network holds at the moment of the case: none from the future."""
    return {
        station: {d: v for d, v in readings.items() if at(d.year, d.month, d.day) <= case.now}
        for station, readings in _READINGS.items()
    }


def _run(case: Case, monkeypatch: pytest.MonkeyPatch) -> StatisticsResult:
    monkeypatch.setattr(group_statistics, "_now", lambda: case.now)
    serve_custom(
        monkeypatch,
        {s: {at(d.year, d.month, d.day): v for d, v in r.items()} for s, r in _readings(case).items()},
        parameter=_NAME,
    )
    first, last = case.window
    request = DwdObservationRequest(
        parameters=[TMIN],
        start=dt.datetime(first.year, first.month, first.day, tzinfo=dt.UTC) if first else None,
        end=dt.datetime(last.year, last.month, last.day, 23, 59, 59, 999999, tzinfo=dt.UTC) if last else None,
    ).all()
    return request.values().statistics(
        case.aggregate,
        by=",".join(case.by) or None,
        filter=case.filter,
        year_start=case.year_start if case.year_start != 1 else None,
        max_missing=case.max_missing or None,
    )


def _same(got: Any, want: Any) -> bool:  # noqa: ANN401
    if isinstance(want, float) or isinstance(got, float):
        return got is not None and want is not None and abs(got - want) < 1e-3
    return got == want


def _compare(result: StatisticsResult, case: Case) -> None:
    readings = _readings(case)
    by_station = {s["station_id"]: s for s in result.series_dicts()}
    assert list(by_station) == list(STATIONS)
    for station, series in by_station.items():
        want = expected_series(readings[station], case)
        rows = series["groups"]
        assert len(rows) == len(want["groups"]), (station, case)
        for got, expected in zip(rows, want["groups"], strict=True):
            for name, value in expected.items():
                if name.startswith("_"):
                    continue
                assert _same(got[name], value), (station, name, got, expected, case)
            assert list(got) == [k for k in expected if not k.startswith("_")]
        for name in case.aggregate.split(","):
            if name in ("earliest", "latest"):
                assert name not in series["over_groups"]
                continue
            stats = over_groups(want["groups"], name, want["total"])
            for member, value in stats.items():
                assert _same(series["over_groups"][name][member], value), (station, name, member, case)
        assert series["first_timestamp"] == (want["first"].isoformat() if want["first"] else None)
        assert series["last_timestamp"] == (want["last"].isoformat() if want["last"] else None)
    seen = result.totals()
    assert seen["groups"] == sum(expected_series(readings[s], case)["total"] for s in STATIONS)
    assert seen["groups_not_listed"] == sum(expected_series(readings[s], case)["not_listed"] for s in STATIONS)


@pytest.mark.parametrize("case", _matrix(), ids=lambda c: f"{c.aggregate}|{'-'.join(c.by)}|{c.filter}|{c.year_start}")
def test_every_group_of_every_request_is_what_the_oracle_works_out(case: Case, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every group of every request is what the oracle works out by hand: keys, numbers, dates and counts."""
    _compare(_run(case, monkeypatch), case)
