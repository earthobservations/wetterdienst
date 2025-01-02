from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class Unit:
    name: str
    symbol: str


class UnitConverter:
    # dict of unit types and their possible units
    units: dict[str, list[Unit]] = {
        "concentration": [
            Unit("milligram_per_liter", "mg/l"), # == g/m³
            Unit("gram_per_liter", "g/l"),
        ],
        "conductivity": [
            Unit("microsiemens_per_meter", "µS/m"),
            Unit("siemens_per_meter", "S/m"),
        ],
        "degree": [
            Unit("degree", "°"),
            Unit("radian", "rad"),
            Unit("gradian", "grad"),
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
        "length_long": [
            Unit("kilometer", "km"),
            Unit("nautical_mile", "nmi"),
            Unit("mile", "mi"),
        ],
        "magnetic_field_strength": [
            Unit("magnetic_field_strength", "A/m"),
        ],
        "precipitation": [
            Unit("millimeter", "mm"),
            Unit("liter_per_square_meter", "l/m²"),
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
    }
    # dict of target unit types and their default unit, default is the first unit in the list, can be changed with
    # update_targets
    targets: dict[str, Unit] = {
        "concentration": units["concentration"][0],
        "conductivity": units["conductivity"][1],
        "degree": units["degree"][0],
        "dimensionless": units["dimensionless"][0],
        "energy_per_area": units["energy_per_area"][0],
        "power_per_area": units["power_per_area"][0],
        "length_short": units["length_short"][1],
        "length_long": units["length_long"][0],
        "fraction": units["fraction"][0],
        "precipitation": units["precipitation"][0],
        "pressure": units["pressure"][1],
        "significant_weather": units["significant_weather"][0],
        "speed": units["speed"][0],
        "temperature": units["temperature"][0],
        "time": units["time"][0],
        "turbidity": units["turbidity"][0],
        "volume_per_time": units["volume_per_time"][1],
        "wave_period": units["wave_period"][0],
    }
    # dict of lambdas for conversion between units (described by names)
    lambdas: dict[tuple[str, str], Callable[[Any], Any]] = {
        # concentration
        ("milligram_per_liter", "gram_per_liter"): lambda x: x / 1000,
        ("gram_per_liter", "milligram_per_liter"): lambda x: x * 1000,
        # conductivity
        ("microsiemens_per_meter", "siemens_per_meter"): lambda x: x / 1000000,
        ("siemens_per_meter", "microsiemens_per_meter"): lambda x: x * 1000000,
        # degree
        ("degree", "radian"): lambda x: x * 0.017453292519943295,
        ("degree", "gradian"): lambda x: x * 1.1111111111111112,
        ("radian", "degree"): lambda x: x * 57.29577951308232,
        ("radian", "gradian"): lambda x: x * 63.66197723675813,
        ("gradian", "degree"): lambda x: x * 0.9,
        ("gradian", "radian"): lambda x: x * 0.015707963267948966,
        # energy_per_area
        ("joule_per_square_centimeter", "joule_per_square_meter"): lambda x: x * 10000,
        ("joule_per_square_centimeter", "kilojoule_per_square_meter"): lambda x: x * 10,
        ("joule_per_square_meter", "joule_per_square_centimeter"): lambda x: x / 10000,
        ("joule_per_square_meter", "kilojoule_per_square_meter"): lambda x: x / 1000,
        ("kilojoule_per_square_meter", "joule_per_square_centimeter"): lambda x: x / 10,
        ("kilojoule_per_square_meter", "joule_per_square_meter"): lambda x: x * 1000,
        # fraction
        ("decimal", "percent"): lambda x: x * 100,
        ("decimal", "one_eighth"): lambda x: x * 8,
        ("percent", "one_eighth"): lambda x: x / 100 * 8,
        ("percent", "decimal"): lambda x: x / 100,
        ("one_eighth", "percent"): lambda x: x / 8 * 100,
        ("one_eighth", "decimal"): lambda x: x / 8,
        # power_per_area
        ("watt_per_square_centimeter", "watt_per_square_meter"): lambda x: x * 10000,
        ("watt_per_square_centimeter", "kilowatt_per_square_meter"): lambda x: x * 10,
        ("watt_per_square_meter", "watt_per_square_centimeter"): lambda x: x / 10000,
        ("watt_per_square_meter", "kilowatt_per_square_meter"): lambda x: x / 1000,
        ("kilowatt_per_square_meter", "watt_per_square_centimeter"): lambda x: x / 10,
        ("kilowatt_per_square_meter", "watt_per_square_meter"): lambda x: x * 1000,
        # length_short
        ("millimeter", "centimeter"): lambda x: x / 10,
        ("millimeter", "meter"): lambda x: x / 1000,
        ("centimeter", "millimeter"): lambda x: x * 10,
        ("centimeter", "meter"): lambda x: x / 100,
        ("meter", "millimeter"): lambda x: x * 1000,
        ("meter", "centimeter"): lambda x: x * 100,
        # length_long
        ("kilometer", "nautical_mile"): lambda x: x / 1.852,
        ("kilometer", "mile"): lambda x: x / 1.609344,
        ("nautical_mile", "kilometer"): lambda x: x * 1.852,
        ("nautical_mile", "mile"): lambda x: x * 1.150779,
        ("mile", "kilometer"): lambda x: x * 1.609344,
        ("mile", "nautical_mile"): lambda x: x / 1.150779,
        # precipitation
        ("millimeter", "liter_per_square_meter"): lambda x: x,
        ("liter_per_square_meter", "millimeter"): lambda x: x,
        # pressure
        ("pascal", "hectopascal"): lambda x: x / 100,
        ("pascal", "kilopascal"): lambda x: x / 1000,
        ("hectopascal", "pascal"): lambda x: x * 100,
        ("hectopascal", "kilopascal"): lambda x: x / 10,
        ("kilopascal", "pascal"): lambda x: x * 1000,
        ("kilopascal", "hectopascal"): lambda x: x * 10,
        # speed
        ("meter_per_second", "kilometer_per_hour"): lambda x: x * 3.6,
        ("meter_per_second", "beaufort"): lambda x: 0.836 * (x ** (2 / 3)),
        ("kilometer_per_hour", "meter_per_second"): lambda x: x / 3.6,
        ("kilometer_per_hour", "beaufort"): lambda x: ((x / 0.836) ** (3 / 2)),
        ("beaufort", "meter_per_second"): lambda x: (x / 0.836) ** (3 / 2),
        ("beaufort", "kilometer_per_hour"): lambda x: 0.836 * (x ** (2 / 3)),
        # temperature
        ("degree_kelvin", "degree_celsius"): lambda x: x - 273.15,
        ("degree_kelvin", "degree_fahrenheit"): lambda x: x * 9 / 5 - 459.67,
        ("degree_celsius", "degree_kelvin"): lambda x: x + 273.15,
        ("degree_celsius", "degree_fahrenheit"): lambda x: x * 9 / 5 + 32,
        ("degree_fahrenheit", "degree_kelvin"): lambda x: (x + 459.67) * 5 / 9,
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
        try:
            return self.lambdas[(unit, unit_target)]
        except KeyError:
            raise ValueError(f"Conversion from {unit} to {unit_target} not supported")

    def get_lambda(self, unit: str, unit_type: str) -> Callable[[Any], Any]:
        if unit_type not in self.targets:
            raise ValueError(f"Unit type {unit_type} not supported")
        unit_target = self.targets[unit_type]
        if unit_target.name == unit:
            return lambda x: x
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