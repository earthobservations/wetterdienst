# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every plausibility check, run by the values core in canonical units (GH-3676).

A reader decodes what its source writes as a code (``-999``, ``---``, a trace, a calm) and hands the numbers over in
the unit of its source. For a dataset a check applies to, the core then

1. makes the periods the reader read one series (``merge_duplicate_readings``, the first reading with a value winning);
2. cuts the frame of a grouped dataset to the parameters asked for and the ones a rule reads beside them (the air beside
   a road surface, the dew point beside a humidity: ``Plan.read_beside``), since a verdict on a parameter that is cut
   afterwards is never seen;
3. converts those parameters to the canonical unit of their unit type (``UnitConverter().targets``), without rounding,
   keeping the number as the source wrote it (and its text, where the provider hands it over) for the ``raw:`` token
   (``to_canonical``);
4. judges the long frame with the five checks of ``Plausibility`` (``judge``), the bounds being the one table of
   ``plausibility_ranges`` and the relations between parameters being evaluated across the parameters of one station
   and timestamp;
5. converts to the unit the caller wants, in one expression, rounding once (``to_requested``).

What stays with a provider is what only it knows, handed over as rules by ``TimeseriesValues._plausibility_rules``: the
stations without frost, the periods in which one sensor of one station did not work, the relation of a road surface to
the air of its minute at night.

Modes and tokens are those of ``Plausibility``: ``hard`` nulls the value (``floor`` sets it to 0) and writes
``rejected:<checks>,raw:<text>``, ``soft`` keeps it and writes ``suspect:<checks>``; several checks are joined with
``+`` in alphabetical order, and a value that a hard check rejects carries only the hard checks.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple

import polars as pl

from wetterdienst.metadata.resolution import reading_step
from wetterdienst.model.plausibility import CHECKS, REJECTED, SUSPECT, Plausibility
from wetterdienst.model.plausibility_ranges import bounds_for
from wetterdienst.model.quality_flags import RAW_TOKEN
from wetterdienst.model.unit import UnitConverter

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from wetterdienst.model.metadata import DatasetModel

_CONVERTER = UnitConverter()
_INF = math.inf
SOURCE = "__source"
_SOURCE = SOURCE
#: the column a provider hands the text of the source's value in, beside the value (the cell of a file, the megajoules
#: of a source that the reader converts): the core writes it in the `raw:` token of a value it rejects
SOURCE_TEXT = "source_text"
_HIT = "__hit_"
_ELIGIBLE = "__eligible"

