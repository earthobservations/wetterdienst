# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every plausibility check, run by the values core in canonical units (spike of GH-3676).

A reader decodes what its source writes as a code (``-999``, ``---``, a trace, a calm) and hands the numbers over in
the unit of its source. The core then

1. converts every parameter of what was collected to the canonical unit of its unit type (``UnitConverter().targets``),
   without rounding, keeping the number as the source wrote it for the ``raw:`` token (``to_canonical``);
2. judges the long frame with the five checks of ``Plausibility`` (``judge``), the bounds being the one table of
   ``plausibility_ranges`` and the relations between parameters being evaluated across the parameters of one station
   and timestamp;
3. cuts the frame to the parameters asked for and converts the rest to the unit the caller wants, rounding once
   (``from_canonical``).

What stays with a provider is what only it knows, handed over as rules by ``TimeseriesValues._plausibility_rules``: the
stations without frost, the periods in which one sensor of one station did not work, the relation of a road surface to
the air of its minute at night.

Modes and tokens are those of ``Plausibility``: ``hard`` nulls the value (``floor`` sets it to 0) and writes
``rejected:<checks>,raw:<number>``, ``soft`` keeps it and writes ``suspect:<checks>``; several checks are joined with
``+`` in alphabetical order, and a value that a hard check rejects carries only the hard checks.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple

import polars as pl

from wetterdienst.model.plausibility import CHECKS, REJECTED, SUSPECT, Plausibility
from wetterdienst.model.plausibility_ranges import OVERRIDES, RANGES, SCOPE
from wetterdienst.model.quality_flags import RAW_TOKEN, station_pressure_range
from wetterdienst.model.unit import UnitConverter

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from wetterdienst.model.metadata import DatasetModel

_CONVERTER = UnitConverter()
_INF = math.inf
SOURCE = "__source"
_SOURCE = SOURCE
_HIT = "__hit_"
_ELIGIBLE = "__eligible"

#: the station pressure that is also held to what the elevation of the station allows (check ``elevation``), by network
STATION_PRESSURE = ("pressure_air_site", "pressure_air_site_mean")
ELEVATION_NETWORKS = ("dwd/observation", "meteofrance/synop")
#: the amounts a model writes a little below zero (check ``floor``), by network
FLOORS: dict[str, tuple[str, ...]] = {
    "dwd/dmo": (
        "precipitation_amount_last_1h",
        "precipitation_amount_last_3h",
        "radiation_global",
        "radiation_short_wave_net_last_3h",
    ),
}
#: a quantity whose readings in one collected frame are too few distinct values to be a measurement (check ``stuck``):
#: by network, then ``resolution/dataset``, the quantity, the readings it takes and the most distinct values it may
#: have. A barometer that writes one pressure for a whole file reflects the station and not the weather (GH-2699): 761
#: of the 1314 hourly moisture files of DWD hold one value in all their readings (997.3 hPa in the 12,844 rows of
#: stundenwerte_TF_14072_akt.zip), 55 more two, and of the 1,305 files of 500 readings or more none holds 3 to 46, the
#: fewest of any other being 47: three sits in that gap. The reader judged one file at a time; the core judges the frame
#: it was handed, which holds the periods asked for together
CONSTANT: dict[str, dict[str, tuple[tuple[str, int, int], ...]]] = {
    "dwd/observation": {"hourly/moisture": (("pressure_air_site", 500, 3),)},
}
#: a sensor that did not move for hours (check ``stuck``), by network: the quantities, and the one whose reading of the
#: same minute tells whether melting ice can hold a road surface at its melting point (GH-1917)
RUNS: dict[str, tuple[tuple[str, ...], str]] = {
    "dwd/road": (("temperature_air", "temperature_dew_point", "temperature_surface"), "temperature_air"),
}
# a working sensor's longest run of one value over a day was 14 readings for the air temperature, 17 for the dew point
# and 9 for the road surface (about 700 stations each); a broken one holds it for 86 to 96 of the day's 96. 24 readings
# (six hours) sit between, over a span of 23 intervals of the quarter hour; a gap above four times the station's usual
# interval ends a run; a road surface at its melting point beside an air within ten degrees of freezing is ice melting
RUN_READINGS = 24
RUN_MIN_SPAN = dt.timedelta(minutes=15) * (RUN_READINGS - 1)
RUN_GAP_FACTOR = 4
MELTING_PLATEAU = 0.05
MELTING_BRINE_DEPRESSION = 10.0
MELTING_AIR_MARGIN = 10.0


