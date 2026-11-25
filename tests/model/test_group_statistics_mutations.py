# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Mutations of the engine of `statistics` that the tests must catch (GH-4412).

A test that passes whatever the code does proves nothing. Each mutant below breaks one rule of the completeness in the
engine, in the process, by replacing the function that makes it; the oracle comparison of `test_group_statistics`
(plain Python over the same readings) must then fail for at least one request of the matrix. A mutant that survives
names a rule the matrix does not hold.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.model import test_group_statistics as matrix
from tests.model.test_group_statistics_review import (
    test_the_first_and_the_last_hour_of_a_record_count_the_steps_they_hold as edges_test,
)
from tests.model.test_group_statistics_rules import test_a_station_of_minutes_costs_hours_of_cells as minutes_test
from wetterdienst.model import group_statistics

if TYPE_CHECKING:
    from collections.abc import Callable

CASES = matrix._matrix()  # noqa: SLF001


def _survives(
    monkeypatch: pytest.MonkeyPatch, mutate: Callable[[pytest.MonkeyPatch], None], cases: list[Any] = CASES
) -> list[Any]:
    """Run the cases of the matrix with `mutate` applied: none if the oracle caught it, else all that passed."""
    uncaught = []
    for case in cases:
        with monkeypatch.context() as patch:
            mutate(patch)
            try:
                matrix._compare(matrix._run(case, patch), case)  # noqa: SLF001
            except AssertionError:
                return []
            uncaught.append(case)
    return uncaught


def _calendar_year(patch: pytest.MonkeyPatch) -> None:
    """Make a season the calendar year: `year_start` is ignored in the bounds of a group's period."""
    original = group_statistics._season_bounds  # noqa: SLF001
    patch.setattr(group_statistics, "_season_bounds", lambda year, _start: original(year, 1))


def _year_of_the_stamp(patch: pytest.MonkeyPatch) -> None:
    """Name the `year` of a value by its calendar year, whatever `year_start` says."""
    original = group_statistics._keyed  # noqa: SLF001
    patch.setattr(group_statistics, "_keyed", lambda frame, _start, columns: original(frame, 1, columns))


def _one_cell_too_few(patch: pytest.MonkeyPatch) -> None:
    """Give a group one cell fewer than it should have: `expected` is off by one."""
    original = group_statistics._cells  # noqa: SLF001

    def fewer(resolution: str, low: Any, high: Any) -> Any:  # noqa: ANN401
        return original(resolution, low, high).slice(1)

    patch.setattr(group_statistics, "_cells", fewer)


def _every_group_is_complete(patch: pytest.MonkeyPatch) -> None:
    """Allow a gap whatever its size: an incomplete group gets its mean and its sum."""
    original = group_statistics.reduce_series

    def lenient(plan: Any, *args: Any) -> Any:  # noqa: ANN401
        return original(dataclasses.replace(plan, max_missing=10**6), *args)

    patch.setattr(group_statistics, "reduce_series", lenient)


def _less_than_is_at_most(patch: pytest.MonkeyPatch) -> None:
    """`<` of a condition is `<=`."""
    original = group_statistics.condition_expr

    def mutant(condition: Any) -> Any:  # noqa: ANN401
        if condition.operator == "<":
            condition = dataclasses.replace(condition, operator="<=")
        return original(condition)

    patch.setattr(group_statistics, "condition_expr", mutant)


def _the_running_year_ends_today(patch: pytest.MonkeyPatch) -> None:
    """Cut a year by today, as the `expected` of `values` is: the running year is then complete."""
    original = group_statistics._period  # noqa: SLF001

    def cut(plan: Any, resolution: Any, window: Any, first: Any, last: Any, now: Any) -> Any:  # noqa: ANN401
        period = original(plan, resolution, window, first, last, now)
        if period is not None and "year" in plan.by:
            return period[0], min(period[1], max(now, last or now))
        return period

    patch.setattr(group_statistics, "_period", cut)


def _time_conditions_do_not_narrow_the_cells(patch: pytest.MonkeyPatch) -> None:
    """Make the cells of a group all the days of its period: a `month` condition leaves `expected` as it was."""
    original = group_statistics.keep

    def keep(frame: Any, conditions: Any) -> Any:  # noqa: ANN401
        # the cells have no `value`: only they are made without the time conditions
        if "value" not in frame.columns and conditions:
            return frame
        return original(frame, conditions)

    patch.setattr(group_statistics, "keep", keep)


def _the_window_cuts_the_year(patch: pytest.MonkeyPatch) -> None:
    """Cut a year or a season by the window, as it was: a group the window cuts is then complete."""
    original = group_statistics._period  # noqa: SLF001

    def cut(plan: Any, resolution: Any, window: Any, first: Any, last: Any, now: Any) -> Any:  # noqa: ANN401
        period = original(plan, resolution, window, first, last, now)
        if period is None or "year" not in plan.by:
            return period
        low, high = period
        w0, w1 = window
        return (max(low, w0) if w0 is not None else low), (min(high, w1) if w1 is not None else high)

    patch.setattr(group_statistics, "_period", cut)


MUTANTS = {
    "a season is the calendar year": _calendar_year,
    "the year of a value is its calendar year": _year_of_the_stamp,
    "a group has one cell fewer": _one_cell_too_few,
    "every group is complete": _every_group_is_complete,
    "less than is at most": _less_than_is_at_most,
    "a year ends today": _the_running_year_ends_today,
    "time conditions do not narrow the cells": _time_conditions_do_not_narrow_the_cells,
    "the window cuts the year": _the_window_cuts_the_year,
}


@pytest.mark.parametrize("name", list(MUTANTS))
def test_the_matrix_catches_the_mutant(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The oracle comparison fails for at least one request of the matrix when the engine is broken this way."""
    uncaught = _survives(monkeypatch, MUTANTS[name])
    assert not uncaught, f"the mutant {name!r} passed all {len(uncaught)} requests of the matrix"


def test_the_matrix_passes_unmutated(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: with no mutation the same loop finds nothing to catch."""
    assert len(_survives(monkeypatch, lambda _patch: None, CASES[:40])) == 40


def test_the_hours_of_a_station_of_minutes_are_counted_by_their_weight(monkeypatch: pytest.MonkeyPatch) -> None:
    """A step finer than an hour counts for the readings it stands for: weight 1 makes a day 24 cells, not 144."""
    original = group_statistics._cells  # noqa: SLF001

    def unweighted(resolution: str, low: Any, high: Any) -> Any:  # noqa: ANN401
        return original(resolution, low, high).with_columns(pl.lit(1, pl.Int64).alias("_w"))

    monkeypatch.setattr(group_statistics, "_cells", unweighted)
    with pytest.raises(AssertionError):
        minutes_test(monkeypatch)


def test_the_first_and_the_last_hour_of_a_period_are_counted_by_the_steps_in_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Weighing the first and the last hour whole (the cells of a minute station as they were) is caught."""
    original = group_statistics._sub_hourly_cells  # noqa: SLF001

    def whole(minutes: int, low: Any, high: Any) -> Any:  # noqa: ANN401
        cells = original(minutes, low, high)
        full = 60 // minutes
        return cells.with_columns(pl.lit(full, pl.Int64).alias("_w"))

    monkeypatch.setattr(group_statistics, "_sub_hourly_cells", whole)
    with pytest.raises(AssertionError):
        edges_test(monkeypatch)
