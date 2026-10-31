# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Judge a reader's frame as the values core does, for the tests of a reader's rules (spike of GH-3676).

A reader no longer judges the numbers it parses: the core converts them to canonical units, judges them
(`model/judge.py`) and converts them to the unit asked for. A test of what the table of ranges and the rules a provider
hands the core make of a frame calls `judged`, which does the first two steps and hands the values back as the source
wrote them, the way `convert_units=False` does.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.model.judge import SOURCE, judge, plan_for, to_canonical
from wetterdienst.model.plausibility import Plausibility

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from wetterdienst.model.judge import Rule
    from wetterdienst.model.metadata import DatasetModel


_MODES: contextvars.ContextVar[Plausibility | None] = contextvars.ContextVar("modes_of_a_test", default=None)


@contextlib.contextmanager
def applying(modes: Plausibility) -> Iterator[None]:
    """Judge the frames `judged` is given inside with the modes of a test, in this context alone."""
    token = _MODES.set(modes)
    try:
        yield
    finally:
        _MODES.reset(token)


def judged(
    df: pl.DataFrame,
    *,
    network: str,
    dataset: DatasetModel,
    rules: Sequence[Rule] = (),
    elevation: float | None = None,
    modes: Plausibility | None = None,
) -> pl.DataFrame:
    """Judge a long frame of the readings of one station and give it back with the values in the unit of the source."""
    if "quality_flags" not in df.columns:
        df = df.with_columns(pl.lit(None, dtype=pl.String).alias("quality_flags"))
    plan = plan_for(network, dataset)
    df = df.with_columns(pl.col("value").alias(SOURCE))
    canonical = to_canonical(plan)
    if canonical is not None:
        df = df.with_columns(canonical.alias("value"))
    df = judge(df, plan, modes or _MODES.get() or Plausibility(), rules, elevation)
    return df.with_columns(pl.col(SOURCE).alias("value")).drop(SOURCE)
