# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The physical range every value a provider returns is held to (GH-2615, GH-3681).

Sources mark a missing value with a number: -999, -99, -9999, 99.9, 9999. One that survives parsing is a value to every
caller, and the unit converter converts it: a mean over a column with a -999 in it is wrong without an error. The tests
of a provider mostly assert that a known value arrives, not that no impossible one does, so the check lives here once.
`conftest.py` applies it to the values the offline tests under `tests/provider` produce, and `test_value_stubs.py` to
the way each stubbed source writes a missing value. A remote test is left alone, since what a real source answers
with changes and a known leak would turn the CI matrix red until it is fixed; `WD_CHECK_RANGES_REMOTE=1` applies the
check to the remote tests as well, which is how a leak the offline fixtures do not hold is found.

The ranges are those of the one table the values core judges every network with
(`wetterdienst.model.plausibility_ranges`, the check `range`): this module keeps none of its own, so that the tests and
the library read one source (GH-3681). They are in the unit a value is returned in (`UnitConverter.targets`, the default
of `Options`; a unit type converted to another unit is not checked) and are generous on purpose: a value outside is a
sentinel, a unit that was not converted or a column read from the wrong place, never a record. What they cannot catch is
a sentinel that looks like data, such as 99.9 % relative humidity, a -1 for "no snow" in a depth that may be read from a
gauge, or 0 for "not measured"; that part of #2615 is read off the source's own documentation, not off the numbers.
Nor do they catch a -999 where the quantity has no bound at all (a discharge: a tidal river runs backwards), and a value
that is converted on its way, such as -999 kJ/m² of radiation (-99.9 J/cm²) or -9999 mm of a depth (-999.9 cm),
is caught only if the converted number lies outside.

A parameter held to no range is `None` in the table, never left out, so that a new unit type fails
`test_every_unit_type_has_a_range_or_says_it_has_none` instead of going unchecked. To hold a quantity to another range,
change the table of the library and its source in the docstring there.

A value outside its range that carries the token `suspect:` is kept on purpose: a plausibility check in the mode `soft`
found it and left it, flagged (GH-3676), so the check here accepts it. Only the core's own verdict counts; a number
outside a range with no such token is still a sentinel the reader missed.
"""

from __future__ import annotations

import polars as pl

from wetterdienst.model.plausibility import SUSPECT_TOKEN
from wetterdienst.model.plausibility_ranges import Bounds, bounds_for

__all__ = ["Bounds", "bounds_for", "describe", "out_of_range"]

_INF = float("inf")


def _canonical(parameter: str, names: dict[str, str] | None) -> str:
    """Give the canonical name of a `parameter` column string, read through `names` in either case."""
    return (names or {}).get(parameter) or (names or {}).get(parameter.lower()) or parameter


def out_of_range(df: pl.DataFrame, names: dict[str, str] | None = None, resolution: str | None = None) -> pl.DataFrame:
    """Give the rows of a tidy values frame whose value lies outside the range of its parameter.

    The frame needs the columns `parameter` and `value`; `resolution`, `dataset`, `station_id` and `timestamp` are
    carried along if it has them. `names` maps the strings of the `parameter` column to canonical names, for a frame
    that has not been humanized and so carries the source's own, whatever the case it is written in; without it the
    column is read as canonical names. `resolution` is that of the frame, where the frame has no such column; a frame
    of several resolutions is read at none of them unless it is given.
    """
    if df.is_empty() or "parameter" not in df.columns or "value" not in df.columns:
        return pl.DataFrame()
    parameters = [str(one) for one in df.get_column("parameter").unique().to_list()]
    low: dict[str, float] = {}
    high: dict[str, float] = {}
    resolutions = df.get_column("resolution").unique().to_list() if "resolution" in df.columns else []
    if resolution is None and len(resolutions) == 1:
        resolution = resolutions[0]
    for parameter in parameters:
        bounds = bounds_for(_canonical(parameter, names), resolution)
        if bounds is not None:
            low[parameter], high[parameter] = bounds
    if not low:
        return pl.DataFrame()
    parameter = pl.col("parameter")
    value = pl.col("value").cast(pl.Float64, strict=False)
    outside = (value < parameter.replace_strict(low, default=-_INF, return_dtype=pl.Float64)) | (
        value > parameter.replace_strict(high, default=_INF, return_dtype=pl.Float64)
    )
    keep = [
        column
        for column in ("resolution", "dataset", "station_id", "timestamp", "parameter", "value")
        if column in df.columns
    ]
    if "quality_flags" in df.columns:
        # a value that a soft plausibility check flagged `suspect:` is kept on purpose, outside its range or not
        # (GH-3676): the flag is the reader's own finding, so the number is not a sentinel the reader missed
        outside = outside & ~pl.col("quality_flags").str.contains(SUSPECT_TOKEN).fill_null(value=False)
    return df.filter(outside.fill_null(value=False)).select(keep)


def describe(
    found: pl.DataFrame, names: dict[str, str] | None = None, limit: int = 3, resolution: str | None = None
) -> str:
    """Say which parameters had values outside their range, with the lowest and the highest of each."""
    lines = []
    for (parameter,), rows in found.group_by(["parameter"], maintain_order=True):
        name = str(parameter)
        canonical = _canonical(name, names)
        values = rows.get_column("value").sort().to_list()
        shown = values[:limit] if len(values) <= 2 * limit else [*values[:limit], "...", *values[-limit:]]
        bounds = tuple(bounds_for(canonical, resolution) or ())
        lines.append(f"{canonical}: {len(values)} outside {bounds}: {shown}")
    return "; ".join(lines)
