# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check `relations` for every provider, in both modes (GH-3681).

Two readings of one row that contradict each other (a maximum below the mean, a dew point above the air temperature,
a gust below the mean wind) and a day of sunshine longer than the day, as the table of `model/relations.py` and the sun
of `model/sun.py` say. The tests run frames through the values core, not lookups in the table.
"""

from __future__ import annotations

import datetime as dt
import random
import re
from pathlib import Path

import polars as pl
import pytest

from tests.provider.judging import judged
from wetterdienst import Wetterdienst
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model.judge import plan_for
from wetterdienst.model.plausibility import COVERAGE, SOFT_BY_DEFAULT, Plausibility
from wetterdienst.model.relations import (
    DAYLIGHT_MARGIN,
    DEW_POINT_TOLERANCE,
    DEW_POINTS,
    LADDERS,
    RESOLUTIONS,
    SUNSHINE,
    daylight_for,
    relations_for,
)
from wetterdienst.model.sun import daylight_hours
from wetterdienst.model.unit import UnitConverter

UTC = dt.UTC
PAGE = Path(__file__).parent.parent.parent / "docs" / "data" / "plausibility.md"
SOFT = Plausibility()
HARD = Plausibility(relations="hard")
STEPS = {
    "1_minute": dt.timedelta(minutes=1),
    "5_minutes": dt.timedelta(minutes=5),
    "10_minutes": dt.timedelta(minutes=10),
    "15_minutes": dt.timedelta(minutes=15),
    "hourly": dt.timedelta(hours=1),
    "subdaily": dt.timedelta(hours=3),
    "daily": dt.timedelta(days=1),
}
START = dt.datetime(2024, 1, 1, tzinfo=UTC)
DWD = "dwd/observation"
CONVERTER = UnitConverter()


def _dataset(network: str, resolution: str, dataset: str) -> object:
    provider, name = network.split("/")
    for res in Wetterdienst.resolve(provider, name).metadata:
        for candidate in res:
            if (res.name, candidate.name) == (resolution, dataset):
                return candidate
    message = f"{network} has no {resolution}/{dataset}"
    raise AssertionError(message)


def _name(dataset: object, canonical: str) -> str:
    """Give the name the source has for a canonical parameter of a dataset."""
    return next(p.name_original for p in dataset if p.name == canonical)


def _frame(
    dataset: object,
    readings: dict[str, list[float | None]],
    step: dt.timedelta,
    flags: dict[str, list[str | None]] | None = None,
    start: dt.datetime = START,
) -> pl.DataFrame:
    """Give the long frame of the readings of canonical parameters, `{canonical: [value per step]}`."""
    frames = []
    for canonical, values in readings.items():
        stamps = [start + step * i for i in range(len(values))]
        frames.append(
            pl.DataFrame(
                {
                    "parameter": _name(dataset, canonical),
                    "timestamp": stamps,
                    "value": values,
                    "quality_flags": (flags or {}).get(canonical) or [None] * len(values),
                },
                schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
            )
        )
    return pl.concat(frames)


def _judge(
    network: str,
    resolution: str,
    dataset: str,
    readings: dict[str, list[float | None]],
    modes: Plausibility = SOFT,
    flags: dict[str, list[str | None]] | None = None,
    **kwargs: object,
) -> dict[str, list[str | None]]:
    """Judge readings of a dataset and give the `quality_flags` of each canonical parameter, in time order."""
    ds = _dataset(network, resolution, dataset)
    out = judged(_frame(ds, readings, STEPS[resolution], flags), network=network, dataset=ds, modes=modes, **kwargs)
    return {
        canonical: out.filter(pl.col("parameter") == _name(ds, canonical)).sort("timestamp")["quality_flags"].to_list()
        for canonical in readings
    }


def _values(
    network: str,
    resolution: str,
    dataset: str,
    readings: dict[str, list[float | None]],
    modes: Plausibility = SOFT,
    **kwargs: object,
) -> dict[str, list[float | None]]:
    ds = _dataset(network, resolution, dataset)
    out = judged(_frame(ds, readings, STEPS[resolution]), network=network, dataset=ds, modes=modes, **kwargs)
    return {
        canonical: out.filter(pl.col("parameter") == _name(ds, canonical)).sort("timestamp")["value"].to_list()
        for canonical in readings
    }


def _relations(flags: dict[str, list[str | None]]) -> dict[str, list[bool]]:
    """Say, per parameter, which readings carry a token of the check `relations`."""
    return {name: [value is not None and "relations" in value for value in values] for name, values in flags.items()}


# --- the table is a table of sources ------------------------------------------------------------------------------


def test_the_table_names_canonical_parameters_and_the_resolutions_of_a_day_or_less() -> None:
    """Every rung of every ladder and every pair is a canonical parameter; no month and no year is judged."""
    assert set(RESOLUTIONS) == set(STEPS)
    names = {name for ladder in LADDERS for rung in ladder.rungs for name in rung}
    names |= {name for pair in DEW_POINTS for name in pair} | set(SUNSHINE)
    for name in names:
        assert name in PARAMETERS, name
    for ladder in LADDERS:
        assert len(ladder.rungs) >= 2, ladder.quantity
        assert ladder.kind in {"extremes", "gust"}, ladder.quantity
    assert DEW_POINT_TOLERANCE == 0.2
    assert DAYLIGHT_MARGIN == 0.05


def test_the_instantaneous_air_temperature_is_no_partner_of_a_maximum() -> None:
    """A thermometer read at the end of the hour is a sample, not the mean of the hour: the table does not pair it."""
    names = frozenset({"temperature_air_2m", "temperature_air_max_2m", "temperature_air_min_2m"})
    pairs = {(r.high, r.low) for r in relations_for(names, "hourly")}
    assert pairs == {("temperature_air_max_2m", "temperature_air_min_2m")}


def test_the_gust_is_held_to_the_mean_of_its_own_interval_and_not_to_a_rolling_mean() -> None:
    """A gust is paired with the mean wind of the same window by name; the rolling mean is never the gust's partner."""
    names = frozenset({"wind_gust_max", "wind_speed_mean", "wind_speed_rolling_mean_max", "wind_speed_min"})
    pairs = {(r.high, r.low) for r in relations_for(names, "daily")}
    assert ("wind_gust_max", "wind_speed_mean") in pairs
    assert ("wind_gust_max", "wind_speed_rolling_mean_max") not in pairs
    # an hourly gust beside a mean of ten minutes: different windows, no relation
    assert relations_for(frozenset({"wind_gust_max", "wind_speed_mean_last_10min"}), "hourly") == ()
    assert {
        (r.high, r.low)
        for r in relations_for(frozenset({"wind_gust_max_last_10min", "wind_speed_mean_last_10min"}), "hourly")
    } == {("wind_gust_max_last_10min", "wind_speed_mean_last_10min")}


