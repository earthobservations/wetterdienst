# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that the `aggregation` of a canonical parameter is what its name says (GH-3134).

`CanonicalParameter.aggregation` is written out in the table, not derived from the name at import: a rename
after v1 must not change a value a caller has been given, and nothing is generated at import time. This test is
the derivation. It reads the name by the naming rules (`docs/data/parameters.md`; GH-2614, GH-2657, GH-3151) and
asks the table for the same value, name by name.

What the rules decide is what the *name* states: a `_max`, `_min`, `_mean` or `_sum`, a `count_` or `probability_`
prefix, the `phenology_` dates, and the totals that are totals by nature (`precipitation_amount`,
`sunshine_duration`, `radiation_global`). A plain name (`temperature_air_2m`, `wind_speed`, `snow_depth`) states no
statistic: the naming page defines it as "a reading at one moment, or a source that states no statistic", so the
name cannot say which of the two it is and the table holds `None` ("not stated"). The provider says it, row by
row, where the source does (a later change), never a guess here.

A name the rules cannot decide is `None`, or is in `BY_HAND` with the evidence for the value. `BY_HAND` is not a
way round a rule: a name there may not be decided by the patterns too (`test_by_hand_names_are_not_decided_by_a_rule`).
"""

import re
from typing import get_args

import pytest

from wetterdienst.metadata.parameter_table import (
    AGGREGATION_DEFINITIONS,
    PARAMETER_TABLE,
    PARAMETERS,
    Aggregation,
    CanonicalParameter,
)

# names decided by hand, each with what decides it. The rules below cannot read these: the name carries no word
# for the statistic, but the quantity or the source's wording is clear.
BY_HAND: dict[str, tuple[Aggregation, str]] = {
    # coded or derived values to which no statistic applies
    "climate_correction_factor": ("code", "a factor correcting a degree-day total for the local climate, no statistic"),
    "soil_state_index": ("code", "DWD's coded soil state (`ZUSTAND_BODEN`), a class"),
    "visibility_index": ("code", "a derived index of the visibility, a class"),
    "true_local_time_offset": ("code", "an offset between true and mean local time, a derived value"),
    "temperature_wet_ice_formation": (
        "code",
        'DWD `e_tf_ter`, "Eisansatz bei der Messung der Feuchttemperatur": a YES/NO flag of one reading',
    ),
    # a flag that says whether the phenomenon happened in the interval
    "precipitation_index": ("occurrence", "DWD's `RS_IND`: whether precipitation fell (1) or not (0) in the interval"),
    # the suffix names how the mean is formed (arithmetic, against the vector mean of the direction), not a window
    "wind_speed_arithmetic": ("mean", "the arithmetic mean of the wind speed, as the name says"),
}

# the totals by nature (GH-2614): a quantity that has no value at a moment but only as an accumulation over an
# interval, so its name needs no word for the statistic. An intensity (a rate) is not one, and the ratios of two
# totals (`_relative`) are decided by hand, above
_TOTAL_PREFIXES = (
    "precipitation_amount",
    "evaporation_amount",
    "evapotranspiration",
    "water_equivalent_snow_depth_new",
    "snow_depth_new",
    "wind_movement",
    "precipitation_duration",
    "leaf_wetness_duration",
    "sunshine_duration",
    "cooling_degree",
    "heating_degree",
    "radiation_global",
    "radiation_long_wave_net",
    "radiation_short_wave_net",
    "radiation_sky_",
)
_TOTALS_BY_NATURE = "|".join(_TOTAL_PREFIXES)

# the coded classes: a weather code, a cloud genus, a road state, the method a value was made by
_CODED = (
    r"(^|_)(weather|weather_type|weather_significant|cloud_type_layer\d|road_surface_condition|precipitation_form"
    r"|precipitation_type_flags|cloud_density)(_|$)|_measurement_method$|^weather"
)

# The naming rules, in the order they are read: the first pattern that matches a name decides it. The order is
# part of the rule: the amount of a significant-weather group is an amount before it is a coded `weather`, and the
# direction at the time of the highest gust carries `max` without being one, so it comes before every `max`.
_RULES: tuple[tuple[str, Aggregation], ...] = (
    (r"^precipitation_amount.*significant_weather", "sum"),
    # not a maximum of the direction (a direction has none), but the direction at the moment of the maximum speed
    (r"^wind_direction_gust_max", "at_max"),
    (r"^phenology_", "date"),
    (r"^count_", "count"),
    (r"^probability_", "probability"),
    (r"^error_absolute_|_uncertainty$", "uncertainty"),
    # a difference over the window: the end minus the start, no statistic of the quantity
    (r"_delta_last_3h$", "change"),
    (r"^weather_type_", "occurrence"),
    (_CODED, "code"),
    # `_max_..._mean`: the mean over the days of the daily maximum, as the annual `temperature_air_max_2m_mean`
    (r"_max(_[a-z0-9_]*)?_mean$", "mean_of_max"),
    (r"_min(_[a-z0-9_]*)?_mean$", "mean_of_min"),
    # the highest value of a rolling mean is a maximum, though `mean` is in the name
    (r"rolling_mean_max", "max"),
    (r"(^|_)max(_|$)", "max"),
    (r"(^|_)min(_|$)", "min"),
    (r"(^|_)mean(_|$)", "mean"),
    (r"_sum$", "sum"),
    (rf"^(?!.*_relative)(?!.*_intensity(_mean)?$)({_TOTALS_BY_NATURE})", "sum"),
)


def _by_the_name(name: str, *, quality_flag: bool = False) -> Aggregation | None:
    """Read the statistic a name states, in the order of the naming page; `None` where the name states none."""
    if quality_flag:
        return "code"
    return next((value for pattern, value in _RULES if re.search(pattern, name)), None)


def expected_aggregation(parameter: CanonicalParameter) -> Aggregation | None:
    """Return what the table must hold for `parameter`: the hand-decided value, else what its name states."""
    if parameter.name in BY_HAND:
        return BY_HAND[parameter.name][0]
    return _by_the_name(parameter.name, quality_flag=parameter.quality_flag)


@pytest.mark.parametrize("parameter", PARAMETER_TABLE, ids=lambda parameter: parameter.name)
def test_aggregation_is_what_the_name_states(parameter: CanonicalParameter) -> None:
    """A declared `aggregation` is the one the naming rules read from the name; a name that states none is `None`."""
    assert parameter.aggregation == expected_aggregation(parameter), (
        f"{parameter.name}: the table holds {parameter.aggregation!r}, the naming rules read "
        f"{expected_aggregation(parameter)!r}. Fix the table, or, if the name states no statistic and the "
        "quantity decides, add the name to BY_HAND with the evidence."
    )


def test_by_hand_names_are_not_decided_by_a_rule() -> None:
    """A name in `BY_HAND` is one the rules cannot read: a rule that reads it the same makes the entry redundant."""
    for name, (value, evidence) in BY_HAND.items():
        assert name in PARAMETERS, f"{name} is no canonical name"
        assert evidence, f"{name} has no evidence"
        assert value in get_args(Aggregation), f"{name}: {value!r} is no member"
        assert _by_the_name(name, quality_flag=PARAMETERS[name].quality_flag) != value, (
            f"{name} is decided by the rules as well: drop it from BY_HAND"
        )


def test_every_member_is_defined_and_used() -> None:
    """The members and their definitions agree, and each is held by at least one canonical name."""
    members = set(get_args(Aggregation))
    assert set(AGGREGATION_DEFINITIONS) == members
    assert all(AGGREGATION_DEFINITIONS[member].strip() for member in members)
    # `instant` is no canonical value: the name of a reading is plain, so only a provider can say it (GH-3134)
    used = {parameter.aggregation for parameter in PARAMETER_TABLE}
    assert members - used == {"instant"}
    assert used - members == {None}


def test_a_plain_name_is_not_a_reading() -> None:
    """`instant` is never a canonical value: a plain name says "a reading, or no statistic stated", and stays `None`."""
    assert not [p.name for p in PARAMETER_TABLE if p.aggregation == "instant"]
    for name in ("temperature_air_2m", "humidity_relative", "wind_speed", "pressure_air_site", "snow_depth", "stage"):
        assert PARAMETERS[name].aggregation is None, name


def test_the_rule_reads_the_names_it_is_named_for() -> None:
    """Pin the rule itself on real names that cover each of its branches, so that a change to a pattern is read here."""
    expected: dict[str, Aggregation | None] = {
        "temperature_air_max_2m": "max",
        "temperature_air_min_2m": "min",
        "temperature_air_mean_2m": "mean",
        "temperature_air_max_2m_mean": "mean_of_max",
        "temperature_air_min_2m_mean": "mean_of_min",
        "wind_speed_rolling_mean_max": "max",
        "wind_gust_max_last_1h": "max",
        "wind_direction_gust_max": "at_max",
        "wind_direction_gust_max_1min": "at_max",
        "precipitation_amount": "sum",
        "precipitation_amount_normal": "sum",
        "sunshine_duration": "sum",
        "snow_depth_sum": "sum",
        "count_days_frost": "count",
        "pressure_air_site_delta_last_3h": "change",
        "temperature_air_2m": None,
        "humidity_relative": None,
        "wind_speed": None,
    }
    for name, value in expected.items():
        assert name in PARAMETERS, name
        assert _by_the_name(name, quality_flag=False) == value, name
    assert _by_the_name("anything", quality_flag=True) == "code"
    # a prefix decides on its own, whatever the rest of the name says
    for prefix, value in (("probability_", "probability"), ("phenology_", "date"), ("count_", "count")):
        names = [p.name for p in PARAMETER_TABLE if p.name.startswith(prefix)]
        assert names
        assert {PARAMETERS[name].aggregation for name in names} == {value}
