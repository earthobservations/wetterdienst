# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Judge a reader's frame as the values core does, for the tests of a reader's rules (GH-3676).

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

from wetterdienst.model.judge import SOURCE, judge, limits_in_canonical, plan_for, to_canonical
from wetterdienst.model.plausibility import Plausibility
from wetterdienst.model.unit import UnitConverter

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

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
    limits: Mapping[str, tuple[float | None, float | None]] | None = None,
    unit_targets: Mapping[str, str] | None = None,
    convert_units: bool = True,
) -> pl.DataFrame:
    """Judge a long frame of the readings of one station and give it back with the values in the unit of the source.

    `limits` are those of `Options.limits`, in the unit the values come back in (`unit_targets`, or the source's with
    `convert_units` off).
    """
    if "quality_flags" not in df.columns:
        df = df.with_columns(pl.lit(None, dtype=pl.String).alias("quality_flags"))
    plan = plan_for(network, dataset)
    df = df.with_columns(pl.col("value").alias(SOURCE))
    canonical = to_canonical(plan)
    if canonical is not None:
        df = df.with_columns(canonical.alias("value"))
    converter = UnitConverter()
    converter.update_targets(dict(unit_targets or {}))
    bounds = limits_in_canonical(plan, dataset, limits or {}, converter, convert_units=convert_units)
    df = judge(df, plan, modes or _MODES.get() or Plausibility(), rules, elevation, bounds)
    return df.with_columns(pl.col(SOURCE).alias("value")).drop(SOURCE)