def test_a_month_and_a_year_are_not_judged() -> None:
    """The extremes of a month are computed from the days by the source's own rule: not judged."""
    names = frozenset(
        {"temperature_air_max_2m", "temperature_air_mean_2m", "temperature_air_min_2m", "sunshine_duration"}
    )
    assert relations_for(names, "monthly") == ()
    assert relations_for(names, "annual") == ()
    assert daylight_for(names, "monthly") == ()
    assert relations_for(names, "daily") != ()


# --- every relation of every dataset, at its limit and a little beyond it ----------------------------------------


def _datasets_with_relations() -> list[tuple[str, str, str]]:
    found = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            metadata = Wetterdienst.resolve(provider, network).metadata
            if metadata.kind != "observation":
                continue
            for resolution in metadata:
                for dataset in resolution:
                    if plan_for(f"{provider}/{network}", dataset).relations:
                        found.append((f"{provider}/{network}", resolution.name, dataset.name))
    return found


def _in_unit_of_source(plan: object, name: str, canonical_value: float) -> float:
    conversion = plan.parameters[name]
    if conversion.unit == conversion.canonical:
        return canonical_value
    return CONVERTER.lambda_between(conversion.canonical, conversion.unit)(canonical_value)


_QUIET = {"temperature": 10.0, "pressure": 1000.0, "humidity": 50.0, "wind": 5.0}


def _quiet(canonical: str) -> float:
    if canonical.startswith("temperature"):
        return _QUIET["temperature"]
    if canonical.startswith("pressure"):
        return _QUIET["pressure"]
    if canonical.startswith("humidity"):
        return _QUIET["humidity"]
    return _QUIET["wind"]


@pytest.mark.parametrize(("network", "resolution", "dataset"), _datasets_with_relations())
def test_every_relation_of_every_dataset_flags_both_readings_beyond_its_tolerance(
    network: str, resolution: str, dataset: str
) -> None:
    """At the limit (and at the tolerance) nothing is flagged; a little beyond it, both readings of the pair are."""
    ds = _dataset(network, resolution, dataset)
    plan = plan_for(network, ds)
    assert plan.relations
    for relation in plan.relations:
        high_name = next(p.name for p in ds if p.name_original == relation.high)
        low_name = next(p.name for p in ds if p.name_original == relation.low)
        base = _quiet(high_name)
        for gap, broken in ((0.0, False), (-1.0, False), (relation.tolerance, False), (relation.tolerance + 0.1, True)):
            # a gap is how far the lower reading is above the higher one: positive breaks the order
            readings = {
                high_name: [_in_unit_of_source(plan, relation.high, base)],
                low_name: [_in_unit_of_source(plan, relation.low, base + gap)],
            }
            flags = _judge(network, resolution, dataset, readings)
            hit = _relations(flags)
            assert hit[high_name] == [broken], (relation, gap)
            assert hit[low_name] == [broken], (relation, gap)
            # no other parameter of the frame is touched
            assert len(hit) == 2


# --- the triple, as the issue states it ---------------------------------------------------------------------------


DAILY = (DWD, "daily", "climate_summary")
MAX, MEAN, MIN = "temperature_air_max_2m", "temperature_air_mean_2m", "temperature_air_min_2m"


def test_a_maximum_below_the_mean_flags_the_maximum_and_the_mean_and_not_the_minimum() -> None:
    """The violated pair of a triple is flagged, nothing else: both readings, in the mode `soft`, are kept."""
    out = _judge(*DAILY, {MAX: [10.0], MEAN: [12.0], MIN: [5.0]})
    assert out == {MAX: ["suspect:relations"], MEAN: ["suspect:relations"], MIN: [None]}
    assert _values(*DAILY, {MAX: [10.0], MEAN: [12.0], MIN: [5.0]}) == {MAX: [10.0], MEAN: [12.0], MIN: [5.0]}