@dataclass(frozen=True)
class Bound:
    """A range for some parameters of the station in hand only: the stations without frost have no air below 0 °C.

    It narrows the bounds of the table (the check ``range``); the quantities are named, or all of a unit type.
    """

    low: float = -_INF
    high: float = _INF
    unit_type: str | None = None
    names: tuple[str, ...] = ()


@dataclass(frozen=True)
class Beside:
    """A reading that the reading of another parameter at the same timestamp contradicts (the check ``consistency``).

    ``when`` is given the value of ``target`` and the value of ``partner`` of the same timestamp, in canonical units,
    and says whether the target is no reading; it may read any column of the frame (``pl.col("timestamp")``). Where the
    partner is missing the check stands aside. ``partner_plausible``: the partner counts only where it passed the range
    check; ``partner_usable``: a further condition on the partner's rows (``value``, ``quality_flags``).
    """

    target: str
    partner: str
    when: Callable[[pl.Expr, pl.Expr], pl.Expr]
    partner_plausible: bool = False
    partner_usable: Callable[[], pl.Expr] | None = None


@dataclass(frozen=True)
class StuckPeriod:
    """A sensor of the station in hand that did not work over a span of days (the check ``stuck``)."""

    parameter: str
    first: dt.date
    last: dt.date


Rule = Bound | Beside | StuckPeriod


class Conversion(NamedTuple):
    """How a parameter of a dataset is converted: its canonical name, unit and unit type."""

    name: str
    unit: str
    unit_type: str
    canonical: str
    to_canonical: Callable[[pl.Expr], pl.Expr] | None


@dataclass(frozen=True)
class Plan:
    """What the checks hold a dataset to, whatever the station: built once per network and dataset."""

    network: str
    parameters: dict[str, Conversion]
    ranges: dict[str, tuple[float, float]]
    pressure: tuple[str, ...] = ()
    floors: tuple[str, ...] = ()
    constants: tuple[tuple[str, int, int], ...] = ()
    runs: tuple[tuple[str, ...], str | None] = ((), None)
    by_name: dict[str, str] = field(default_factory=dict)

    @property
    def judges(self) -> bool:
        """Tell whether any check applies to every station of the dataset."""
        return bool(self.ranges or self.pressure or self.floors or self.constants or self.runs[0])


_PLANS: dict[tuple[str, str, str], Plan] = {}


def plan_for(network: str, dataset: DatasetModel) -> Plan:
    """Give the plan of a network's dataset, built on first use."""
    key = (network, dataset.resolution.name, dataset.name)
    plan = _PLANS.get(key)
    if plan is None:
        plan = _PLANS[key] = _build_plan(network, dataset)
    return plan


def _build_plan(network: str, dataset: DatasetModel) -> Plan:
    resolution = dataset.resolution.name
    dataset_id = f"{resolution}/{dataset.name}"
    parameters: dict[str, Conversion] = {}
    by_name: dict[str, str] = {}
    ranges: dict[str, tuple[float, float]] = {}
    scope = set(SCOPE.get(network, ()))
    overrides = OVERRIDES.get(network, {})
    for parameter in dataset:
        unit_type = parameter.unit_type
        canonical = _CONVERTER.targets[unit_type].name
        to = None if parameter.unit == canonical else _CONVERTER.lambda_between(parameter.unit, canonical)
        parameters[parameter.name_original] = Conversion(parameter.name, parameter.unit, unit_type, canonical, to)
        by_name.setdefault(parameter.name, parameter.name_original)
        if parameter.name in scope:
            bounds = overrides.get(parameter.name, {}).get(resolution)
            if bounds is None:
                table = RANGES.get(parameter.name, {})
                bounds = table.get(resolution, table.get("*"))
            if bounds is not None:
                ranges[parameter.name_original] = bounds
    original = by_name
    pressure = (
        tuple(original[name] for name in STATION_PRESSURE if name in original) if network in ELEVATION_NETWORKS else ()
    )
    floors = tuple(original[name] for name in FLOORS.get(network, ()) if name in original)
    constants = tuple(
        (original[name], readings, values)
        for name, readings, values in CONSTANT.get(network, {}).get(dataset_id, ())
        if name in original
    )
    runs: tuple[tuple[str, ...], str | None] = ((), None)
    if network in RUNS:
        names, air = RUNS[network]
        if all(name in original for name in names):
            runs = (tuple(original[name] for name in names), original[air])
    return Plan(network, parameters, ranges, pressure, floors, constants, runs, by_name)


