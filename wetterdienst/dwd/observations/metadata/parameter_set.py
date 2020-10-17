""" enumeration for parameter """
from enum import Enum
from typing import Dict, List

from wetterdienst.dwd.metadata.time_resolution import DWDObservationTimeResolution
from wetterdienst.dwd.observations.metadata.period_type import PeriodType


class DWDParameterSet(Enum):
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
    DWDObservationTimeResolution, Dict[DWDParameterSet, List[PeriodType]]
] = {
    DWDObservationTimeResolution.MINUTE_1: {
        DWDParameterSet.PRECIPITATION: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
    },
    DWDObservationTimeResolution.MINUTE_10: {
        DWDParameterSet.PRECIPITATION: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        DWDParameterSet.TEMPERATURE_AIR: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        DWDParameterSet.TEMPERATURE_EXTREME: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        DWDParameterSet.WIND_EXTREME: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        DWDParameterSet.SOLAR: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        DWDParameterSet.WIND: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
    },
    DWDObservationTimeResolution.HOURLY: {
        DWDParameterSet.TEMPERATURE_AIR: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.CLOUD_TYPE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.CLOUDINESS: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.DEW_POINT: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.PRECIPITATION: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.PRESSURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.TEMPERATURE_SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.SOLAR: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.SUNSHINE_DURATION: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.VISIBILITY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.WIND: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.WIND_SYNOPTIC: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    DWDObservationTimeResolution.SUBDAILY: {
        DWDParameterSet.TEMPERATURE_AIR: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.CLOUDINESS: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.MOISTURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.PRESSURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.VISIBILITY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.WIND: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    DWDObservationTimeResolution.DAILY: {
        DWDParameterSet.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.TEMPERATURE_SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.SOLAR: [PeriodType.RECENT],
        DWDParameterSet.WATER_EQUIVALENT: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    DWDObservationTimeResolution.MONTHLY: {
        DWDParameterSet.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    DWDObservationTimeResolution.ANNUAL: {
        DWDParameterSet.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        DWDParameterSet.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
}