def test_a_mean_below_the_minimum_flags_the_mean_and_the_minimum_and_not_the_maximum() -> None:
    """A mean below the minimum flags the mean and the minimum and not the maximum."""
    out = _judge(*DAILY, {MAX: [10.0], MEAN: [4.0], MIN: [5.0]})
    assert out == {MAX: [None], MEAN: ["suspect:relations"], MIN: ["suspect:relations"]}


def test_a_maximum_below_a_minimum_flags_the_pairs_it_breaks() -> None:
    """A maximum of 2, a mean of 2.5, a minimum of 3: both pairs are broken, so all three are flagged."""
    out = _judge(*DAILY, {MAX: [2.0], MEAN: [2.5], MIN: [3.0]})
    assert all(flag == ["suspect:relations"] for flag in out.values())


def test_equal_readings_are_no_violation_whatever_the_rounding() -> None:
    """A mean of a day of one value is that value: the order is not strict, and 0.1 steps compare exactly."""
    assert _relations(_judge(*DAILY, {MAX: [4.2, 0.0], MEAN: [4.2, 0.0], MIN: [4.2, 0.0]})) == {
        MAX: [False, False],
        MEAN: [False, False],
        MIN: [False, False],
    }
    # 0.1 + 0.2 is not 0.3 in a double, and the comparison is made after rounding to six decimals
    flagged = _relations(_judge(*DAILY, {MAX: [0.1 + 0.2], MEAN: [0.3], MIN: [0.3]}))
    assert not any(any(flags) for flags in flagged.values())


def test_a_dataset_without_a_mean_holds_the_maximum_to_the_minimum() -> None:
    """DWD's 10-minute extremes have a maximum and a minimum and no mean in the file: that is the pair."""
    out = _judge(DWD, "10_minutes", "temperature_extreme", {MAX: [4.2, 5.0], MIN: [5.0, 4.0]})
    assert _relations(out) == {MAX: [True, False], MIN: [True, False]}


def test_a_null_mean_leaves_the_pairs_it_is_in_unjudged_and_holds_the_maximum_to_the_minimum() -> None:
    """With the mean null the check stands aside for its pairs, and the maximum and minimum are held to each other."""
    out = _judge(*DAILY, {MAX: [2.0, 9.0], MEAN: [None, None], MIN: [3.0, 3.0]})
    assert _relations(out) == {MAX: [True, False], MEAN: [False, False], MIN: [True, False]}


def test_the_maximum_and_the_minimum_are_held_to_each_other_only_where_the_mean_is_no_reading() -> None:
    """With a mean to judge, the pairs are the adjacent ones: a broken mean flags its pair and not the far reading."""
    out = _judge(*DAILY, {MAX: [10.0, 10.0], MEAN: [12.0, 12.0], MIN: [5.0, 5.0]}, flags={MEAN: [None, "raw:-999"]})
    # the second day's mean is a code: no partner, so the maximum and the minimum are compared, and are in order
    assert _relations(out) == {MAX: [True, False], MEAN: [True, False], MIN: [False, False]}


def test_readings_of_different_timestamps_are_no_pair() -> None:
    """Readings of different timestamps are no pair."""
    ds = _dataset(*DAILY)
    frame = pl.concat(
        [
            _frame(ds, {MAX: [10.0]}, dt.timedelta(days=1)),
            _frame(ds, {MEAN: [12.0]}, dt.timedelta(days=1), start=START + dt.timedelta(days=1)),
        ]
    )
    out = judged(frame, network=DWD, dataset=ds)
    assert out["quality_flags"].is_null().all()


def test_a_code_of_the_source_is_no_partner() -> None:
    """A mean the source wrote as a code (`raw:`) is not a reading: the relation stands aside, however it compares."""
    out = _judge(
        *DAILY,
        {MAX: [10.0, 2.0], MEAN: [12.0, 12.0], MIN: [5.0, 3.0]},
        flags={MEAN: ["raw:-999", "raw:-999"]},
    )
    # the first day's maximum is above its minimum, and the mean is a code: nothing is flagged. The second day's
    # maximum is below the minimum, and that pair is told without the mean
    assert _relations(out) == {MAX: [False, True], MEAN: [False, False], MIN: [False, True]}


def test_a_partner_another_check_judged_bad_is_no_partner() -> None:
    """A mean of 400 degrees (`range`, whatever the mode) is no partner of a maximum, which stays unflagged."""
    for modes in (SOFT, Plausibility.model_validate("hard"), Plausibility(range="soft")):
        out = _judge(*DAILY, {MAX: [10.0, 2.0], MEAN: [400.0, 400.0], MIN: [5.0, 3.0]}, modes=modes)
        assert _relations(out) == {MAX: [False, True], MEAN: [False, False], MIN: [False, True]}
        assert out[MAX][0] is None
        assert "range" in (out[MEAN][0] or "")


# --- modes ---------------------------------------------------------------------------------------------------------