def to_canonical(plan: Plan) -> pl.Expr | None:
    """Give the expression that converts the ``value`` of every parameter to its canonical unit, no rounding.

    ``None`` where no parameter of the dataset needs a conversion. A name the dataset does not declare is left as it is.
    """
    groups: dict[tuple[str, str], tuple[Callable[[pl.Expr], pl.Expr], list[str]]] = {}
    for name, conversion in plan.parameters.items():
        if conversion.to_canonical is not None:
            groups.setdefault((conversion.unit, conversion.canonical), (conversion.to_canonical, []))[1].append(name)
    if not groups:
        return None
    value = pl.col("value")
    # the groups name different parameters, so each is a branch that is null where it does not apply
    branches = [pl.when(pl.col("parameter").is_in(names)).then(convert(value)) for convert, names in groups.values()]
    return pl.coalesce(*branches, value)


def from_canonical(
    plan: Plan, requested: Sequence[str], converter: UnitConverter, *, decimals: Callable[[str, str], int]
) -> pl.Expr:
    """Give the expression that converts the canonical ``value`` of the parameters asked for to the unit asked for.

    Rounded once, to as many decimals as the target unit needs (``UnitConverter.decimals``), as the direct conversion
    from the source did.
    """
    groups: dict[tuple[str, str, int], tuple[Callable[[pl.Expr], pl.Expr], list[str]]] = {}
    for name in requested:
        conversion = plan.parameters[name]
        target = converter.targets[conversion.unit_type].name
        places = decimals(conversion.unit, target)
        convert = converter.lambda_between(conversion.canonical, target)
        groups.setdefault((conversion.canonical, target, places), (convert, []))[1].append(name)
    value = pl.col("value")
    if len(groups) == 1:
        (convert, _), places = next(iter(groups.values())), next(iter(groups))[2]
        return convert(value).round(places).alias("value")
    branches = [
        pl.when(pl.col("parameter").is_in(names)).then(convert(value).round(places))
        for (_, _, places), (convert, names) in groups.items()
    ]
    return pl.coalesce(*branches, value).alias("value")


def judge(  # noqa: C901
    df: pl.DataFrame,
    plan: Plan,
    modes: Plausibility,
    rules: Sequence[Rule] = (),
    elevation: float | None = None,
) -> pl.DataFrame:
    """Judge a long frame in canonical units, with ``__source`` beside ``value``, and write the verdicts.

    Returns the frame with ``value`` and ``quality_flags`` as the modes say, and ``__source``, the number the source
    wrote, set where a hard check mapped the value (null, or 0 for a floor), for a caller that does not convert units.
    A reading that carries a ``raw:`` token already is a code of the source, which decides first, and is not judged.
    """
    parameter = pl.col("parameter")
    value = pl.col("value")
    exprs: dict[str, list[pl.Expr]] = defaultdict(list)
    series: dict[str, list[pl.Series]] = defaultdict(list)

    bounds = dict(plan.ranges)
    for rule in rules:
        if isinstance(rule, Bound):
            names = [
                name
                for name, conversion in plan.parameters.items()
                if conversion.name in rule.names or conversion.unit_type == rule.unit_type
            ]
            for name in names:
                low, high = bounds.get(name, (-_INF, _INF))
                bounds[name] = (max(low, rule.low), min(high, rule.high))
    outside = None
    if bounds:
        low = parameter.replace_strict({n: b[0] for n, b in bounds.items()}, default=-_INF, return_dtype=pl.Float64)
        high = parameter.replace_strict({n: b[1] for n, b in bounds.items()}, default=_INF, return_dtype=pl.Float64)
        outside = (value < low) | (value > high)
        exprs["range"].append(outside)
    if plan.pressure and elevation is not None:
        rule = station_pressure_range(elevation)
        if rule is not None:
            exprs["elevation"].append(parameter.is_in(plan.pressure) & ((value < rule.low) | (value > rule.high)))
    if plan.floors:
        exprs["floor"].append(parameter.is_in(plan.floors) & (value < 0.0))
    for name, readings, distinct in plan.constants:
        rows = df.filter(parameter.eq(name)).get_column("value").drop_nulls()
        if rows.len() >= readings and rows.n_unique() <= distinct:
            exprs["stuck"].append(parameter.eq(name))
    for rule in rules:
        if isinstance(rule, StuckPeriod) and rule.parameter in plan.by_name:
            stamp = pl.col("timestamp")
            first = dt.datetime.combine(rule.first, dt.time(), tzinfo=dt.UTC)
            end = dt.datetime.combine(rule.last + dt.timedelta(days=1), dt.time(), tzinfo=dt.UTC)
            exprs["stuck"].append(parameter.eq(plan.by_name[rule.parameter]) & (stamp >= first) & (stamp < end))
    if plan.runs[0]:
        series["stuck"].append(_stuck_runs(df, plan))
    for rule in rules:
        if isinstance(rule, Beside) and rule.target in plan.by_name and rule.partner in plan.by_name:
            series["consistency"].append(_beside(df, plan, rule, outside))

    columns = {check: pl.any_horizontal(*items) for check, items in exprs.items() if items}
    frame = df.with_columns(*(expr.alias(_HIT + check) for check, expr in columns.items()))
    for check, items in series.items():
        hits = _any_of(items).alias(_HIT + check)
        frame = (
            frame.with_columns(pl.col(_HIT + check).fill_null(value=False) | hits)
            if check in columns
            else frame.with_columns(hits)
        )
    if not columns and not series:
        return df
    names = [_HIT + check for check in sorted(CHECKS) if _HIT + check in frame.columns]
    counts = frame.select(pl.col(name).fill_null(value=False).any() for name in names).row(0)
    fired = [name for name, any_hit in zip(names, counts, strict=True) if any_hit]
    if not fired:
        return df
    # a value that carries the text of a code is judged by nobody: the code decided first
    eligible = value.is_not_null() & ~pl.col("quality_flags").str.contains(RAW_TOKEN).fill_null(value=False)
    frame = frame.with_columns(eligible.alias(_ELIGIBLE)).with_columns(
        (pl.col(name).fill_null(value=False) & pl.col(_ELIGIBLE)).alias(name) for name in fired
    )
    # the verdicts are written for the rows that have one, which are few: the rest of the frame is not touched
    rows = frame.select(pl.any_horizontal(fired).alias("any")).get_column("any").arg_true()
    if rows.is_empty():
        return df
    judged = _verdicts(frame[rows], [name.removeprefix(_HIT) for name in fired], modes)
    return df.with_columns(
        df.get_column("value").scatter(rows, judged.get_column("value")),
        df.get_column("quality_flags").scatter(rows, judged.get_column("quality_flags")),
        df.get_column(_SOURCE).scatter(rows, judged.get_column(_SOURCE)),
    )


