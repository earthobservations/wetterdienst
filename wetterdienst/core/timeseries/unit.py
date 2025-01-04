import math
from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class Unit:
    name: str
    symbol: str


class UnitConverter:
    # dict of unit types and their possible units
    units: dict[str, list[Unit]] = {
        "angle": [
            Unit("degree", "°"),
            Unit("radian", "rad"),
            Unit("gradian", "grad"),
        ],
        "concentration": [
            Unit("milligram_per_liter", "mg/l"), # == g/m³
            Unit("gram_per_liter", "g/l"),
        ],
        "conductivity": [
            Unit("microsiemens_per_meter", "µS/m"),
            Unit("siemens_per_meter", "S/m"),
        ],
        # special unit, don't do any conversion
        "dimensionless": [
            Unit("dimensionless", "-"),
        ],
        "energy_per_area": [
            Unit("joule_per_square_centimeter", "J/cm²"),
            Unit("joule_per_square_meter", "J/m²"),
            Unit("kilojoule_per_square_meter", "kJ/m²"),
        ],
        "fraction": [
            Unit("decimal", "-"),
            Unit("percent", "%"),
            Unit("one_eighth", "1/8"),
        ],
        "power_per_area": [
            Unit("watt_per_square_centimeter", "W/cm²"),
            Unit("watt_per_square_meter", "W/m²"),
            Unit("kilowatt_per_square_meter", "kW/m²"),
        ],
        "length_short": [
            Unit("millimeter", "mm"),
            Unit("centimeter", "cm"),
            Unit("meter", "m"),
        ],
        "length_medium": [
            Unit("meter", "m"),
            Unit("kilometer", "km"),
        ],
        "length_long": [
            Unit("kilometer", "km"),
            Unit("mile", "mi"),
            Unit("nautical_mile", "nmi"),
        ],
        "magnetic_field_strength": [
            Unit("magnetic_field_strength", "A/m"),
        ],
        "precipitation": [
            Unit("millimeter", "mm"),
            Unit("liter_per_square_meter", "l/m²"),
        ],
        "precipitation_intensity": [
            Unit("millimeter_per_hour", "mm/h"),
            Unit("liter_per_square_meter_per_hour", "l/m²/h"),
        ],
        "pressure": [
            Unit("pascal", "Pa"),
            Unit("hectopascal", "hPa"),
            Unit("kilopascal", "kPa"),
        ],
        "significant_weather": [
            Unit("significant_weather", "sign [0..95]"),
        ],
        "speed": [
            Unit("meter_per_second", "m/s"),
            Unit("kilometer_per_hour", "km/h"),
            Unit("knots", "kn"),
            Unit("beaufort", "bft"),
        ],
        "temperature": [
            Unit("degree_celsius", "°C"),
            Unit("degree_kelvin", "K"),
            Unit("degree_fahrenheit", "°F"),
        ],
        "time": [
            Unit("second", "s"),
            Unit("minute", "min"),
            Unit("hour", "h"),
        ],
        "turbidity": [
            Unit("nephelometric_turbidity", "NTU"),
        ],
        "volume_per_time": [
            Unit("liter_per_second", "l/s"),
            Unit("cubic_meter_per_second", "m³/s"),
        ],
        "wave_period": [
            Unit("wave_period", "1/s"),  # TODO: check if this is correct
        ],
        "wind_scale": [
            Unit("beaufort", "bft"),
        ],
    }
    # dict of target unit types and their default unit, default is the first unit in the list, can be changed with
    # update_targets
    targets: dict[str, Unit] = {
        "angle": units["angle"][0],
        "concentration": units["concentration"][0],
        "conductivity": units["conductivity"][1],
        "dimensionless": units["dimensionless"][0],
        "energy_per_area": units["energy_per_area"][0],
        "power_per_area": units["power_per_area"][0],
        "length_short": units["length_short"][1],
        "length_medium": units["length_medium"][0],
        "length_long": units["length_long"][0],
        "fraction": units["fraction"][0],
        "precipitation": units["precipitation"][0],
        "precipitation_intensity": units["precipitation_intensity"][0],
        "pressure": units["pressure"][1],
        "significant_weather": units["significant_weather"][0],
        "speed": units["speed"][0],
        "temperature": units["temperature"][0],
        "time": units["time"][0],
        "turbidity": units["turbidity"][0],
        "volume_per_time": units["volume_per_time"][1],
        "wave_period": units["wave_period"][0],
        "wind_scale": units["wind_scale"][0],
    }
    # dict of lambdas for conversion between units (described by names)
    lambdas: dict[tuple[str, str], Callable[[Any], Any]] = {
        # angle
        ("degree", "radian"): lambda x: x * math.pi / 180,
        ("degree", "gradian"): lambda x: x * 400 / 360,
        ("radian", "degree"): lambda x: x * 180 / math.pi,
        ("radian", "gradian"): lambda x: x * 200 / math.pi,
        ("gradian", "degree"): lambda x: x * 360 / 400,
        ("gradian", "radian"): lambda x: x * math.pi / 200,
        # concentration
        ("milligram_per_liter", "gram_per_liter"): lambda x: x / 1000,
        ("gram_per_liter", "milligram_per_liter"): lambda x: x * 1000,
        # conductivity
        ("microsiemens_per_meter", "siemens_per_meter"): lambda x: x / 1000000,
        ("siemens_per_meter", "microsiemens_per_meter"): lambda x: x * 1000000,
        # energy_per_area
        ("joule_per_square_centimeter", "joule_per_square_meter"): lambda x: x * 10000,
        ("joule_per_square_centimeter", "kilojoule_per_square_meter"): lambda x: x * 10,
        ("joule_per_square_meter", "joule_per_square_centimeter"): lambda x: x / 10000,
        ("joule_per_square_meter", "kilojoule_per_square_meter"): lambda x: x / 1000,
        ("kilojoule_per_square_meter", "joule_per_square_centimeter"): lambda x: x / 10,
        ("kilojoule_per_square_meter", "joule_per_square_meter"): lambda x: x * 1000,
        # (energy/time) power_per_area
        ("watt_per_square_centimeter", "watt_per_square_meter"): lambda x: x * 10000,
        ("watt_per_square_centimeter", "kilowatt_per_square_meter"): lambda x: x * 10,
        ("watt_per_square_meter", "watt_per_square_centimeter"): lambda x: x / 10000,
        ("watt_per_square_meter", "kilowatt_per_square_meter"): lambda x: x / 1000,
        ("kilowatt_per_square_meter", "watt_per_square_centimeter"): lambda x: x / 10,
        ("kilowatt_per_square_meter", "watt_per_square_meter"): lambda x: x * 1000,
        # fraction
        ("decimal", "percent"): lambda x: x * 100,
        ("decimal", "one_eighth"): lambda x: x * 8,
        ("percent", "one_eighth"): lambda x: x / 100 * 8,
        ("percent", "decimal"): lambda x: x / 100,
        ("one_eighth", "percent"): lambda x: x / 8 * 100,
        ("one_eighth", "decimal"): lambda x: x / 8,
        # length_short
        ("millimeter", "centimeter"): lambda x: x / 10,
        ("millimeter", "meter"): lambda x: x / 1000,
        ("centimeter", "millimeter"): lambda x: x * 10,
        ("centimeter", "meter"): lambda x: x / 100,
        ("meter", "millimeter"): lambda x: x * 1000,
        ("meter", "centimeter"): lambda x: x * 100,
        # length_medium
        ("meter", "kilometer"): lambda x: x / 1000,
        ("kilometer", "meter"): lambda x: x * 1000,
        # length_long
        ("kilometer", "mile"): lambda x: x / 1.609,
        ("kilometer", "nautical_mile"): lambda x: x / 1.852,
        ("nautical_mile", "kilometer"): lambda x: x * 1.852,
        ("nautical_mile", "mile"): lambda x: x * 1.151,
        ("mile", "kilometer"): lambda x: x * 1.609,
        ("mile", "nautical_mile"): lambda x: x / 1.151,
        # precipitation
        ("millimeter", "liter_per_square_meter"): lambda x: x,
        ("liter_per_square_meter", "millimeter"): lambda x: x,
        # precipitation_intensity
        ("millimeter_per_hour", "liter_per_square_meter_per_hour"): lambda x: x,
        ("liter_per_square_meter_per_hour", "millimeter_per_hour"): lambda x: x,
        # pressure
        ("pascal", "hectopascal"): lambda x: x / 100,
        ("pascal", "kilopascal"): lambda x: x / 1000,
        ("hectopascal", "pascal"): lambda x: x * 100,
        ("hectopascal", "kilopascal"): lambda x: x / 10,
        ("kilopascal", "pascal"): lambda x: x * 1000,
        ("kilopascal", "hectopascal"): lambda x: x * 10,
        # speed
        ("meter_per_second", "kilometer_per_hour"): lambda x: x * 3.6,
        ("meter_per_second", "knots"): lambda x: x * 1.944,
        ("meter_per_second", "beaufort"): lambda x: (x / 0.836) ** (2 / 3),
        ("kilometer_per_hour", "meter_per_second"): lambda x: x / 3.6,
        ("kilometer_per_hour", "knots"): lambda x: x / 1.852,
        ("kilometer_per_hour", "beaufort"): lambda x: ((x / 3.6 / 0.836) ** (2 / 3)),
        ("knots", "meter_per_second"): lambda x: x / 1.944,
        ("knots", "kilometer_per_hour"): lambda x: x * 1.852,
        ("knots", "beaufort"): lambda x: ((x / 1.944 / 0.836) ** (2 / 3)),
        ("beaufort", "meter_per_second"): lambda x: 0.836 * (x ** (3 / 2)),
        ("beaufort", "kilometer_per_hour"): lambda x: 0.836 * (x ** (3 / 2)) * 3.6,
        ("beaufort", "knots"): lambda x: 0.836 * (x ** (3 / 2)) * 1.944,
        # temperature
        ("degree_kelvin", "degree_celsius"): lambda x: x - 273.15,
        ("degree_kelvin", "degree_fahrenheit"): lambda x: (x - 273.15) * 9 / 5 + 32,
        ("degree_celsius", "degree_kelvin"): lambda x: x + 273.15,
        ("degree_celsius", "degree_fahrenheit"): lambda x: x * 9 / 5 + 32,
        ("degree_fahrenheit", "degree_kelvin"): lambda x: (x - 32) * 5 / 9 + 273.15,
        ("degree_fahrenheit", "degree_celsius"): lambda x: (x - 32) * 5 / 9,
        # time
        ("second", "minute"): lambda x: x / 60,
        ("second", "hour"): lambda x: x / 3600,
        ("minute", "second"): lambda x: x * 60,
        ("minute", "hour"): lambda x: x / 60,
        ("hour", "second"): lambda x: x * 3600,
        ("hour", "minute"): lambda x: x * 60,
        # volume_per_time
        ("liter_per_second", "cubic_meter_per_second"): lambda x: x / 1000,
        ("cubic_meter_per_second", "liter_per_second"): lambda x: x * 1000,
    }

    def update_targets(self, targets: dict[str, str]) -> None:
        for key, value in targets.items():
            if key not in self.targets:
                raise ValueError(f"Unit type {key} not supported")
            # find the unit with the given name
            unit = next((unit for unit in self.units[key] if unit.name == value), None)
            if not unit:
                raise ValueError(f"Unit {value} not supported for type {key}. Supported units are: {', '.join([unit.name for unit in self.units[key]])}")
            self.targets[key] = unit

    def _get_lambda(self, unit: str, unit_target: str) -> Callable[[Any], Any]:
        if unit == unit_target:
            return lambda x: x
        try:
            return self.lambdas[(unit, unit_target)]
        except KeyError:
            raise ValueError(f"Conversion from {unit} to {unit_target} not supported")

    def get_lambda(self, unit: str, unit_type: str) -> Callable[[Any], Any]:
        if unit_type not in self.targets:
            raise ValueError(f"Unit type {unit_type} not supported")
        unit_target = self.targets[unit_type]
        return self._get_lambda(unit, unit_target.name)



if __name__ == "__main__":
    unit_original = "degree_kelvin"
    unit_type = "temperature"
    unit = "degree_celsius"
    
    unit_converter = UnitConverter()
    unit_converter.update_targets(
        {
            "temperature": unit
        }
    )
    converter = unit_converter.get_lambda(unit_original, unit_type)
    print(converter(300))