def test_soft_is_the_default_and_flags_without_removing() -> None:
    """Soft is the default and flags without removing."""
    assert Plausibility().relations == "soft"
    assert "relations" in SOFT_BY_DEFAULT
    out = _values(*DAILY, {MAX: [10.0], MEAN: [12.0], MIN: [5.0]})
    assert out[MAX] == [10.0]
    assert out[MEAN] == [12.0]


def test_hard_nulls_both_readings_and_keeps_the_numbers() -> None:
    """In the mode `hard` both readings of the pair are null and the token keeps what the source wrote."""
    flags = _judge(*DAILY, {MAX: [10.0], MEAN: [12.5], MIN: [5.0]}, modes=HARD)
    assert flags[MAX] == ["rejected:relations,raw:10"]
    assert flags[MEAN] == ["rejected:relations,raw:12.5"]
    assert flags[MIN] == [None]
    values = _values(*DAILY, {MAX: [10.0], MEAN: [12.5], MIN: [5.0]}, modes=HARD)
    assert values == {MAX: [None], MEAN: [None], MIN: [5.0]}


def test_a_bare_hard_sets_the_check_and_a_check_named_beside_it_wins() -> None:
    """A bare hard sets the check and a check named beside it wins."""
    bare = Plausibility.model_validate("hard")
    assert bare.relations == "hard"
    beside = Plausibility.model_validate({"relations": "soft"})
    assert beside.relations == "soft"
    out = _judge(*DAILY, {MAX: [10.0], MEAN: [12.0], MIN: [5.0]}, modes=bare)
    assert out[MAX][0].startswith("rejected:relations")
    both = _judge(
        *DAILY,
        {MAX: [10.0], MEAN: [12.0], MIN: [5.0]},
        modes=Plausibility(**{**bare.model_dump(), "relations": "soft"}),
    )
    assert both[MAX] == ["suspect:relations"]


def test_a_forecast_is_judged_soft_and_has_no_relation() -> None:
    """A forecast is a model's output: no relation is judged for it, and `for_forecast` keeps the mode soft."""
    assert HARD.for_forecast().relations == "soft"
    ds = _dataset("dwd/mosmix", "hourly", "large")
    assert not plan_for("dwd/mosmix", ds).relational


def test_a_reading_relations_flagged_carries_no_other_verdict() -> None:
    """A relation's reading has no other verdict in its token.

    The relation is made before `step` and after the others: what they judged bad is no partner, what it flagged is no
    neighbour, so no reading has `relations` and another check in its token.
    """
    # a spike of the daily mean (35 K beside 5 K) that is also above its maximum: only `relations` writes it
    out = _judge(*DAILY, {MAX: [8.0] * 5, MEAN: [5.0, 5.0, 35.0, 5.0, 5.0], MIN: [2.0] * 5})
    assert out[MEAN] == [None, None, "suspect:relations", None, None]
    assert out[MAX][2] == "suspect:relations"


# --- the interaction with `step` ----------------------------------------------------------------------------------


HOURLY = ("meteoswiss/observation", "hourly", "data")


def test_a_reading_a_relation_flagged_is_no_neighbour_of_a_jump() -> None:
    """A good reading a relation flagged is no neighbour: a real spike beside it moves its flag to the next reading."""
    # an hourly mean with a real jump of 35 K at the fourth reading; the third mean is good, but the maximum of 5.0
    # beside it breaks the order, so both are flagged and the third mean is no neighbour of the fourth
    mean = [10.0, 10.0, 10.0, 45.0, 10.0, 10.0]
    maximum = [12.0, 12.0, 5.0, 50.0, 12.0, 12.0]
    out = _judge(*HOURLY, {MEAN: mean, MAX: maximum})
    assert _relations(out)[MEAN] == [False, False, True, False, False, False]
    # the 45.0 has no predecessor one hour away left to jump from, so it is not judged; the 10.0 after it is judged
    # against it, and the flag lands on the good reading
    assert out[MEAN][3] is None
    assert out[MEAN][4] == "suspect:step"


def test_without_the_relation_the_same_spike_is_found_where_it_is() -> None:
    """The same hourly series with no maximum to break the order: the spike is flagged on the middle reading."""
    out = _judge(*HOURLY, {MEAN: [10.0, 10.0, 10.0, 45.0, 10.0, 10.0]})
    assert out[MEAN] == [None, None, None, "suspect:step", None, None]


# --- the dew point, gusts, calm wind ------------------------------------------------------------------------------


def test_the_dew_point_may_exceed_the_air_by_two_tenths_of_a_kelvin_and_no_more() -> None:
    """The dew point may exceed the air by two tenths of a kelvin and no more."""
    air, dew = "temperature_air_2m", "temperature_dew_point_2m"
    ok = _judge(DWD, "hourly", "dew_point", {air: [4.0, 4.0], dew: [4.2, 3.0]})
    assert _relations(ok) == {air: [False, False], dew: [False, False]}
    broken = _judge(DWD, "hourly", "dew_point", {air: [4.0], dew: [4.3]})
    assert _relations(broken) == {air: [True], dew: [True]}