def _verdicts(rows: pl.DataFrame, checks: list[str], modes: Plausibility) -> pl.DataFrame:
    """Write the verdicts of the checks that fired on the rows that have one: the value, the flags and the source.

    ``rows`` carries a boolean column ``__hit_<check>`` for each check, true only where the check judged the reading.
    """
    value = pl.col("value")
    hard = [check for check in checks if modes.mode(check) == "hard"]
    soft = [check for check in checks if modes.mode(check) == "soft"]
    hit = {check: pl.col(_HIT + check) for check in checks}
    written = pl.col(_SOURCE).cast(pl.String).str.replace(r"\.0$", "")
    tokens = []
    if hard:
        hard_names = pl.concat_str([pl.when(hit[c]).then(pl.lit(c)) for c in hard], separator="+", ignore_nulls=True)
        tokens.append(
            pl.when(pl.any_horizontal(hit[c] for c in hard)).then(
                pl.concat_str(pl.lit(f"{REJECTED}:"), hard_names, pl.lit(",raw:"), written)
            )
        )
    if soft:
        soft_names = pl.concat_str([pl.when(hit[c]).then(pl.lit(c)) for c in soft], separator="+", ignore_nulls=True)
        tokens.append(
            pl.when(pl.any_horizontal(hit[c] for c in soft)).then(pl.concat_str(pl.lit(f"{SUSPECT}:"), soft_names))
        )
    nulled = [hit[c] for c in hard if c != "floor"]
    floored = hit["floor"] if "floor" in hard else None
    new_value = value
    if floored is not None:
        new_value = pl.when(floored).then(pl.lit(0.0)).otherwise(new_value)
    if nulled:
        new_value = pl.when(pl.any_horizontal(nulled)).then(pl.lit(None, dtype=pl.Float64)).otherwise(new_value)
    source = pl.col(_SOURCE)
    if hard:
        # a caller that does not convert units gets the number back as the source wrote it, but for what a check mapped
        changed = pl.any_horizontal(nulled + ([floored] if floored is not None else []))
        source = pl.when(changed).then(new_value).otherwise(source)
    flags = pl.col("quality_flags")
    return rows.with_columns(pl.coalesce(*tokens).alias("__token")).select(
        new_value.alias("value"),
        pl.when(pl.col("__token").is_not_null())
        .then(pl.concat_str([flags, pl.col("__token")], separator=",", ignore_nulls=True))
        .otherwise(flags)
        .alias("quality_flags"),
        source.alias(_SOURCE),
    )


