# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for unit conversion."""

import math
from itertools import permutations, product

import polars as pl
import pytest

from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.model.unit import UnitConverter


@pytest.fixture
def unit_converter() -> UnitConverter:
    """Provide unit converter."""
    return UnitConverter()


def test_unit_converter_targets_defaults(unit_converter: UnitConverter) -> None:
    """Test that the default targets are as expected."""
    unit_converter_targets_defaults = {k: v.name for k, v in unit_converter.targets.items()}
    assert unit_converter_targets_defaults == {
        "angle": "degree",
        "concentration": "milligram_per_liter",
        "conductivity": "microsiemens_per_centimeter",
        "dimensionless": "dimensionless",
        "duration": "hour",
        "energy_per_area": "megajoule_per_square_meter",
        "fraction": "percent",
        "length_day": "centimeter_day",
        "length_tiny": "millimeter",
        "length_short": "centimeter",
        "mass_per_volume": "gram_per_cubic_meter",
        "length_medium": "meter",
        "length_long": "kilometer",
        "power_per_area": "watt_per_square_meter",
        "precipitation": "millimeter",
        "precipitation_intensity": "millimeter_per_hour",
        "pressure": "hectopascal",
        "significant_weather": "significant_weather",
        "speed": "meter_per_second",
        "temperature": "degree_celsius",
        "temperature_difference": "degree_kelvin",
        "time": "second",
        "turbidity": "nephelometric_turbidity",
        "volume": "cubic_meter",
        "volume_per_time": "cubic_meter_per_second",
        "wind_scale": "beaufort",
        "degree_day": "degree_celsius_day",
        "degree_hour": "degree_celsius_hour",
    }


def test_unit_converter_lambdas_combinations(unit_converter: UnitConverter) -> None:
    """Test that lambdas contain all combinations of each unit."""
    unit_combinations = set()
    for units in unit_converter.units.values():
        unit_names = [unit.name for unit in units]
        for unit_1 in unit_names:
            for unit_2 in unit_names:
                if unit_1 != unit_2:
                    unit_combinations.add((unit_1, unit_2))
    assert unit_converter.lambdas.keys() == unit_combinations, set(unit_converter.lambdas.keys()).symmetric_difference(
        unit_combinations,
    )


def test_unit_converter_update_targets(unit_converter: UnitConverter) -> None:
    """Test that the update_targets method works as expected."""
    unit_converter.update_targets(
        {
            "fraction": "decimal",
            "dimensionless": "dimensionless",  # possible although nothing changes
        },
    )
    assert unit_converter.targets["fraction"].name == "decimal"
    assert unit_converter.targets["dimensionless"].name == "dimensionless"
    lambda_fraction = unit_converter.get_lambda("percent", "fraction")
    assert lambda_fraction(42) == 0.42
    lambda_dimensionless = unit_converter.get_lambda("dimensionless", "dimensionless")
    assert lambda_dimensionless(42) == 42


def test_unit_converter_lambda_dimensionless(unit_converter: UnitConverter) -> None:
    """Test that the lambda function for dimensionless units works as expected."""
    lambda_dimensionless = unit_converter.get_lambda("dimensionless", "dimensionless")
    assert lambda_dimensionless(42) == 42
    assert lambda_dimensionless("foo") == "foo"  # this is not a valid use case but should not raise an error


