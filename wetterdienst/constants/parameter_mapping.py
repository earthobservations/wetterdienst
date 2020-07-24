""" time resolution to parameter mapping """
from typing import Dict, List

from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution

TIME_RESOLUTION_PARAMETER_MAPPING: Dict[
    TimeResolution, Dict[Parameter, List[PeriodType]]
] = {
    TimeResolution.MINUTE_1: {
        Parameter.PRECIPITATION: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
    },
    TimeResolution.MINUTE_10: {
        Parameter.PRECIPITATION: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        Parameter.TEMPERATURE_AIR: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        Parameter.TEMPERATURE_EXTREME: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        Parameter.WIND_EXTREME: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        Parameter.SOLAR: [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        Parameter.WIND: [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
    },
    TimeResolution.HOURLY: {
        Parameter.TEMPERATURE_AIR: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUD_TYPE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUDINESS: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.DEW_POINT: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRESSURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.TEMPERATURE_SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOLAR: [PeriodType.RECENT],
        Parameter.SUNSHINE_DURATION: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.VISIBILITY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND_SYNOPTIC: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.SUBDAILY: {
        Parameter.TEMPERATURE_AIR: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUDINESS: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.MOISTURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRESSURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.VISIBILITY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.DAILY: {
        Parameter.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.TEMPERATURE_SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOLAR: [PeriodType.RECENT],
        Parameter.WATER_EQUIVALENT: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.MONTHLY: {
        Parameter.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.ANNUAL: {
        Parameter.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
}