def test_a_dew_point_at_the_air_temperature_in_whole_degrees_is_no_violation() -> None:
    """Fog: a dew point equal to the air, both rounded to whole degrees, is saturation and no mistake."""
    out = _judge(
        DWD,
        "hourly",
        "moisture",
        {"temperature_air_2m": [3.0, 4.0, -2.0], "temperature_dew_point_2m": [3.0, 4.0, -2.0]},
    )
    assert not any(any(flags) for flags in _relations(out).values())


def test_a_gust_below_the_mean_wind_flags_both_and_a_calm_flags_none() -> None:
    """A gust below the mean wind flags both and a calm flags none."""
    gust, mean = "wind_gust_max", "wind_speed_mean"
    out = _judge(*DAILY, {gust: [4.0, 0.0, 6.1], mean: [5.0, 0.0, 6.1]})
    assert _relations(out) == {gust: [True, False, False], mean: [True, False, False]}


def test_a_gust_is_not_held_to_a_rolling_mean_of_ten_minutes() -> None:
    """DWD's 10-minute highest rolling mean exceeds the gust in 1.4 % of the readings: no relation between the two."""
    ds = (DWD, "10_minutes", "wind_extreme")
    gust, rolling, low = "wind_gust_max", "wind_speed_rolling_mean_max", "wind_speed_min"
    out = _judge(*ds, {gust: [0.0, 5.0], rolling: [11.5, 5.5], low: [3.0, 6.0]})
    # the rolling mean above the lowest rolling mean is the order held: 5.5 is below 6.0 at the second reading
    assert _relations(out) == {gust: [False, False], rolling: [False, True], low: [False, True]}


def test_an_hourly_gust_beside_a_mean_of_ten_minutes_is_no_pair() -> None:
    """An hourly gust beside a mean of ten minutes is no pair."""
    out = _judge("aemet/observation", "hourly", "data", {"wind_gust_max": [3.0], "wind_speed_mean_last_10min": [12.0]})
    assert _relations(out) == {"wind_gust_max": [False], "wind_speed_mean_last_10min": [False]}


def test_the_gust_and_the_mean_of_the_same_ten_minutes_are_a_pair() -> None:
    """The gust and the mean of the same ten minutes are a pair."""
    out = _judge(
        "fmi/observation",
        "hourly",
        "data",
        {"wind_gust_max_last_10min": [3.0], "wind_speed_mean_last_10min": [12.0]},
    )
    assert _relations(out) == {"wind_gust_max_last_10min": [True], "wind_speed_mean_last_10min": [True]}


# --- sunshine and the length of the day ---------------------------------------------------------------------------


def _day_length(latitude: float, date: dt.datetime, elevation: float = 0.0) -> float:
    frame = pl.DataFrame({"timestamp": [date]}, schema={"timestamp": pl.Datetime("us", "UTC")})
    return frame.select(daylight_hours(pl.col("timestamp"), latitude, elevation)).item()


def test_the_day_length_agrees_with_the_almanac() -> None:
    """Hamburg at the June solstice, the equator, Tromsø in the polar night and the polar day (sunrise at -0.833)."""
    june = dt.datetime(2024, 6, 21, tzinfo=UTC)
    december = dt.datetime(2024, 12, 21, tzinfo=UTC)
    assert 16.9 < _day_length(53.55, june) < 17.3
    assert 7.0 < _day_length(53.55, december) < 7.5
    assert 12.0 < _day_length(0.0, june) < 12.3
    assert _day_length(69.65, december) == 0.0
    assert _day_length(69.65, june) == 24.0
    assert _day_length(-69.65, december) == 24.0
    assert 0.0 <= _day_length(90.0, june) <= 24.0


def test_a_summit_sees_a_longer_day_than_the_foot_of_its_mountain() -> None:
    """The Zugspitze (2,962 m) lowers the horizon by 1.6 degrees: December's day is 20 to 30 minutes longer on top."""
    december = dt.datetime(2024, 12, 21, tzinfo=UTC)
    foot, top = _day_length(47.42, december), _day_length(47.42, december, 2962.0)
    assert 0.3 < top - foot < 0.6


def test_the_day_is_the_longest_of_three_so_that_a_date_one_day_off_cannot_make_it_too_short() -> None:
    """Tromsø, 2024-01-14: no sun yet by that day, but the next day has some, and the reading is not flagged."""
    assert _day_length(69.65, dt.datetime(2024, 1, 13, tzinfo=UTC)) == 0.0
    assert _day_length(69.65, dt.datetime(2024, 1, 14, tzinfo=UTC)) > 0.0
    assert _day_length(69.65, dt.datetime(2024, 1, 15, tzinfo=UTC)) > _day_length(
        69.65, dt.datetime(2024, 1, 14, tzinfo=UTC)
    )


SUN = "sunshine_duration"


def _sunshine(
    values: list[float | None],
    latitude: float | None,
    date: dt.datetime,
    network: str = DWD,
    resolution: str = "daily",
    dataset: str = "climate_summary",
    modes: Plausibility = SOFT,
    elevation: float | None = None,
    longitude: float | None = 10.0,
) -> list[str | None]:
    ds = _dataset(network, resolution, dataset)
    step = STEPS[resolution]
    position = None if latitude is None or longitude is None else (latitude, longitude)
    frame = _frame(ds, {SUN: values}, step, start=date)
    out = judged(frame, network=network, dataset=ds, modes=modes, position=position, elevation=elevation)
    return out.sort("timestamp")["quality_flags"].to_list()


