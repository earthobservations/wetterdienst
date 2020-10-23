""" enumeration for parameter """
from enum import Enum
from typing import Dict, List

from wetterdienst.dwd.observations.metadata.resolution import DWDObservationResolution
from wetterdienst.dwd.observations.metadata.period import DWDObservationPeriod


class DWDObservationParameterSet(Enum):
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


RESOLUTION_PARAMETER_MAPPING: Dict[
    DWDObservationResolution,
    Dict[DWDObservationParameterSet, List[DWDObservationPeriod]],
] = {
    DWDObservationResolution.MINUTE_1: {
        DWDObservationParameterSet.PRECIPITATION: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
            DWDObservationPeriod.NOW,
        ],
    },
    DWDObservationResolution.MINUTE_10: {
        DWDObservationParameterSet.PRECIPITATION: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
            DWDObservationPeriod.NOW,
        ],
        DWDObservationParameterSet.TEMPERATURE_AIR: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
            DWDObservationPeriod.NOW,
        ],
        DWDObservationParameterSet.TEMPERATURE_EXTREME: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
            DWDObservationPeriod.NOW,
        ],
        DWDObservationParameterSet.WIND_EXTREME: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
            DWDObservationPeriod.NOW,
        ],
        DWDObservationParameterSet.SOLAR: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
            DWDObservationPeriod.NOW,
        ],
        DWDObservationParameterSet.WIND: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
            DWDObservationPeriod.NOW,
        ],
    },
    DWDObservationResolution.HOURLY: {
        DWDObservationParameterSet.TEMPERATURE_AIR: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.CLOUD_TYPE: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.CLOUDINESS: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.DEW_POINT: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.PRECIPITATION: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.PRESSURE: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.TEMPERATURE_SOIL: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.SOLAR: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.SUNSHINE_DURATION: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.VISIBILITY: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.WIND: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.WIND_SYNOPTIC: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
    },
    DWDObservationResolution.SUBDAILY: {
        DWDObservationParameterSet.TEMPERATURE_AIR: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.CLOUDINESS: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.MOISTURE: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.PRESSURE: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.SOIL: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.VISIBILITY: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.WIND: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
    },
    DWDObservationResolution.DAILY: {
        DWDObservationParameterSet.CLIMATE_SUMMARY: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.PRECIPITATION_MORE: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.TEMPERATURE_SOIL: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.SOLAR: [DWDObservationPeriod.RECENT],
        DWDObservationParameterSet.WATER_EQUIVALENT: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.WEATHER_PHENOMENA: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
    },
    DWDObservationResolution.MONTHLY: {
        DWDObservationParameterSet.CLIMATE_SUMMARY: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.PRECIPITATION_MORE: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.WEATHER_PHENOMENA: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
    },
    DWDObservationResolution.ANNUAL: {
        DWDObservationParameterSet.CLIMATE_SUMMARY: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.PRECIPITATION_MORE: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
        DWDObservationParameterSet.WEATHER_PHENOMENA: [
            DWDObservationPeriod.HISTORICAL,
            DWDObservationPeriod.RECENT,
        ],
    },
}
