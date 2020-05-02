""" time resolution to parameter mapping """
from typing import Dict, List

from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution

TIME_RESOLUTION_PARAMETER_MAPPING: Dict[TimeResolution, List[List[Parameter], List[PeriodType]]] = {
    TimeResolution.MINUTE_1: [[Parameter.PRECIPITATION],
                              [PeriodType.HISTORICAL,
                               PeriodType.RECENT,
                               PeriodType.NOW]],
    TimeResolution.MINUTE_10: [[Parameter.TEMPERATURE_AIR,
                                Parameter.TEMPERATURE_EXTREME,
                                Parameter.WIND_EXTREME,
                                Parameter.PRECIPITATION,
                                Parameter.SOLAR,
                                Parameter.WIND],
                               [PeriodType.HISTORICAL,
                                PeriodType.RECENT,
                                PeriodType.NOW]],
    TimeResolution.HOURLY: [[Parameter.TEMPERATURE_AIR,
                             Parameter.CLOUD_TYPE,
                             Parameter.CLOUDINESS,
                             Parameter.PRECIPITATION,
                             Parameter.PRESSURE,
                             Parameter.TEMPERATURE_SOIL,
                             Parameter.SOLAR,
                             Parameter.SUNSHINE_DURATION,
                             Parameter.VISBILITY,
                             Parameter.WIND],
                            [PeriodType.HISTORICAL,
                             PeriodType.RECENT,
                             ]],
    TimeResolution.DAILY: [[Parameter.CLIMATE_SUMMARY,
                            Parameter.PRECIPITATION_MORE,
                            Parameter.TEMPERATURE_SOIL,
                            Parameter.SOLAR,
                            Parameter.WATER_EQUIVALENT],
                           [PeriodType.HISTORICAL,
                            PeriodType.RECENT,
                            ]],
    TimeResolution.MONTHLY: [[Parameter.CLIMATE_SUMMARY,
                              Parameter.PRECIPITATION_MORE],
                             [PeriodType.HISTORICAL,
                              PeriodType.RECENT,
                              ]],
    TimeResolution.ANNUAL: [[Parameter.CLIMATE_SUMMARY,
                             Parameter.PRECIPITATION_MORE],
                            [PeriodType.HISTORICAL,
                             PeriodType.RECENT,
                             ]]
}
PARAMETER_WORDLIST_MAPPING: Dict[Parameter, List[List[str]]] = {
    Parameter.TEMPERATURE_SOIL:     [["soil", "boden", "ground"], ["temp"]],
    Parameter.TEMPERATURE_AIR:      [["air", "luft"], ["temp"]],
    Parameter.PRECIPITATION:        [["prec", "nied"]],
    Parameter.TEMPERATURE_EXTREME:  [["extr"], ["temp"]],
    Parameter.WIND_EXTREME:         [["extr"], ["wind"]],
    Parameter.SOLAR:                [["sol"]],
    Parameter.WIND:                 [["wind"]],
    Parameter.CLOUD_TYPE:           [["cloud", "wolke"], ["typ"]],
    Parameter.CLOUDINESS:           [["cloud", "bewölkung", "bewölkung"]],
    Parameter.SUNSHINE_DURATION:    [["sun", "sonne"], ["dur", "dauer"]],
    Parameter.VISBILITY:            [["vis", "sicht"]],
    Parameter.WATER_EQUIVALENT:     [["wat", "was"], ["eq"]],
    Parameter.PRECIPITATION_MORE:   [["more", "mehr"], ["prec", "nied"]],
    Parameter.PRESSURE:             [["press", "druck"]],
    Parameter.CLIMATE_SUMMARY:      [["kl", "cl"]]
}
TIMERESOLUTION_WORDLIST_MAPPING: Dict[TimeResolution, List[List[str]]] = {
    TimeResolution.MINUTE_1:    [["1", "one", "ein"], ["min"]],
    TimeResolution.MINUTE_10:   [["10", "ten", "zehn"], ["min"]],
    TimeResolution.HOURLY:      [["hour", "stünd"]],
    TimeResolution.DAILY:       [["day", "tag", "daily", "täg"]],
    TimeResolution.MONTHLY:     [["month", "monat"]],
    TimeResolution.ANNUAL:      [["year", "jahr", "annual", "jähr"]]
}
PERIODTYPE_WORDLIST_MAPPING: Dict[PeriodType, List[List[str]]] = {
    PeriodType.HISTORICAL:  [["hist"]],
    PeriodType.RECENT:      [["rec", "akt"]],
    PeriodType.NOW:         [["now", "jetzt", "real-time"]]
}