# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pint
from aenum import Enum, NoAlias


class UnitEnum(Enum, settings=NoAlias):
    pass


REGISTRY = pint.UnitRegistry()

REGISTRY.define("fraction = [] = frac")
REGISTRY.define("percent = 1e-2 frac = pct")
REGISTRY.define("one_eighth = 0.125 frac = 1/8")
REGISTRY.define("beaufort = 1 frac = bft")
REGISTRY.define("significant_weather = 1frac = sign [0..95]")
REGISTRY.define("global_irradiance = 1/80 frac = % [0..80]")
REGISTRY.define("@alias degree = wind_direction = []")


class OriginUnit(Enum):
    DIMENSIONLESS = REGISTRY.dimensionless

    # Length
    MILLIMETER = REGISTRY.millimeter
    CENTIMETER = REGISTRY.centimeter
    METER = REGISTRY.meter
    KILOMETER = REGISTRY.kilometer

    # Partial
    ONE_EIGHTH = REGISTRY.one_eighth
    PERCENT = REGISTRY.percent
    WIND_DIRECTION = REGISTRY.wind_direction
    DEGREE = REGISTRY.degree

    SIGNIFICANT_WEATHER = REGISTRY.significant_weather  # should stay the same in SI

    KILOGRAM_PER_SQUARE_METER = REGISTRY.kilogram / (REGISTRY.meter ** 2)

    # Temperature
    DEGREE_CELSIUS = 1 * REGISTRY.degree_Celsius  # without the "1 *" we get an offset error
    DEGREE_KELVIN = 1 * REGISTRY.degree_Kelvin

    # Speed
    METER_PER_SECOND = REGISTRY.meter / REGISTRY.second
    KILOMETER_PER_HOUR = REGISTRY.kilometer / REGISTRY.hour
    BEAUFORT = REGISTRY.beaufort  # beaufort should always stay beaufort! Calculations to m/s are empirical

    # Pressure
    PASCAL = REGISTRY.pascal
    HECTOPASCAL = REGISTRY.hectopascal
    KILOPASCAL = REGISTRY.kilopascal

    # Time
    SECOND = REGISTRY.second
    MINUTE = REGISTRY.minute
    HOUR = REGISTRY.hour

    # Energy
    GLOBAL_IRRADIANCE = REGISTRY.global_irradiance  # should stay the same in SI
    JOULE_PER_SQUARE_CENTIMETER = REGISTRY.joule / (REGISTRY.centimeter ** 2)
    KILOJOULE_PER_SQUARE_METER = REGISTRY.kilojoule / (REGISTRY.meter ** 2)


class SIUnit(Enum):
    DIMENSIONLESS = REGISTRY.dimensionless

    # Length
    METER = REGISTRY.meter

    # Partial
    PERCENT = REGISTRY.percent
    WIND_DIRECTION = REGISTRY.wind_direction
    DEGREE = REGISTRY.degree

    # Temperature
    DEGREE_KELVIN = 1 * REGISTRY.degree_Kelvin

    # Speed
    METER_PER_SECOND = REGISTRY.meter / REGISTRY.second
    BEAUFORT = REGISTRY.beaufort

    SIGNIFICANT_WEATHER = REGISTRY.significant_weather  # should stay the same in SI

    # Pressure
    PASCAL = REGISTRY.pascal

    # Time
    SECOND = REGISTRY.second

    # Energy
    GLOBAL_IRRADIANCE = REGISTRY.global_irradiance  # should stay the same in SI

    JOULE_PER_SQUARE_METER = REGISTRY.joule / (REGISTRY.meter ** 2)

    # Precipitation
    KILOGRAM_PER_SQUARE_METER = REGISTRY.kilogram / (REGISTRY.meter ** 2)
