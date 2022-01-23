# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum
from typing import Dict, List

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


class DwdObservationDataset(Enum):
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
    MOISTURE = "moisture"
    # subdaily - left out: standard_format
    SOIL = "soil"
    # daily
    CLIMATE_SUMMARY = "kl"
    PRECIPITATION_MORE = "more_precip"
    WATER_EQUIVALENT = "water_equiv"
    WEATHER_PHENOMENA = "weather_phenomena"


RESOLUTION_DATASET_MAPPING: Dict[Resolution, Dict[DwdObservationDataset, List[Period]]] = {
    Resolution.MINUTE_1: {
        DwdObservationDataset.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
    },
    Resolution.MINUTE_10: {
        DwdObservationDataset.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationDataset.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationDataset.TEMPERATURE_EXTREME: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationDataset.WIND_EXTREME: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationDataset.SOLAR: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
        DwdObservationDataset.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
            Period.NOW,
        ],
    },
    Resolution.HOURLY: {
        DwdObservationDataset.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.CLOUD_TYPE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.CLOUDINESS: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.DEW_POINT: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.PRECIPITATION: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.PRESSURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.TEMPERATURE_SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.SOLAR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.SUNSHINE_DURATION: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.VISIBILITY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.WIND_SYNOPTIC: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.MOISTURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.SUBDAILY: {
        DwdObservationDataset.TEMPERATURE_AIR: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.CLOUDINESS: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.MOISTURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.PRESSURE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.VISIBILITY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.WIND: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.DAILY: {
        DwdObservationDataset.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.TEMPERATURE_SOIL: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.SOLAR: [Period.RECENT],
        DwdObservationDataset.WATER_EQUIVALENT: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.MONTHLY: {
        DwdObservationDataset.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
    Resolution.ANNUAL: {
        DwdObservationDataset.CLIMATE_SUMMARY: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.PRECIPITATION_MORE: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
        DwdObservationDataset.WEATHER_PHENOMENA: [
            Period.HISTORICAL,
            Period.RECENT,
        ],
    },
}