@pytest.mark.parametrize(
    ("unit", "target", "value", "expected"),
    [
        # angle
        ("degree", "degree", 42, 42),
        ("degree", "radian", 42, 0.7330382858376184),
        ("degree", "gradian", 42, 46.666666666666664),
        ("radian", "degree", 0.733, 41.99780638308934),
        ("radian", "gradian", 0.733, 46.66422931454371),
        # concentration / mass_per_volume
        ("milligram_per_liter", "milligram_per_liter", 42, 42),
        ("milligram_per_liter", "gram_per_liter", 42, 0.042),
        ("gram_per_liter", "milligram_per_liter", 0.042, 42),
        # mg/l and g/m³ are the same quantity, as are g/l and kg/m³
        ("milligram_per_liter", "gram_per_cubic_meter", 42, 42),
        ("gram_per_cubic_meter", "milligram_per_liter", 42, 42),
        ("gram_per_liter", "kilogram_per_cubic_meter", 42, 42),
        ("kilogram_per_cubic_meter", "gram_per_liter", 42, 42),
        ("gram_per_cubic_meter", "gram_per_liter", 42, 0.042),
        ("gram_per_liter", "gram_per_cubic_meter", 0.042, 42),
        ("gram_per_cubic_meter", "kilogram_per_cubic_meter", 42, 0.042),
        ("kilogram_per_cubic_meter", "gram_per_cubic_meter", 0.042, 42),
        ("milligram_per_liter", "kilogram_per_cubic_meter", 42, 0.042),
        ("kilogram_per_cubic_meter", "milligram_per_liter", 0.042, 42),
        # conductivity; 1 S/cm == 100 S/m and 1 µS/cm == 1e-4 S/m, so every cm<->m pair moves the
        # value by 100 in the direction that makes the shorter length the larger number
        ("siemens_per_meter", "siemens_per_meter", 42, 42),
        ("siemens_per_meter", "microsiemens_per_meter", 42, 42000000),
        ("microsiemens_per_meter", "siemens_per_meter", 42000000, 42),
        ("microsiemens_per_centimeter", "siemens_per_meter", 1633, 0.1633),
        ("siemens_per_meter", "microsiemens_per_centimeter", 0.1633, 1633),
        ("microsiemens_per_centimeter", "microsiemens_per_meter", 1633, 163300),
        ("microsiemens_per_meter", "microsiemens_per_centimeter", 163300, 1633),
        ("microsiemens_per_centimeter", "siemens_per_centimeter", 1633, 0.001633),
        ("siemens_per_centimeter", "microsiemens_per_centimeter", 0.001633, 1633),
        ("siemens_per_centimeter", "siemens_per_meter", 0.001633, 0.1633),
        ("siemens_per_meter", "siemens_per_centimeter", 0.1633, 0.001633),
        ("siemens_per_centimeter", "microsiemens_per_meter", 0.001633, 163300),
        ("microsiemens_per_meter", "siemens_per_centimeter", 163300, 0.001633),
        # energy_per_area
        ("joule_per_square_centimeter", "joule_per_square_centimeter", 42, 42),
        ("joule_per_square_centimeter", "joule_per_square_meter", 42, 420000),
        ("joule_per_square_meter", "joule_per_square_centimeter", 420000, 42),
        # 1 MJ/m² is 100 J/cm², 1,000 kJ/m² and 1,000,000 J/m²
        ("joule_per_square_centimeter", "megajoule_per_square_meter", 42, 0.42),
        ("megajoule_per_square_meter", "joule_per_square_centimeter", 0.42, 42),
        ("joule_per_square_meter", "megajoule_per_square_meter", 420000, 0.42),
        ("megajoule_per_square_meter", "joule_per_square_meter", 0.42, 420000),
        ("kilojoule_per_square_meter", "megajoule_per_square_meter", 420, 0.42),
        ("megajoule_per_square_meter", "kilojoule_per_square_meter", 0.42, 420),
        # (energy/time) power_per_area
        ("watt_per_square_centimeter", "watt_per_square_centimeter", 42, 42),
        ("watt_per_square_centimeter", "watt_per_square_meter", 42, 420000),
        ("watt_per_square_meter", "watt_per_square_centimeter", 420000, 42),
        # fraction
        ("decimal", "decimal", 0.42, 0.42),
        ("decimal", "percent", 0.42, 42),
        ("decimal", "one_eighth", 0.42, 3.36),
        ("percent", "decimal", 42, 0.42),
        ("percent", "one_eighth", 42, 3.36),
        ("one_eighth", "decimal", 3, 0.375),
        ("one_eighth", "percent", 3, 37.5),
        # length_short
        ("centimeter", "centimeter", 42, 42),
        ("millimeter", "centimeter", 42, 4.2),
        ("millimeter", "meter", 42, 0.042),
        ("centimeter", "millimeter", 42, 420),
        ("centimeter", "meter", 42, 0.42),
        ("meter", "millimeter", 0.42, 420),
        ("meter", "centimeter", 0.42, 42),
        # length_long
        ("kilometer", "kilometer", 42, 42),
        ("kilometer", "mile", 42, 26.097590073968025),
        ("kilometer", "nautical_mile", 42, 22.67818574514039),
        ("mile", "kilometer", 42, 67.592448),
        ("mile", "nautical_mile", 42, 36.49700215982721),
        ("nautical_mile", "kilometer", 42, 77.784),
        ("nautical_mile", "mile", 42, 48.332736816988785),
        # precipitation
        ("millimeter", "millimeter", 42, 42),
        ("millimeter", "liter_per_square_meter", 42, 42),
        ("liter_per_square_meter", "millimeter", 42, 42),
        # precipitation_intensity. 0.0056 mm/s is what a dwd/road station reports in a shower, its
        # BUFR element being kg m-2 s-1, and 20.16 mm/h is the same rain
        ("millimeter_per_hour", "millimeter_per_hour", 42, 42),
        ("millimeter_per_hour", "liter_per_square_meter_per_hour", 42, 42),
        ("liter_per_square_meter_per_hour", "millimeter_per_hour", 42, 42),
        ("millimeter_per_second", "millimeter_per_hour", 0.0056, 20.16),
        ("millimeter_per_second", "liter_per_square_meter_per_hour", 0.0056, 20.16),
        ("millimeter_per_hour", "millimeter_per_second", 20.16, 0.0056),
        ("liter_per_square_meter_per_hour", "millimeter_per_second", 20.16, 0.0056),
        # pressure
        ("hectopascal", "hectopascal", 42, 42),
        ("pascal", "hectopascal", 4200, 42),
        ("pascal", "kilopascal", 42, 0.042),
        ("hectopascal", "pascal", 42, 4200),
        ("hectopascal", "kilopascal", 42, 4.2),
        ("kilopascal", "pascal", 0.42, 420),
        ("kilopascal", "hectopascal", 0.42, 4.2),
        # speed
        ("meter_per_second", "meter_per_second", 42, 42),
        ("meter_per_second", "kilometer_per_hour", 1, 3.6),
        ("meter_per_second", "knots", 1, 1.9438444924406046),
        ("meter_per_second", "beaufort", 4.2, 2.9333373265075173),
        ("kilometer_per_hour", "meter_per_second", 42, 11.666666666666666),
        ("kilometer_per_hour", "knots", 42, 22.67818574514039),
        ("kilometer_per_hour", "beaufort", 15.12, 2.933337326507517),
        ("knots", "meter_per_second", 42, 21.60666666666667),
        ("knots", "kilometer_per_hour", 42, 77.784),
        ("knots", "beaufort", 4.2, 1.8833064611373287),
        ("beaufort", "meter_per_second", 12, 34.75186740306195),
        ("beaufort", "kilometer_per_hour", 12, 125.10672265102302),
        ("beaufort", "knots", 12, 67.55222605346815),
        # temperature
        ("degree_celsius", "degree_celsius", 42, 42),
        ("degree_celsius", "degree_fahrenheit", 42, 107.6),
        ("degree_celsius", "degree_kelvin", 42, 315.15),
        ("degree_fahrenheit", "degree_celsius", 42, 5.555555555555555),
        ("degree_fahrenheit", "degree_kelvin", 42, 278.7055555555555),
        ("degree_kelvin", "degree_celsius", 42, -231.14999999999998),
        ("degree_kelvin", "degree_fahrenheit", 42, -384.07),
        # time and duration, the same units
        ("second", "second", 42, 42),
        ("second", "minute", 42, 0.7),
        ("second", "hour", 42, 0.011666666666666667),
        ("minute", "second", 42, 2520),
        ("minute", "hour", 42, 0.7),
        ("hour", "second", 42, 151200),
        ("hour", "minute", 42, 2520),
        # volume
        ("cubic_meter", "cubic_meter", 10_809_186, 10_809_186),
        ("cubic_meter", "cubic_hectometer", 10_809_186, 10.809186),
        ("cubic_hectometer", "cubic_meter", 10.809186, 10_809_186),
        # volume_per_time
        ("cubic_meter_per_second", "cubic_meter_per_second", 42, 42),
        ("cubic_meter_per_second", "liter_per_second", 42, 42000),
        ("liter_per_second", "cubic_meter_per_second", 42000, 42),
        # degree_day
        ("degree_celsius_day", "degree_celsius_day", 42, 42),
        ("degree_kelvin_day", "degree_kelvin_day", 42, 42),
        ("degree_fahrenheit_day", "degree_fahrenheit_day", 42, 42),
        ("degree_celsius_day", "degree_kelvin_day", 42, 42),
        ("degree_kelvin_day", "degree_celsius_day", 42, 42),
        ("degree_celsius_day", "degree_fahrenheit_day", 50, 90),
        ("degree_kelvin_day", "degree_fahrenheit_day", 50, 90),
        ("degree_fahrenheit_day", "degree_celsius_day", 90, 50),
        ("degree_fahrenheit_day", "degree_kelvin_day", 90, 50),
        # degree_hour
        ("degree_celsius_hour", "degree_celsius_hour", 42, 42),
        ("degree_celsius_hour", "degree_kelvin_hour", 42, 42),
        ("degree_kelvin_hour", "degree_celsius_hour", 42, 42),
        ("degree_celsius_hour", "degree_fahrenheit_hour", 50, 90),
        ("degree_kelvin_hour", "degree_fahrenheit_hour", 50, 90),
        ("degree_fahrenheit_hour", "degree_celsius_hour", 90, 50),
        ("degree_fahrenheit_hour", "degree_kelvin_hour", 90, 50),
    ],
)
def test_unit_converter_lambdas(
    unit_converter: UnitConverter,
    unit: str,
    target: str,
    value: float,
    expected: float,
) -> None:
    """Test that the lambda functions work as expected."""
    lambda_ = unit_converter._get_lambda(unit, target)  # noqa: SLF001
    assert lambda_(value) == expected