def _no_hits(df: pl.DataFrame) -> pl.Series:
    """Give a series that marks no row of the frame."""
    return pl.repeat(value=False, n=df.height, dtype=pl.Boolean, eager=True).alias("hit")


def _any_of(items: list[pl.Series]) -> pl.Series:
    """Give the rows any of the boolean series marks."""
    result = items[0].fill_null(value=False)
    for item in items[1:]:
        result |= item.fill_null(value=False)
    return result


def _beside(df: pl.DataFrame, plan: Plan, rule: Beside, outside: pl.Expr | None) -> pl.Series:
    """Evaluate a relation between two parameters of one timestamp over the long frame: the rows it rejects."""
    target, partner = plan.by_name[rule.target], plan.by_name[rule.partner]
    beside = df.filter(pl.col("parameter").eq(partner))
    if beside.is_empty():
        return _no_hits(df)
    usable = pl.lit(value=True)
    if rule.partner_plausible and outside is not None:
        beside = beside.with_columns(outside.alias("__outside"))
        usable = ~pl.col("__outside").fill_null(value=False)
    if rule.partner_usable is not None:
        usable = usable & rule.partner_usable()
    beside = beside.select("timestamp", pl.when(usable).then(pl.col("value")).alias("__beside")).unique(
        subset=["timestamp"], keep="first", maintain_order=True
    )
    joined = df.select("timestamp", "parameter", "value").join(
        beside, on="timestamp", how="left", maintain_order="left"
    )
    hit = pl.col("parameter").eq(target) & rule.when(pl.col("value"), pl.col("__beside"))
    return joined.select(hit.fill_null(value=False).alias("hit")).get_column("hit")


def _stuck_runs(df: pl.DataFrame, plan: Plan) -> pl.Series:
    """Mark the readings of a sensor that did not move for hours: a run of one value over readings and a span.

    The rule of ``dwd/road`` (GH-1917), judged on the station's own readings: a working sensor's longest run of one
    value is 14 readings for the air, 17 for the dew point and 9 for the road surface, a stopped one holds it for the
    day. A reading of a road surface at the melting point beside an air near freezing is no stuck sensor: ice melts.
    The values are in °C, the melting point 0.
    """
    names, air_name = plan.runs
    keys = ["parameter"]
    readings = (
        df.select("parameter", "timestamp", "value")
        .filter(pl.col("parameter").is_in(names) & pl.col("value").is_not_null())
        .unique(subset=[*keys, "timestamp"], keep="first")
        .sort(*keys, "timestamp")
    )
    air = readings.filter(pl.col("parameter").eq(air_name)).select("timestamp", pl.col("value").alias("_air"))
    marked = (
        readings.join(air, on="timestamp", how="left")
        .sort(*keys, "timestamp")
        .with_columns(_gap=pl.col("timestamp").diff().over(keys))
        .with_columns(
            _run=(
                pl.col("value").ne(pl.col("value").shift().over(keys)).fill_null(value=True)
                | pl.col("_gap").gt(pl.col("_gap").median().over(keys).mul(RUN_GAP_FACTOR)).fill_null(value=False)
            )
            .cum_sum()
            .over(keys)
        )
        .with_columns(
            _stuck=pl.len().over(*keys, "_run").ge(RUN_READINGS)
            & (pl.col("timestamp").max().over(*keys, "_run") - pl.col("timestamp").min().over(*keys, "_run")).ge(
                RUN_MIN_SPAN
            )
        )
        .with_columns(
            _stuck=pl.col("_stuck")
            & ~(
                pl.col("parameter").eq(plan.by_name["temperature_surface"])
                & pl.col("value").le(MELTING_PLATEAU)
                & pl.col("value").ge(-MELTING_BRINE_DEPRESSION)
                & pl.col("_air").is_between(-MELTING_AIR_MARGIN, MELTING_AIR_MARGIN).fill_null(value=True)
            )
        )
        .filter(pl.col("_stuck"))
        .select("parameter", "timestamp", "value", "_stuck")
    )
    if marked.is_empty():
        return _no_hits(df)
    joined = (
        df.select("parameter", "timestamp", "value")
        .with_row_index("_row")
        .join(marked, on=["parameter", "timestamp", "value"], how="left")
        .sort("_row")
    )
    return joined.select(pl.col("_stuck").fill_null(value=False).alias("hit")).get_column("hit")
