import pytest

from wetterdienst.core.timeseries.unit import UnitConverter


@pytest.fixture
def unit_converter():
    return UnitConverter()


def test_unit_converter_targets_defaults(unit_converter):
    """test that the default targets are as expected"""
    unit_converter_targets_defaults = {k: v.name for k, v in unit_converter.targets.items()}
    assert unit_converter_targets_defaults == {
        "angle": "degree",
        "concentration": "milligram_per_liter",
        "conductivity": "siemens_per_meter",
        "dimensionless": "dimensionless",
        "energy_per_area": "joule_per_square_centimeter",
        "fraction": "decimal",
        "length_short": "centimeter",
        "length_medium": "meter",
        "length_long": "kilometer",
        "magnetic_field_intensity": "magnetic_field_strength",
        "power_per_area": "watt_per_square_centimeter",
        "precipitation": "millimeter",
        "precipitation_intensity": "millimeter_per_hour",
        "pressure": "hectopascal",
        "significant_weather": "significant_weather",
        "speed": "meter_per_second",
        "temperature": "degree_celsius",
        "time": "second",
        "turbidity": "nephelometric_turbidity",
        "volume_per_time": "cubic_meter_per_second",
        "wave_period": "wave_period",
        "wind_scale": "beaufort",
    }


def test_unit_converter_lambdas_combinations(unit_converter):
    """test that lambdas contain all combinations of each unit"""
    unit_combinations = set()
    for units in unit_converter.units.values():
        unit_names = [unit.name for unit in units]
        for unit_1 in unit_names:
            for unit_2 in unit_names:
                if unit_1 != unit_2:
                    unit_combinations.add((unit_1, unit_2))
    assert unit_converter.lambdas.keys() == unit_combinations, set(unit_converter.lambdas.keys()).symmetric_difference(
        unit_combinations
    )


def test_unit_converter_update_targets(unit_converter):
    """test that the update_targets method works as expected"""
    unit_converter.update_targets(
        {
            "fraction": "percent",
            "dimensionless": "dimensionless",  # possible although nothing changes
        }
    )
    assert unit_converter.targets["fraction"].name == "percent"
    assert unit_converter.targets["dimensionless"].name == "dimensionless"
    lambda_fraction = unit_converter.get_lambda("decimal", "fraction")
    assert lambda_fraction(0.42) == 42
    lambda_dimensionless = unit_converter.get_lambda("dimensionless", "dimensionless")
    assert lambda_dimensionless(42) == 42


def test_unit_converter_lambda_dimensionless(unit_converter):
    """test that the lambda function for dimensionless units works as expected"""
    lambda_dimensionless = unit_converter.get_lambda("dimensionless", "dimensionless")
    assert lambda_dimensionless(42) == 42
    assert lambda_dimensionless("foo") == "foo"  # this is not a valid use case but should not raise an error