def test_a_temperature_difference_is_kept_in_kelvin_and_gets_no_offset(unit_converter: UnitConverter) -> None:
    """2 K of error is 2.0 K, not the -271.15 that `temperature` makes of it, and no target moves it (GH-3688).

    The unit of `dwd/mosmix` `e_ttt` is kelvin, and the unit type decides which conversion it goes through. A
    difference has the one unit, so it is its only target: the target of a reading does not apply to it, and none
    of the units of a reading can be asked for it.
    """
    values = pl.DataFrame({"v": [2.0, 0.0, 0.5]})
    reading = values.select(unit_converter.get_lambda("degree_kelvin", "temperature")(pl.col("v")))["v"].to_list()
    assert reading == [2.0 - 273.15, -273.15, 0.5 - 273.15]
    difference = values.select(unit_converter.get_lambda("degree_kelvin", "temperature_difference")(pl.col("v")))
    assert difference["v"].to_list() == [2.0, 0.0, 0.5]
    assert unit_converter.get_unit("degree_kelvin", "temperature_difference").symbol == "K"
    assert [unit.name for unit in unit_converter.units["temperature_difference"]] == ["degree_kelvin"]
    unit_converter.update_targets({"temperature": "degree_fahrenheit", "temperature_difference": "degree_kelvin"})
    assert unit_converter.targets["temperature_difference"].name == "degree_kelvin"
    assert unit_converter.get_lambda("degree_kelvin", "temperature_difference")(2.0) == 2.0
    for target in ("degree_celsius", "degree_fahrenheit"):
        with pytest.raises(ValueError, match=rf"Unit {target} not supported for type temperature_difference"):
            unit_converter.update_targets({"temperature_difference": target})