def test_a_day_of_sunshine_longer_than_the_day_and_five_percent_is_flagged() -> None:
    """A day of sunshine longer than the day and five percent is flagged."""
    june = dt.datetime(2024, 6, 21, tzinfo=UTC)
    limit = _day_length(50.0, june) * (1 + DAYLIGHT_MARGIN)
    assert _sunshine([limit - 0.05], 50.0, june) == [None]
    assert _sunshine([limit + 0.05], 50.0, june) == ["suspect:relations"]


def test_a_hard_verdict_on_the_sunshine_nulls_only_that_reading_and_keeps_its_number() -> None:
    """A hard verdict on the sunshine nulls only that reading and keeps its number."""
    ds = _dataset(DWD, "daily", "climate_summary")
    june = dt.datetime(2024, 6, 21, tzinfo=UTC)
    frame = _frame(ds, {SUN: [19.0]}, STEPS["daily"], start=june)
    out = judged(frame, network=DWD, dataset=ds, modes=HARD, position=(50.0, 10.0))
    assert out["value"].to_list() == [None]
    assert out["quality_flags"].to_list() == ["rejected:relations,raw:19"]


def test_in_the_polar_night_any_sunshine_is_flagged_and_none_is_not() -> None:
    """In the polar night any sunshine is flagged and none is not."""
    december = dt.datetime(2024, 12, 21, tzinfo=UTC)
    assert _sunshine([0.0], 69.65, december) == [None]
    assert _sunshine([0.5], 69.65, december) == ["suspect:relations"]


def test_in_the_polar_day_a_whole_day_of_sunshine_is_fine() -> None:
    """In the polar day a whole day of sunshine is fine."""
    june = dt.datetime(2024, 6, 21, tzinfo=UTC)
    assert _sunshine([24.0], 69.65, june) == [None]


def test_a_summit_is_given_its_longer_day_and_the_foot_is_not() -> None:
    """The Zugspitze's 9.4 hours on a December day are beyond the foot's limit and within its own."""
    december = dt.datetime(2024, 12, 21, tzinfo=UTC)
    value = _day_length(47.42, december, 2962.0) * (1 + DAYLIGHT_MARGIN) - 0.05
    assert value > _day_length(47.42, december) * (1 + DAYLIGHT_MARGIN)
    assert _sunshine([value], 47.42, december, elevation=2962.0) == [None]
    assert _sunshine([value], 47.42, december, elevation=0.0) == ["suspect:relations"]


def test_an_elevation_that_is_no_height_lowers_no_horizon() -> None:
    """An elevation that is no height lowers no horizon."""
    december = dt.datetime(2024, 12, 21, tzinfo=UTC)
    value = _day_length(47.42, december) * (1 + DAYLIGHT_MARGIN) + 0.1
    assert _sunshine([value], 47.42, december, elevation=99999.0) == ["suspect:relations"]
    assert _sunshine([value], 47.42, december, elevation=-9999.0) == ["suspect:relations"]


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(None, 10.0), (50.0, None), (0.0, 0.0), (91.0, 10.0), (50.0, 200.0), (float("nan"), 1.0)],
)
def test_a_station_without_a_usable_position_has_no_day_length(latitude: float | None, longitude: float | None) -> None:
    """A station list that has no position, or the 0, 0 of one that has none, or a number off the globe: aside."""
    december = dt.datetime(2024, 12, 21, tzinfo=UTC)
    assert _sunshine([20.0], latitude, december, longitude=longitude) == [None]


def test_sunshine_in_an_hour_of_the_polar_night_is_flagged() -> None:
    """Hourly sunshine is held to the day as well: it only finds the polar night, where the day is 0."""
    december = dt.datetime(2024, 12, 21, 12, tzinfo=UTC)
    assert _sunshine([0.5], 69.65, december, DWD, "hourly", "sun") == ["suspect:relations"]
    assert _sunshine([0.5], 50.0, dt.datetime(2024, 6, 21, 12, tzinfo=UTC), DWD, "hourly", "sun") == [None]


def test_a_sunshine_a_range_rejected_is_not_judged_by_the_relation() -> None:
    """A sunshine of 80 hours in a day is the range's (hard): the relation stands aside for it."""
    june = dt.datetime(2024, 6, 21, tzinfo=UTC)
    out = _sunshine([80.0], 50.0, june, modes=Plausibility(range="soft"))
    assert out == ["suspect:range"]


# --- where the mean is not of the window of the extremes -------------------------------------------------------