#: the station pressure whose constant run is a barometer that does not work (check ``stuck``, DWD observation)
STATION_PRESSURE = ("pressure_air_site", "pressure_air_site_mean")
#: the station pressure that is also held to what the elevation of the station allows (check ``elevation``): in every
#: network, for every station of it that has an elevation
ELEVATION_PRESSURE = ("pressure_air_site", "pressure_air_site_mean", "pressure_air_site_min", "pressure_air_site_max")
#: the networks whose list writes 0.0 for a station of which it knows no elevation, so that 0.0 is no elevation there:
#: GHCN lists 54 hourly stations at 0.0 that stand between 150 and 4,329 m (CHM00052940 reads 500.2 to 998 hPa; the
#: daily list has BRM00083566, inland at about 827 m), and a pressure of the height they stand at is none for the sea
#: level the list puts them at (GH-3681). The 0.0 of the lists read is a coast (those of DWD, ECCC, IMGW and
#: Météo-France, read 2026-11-01, hold no station at 0.0 that stands higher than 75 m)
ELEVATION_ZERO_IS_UNKNOWN = frozenset({"noaa/ghcn"})
# the pressure of the standard atmosphere at sea level, in hPa, and what the barometric formula of it (the international
# standard atmosphere, valid in the troposphere) expects at a height (GH-3627). A station pressure further below it
# than `STATION_PRESSURE_LOW_SHARE` of it or further above it than `STATION_PRESSURE_HIGH_MARGIN` is no reading
# (GH-3681). The low end is the lowest pressure the WMO Archive lists at sea level, 870 hPa (Typhoon Tip, 1979-10-12),
# as a share of the standard atmosphere's 1013.25 hPa, so that it holds at every height: 143 hPa below at sea level,
# which keeps the 917.4 hPa of Hurricane Irma at St-Barthélemy (3 m, 2017-09-06, quality code 1). The high end is
# from the highest sea level pressures on record, 1,083.8 hPa (Agata, 261 m, 1968-12-31) and 1,089.1 hPa (Tosontsengel,
# 1,725 m, 2004-12-30), reduced to the station with the cold column of those days: 59 to 64 hPa over the standard
# atmosphere at Agata and 14 to 40 at Tosontsengel (a derivation of GH-3681), so 75 hPa leaves room above
STANDARD_SEA_LEVEL_PRESSURE = 1013.25
STATION_PRESSURE_LOW_SHARE = 870.0 / STANDARD_SEA_LEVEL_PRESSURE
STATION_PRESSURE_HIGH_MARGIN = 75.0
# the elevations the check is made for, in metres: a catalogue that gives another (a missing-value code, a typo) tells
# nothing, and the formula is the standard atmosphere's to 11 km
_STATION_ELEVATIONS = (-500.0, 9000.0)
#: the amounts a model writes a little below zero (check ``floor``), by network
FLOORS: dict[str, tuple[str, ...]] = {
    "dwd/dmo": (
        "precipitation_amount_last_1h",
        "precipitation_amount_last_3h",
        "radiation_global",
        "radiation_short_wave_net_last_3h",
    ),
}
#: a barometer that writes one pressure for hours reflects the station and not the weather (check ``stuck``, GH-2699):
#: by network, the quantities, and by resolution the number of consecutive readings of one value that makes it so. The
#: run is judged in the series the core is handed, the periods of the archive merged (the historical file first), so a
#: station whose historical file is constant and whose recent one is not is flagged for the stretch that is.
#:
#: The numbers are those of the research for GH-3681 (section 4.1, persistence of station and sea level pressure).
#: Hourly, 72 readings: HadISD (Dunn et al. 2012, Clim. Past 8, 1649-1679, Table 4) holds a straight repeat of 72
#: values at a resolution of 0.1 hPa, which DWD's pressures have (it says 100 at 0.5 hPa and 120 at 1 hPa). Daily, 5
#: days: ECA&D (KNMI, Algorithm Theoretical Basis Document v11, 2021, section 3: PP, "not exactly the same value 5 days
#: in a row"). 10 minutes, 36 readings (6 hours): derived by the research, since no source publishes a 10-minute
#: count. Sub-daily, monthly and annual values have no source and are not judged.
CONSTANT_RUNS: dict[str, tuple[tuple[str, ...], dict[str, int]]] = {
    "dwd/observation": (STATION_PRESSURE, {"10_minutes": 36, "hourly": 72, "daily": 5}),
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


def standard_station_pressure(elevation: float) -> float:
    """Give the pressure in hPa that the barometric formula of the standard atmosphere expects at an elevation in m."""
    return STANDARD_SEA_LEVEL_PRESSURE * (1.0 - 2.25577e-5 * elevation) ** 5.25588


def station_pressure_bounds(elevation: float | None) -> tuple[float, float] | None:
    """Give the pressure in hPa a station at an elevation may read: the standard atmosphere there, less and more.

    The world-wide bounds of a pressure at the station (300 to 1100 hPa) are too wide to find a reading of another
    height (968.6 hPa at the Zugspitze, 2,956 m, where 705 hPa are expected) or one mistyped by a digit above the
    standard atmosphere of the station (a P0 of 1093.3 hPa at 48 m). The low end is the lowest pressure on record at sea
    level as a share of the standard atmosphere (870/1013.25), which lets the deepest storms through: Irma read 917.4
    hPa at 3 m, 95.5 hPa below the standard atmosphere there, and Typhoon Tip 143 hPa below it at sea level. A reading
    mistyped by a digit to a pressure in between (909.5 hPa at 48 m) is for the checks of a step in a series to find.

    Returns:
        The bounds, or ``None`` where the station has no elevation or one outside -500 to 9000 m.

    """
    if elevation is None or not _STATION_ELEVATIONS[0] <= elevation <= _STATION_ELEVATIONS[1]:
        return None
    expected = standard_station_pressure(elevation)
    return expected * STATION_PRESSURE_LOW_SHARE, expected + STATION_PRESSURE_HIGH_MARGIN


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
    constants: tuple[tuple[str, int], ...] = ()
    #: the time between two readings that ends a run of one value: four times the interval of the resolution
    constant_gap: dt.timedelta | None = None
    runs: tuple[tuple[str, ...], str | None] = ((), None)
    by_name: dict[str, str] = field(default_factory=dict)

    def read_beside(self, rules: Sequence[Rule]) -> set[str]:
        """Name the parameters (as the source does) that the checks read beside the ones asked for.

        The neighbour of a relation (`Beside`: the air beside a road surface, the dew point beside a humidity) and the
        air of the road's run rule, which tells whether melting ice holds a surface at its melting point.
        """
        names = {
            self.by_name[rule.partner] for rule in rules if isinstance(rule, Beside) and rule.partner in self.by_name
        }
        if self.runs[1] is not None:
            names.add(self.runs[1])
        return names

    @property
    def judges(self) -> bool:
        """Tell whether any check applies to every station of the dataset."""
        return bool(self.ranges or self.pressure or self.floors or self.constants or self.runs[0])


_PLANS: dict[tuple[int, str], tuple[DatasetModel, Plan]] = {}


def plan_for(network: str, dataset: DatasetModel) -> Plan:
    """Give the plan of a network's dataset, built on first use (and kept for as long as the dataset lives)."""
    key = (id(dataset), network)
    cached = _PLANS.get(key)
    if cached is None or cached[0] is not dataset:
        cached = _PLANS[key] = (dataset, _build_plan(network, dataset))
    return cached[1]


def _build_plan(network: str, dataset: DatasetModel) -> Plan:
    resolution = dataset.resolution.name
    parameters: dict[str, Conversion] = {}
    by_name: dict[str, str] = {}
    ranges: dict[str, tuple[float, float]] = {}
    for parameter in dataset:
        unit_type = parameter.unit_type
        canonical = _CONVERTER.targets[unit_type].name
        to = None if parameter.unit == canonical else _CONVERTER.lambda_between(parameter.unit, canonical)
        parameters[parameter.name_original] = Conversion(parameter.name, parameter.unit, unit_type, canonical, to)
        by_name.setdefault(parameter.name, parameter.name_original)
        bounds = bounds_for(parameter.name, resolution, unit_type)
        if bounds is not None:
            ranges[parameter.name_original] = tuple(bounds)
    original = by_name
    pressure = tuple(original[name] for name in ELEVATION_PRESSURE if name in original)
    floors = tuple(original[name] for name in FLOORS.get(network, ()) if name in original)
    names, limits = CONSTANT_RUNS.get(network, ((), {}))
    constants = tuple(
        (original[name], limits[resolution]) for name in names if name in original and resolution in limits
    )
    step = reading_step(dataset.resolution.value)
    constant_gap = step * RUN_GAP_FACTOR if constants and step is not None else None
    runs: tuple[tuple[str, ...], str | None] = ((), None)
    if network in RUNS:
        names, air = RUNS[network]
        if all(name in original for name in names):
            runs = (tuple(original[name] for name in names), original[air])
    return Plan(network, parameters, ranges, pressure, floors, constants, constant_gap, runs, by_name)


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


def to_requested(plan: Plan, requested: Mapping[str, str], converter: UnitConverter, *, canonical: bool) -> pl.Expr:
    """Give the expression that converts the ``value`` of the parameters asked for to the unit asked for, in one.

    From the canonical unit of the judged frame (``canonical``) or from the unit of the source, whichever the frame is
    in. Rounded once, to as many decimals as the target unit needs to keep the reading's precision
    (``UnitConverter.decimals``), whatever the unit it came from.

    ``requested`` maps each name the frame has to the parameter of the dataset that declares it (they differ in casing
    where a provider wrote a name in another one).
    """
    groups: dict[tuple[str, str, int], tuple[Callable[[pl.Expr], pl.Expr], list[str]]] = {}
    for name, declared in requested.items():
        conversion = plan.parameters[declared]
        target = converter.targets[conversion.unit_type].name
        places = converter.decimals(conversion.unit, target)
        source = conversion.canonical if canonical else conversion.unit
        groups.setdefault((source, target, places), (converter.lambda_between(source, target), []))[1].append(name)
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
    # a value below the floor of a quantity the model writes a little below it is the floor's to map to the floor
    # (GH-3681): the range stands aside at the low end, as it never judged these networks before
    for name in plan.floors:
        if name in bounds:
            bounds[name] = (-_INF, bounds[name][1])
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
    if plan.pressure and elevation is not None and not (elevation == 0.0 and plan.network in ELEVATION_ZERO_IS_UNKNOWN):
        allowed = station_pressure_bounds(elevation)
        if allowed is not None:
            exprs["elevation"].append(parameter.is_in(plan.pressure) & ((value < allowed[0]) | (value > allowed[1])))
    if plan.floors:
        exprs["floor"].append(parameter.is_in(plan.floors) & (value < 0.0))
    if plan.constants:
        series["stuck"].append(_constant_runs(df, plan))
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
    # the text the source wrote where the provider gave it, else the number as short as it goes (`4021.0` as `4021`)
    short = pl.col(_SOURCE).cast(pl.String).str.replace(r"\.0$", "")
    if SOURCE_TEXT in rows.columns:
        text = pl.col(SOURCE_TEXT).str.strip_chars().replace("", None)
        written = pl.coalesce(text.str.replace_all(",", ";"), short)
    else:
        written = short
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


def _constant_runs(df: pl.DataFrame, plan: Plan) -> pl.Series:
    """Mark the readings of a quantity that held one value for as many consecutive readings as its limit says.

    The nulls are skipped (a reading that is missing does not break a run) but a gap of more than four times the
    interval of the resolution between two readings does.
    """
    limits = dict(plan.constants)
    runs = (
        df.select("parameter", "timestamp", "value")
        .with_row_index("_row")
        .filter(pl.col("parameter").is_in(list(limits)) & pl.col("value").is_not_null())
        .sort("parameter", "timestamp", "_row")
        .with_columns(_gap=pl.col("timestamp").diff().over("parameter"))
        .with_columns(
            # a run ends where the value changes, and where the readings are further apart than the gap: a null
            # between two readings of a short stretch is bridged, a month without readings is not
            _run=(
                pl.col("value").ne(pl.col("value").shift().over("parameter")).fill_null(value=True)
                | (pl.col("_gap") > plan.constant_gap).fill_null(value=False)
            )
            .cum_sum()
            .over("parameter")
        )
        .with_columns(
            _length=pl.len().over("parameter", "_run"),
            _limit=pl.col("parameter").replace_strict(limits, return_dtype=pl.Int64),
        )
        .filter(pl.col("_length") >= pl.col("_limit"))
    )
    if runs.is_empty():
        return _no_hits(df)
    mask = pl.repeat(value=False, n=df.height, dtype=pl.Boolean, eager=True)
    return mask.scatter(runs.get_column("_row"), True).alias("hit")  # noqa: FBT003


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