def test_unit_converter_refuses_a_source_only_unit_as_a_target(unit_converter: UnitConverter) -> None:
    """A unit declared for a source cannot be asked for as a target.

    `millimeter_per_second` exists so that `dwd/road` converts what BUFR publishes rather than
    labelling it, and it is not a unit to report values in: KNMI's 0.1 mm/h is 0.0000278 mm/s.
    `get_unit` raised for the unit before it existed, and this keeps the setting failing as loudly
    as it did.
    """
    with pytest.raises(
        ValueError,
        match=r"Unit millimeter_per_second is what a source publishes in and cannot be a target",
    ):
        unit_converter.update_targets({"precipitation_intensity": "millimeter_per_second"})
    assert unit_converter.targets["precipitation_intensity"].name == "millimeter_per_hour"
    # the unit is still there for a source to declare, and converts
    assert unit_converter.get_unit("millimeter_per_second", "precipitation_intensity").symbol == "mm/s"
    assert unit_converter.get_lambda("millimeter_per_second", "precipitation_intensity")(0.0056) == 20.16
    # and asked for under a type it is no unit of, it is reported as that rather than as held back:
    # a typo in `WD_TS_UNIT_TARGETS` wants the list of units the type does have
    with pytest.raises(
        ValueError,
        match=r"Unit millimeter_per_second not supported for type temperature\. Supported units are: "
        r"degree_celsius,degree_kelvin,degree_fahrenheit",
    ):
        unit_converter.update_targets({"temperature": "millimeter_per_second"})


def test_unit_converter_holds_a_source_only_unit_against_its_own_type(unit_converter: UnitConverter) -> None:
    """A source-only unit is named per unit type, a name not belonging to only one.

    Eleven names in this table are shared -- `millimeter` between `precipitation` and all three
    `length_*`, `beaufort` between `speed` and `wind_scale`, the whole mass-per-volume list between
    `concentration` and `mass_per_volume`. Matching on the name alone would make the next source-only
    unit unaskable for every type carrying it, and call it "what a source publishes in" for a type
    where it is an ordinary target.
    """
    for unit_type, name in unit_converter.source_only_units:
        # each entry names a unit the type has, so a typo cannot sit here refusing nothing
        assert unit_converter.get_unit(name, unit_type).name == name
    # and the refusal keys on the pair, `millimeter` standing for the shared names
    converter = UnitConverter()
    converter.source_only_units = frozenset({("precipitation", "millimeter")})
    with pytest.raises(ValueError, match="Unit millimeter is what a source publishes in"):
        converter.update_targets({"precipitation": "millimeter"})
    # `length_short`, whose own default is `centimeter`, so this moves and a name-only match would
    # have refused it. Asserting `precipitation`'s target here would prove nothing: `millimeter` is
    # already its default
    converter.update_targets({"length_short": "millimeter"})
    assert converter.targets["length_short"].name == "millimeter"


def test_unit_converter_update_targets_applies_all_of_a_mapping_or_none(unit_converter: UnitConverter) -> None:
    """A mapping carrying one unusable entry changes no target at all.

    The entries were validated and assigned in one pass, so an unusable one took effect only after
    those before it already had -- and which those were depended on the order the caller happened to
    write them in. `WD_TS_UNIT_TARGETS` is one mapping to a reader, so a rejected one should leave
    the defaults it was meant to replace.
    """
    for targets in (
        {"temperature": "degree_fahrenheit", "precipitation_intensity": "millimeter_per_second"},
        {"temperature": "degree_fahrenheit", "nonsense": "degree_fahrenheit"},
        {"temperature": "degree_fahrenheit", "pressure": "not_a_unit"},
    ):
        with pytest.raises(ValueError):  # noqa: PT011
            unit_converter.update_targets(targets)
        assert unit_converter.targets["temperature"].name == "degree_celsius"
        assert unit_converter.targets["pressure"].name == "hectopascal"
        assert unit_converter.targets["precipitation_intensity"].name == "millimeter_per_hour"


def test_unit_converter_update_targets_invalid(unit_converter: UnitConverter) -> None:
    """Test that the update_targets method raises an error for invalid units."""
    with pytest.raises(
        ValueError,
        match=r"Unit invalid not supported for type dimensionless\. Supported units are: dimensionless",
    ):
        unit_converter.update_targets({"fraction": "percent", "dimensionless": "invalid"})


def test_unit_converter_get_lambda(unit_converter: UnitConverter) -> None:
    """Test retrieval of lambda function."""
    lambda_ = unit_converter.get_lambda("degree_kelvin", "temperature")
    assert lambda_(0) == -273.15


def test_unit_converter_get_lambda_invalid(unit_converter: UnitConverter) -> None:
    """Test retrieval of lambda function for invalid unit."""
    with pytest.raises(ValueError, match="Conversion from invalid to degree_celsius not supported"):
        unit_converter.get_lambda("invalid", "temperature")
    with pytest.raises(ValueError, match="Unit type invalid not supported"):
        unit_converter.get_lambda("degree_kelvin", "invalid")


