""" enumeration for parameter """
from enum import Enum


class Parameter(Enum):
    """
    enumeration for different parameter/variables
    measured by dwd weather stations, listed from 1_minute to yearly resolution
    """

    # 1_minute
    PRECIPITATION = "precipitation"
    # 10_minutes - left out: wind_test
    TEMPERATURE_AIR = "air_temperature"
    TEMPERATURE_EXTREME = "extreme_temperature"
    WIND_EXTREME = "extreme_wind"
    SOLAR = "solar"
    WIND = "wind"
    # hourly
    CLOUD_TYPE = "cloud_type"
    CLOUDINESS = "cloudiness"
    DEW_POINT = "dew_point"
    PRESSURE = "pressure"
    TEMPERATURE_SOIL = "soil_temperature"
    SUNSHINE_DURATION = "sun"
    VISIBILITY = "visibility"
    WIND_SYNOPTIC = "wind_synop"
    # subdaily - left out: standard_format
    MOISTURE = "moisture"
    SOIL = "soil"
    # daily
    CLIMATE_SUMMARY = "kl"
    PRECIPITATION_MORE = "more_precip"
    WATER_EQUIVALENT = "water_equiv"
    WEATHER_PHENOMENA = "weather_phenomena"

    # Others
    RADOLAN = "radolan"
