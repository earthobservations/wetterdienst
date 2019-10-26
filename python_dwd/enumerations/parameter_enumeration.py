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


PARAMETER_WORDLISTS = {
    Parameter.TEMPERATURE_SOIL: [["soil", "boden", "ground"], ["temp"]],
    Parameter.TEMPERATURE_AIR: [["air", "luft"], ["temp"]],
    Parameter.PRECIPITATION: [["prec", "nied"]],
    Parameter.TEMPERATURE_EXTREME: [["extr"], ["temp"]],
    Parameter.WIND_EXTREME: [["extr"], ["wind"]],
    Parameter.SOLAR: [["sol"]],
    Parameter.WIND: [["wind"]],
    Parameter.CLOUD_TYPE: [["cloud", "wolke"], ["typ"]],
    Parameter.CLOUDINESS: [["cloud", "bewölkung", "bewölkung"]],
    Parameter.SUNSHINE_DURATION: [["sun", "sonne"]],
    Parameter.VISBILITY: [["vis", "sicht"]],
    Parameter.WATER_EQUIVALENT: [["wat", "was"], ["eq"]],
    Parameter.PRECIPITATION_MORE: [["more", "mehr"], ["prec", "nied"]],
    Parameter.PRESSURE: [["press", "druck"]],
    Parameter.CLIMATE_SUMMARY: [["kl", "cl"]]
}