def test_unit_converter__get_lambda(unit_converter: UnitConverter) -> None:
    """Test retrieval of lambda function (direct unit - unit target combination)."""
    lambda_ = unit_converter._get_lambda("degree_kelvin", "degree_fahrenheit")  # noqa: SLF001
    assert lambda_(0) == -459.66999999999996


def test_unit_converter__get_lambda_invalid(unit_converter: UnitConverter) -> None:
    """Test retrieval of lambda function for invalid unit (direct unit - unit target combination)."""
    with pytest.raises(ValueError, match="Conversion from invalid to degree_fahrenheit not supported"):
        unit_converter._get_lambda("invalid", "degree_fahrenheit")  # noqa: SLF001
    with pytest.raises(ValueError, match="Conversion from degree_kelvin to invalid not supported"):
        unit_converter._get_lambda("degree_kelvin", "invalid")  # noqa: SLF001


def test_conversions_agree_whichever_route_they_take() -> None:
    """Converting a to c directly gives what converting a to b to c gives.

    A conversion table is only consistent if its factors are, and rounded ones are not: `1.609` for
    the kilometre-to-mile ratio put kilometre-to-mile 0.0214% away from the metre-to-mile route,
    `1.151` did the same to the two miles, and `1.944` for the knot -- which every Met Office wind
    speed passes through, the source publishing knots and the target being metres per second --
    left knots-to-metres-per-second 0.0080% from its own kilometres-per-hour route. A round trip
    hid all three, since both directions carried the same rounding.
    """
    unit_converter = UnitConverter()
    for units in unit_converter.units.values():
        names = [unit.name for unit in units]
        for first, second, third in permutations(names, 3):
            lambdas = unit_converter.lambdas
            if not all(pair in lambdas for pair in ((first, second), (second, third), (first, third))):
                continue
            direct = lambdas[(first, third)](100.0)
            via = lambdas[(second, third)](lambdas[(first, second)](100.0))
            assert direct == pytest.approx(via, rel=1e-9), (
                f"{first} -> {third} disagrees with {first} -> {second} -> {third}"
            )


def test_every_pair_of_units_of_a_type_converts() -> None:
    """Every unit of a type converts to every other, which a target override relies on."""
    unit_converter = UnitConverter()
    for unit_type, units in unit_converter.units.items():
        for source, target in permutations([unit.name for unit in units], 2):
            assert (source, target) in unit_converter.lambdas, f"{unit_type}: {source} -> {target}"


def test_converting_to_a_unit_and_back_returns_the_value() -> None:
    """A value converted to another unit and back is the value it started as."""
    unit_converter = UnitConverter()
    for units in unit_converter.units.values():
        for source, target in permutations([unit.name for unit in units], 2):
            forth = unit_converter.lambdas[(source, target)]
            back = unit_converter.lambdas[(target, source)]
            assert back(forth(100.0)) == pytest.approx(100.0, rel=1e-9), f"{source} -> {target} -> {source}"


@pytest.mark.parametrize("value", [0.1, 1.0, 42.0, 1000.0])
def test_decimals_keep_a_reading_whatever_the_target(value: float) -> None:
    """A converted value rounded to its decimals keeps the reading, whichever pair of units it is.

    Asserted over every ordered pair of every unit type rather than a list of the lossy ones, since
    that list is what changes as units are added. Converted back to the source unit, the rounded
    value is within half a step of the third decimal of the reading -- so 5 cm reported in miles is
    not 0.0. Beaufort is a power law, which `decimals` approximates by a factor, so a pair with it
    is only held to keeping something of the reading.
    """
    unit_converter = UnitConverter()
    for unit_type, units in unit_converter.units.items():
        for source, target in product([unit.name for unit in units], repeat=2):
            convert = unit_converter._get_lambda(source, target)  # noqa: SLF001
            # rounded as `_convert_units` rounds, by polars rather than by Python's `round`
            rounded = pl.Series([convert(value)]).round(unit_converter.decimals(source, target)).item()
            assert rounded != 0, f"{unit_type}: {source} -> {target}"
            if "beaufort" in (source, target):
                continue
            back = unit_converter._get_lambda(target, source)(rounded)  # noqa: SLF001
            assert abs(back - value) < 0.5e-3 + 1e-12, f"{unit_type}: {source} -> {target}"


def test_decimals_stay_at_four_unless_a_conversion_shrinks_a_value_by_an_order_of_magnitude() -> None:
    """Four decimals stay where a conversion keeps a value within an order of magnitude, or grows it.

    Those are most of what the default targets do, and their values come back as they did.
    """
    unit_converter = UnitConverter()
    assert unit_converter.decimals("degree_kelvin", "degree_celsius") == 4
    assert unit_converter.decimals("kilometer_per_hour", "meter_per_second") == 4
    assert unit_converter.decimals("meter", "millimeter") == 4
    assert unit_converter.decimals("millimeter", "centimeter") == 5
    assert unit_converter.decimals("percent", "decimal") == 6
    assert unit_converter.decimals("centimeter", "mile") == 9


