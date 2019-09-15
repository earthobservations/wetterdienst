""" enumeration for parameter """
from enum import Enum


class Parameter(Enum):
    """
        enumeration for different parameter/variables
        measured by dwd weather stations
    """
    TEMPERATURE_SOIL = "soil_temperature"
    TEMPERATURE_AIR = "air_temperature"
    PRECIPITATION = "precipitation"
    TEMPERATURE_EXTREME = "extreme_temperature"
    WIND_EXTREME = "extreme_wind"
    SOLAR = "solar"
    WIND = "wind"
    CLOUD_TYPE = "cloud_type"
    CLOUDINESS = "cloudiness"
    SUNSHINE_DURATION = "sun"
    VISBILITY = "visibility"
    WATER_EQUIVALENT = "water_equiv"
    PRECIPITATION_MORE = "more_precip"
    PRESSURE = "pressure"
    CLIMATE_SUMMARY = "kl"
