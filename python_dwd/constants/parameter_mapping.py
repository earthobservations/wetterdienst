""" time resolution to parameter mapping """
from typing import Dict, List

from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution

TIME_RESOLUTION_PARAMETER_MAPPING: Dict[TimeResolution, Dict[Parameter, List[PeriodType]]] = {
    TimeResolution.MINUTE_1: {
        Parameter.PRECIPITATION:
            [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
    },
    TimeResolution.MINUTE_10: {
        Parameter.PRECIPITATION:
            [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        Parameter.TEMPERATURE_AIR:
            [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        Parameter.TEMPERATURE_EXTREME:
            [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        Parameter.WIND_EXTREME:
            [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        Parameter.SOLAR:
            [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        Parameter.WIND:
            [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
    },
    TimeResolution.HOURLY: {
        Parameter.TEMPERATURE_AIR:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUD_TYPE:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUDINESS:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.DEW_POINT:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRESSURE:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.TEMPERATURE_SOIL:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOLAR:
            [PeriodType.ROW],
        Parameter.SUNSHINE_DURATION:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.VISIBILITY:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND_SYNOPTIC:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.SUBDAILY: {
        Parameter.TEMPERATURE_AIR:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUDINESS:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.MOISTURE:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRESSURE:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOIL:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.VISIBILITY:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND:
            [PeriodType.HISTORICAL, PeriodType.RECENT]
    },
    TimeResolution.DAILY: {
        Parameter.CLIMATE_SUMMARY:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.TEMPERATURE_SOIL:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOLAR:
            [PeriodType.ROW],
        Parameter.WATER_EQUIVALENT:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA:
            [PeriodType.HISTORICAL, PeriodType.RECENT]
    },
    TimeResolution.MONTHLY: {
        Parameter.CLIMATE_SUMMARY:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.ANNUAL: {
        Parameter.CLIMATE_SUMMARY:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA:
            [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
}
PARAMETER_WORDLIST_MAPPING: Dict[Parameter, List[List[str]]] = {
    # 1_minute
    Parameter.PRECIPITATION: [["prec"]],
    # 10_minutes
    Parameter.TEMPERATURE_AIR: [["air"], ["temp"]],
    Parameter.TEMPERATURE_EXTREME: [["extr"], ["temp"]],
    Parameter.WIND_EXTREME: [["extr"], ["wind"]],
    Parameter.SOLAR: [["sol"]],
    Parameter.WIND: [["wind"]],
    # hourly
    Parameter.CLOUD_TYPE: [["cloud", "wolke"], ["typ"]],
    Parameter.CLOUDINESS: [["cloud"]],
    Parameter.DEW_POINT: [["dew", "tau"], ["point", "punkt"]],
    Parameter.PRESSURE: [["press", "druck"]],
    Parameter.TEMPERATURE_SOIL: [["soil", "ground"], ["temp"]],
    Parameter.SUNSHINE_DURATION: [["sun"], ["dur"]],
    Parameter.VISIBILITY: [["vis"]],
    Parameter.WIND_SYNOPTIC: [["wind"], ["synop"]],
    # subdaily
    Parameter.MOISTURE: [["moist"]],
    Parameter.SOIL: [["soil", "ground"]],
    # daily
    Parameter.CLIMATE_SUMMARY: [["cl"]],
    Parameter.PRECIPITATION_MORE: [["more"], ["prec"]],
    Parameter.WATER_EQUIVALENT: [["wat"], ["eq"]],
    Parameter.WEATHER_PHENOMENA: [["weather"], ["phenom"]],
}
TIMERESOLUTION_WORDLIST_MAPPING: Dict[TimeResolution, List[List[str]]] = {
    TimeResolution.MINUTE_1:    [["1", "one"], ["min"]],
    TimeResolution.MINUTE_10:   [["10", "ten"], ["min"]],
    TimeResolution.HOURLY:      [["hour"]],
    TimeResolution.DAILY:       [["day", "daily"]],
    TimeResolution.MONTHLY:     [["month"]],
    TimeResolution.ANNUAL:      [["year", "annual"]]
}
PERIODTYPE_WORDLIST_MAPPING: Dict[PeriodType, List[List[str]]] = {
    PeriodType.HISTORICAL:  [["hist"]],
    PeriodType.RECENT:      [["rec"]],
    PeriodType.NOW:         [["now"]]
}