# What each unit is worth in the SI unit of its quantity, and the offset of its zero from the SI zero: `value_in_si =
# value * factor + offset`. Written down once from the definitions of the units (the mile is 1609.344 m and the
# nautical mile 1852 m by definition, a knot a nautical mile per hour, a litre a thousandth of a cubic metre, a °F
# 5/9 K from a zero at 459.67 °R), not from the converter's own arithmetic, so that a factor that is wrong in both
# directions, or carried through every route alike -- which the round trip and the route tests cannot see -- fails here
# (GH-3702). `pint` gave the same for every pair it can express, run once on 2026-11-02 (not a dependency of the tests).
_SI: dict[str, dict[str, tuple[float, float]]] = {
    # rad
    "angle": {"degree": (math.pi / 180, 0), "radian": (1, 0), "gradian": (math.pi / 200, 0)},
    # kg/m³
    "mass_per_volume": {
        "milligram_per_liter": (1e-3, 0),
        "gram_per_liter": (1, 0),
        "gram_per_cubic_meter": (1e-3, 0),
        "kilogram_per_cubic_meter": (1, 0),
    },
    # S/m
    "conductivity": {
        "microsiemens_per_centimeter": (1e-4, 0),
        "microsiemens_per_meter": (1e-6, 0),
        "siemens_per_centimeter": (100, 0),
        "siemens_per_meter": (1, 0),
    },
    # J/m²
    "energy_per_area": {
        "joule_per_square_centimeter": (1e4, 0),
        "joule_per_square_meter": (1, 0),
        "kilojoule_per_square_meter": (1e3, 0),
        "megajoule_per_square_meter": (1e6, 0),
    },
    # 1
    "fraction": {"decimal": (1, 0), "percent": (0.01, 0), "one_eighth": (0.125, 0)},
    # W/m²
    "power_per_area": {
        "watt_per_square_centimeter": (1e4, 0),
        "watt_per_square_meter": (1, 0),
        "kilowatt_per_square_meter": (1e3, 0),
    },
    # m
    "length_short": {
        "millimeter": (1e-3, 0),
        "centimeter": (1e-2, 0),
        "meter": (1, 0),
        "kilometer": (1e3, 0),
        "mile": (1609.344, 0),
        "nautical_mile": (1852, 0),
    },
    # m (a depth of water: 1 l/m² is 1 mm)
    "precipitation": {"millimeter": (1e-3, 0), "liter_per_square_meter": (1e-3, 0)},
    # m/s (a depth of water per time)
    "precipitation_intensity": {
        "millimeter_per_hour": (1e-3 / 3600, 0),
        "liter_per_square_meter_per_hour": (1e-3 / 3600, 0),
        "millimeter_per_second": (1e-3, 0),
    },
    # Pa
    "pressure": {"pascal": (1, 0), "hectopascal": (100, 0), "kilopascal": (1e3, 0)},
    # m/s; Beaufort is no linear unit and has its own test below
    "speed": {"meter_per_second": (1, 0), "kilometer_per_hour": (1 / 3.6, 0), "knots": (1852 / 3600, 0)},
    # K
    "temperature": {
        "degree_kelvin": (1, 0),
        "degree_celsius": (1, 273.15),
        "degree_fahrenheit": (5 / 9, 273.15 - 32 * 5 / 9),
    },
    # s
    "time": {"second": (1, 0), "minute": (60, 0), "hour": (3600, 0)},
    # m³
    "volume": {"cubic_meter": (1, 0), "cubic_hectometer": (1e6, 0)},
    # m³/s
    "volume_per_time": {"liter_per_second": (1e-3, 0), "cubic_meter_per_second": (1, 0)},
    # K day and K hour: a sum of temperature differences, so a scale and never an offset
    "degree_day": {"degree_celsius_day": (1, 0), "degree_kelvin_day": (1, 0), "degree_fahrenheit_day": (5 / 9, 0)},
    "degree_hour": {"degree_celsius_hour": (1, 0), "degree_kelvin_hour": (1, 0), "degree_fahrenheit_hour": (5 / 9, 0)},
}
# the types that share their list of units with another one
_SI["concentration"] = _SI["mass_per_volume"]
_SI["length_tiny"] = _SI["length_medium"] = _SI["length_long"] = _SI["length_short"]
_SI["duration"] = _SI["time"]
# types with one unit, which no conversion can get wrong
_SI_NOTHING_TO_CONVERT = {
    "dimensionless",
    "length_day",
    "significant_weather",
    "temperature_difference",
    "turbidity",
    "wind_scale",
}


def test_every_unit_type_is_checked_against_the_si_definitions(unit_converter: UnitConverter) -> None:
    """A unit type that has units to convert between has all of them in the reference table."""
    for unit_type, units in unit_converter.units.items():
        if unit_type in _SI_NOTHING_TO_CONVERT:
            assert len(units) == 1, f"{unit_type} has more than one unit, so it has a conversion to check"
            continue
        names = {unit.name for unit in units}
        # beaufort is the one unit with no linear factor, and is checked by the test of its own
        assert names - {"beaufort"} == set(_SI[unit_type]), unit_type