@pytest.mark.parametrize(
    "unit, target, value, expected",
    [
        # angle
        ("degree", "degree", 42, 42),
        ("degree", "radian", 42, 0.7330382858376184),
        ("degree", "gradian", 42, 46.666666666666664),
        ("radian", "degree", 0.733, 41.99780638308934),
        ("radian", "gradian", 0.733, 46.66422931454371),
        # concentration
        ("milligram_per_liter", "milligram_per_liter", 42, 42),
        ("milligram_per_liter", "gram_per_liter", 42, 0.042),
        ("gram_per_liter", "milligram_per_liter", 0.042, 42),
        # conductivity
        ("siemens_per_meter", "siemens_per_meter", 42, 42),
        ("siemens_per_meter", "microsiemens_per_meter", 42, 42000000),
        ("microsiemens_per_meter", "siemens_per_meter", 42000000, 42),
        # energy_per_area
        ("joule_per_square_centimeter", "joule_per_square_centimeter", 42, 42),
        ("joule_per_square_centimeter", "joule_per_square_meter", 42, 420000),
        ("joule_per_square_meter", "joule_per_square_centimeter", 420000, 42),
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
        ("kilometer", "mile", 42, 26.10316967060286),
        ("kilometer", "nautical_mile", 42, 22.67818574514039),
        ("mile", "kilometer", 42, 67.578),
        ("mile", "nautical_mile", 42, 36.490008688097305),
        ("nautical_mile", "kilometer", 42, 77.784),
        ("nautical_mile", "mile", 42, 48.342),
        # precipitation
        ("millimeter", "millimeter", 42, 42),
        ("millimeter", "liter_per_square_meter", 42, 42),
        ("liter_per_square_meter", "millimeter", 42, 42),
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
        ("meter_per_second", "knots", 1, 1.944),
        ("meter_per_second", "beaufort", 4.2, 2.9333373265075173),
        ("kilometer_per_hour", "meter_per_second", 42, 11.666666666666666),
        ("kilometer_per_hour", "knots", 42, 22.67818574514039),
        ("kilometer_per_hour", "beaufort", 15.12, 2.933337326507517),
        ("knots", "meter_per_second", 42, 21.60493827160494),
        ("knots", "kilometer_per_hour", 42, 77.784),
        ("knots", "beaufort", 4.2, 1.8832060248217928),
        ("beaufort", "meter_per_second", 12, 34.75186740306195),
        ("beaufort", "kilometer_per_hour", 12, 125.10672265102302),
        ("beaufort", "knots", 12, 67.55763023155244),
        # temperature
        ("degree_celsius", "degree_celsius", 42, 42),
        ("degree_celsius", "degree_fahrenheit", 42, 107.6),
        ("degree_celsius", "degree_kelvin", 42, 315.15),
        ("degree_fahrenheit", "degree_celsius", 42, 5.555555555555555),
        ("degree_fahrenheit", "degree_kelvin", 42, 278.7055555555555),
        ("degree_kelvin", "degree_celsius", 42, -231.14999999999998),
        ("degree_kelvin", "degree_fahrenheit", 42, -384.07),
        # time
        ("second", "second", 42, 42),
        ("second", "minute", 42, 0.7),
        ("second", "hour", 42, 0.011666666666666667),
        ("minute", "second", 42, 2520),
        ("minute", "hour", 42, 0.7),
        ("hour", "second", 42, 151200),
        ("hour", "minute", 42, 2520),
        # volume_per_time
        ("cubic_meter_per_second", "cubic_meter_per_second", 42, 42),
        ("cubic_meter_per_second", "liter_per_second", 42, 42000),
        ("liter_per_second", "cubic_meter_per_second", 42000, 42),
    ],
)
def test_unit_converter_lambdas(unit_converter, unit, target, value, expected):
    """test that the lambda functions work as expected"""
    lambda_ = unit_converter._get_lambda(unit, target)
    assert lambda_(value) == expected


def test_unit_converter_update_targets_invalid(unit_converter):
    """test that the update_targets method raises an error for invalid units"""
    with pytest.raises(ValueError):
        unit_converter.update_targets({"fraction": "percent", "dimensionless": "invalid"})


def test_unit_converter_get_lambda(unit_converter):
    """test retrieval of lambda function"""
    lambda_ = unit_converter.get_lambda("degree_kelvin", "temperature")
    assert lambda_(0) == -273.15


def test_unit_converter_get_lambda_invalid(unit_converter):
    """test retrieval of lambda function for invalid unit"""
    with pytest.raises(ValueError):
        unit_converter.get_lambda("invalid", "temperature")
    with pytest.raises(ValueError):
        unit_converter.get_lambda("degree_kelvin", "invalid")


def test_unit_converter__get_lambda(unit_converter):
    """test retrieval of lambda function (direct unit - unit target combination)"""
    lambda_ = unit_converter._get_lambda("degree_kelvin", "degree_fahrenheit")
    assert lambda_(0) == -459.66999999999996


def test_unit_converter__get_lambda_invalid(unit_converter):
    """test retrieval of lambda function for invalid unit (direct unit - unit target combination)"""
    with pytest.raises(ValueError):
        unit_converter._get_lambda("invalid", "degree_fahrenheit")
    with pytest.raises(ValueError):
        unit_converter._get_lambda("degree_kelvin", "invalid")
