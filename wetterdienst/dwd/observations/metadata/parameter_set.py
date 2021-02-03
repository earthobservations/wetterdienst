# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum
from typing import Dict, List

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


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
    Resolution, Dict[DWDObservationParameterSet, List[Period]]
] = {
    Resolution.MINUTE_1: {
        DWDObservationParameterSet.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
    },
    Resolution.MINUTE_10: {
        DWDObservationParameterSet.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DWDObservationParameterSet.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DWDObservationParameterSet.TEMPERATURE_EXTREME: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DWDObservationParameterSet.WIND_EXTREME: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DWDObservationParameterSet.SOLAR: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DWDObservationParameterSet.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
    },
    Resolution.HOURLY: {
        DWDObservationParameterSet.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.CLOUD_TYPE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.CLOUDINESS: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.DEW_POINT: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.PRESSURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.TEMPERATURE_SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.SOLAR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.SUNSHINE_DURATION: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.VISIBILITY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.WIND_SYNOPTIC: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.SUBDAILY: {
        DWDObservationParameterSet.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.CLOUDINESS: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.MOISTURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.PRESSURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.VISIBILITY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.DAILY: {
        DWDObservationParameterSet.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.TEMPERATURE_SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.SOLAR: [Period.RECENT],
        DWDObservationParameterSet.WATER_EQUIVALENT: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.MONTHLY: {
        DWDObservationParameterSet.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.ANNUAL: {
        DWDObservationParameterSet.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DWDObservationParameterSet.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
}