def test_every_conversion_gives_what_the_si_definitions_give(unit_converter: UnitConverter) -> None:
    """Each conversion of each type is the value taken to the SI unit and out again, below, at and above 0.

    This is the check against the definitions of the units that the round trip (which a factor wrong both ways
    passes) and the route test (which a factor wrong on every route passes) are not. It also holds an offset to the
    temperature: a degree day or a degree hour has none, its zero being a temperature difference.
    """
    checked = 0
    for unit_type, units in _SI.items():
        for source, target in permutations(units, 2):
            (source_factor, source_offset), (target_factor, target_offset) = units[source], units[target]
            for value in (-40.0, 0.0, 1.0, 37.5, 12345.678):
                expected = (value * source_factor + source_offset - target_offset) / target_factor
                assert unit_converter.lambdas[source, target](value) == pytest.approx(expected, rel=1e-12, abs=1e-9), (
                    f"{unit_type}: {value} {source} in {target}"
                )
                checked += 1
    assert checked > 900


def test_only_a_temperature_reading_has_an_offset(unit_converter: UnitConverter) -> None:
    """0 of any unit is 0 of every other, except where the unit is a temperature: a scale with a zero of its own.

    Degree days and degree hours are a sum of temperature differences, and a precipitation or a pressure has a true
    zero. A conversion that moves 0 anywhere else is an offset on a quantity that has none (GH-3702).
    """
    for unit_type, units in unit_converter.units.items():
        for source, target in permutations([unit.name for unit in units], 2):
            moved = unit_converter.lambdas[source, target](0.0)
            if unit_type == "temperature":
                # kelvin to Celsius, Celsius to Fahrenheit and so on: every pair of the three has an offset
                assert moved != 0, f"{source} -> {target}"
            else:
                assert moved == 0, f"{unit_type}: {source} -> {target} moves 0 to {moved}"


def test_beaufort_follows_the_wmo_scale(unit_converter: UnitConverter) -> None:
    """The forces of the Beaufort scale meet the class limits of the WMO table, in m/s.

    `v = 0.836 * B^(3/2)` m/s is the scale's own formula; the limits of the forces 1 to 12 (0.3, 1.6, 3.4, 5.5, 8.0,
    10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7 m/s) lie within 0.05 of a force of the half forces 0.5, 1.5, ... 11.5
    that formula gives. The pairs with km/h and knots are held to the same scale through the speed they stand for.
    """
    limits = (0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7)
    for source, to_ms in (("meter_per_second", 1.0), ("kilometer_per_hour", 1 / 3.6), ("knots", 1852 / 3600)):
        to_beaufort = unit_converter.lambdas[source, "beaufort"]
        for force, limit in enumerate(limits):
            assert to_beaufort(limit / to_ms) == pytest.approx(force + 0.5, abs=0.05), (source, limit)
        assert to_beaufort(0.0) == 0.0
    for target, from_ms in (("meter_per_second", 1.0), ("kilometer_per_hour", 3.6), ("knots", 3600 / 1852)):
        for force in range(13):
            assert unit_converter.lambdas["beaufort", target](force) == pytest.approx(0.836 * force**1.5 * from_ms)


def test_a_temperature_is_never_typed_as_what_it_is_not() -> None:
    """A parameter typed `temperature` is a reading of the temperature of something, no error, spread or anomaly.

    A reading has a zero of its own, so a conversion to another scale adds an offset, and a difference of two readings
    has none: 2 K of error is 2 K, never -271.15 °C (GH-3688). The words that make a name a difference are held out of
    the `temperature` type, so that the next spread or standard deviation a source publishes is not declared as a
    reading by accident. The types are the table's: a provider cannot declare another.
    """
    difference_words = {
        "amplitude",
        "anomaly",
        "delta",
        "depression",
        "deviation",
        "difference",
        "error",
        "range",
        "spread",
        "std",
        "uncertainty",
    }
    readings = [parameter for parameter in PARAMETER_TABLE if parameter.unit_type == "temperature"]
    assert readings
    for parameter in readings:
        assert parameter.name.startswith("temperature_"), parameter.name
        assert not difference_words & set(parameter.name.split("_")), parameter.name
    # the two errors that were typed as readings stay what they are; a difference added later joins them
    assert {p.name for p in PARAMETER_TABLE if p.unit_type == "temperature_difference"} >= {
        "error_absolute_temperature_air_2m",
        "error_absolute_temperature_dew_point_2m",
    }


def test_a_length_times_days_has_the_one_unit_and_no_target_moves_it(unit_converter: UnitConverter) -> None:
    """`snow_depth_sum`, the sum of the daily snow depths, is in cm·d whichever length is asked for (GH-3747).

    A length is no depth times days: 1 m of snow for 31 days is 3,100 cm·d, and no length unit reads that. The type has
    the one unit, so it is its own only target, as `temperature_difference` is.
    """
    assert [(unit.name, unit.symbol) for unit in unit_converter.units["length_day"]] == [("centimeter_day", "cm·d")]
    unit_converter.update_targets({"length_short": "meter", "length_medium": "kilometer", "length_tiny": "centimeter"})
    assert unit_converter.targets["length_day"].name == "centimeter_day"
    assert unit_converter.get_lambda("centimeter_day", "length_day")(3100.0) == 3100.0
    for target in ("centimeter", "meter", "millimeter"):
        with pytest.raises(ValueError, match=rf"Unit {target} not supported for type length_day"):
            unit_converter.update_targets({"length_day": target})
    assert PARAMETERS["snow_depth_sum"].unit_type == "length_day"


