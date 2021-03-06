# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum
from typing import Dict, List

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


class DwdObservationParameterSet(Enum):
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
    Resolution, Dict[DwdObservationParameterSet, List[Period]]
] = {
    Resolution.MINUTE_1: {
        DwdObservationParameterSet.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
    },
    Resolution.MINUTE_10: {
        DwdObservationParameterSet.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationParameterSet.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationParameterSet.TEMPERATURE_EXTREME: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationParameterSet.WIND_EXTREME: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationParameterSet.SOLAR: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationParameterSet.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
    },
    Resolution.HOURLY: {
        DwdObservationParameterSet.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.CLOUD_TYPE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.CLOUDINESS: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.DEW_POINT: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.PRESSURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.TEMPERATURE_SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.SOLAR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.SUNSHINE_DURATION: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.VISIBILITY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.WIND_SYNOPTIC: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.SUBDAILY: {
        DwdObservationParameterSet.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.CLOUDINESS: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.MOISTURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.PRESSURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.VISIBILITY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.DAILY: {
        DwdObservationParameterSet.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.TEMPERATURE_SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.SOLAR: [Period.RECENT],
        DwdObservationParameterSet.WATER_EQUIVALENT: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.MONTHLY: {
        DwdObservationParameterSet.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.ANNUAL: {
        DwdObservationParameterSet.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationParameterSet.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
}