def test_the_daily_temperatures_of_meteofrance_are_not_held_to_each_other() -> None:
    """Bordeaux-Mérignac, 2023-12-01: TX 9.3, TM 8.3, TN 8.5, all good (TN is of another window than the mean)."""
    network, resolution, dataset = "meteofrance/observation", "daily", "core"
    out = _judge(network, resolution, dataset, {MAX: [9.3], MEAN: [8.3], MIN: [8.5]})
    assert out == {MAX: [None], MEAN: [None], MIN: [None]}
    # the maximum against the minimum goes with them: the source gives no window that makes it hold
    assert _relations(_judge(network, resolution, dataset, {MAX: [2.0], MIN: [3.0]})) == {MAX: [False], MIN: [False]}
    # the gust and the mean wind of the day are still held to each other
    wind = _judge(network, resolution, dataset, {"wind_gust_max": [4.0], "wind_speed_mean": [5.0]})
    assert _relations(wind) == {"wind_gust_max": [True], "wind_speed_mean": [True]}
    # the hourly extremes are of one hour, and the 10-minute and daily ones of other networks are untouched
    assert _relations(_judge(network, "hourly", "core", {MAX: [2.0], MIN: [3.0]})) == {MAX: [True], MIN: [True]}
    assert _relations(_judge(*DAILY, {MAX: [10.0], MEAN: [12.0], MIN: [5.0]}))[MAX] == [True]


def test_fmis_daily_mean_is_not_held_to_its_extremes_and_the_extremes_are_held_to_each_other() -> None:
    """FMI, Sodankylä, 2012-11-12: 1.3, -0.1, 0.1: the mean is of one day (P1D), the extremes of 24 hours (PT24H)."""
    network, resolution, dataset = "fmi/observation", "daily", "data"
    out = _judge(network, resolution, dataset, {MAX: [1.3, 2.0], MEAN: [-0.1, 0.0], MIN: [0.1, 3.0]})
    assert _relations(out) == {MAX: [False, True], MEAN: [False, False], MIN: [False, True]}


# --- through the values core: what a request reads and where a station is --------------------------------------


_DAILY_COLUMNS = ["STATIONS_ID", "MESS_DATUM", "QN_3", "FX", "FM", "QN_4", "RSK", "RSKF", "SDK", "SHK_TAG", "NM", "VPM"]
_DAILY_COLUMNS += ["PM", "TMK", "UPM", "TXK", "TNK", "TGK"]


def _daily_product(day: str, **cells: str) -> str:
    """Give the file of one day of DWD's `climate_summary` (the fields of the cells given replace the quiet ones)."""
    quiet = {
        "STATIONS_ID": "44", "MESS_DATUM": day, "QN_3": "10", "FX": "8.3", "FM": "3.2", "QN_4": "3", "RSK": "0.0",
        "RSKF": "0", "SDK": "1.0", "SHK_TAG": "0", "NM": "7.3", "VPM": "6.6", "PM": "1008.7", "TMK": "2.9",
        "UPM": "86.0", "TXK": "4.0", "TNK": "1.2", "TGK": "0.8",
    }  # fmt: skip
    quiet.update(cells)
    return (
        "\n".join(
            ";".join(f"{cell:>8}" for cell in row) + ";eor"
            for row in (_DAILY_COLUMNS, [quiet[c] for c in _DAILY_COLUMNS])
        )
        + "\n"
    )


def test_a_request_for_one_parameter_reads_its_partners_and_is_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asking for the daily maximum alone reads the mean and the minimum, judges the pair and returns the maximum."""
    from tests.provider.value_stubs import _dwd_observation  # noqa: PLC0415

    product = _daily_product("20250101", TXK="10.0", TMK="12.0", TNK="5.0")
    df = _dwd_observation(
        monkeypatch, "daily", "climate_summary", product, parameters=[("daily", "climate_summary", MAX)]
    )
    assert df["parameter"].to_list() == [MAX]
    assert df["value"].to_list() == [10.0]
    assert df["quality_flags"].to_list()[0].endswith("suspect:relations")


def test_a_request_for_a_parameter_in_no_relation_reads_no_partner(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pressure of a day is in no relation: the broken pair beside it is not read, and the answer is unchanged."""
    from tests.provider.value_stubs import _dwd_observation  # noqa: PLC0415

    product = _daily_product("20250101", TXK="10.0", TMK="12.0", TNK="5.0")
    df = _dwd_observation(
        monkeypatch,
        "daily",
        "climate_summary",
        product,
        parameters=[("daily", "climate_summary", "pressure_air_site_mean")],
    )
    assert df["value"].to_list() == [1008.7]
    assert "relations" not in " ".join(df["quality_flags"].drop_nulls().to_list())
    plan = plan_for(DWD, _dataset(*DAILY))
    names = {p.name: p.name_original for p in _dataset(*DAILY)}
    assert plan.read_beside([], {names["pressure_air_site_mean"]}) == set()
    assert plan.read_beside([], {names[MAX]}) == {names[MAX], names[MEAN], names[MIN]}
    assert plan.read_beside([], {names["wind_gust_max"]}) == {names["wind_gust_max"], names["wind_speed_mean"]}


