""" enumeration for parameter """
from enum import Enum
from typing import Dict, List

from wetterdienst.dwd.observations.metadata.time_resolution import DWDObsTimeResolution
from wetterdienst.dwd.observations.metadata.period_type import DWDObsPeriodType


class DWDObsParameterSet(Enum):
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


TIME_RESOLUTION_PARAMETER_MAPPING: Dict[
    DWDObsTimeResolution, Dict[DWDObsParameterSet, List[DWDObsPeriodType]]
] = {
    DWDObsTimeResolution.MINUTE_1: {
        DWDObsParameterSet.PRECIPITATION: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
            DWDObsPeriodType.NOW,
        ],
    },
    DWDObsTimeResolution.MINUTE_10: {
        DWDObsParameterSet.PRECIPITATION: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
            DWDObsPeriodType.NOW,
        ],
        DWDObsParameterSet.TEMPERATURE_AIR: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
            DWDObsPeriodType.NOW,
        ],
        DWDObsParameterSet.TEMPERATURE_EXTREME: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
            DWDObsPeriodType.NOW,
        ],
        DWDObsParameterSet.WIND_EXTREME: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
            DWDObsPeriodType.NOW,
        ],
        DWDObsParameterSet.SOLAR: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
            DWDObsPeriodType.NOW,
        ],
        DWDObsParameterSet.WIND: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
            DWDObsPeriodType.NOW,
        ],
    },
    DWDObsTimeResolution.HOURLY: {
        DWDObsParameterSet.TEMPERATURE_AIR: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.CLOUD_TYPE: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.CLOUDINESS: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.DEW_POINT: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.PRECIPITATION: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.PRESSURE: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.TEMPERATURE_SOIL: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.SOLAR: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.SUNSHINE_DURATION: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.VISIBILITY: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.WIND: [DWDObsPeriodType.HISTORICAL, DWDObsPeriodType.RECENT],
        DWDObsParameterSet.WIND_SYNOPTIC: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
    },
    DWDObsTimeResolution.SUBDAILY: {
        DWDObsParameterSet.TEMPERATURE_AIR: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.CLOUDINESS: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.MOISTURE: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.PRESSURE: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.SOIL: [DWDObsPeriodType.HISTORICAL, DWDObsPeriodType.RECENT],
        DWDObsParameterSet.VISIBILITY: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.WIND: [DWDObsPeriodType.HISTORICAL, DWDObsPeriodType.RECENT],
    },
    DWDObsTimeResolution.DAILY: {
        DWDObsParameterSet.CLIMATE_SUMMARY: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.PRECIPITATION_MORE: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.TEMPERATURE_SOIL: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.SOLAR: [DWDObsPeriodType.RECENT],
        DWDObsParameterSet.WATER_EQUIVALENT: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.WEATHER_PHENOMENA: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
    },
    DWDObsTimeResolution.MONTHLY: {
        DWDObsParameterSet.CLIMATE_SUMMARY: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.PRECIPITATION_MORE: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.WEATHER_PHENOMENA: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
    },
    DWDObsTimeResolution.ANNUAL: {
        DWDObsParameterSet.CLIMATE_SUMMARY: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.PRECIPITATION_MORE: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
        DWDObsParameterSet.WEATHER_PHENOMENA: [
            DWDObsPeriodType.HISTORICAL,
            DWDObsPeriodType.RECENT,
        ],
    },
}