def test_a_duration_is_in_hours_and_a_period_or_an_offset_in_seconds(unit_converter: UnitConverter) -> None:
    """The unit type `duration` holds the lengths of time, in hours; `time` keeps a period and an offset in seconds.

    A year of sunshine is about 1,700 h and a day 24 h at most: WMO-No. 8 gives sunshine in hours. A wave period
    of 7 s would be 0.0019 h, so it stays with the offset of solar time in `time` (GH-3702).
    """
    assert unit_converter.targets["duration"].name == "hour"
    assert unit_converter.targets["time"].name == "second"
    assert [unit.name for unit in unit_converter.units["duration"]] == ["second", "minute", "hour"]
    assert unit_converter.get_lambda("minute", "duration")(90.0) == 1.5
    assert unit_converter.get_lambda("second", "duration")(5400.0) == 1.5
    assert unit_converter.get_lambda("hour", "duration")(1.5) == 1.5
    assert unit_converter.get_lambda("second", "time")(5400.0) == 5400.0
    unit_converter.update_targets({"duration": "minute"})
    assert unit_converter.targets["time"].name == "second"
    assert unit_converter.get_lambda("hour", "duration")(1.5) == 90.0


def test_the_moved_parameters_have_the_unit_type_of_the_decision_of_gh_3702() -> None:
    """Each parameter that changed its unit type is pinned to the new one, and each family is whole.

    Snow, ice and frozen ground stay in cm (`length_short`); the water levels, the waves and the clearance are metres;
    a film of water on a road is millimetres, in a type of its own: `precipitation` (mm, l/m²) lacks the metre in which
    `dwd/road` writes it.
    """
    types = {parameter.name: parameter.unit_type for parameter in PARAMETER_TABLE}
    durations = {name for name in types if name.startswith("sunshine_duration") and "relative" not in name}
    assert durations == {
        "sunshine_duration",
        "sunshine_duration_last_3h",
        "sunshine_duration_normal",
        "sunshine_duration_uncertainty",
        "sunshine_duration_yesterday",
    }
    for name in (*durations, "precipitation_duration", "leaf_wetness_duration"):
        assert types[name] == "duration", name
    assert {name for name, unit_type in types.items() if unit_type == "time"} == {
        "true_local_time_offset",
        "wave_period",
    }
    lengths = {
        name
        for name in types
        if name.startswith(("stage", "wave_height_")) or name in {"clearance_height", "distance_river_gauge_height"}
    }
    assert lengths == {
        "stage",
        "stage_max",
        "stage_mean",
        "stage_min",
        "wave_height_max",
        "wave_height_significant",
        "clearance_height",
        "distance_river_gauge_height",
    }
    for name in lengths:
        assert types[name] == "length_medium", name
    assert types["water_film_thickness"] == "length_tiny"
    assert types["snow_depth_sum"] == "length_day"
    assert {name for name, unit_type in types.items() if unit_type == "length_short"} == {
        "frozen_ground_layer_base",
        "frozen_ground_layer_thickness",
        "frozen_ground_layer_thickness_max_month",
        "frozen_ground_layer_top",
        "ice_on_water_thickness",
        "snow_depth",
        "snow_depth_mean",
        "snow_depth_sampled",
        "snow_depth_manual",
        "snow_depth_max",
        "snow_depth_new",
        "snow_depth_new_max",
        "snow_depth_new_multiday",
        "snow_depth_new_normal",
        "thawing_thickness_bare_ground",
        "thawing_thickness_bare_ground_max_month",
        "thawing_thickness_plant_cover",
        "thawing_thickness_plant_cover_max_month",
    }


def test_a_film_of_water_has_the_units_of_a_length_and_reads_in_millimetres(unit_converter: UnitConverter) -> None:
    """`dwd/road` writes the film in metres, so its type has the metre: 0.0003 m is 0.3 mm, no longer 0.03 cm."""
    assert unit_converter.get_lambda("meter", "length_tiny")(0.0003) == pytest.approx(0.3)
    unit_converter.update_targets({"length_tiny": "centimeter"})
    assert unit_converter.get_lambda("meter", "length_tiny")(0.0003) == pytest.approx(0.03)


def test_a_sum_of_radiation_is_in_megajoules_and_a_share_in_percent(unit_converter: UnitConverter) -> None:
    """A day of DWD's 1,500 J/cm² is 15 MJ/m²; a humidity of 87 % is 87, the number the source writes (GH-3702)."""
    assert unit_converter.targets["energy_per_area"].name == "megajoule_per_square_meter"
    assert unit_converter.targets["energy_per_area"].symbol == "MJ/m²"
    assert unit_converter.get_lambda("joule_per_square_centimeter", "energy_per_area")(1500.0) == 15.0
    assert unit_converter.get_lambda("kilojoule_per_square_meter", "energy_per_area")(15000.0) == 15.0
    assert unit_converter.targets["fraction"].name == "percent"
    assert unit_converter.get_lambda("percent", "fraction")(87.0) == 87.0
    assert unit_converter.get_lambda("one_eighth", "fraction")(4.0) == 50.0
    unit_converter.update_targets({"energy_per_area": "joule_per_square_centimeter", "fraction": "decimal"})
    assert unit_converter.get_lambda("megajoule_per_square_meter", "energy_per_area")(15.0) == 1500.0
    assert unit_converter.get_lambda("percent", "fraction")(87.0) == 0.87