def test_the_elevation_of_the_station_list_lowers_the_horizon_of_the_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """A summit's sunshine in December is within its day and beyond the day at the foot of the mountain.

    The dataset (`daily/solar`) has no station pressure, so the elevation reaches the check by the sunshine alone.
    """
    from tests.provider.value_stubs import _dwd_observation  # noqa: PLC0415

    december = dt.datetime(2024, 12, 21, tzinfo=UTC)
    summit = _day_length(47.421, december, 2956.0) * (1 + DAYLIGHT_MARGIN)
    foot = _day_length(47.421, december, 0.0) * (1 + DAYLIGHT_MARGIN)
    sunshine = round((summit + foot) / 2, 1)
    assert foot < sunshine < summit
    product = (
        "STATIONS_ID;MESS_DATUM;QN_592;ATMO_STRAHL;FD_STRAHL;FG_STRAHL;SD_STRAHL;eor\n"
        f"      44;20241221;      10;      20.0;      30.0;      50.0;    {sunshine};eor\n"
    )

    def flags(elevation: float) -> list[str | None]:
        out = _dwd_observation(
            monkeypatch,
            "daily",
            "solar",
            product,
            year=2024,
            elevation=elevation,
            position=(47.421, 10.9848),
            parameters=[("daily", "solar", SUN)],
        )
        return out["quality_flags"].to_list()

    assert not plan_for(DWD, _dataset(DWD, "daily", "solar")).pressure
    assert "relations" not in (flags(2956.0)[0] or "")
    assert "suspect:relations" in (flags(0.0)[0] or "")


# --- where the check does not run ----------------------------------------------------------------------------------


def test_a_dataset_that_is_collected_a_parameter_at_a_time_has_no_relations() -> None:
    """SMHI's hourly parameters are separate files: a check never downloads a partner, so nothing is judged."""
    ds = _dataset("smhi/observation", "hourly", "data")
    assert not ds.grouped
    plan = plan_for("smhi/observation", ds)
    assert plan.relations == ()
    assert plan.daylight == ()


def test_the_coverage_has_no_network_without_a_relation() -> None:
    """The coverage has no network without a relation."""
    for network in COVERAGE["relations"]:
        provider, name = network.split("/")
        metadata = Wetterdienst.resolve(provider, name).metadata
        assert metadata.kind == "observation", network
        assert any(plan_for(network, dataset).relational for resolution in metadata for dataset in resolution), network


# --- a random series, against a reading-by-reading judge that states the intended behaviour -----------------------


@pytest.mark.parametrize("seed", range(12))
def test_random_daily_series_agree_with_a_reading_by_reading_judge(seed: int) -> None:
    """Nulls, ties and violations: the frame's flags are those of the rules as the issue states them."""
    rng = random.Random(seed)  # noqa: S311
    n = 40
    gust, wind = "wind_gust_max", "wind_speed_mean"
    series = {
        MAX: [rng.choice([None, *range(8)]) for _ in range(n)],
        MEAN: [rng.choice([None, *range(8)]) for _ in range(n)],
        MIN: [rng.choice([None, *range(8)]) for _ in range(n)],
        gust: [rng.choice([None, *range(8)]) for _ in range(n)],
        wind: [rng.choice([None, *range(8)]) for _ in range(n)],
    }
    readings = {k: [None if v is None else float(v) for v in vals] for k, vals in series.items()}
    expected = {k: [False] * n for k in readings}
    for i in range(n):
        pairs = [(MAX, MEAN), (MEAN, MIN), (gust, wind)]
        if readings[MEAN][i] is None:
            # the maximum and the minimum are held to each other where the mean is no reading
            pairs.append((MAX, MIN))
        for high, low in pairs:
            h, lo = readings[high][i], readings[low][i]
            if h is not None and lo is not None and lo > h:
                expected[high][i] = expected[low][i] = True
    # small whole numbers: no jump of a daily temperature is a spike, so `relations` is the only check that speaks
    assert _relations(_judge(*DAILY, readings)) == expected


# --- the page --------------------------------------------------------------------------------------------------


def _page_ladders() -> dict[str, list[str]]:
    text = PAGE.read_text(encoding="utf-8")
    block = text.split("<!-- relations:start -->")[1].split("<!-- relations:end -->")[0]
    rows = {}
    for line in block.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in {"quantity", "---"}:
            continue
        rows[cells[0]] = cells
    return rows


def test_the_relations_on_the_page_are_the_table_of_the_code() -> None:
    """Every ladder and every dew point pair of the code is a row of the page's table, with its parameters."""
    page = _page_ladders()
    for ladder in LADDERS:
        row = page[ladder.quantity][1]
        for rung in ladder.rungs:
            for name in rung:
                assert f"`{name}`" in row, (ladder.quantity, name)
    for air, dew in DEW_POINTS:
        row = page["dew point"][1]
        assert f"`{air}`" in row, air
        assert f"`{dew}`" in row, dew
    assert f"{DEW_POINT_TOLERANCE:g} K" in page["dew point"][2]
    assert f"{DAYLIGHT_MARGIN * 100:g} %" in page["sunshine"][2]
    for ladder in LADDERS:
        assert page[ladder.quantity][2] == "none", ladder.quantity


def test_the_page_tells_relations_from_consistency() -> None:
    """A reader must know which to set: the page says what each does, and that `consistency` is not touched."""
    text = PAGE.read_text(encoding="utf-8")
    section = text.split("### How `relations` differs from `consistency`")[1].split("\n## ")[0].split("\n### ")[0]
    for word in ("hard", "soft", "provider", "both readings", "plausibility_relations", "plausibility_consistency"):
        assert word in section, word
    assert re.search(r"\| `relations` \|[^|]*\| \*\*soft\*\* \|", text)
