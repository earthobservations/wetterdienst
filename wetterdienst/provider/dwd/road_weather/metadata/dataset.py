# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class DwdObservationRoadWeatherDataset(Enum):
    """
    enumeration for different parameter/variables
    measured by dwd road weather stations
    """

    ROAD_SURFACE_TEMPERATURE = "roadSurfaceTemperature"
    TEMPERATURE_AIR = "airTemperature"
    ROAD_SURFACE_CONDITION = "roadSurfaceCondition"
    WATER_FILM_THICKNESS = "waterFilmThickness"
    WIND_EXTREME = "maximumWindGustSpeed"
    WIND_EXTREME_DIRECTION = "maximumWindGustDirection"
    WIND_DIRECTION = "windDirection"
    WIND = "windSpeed"
    DEW_POINT = "dewpointTemperature"
    RELATIVE_HUMIDITY = "relativeHumidity"
    TEMPERATURE_SOIL = "soil_temperature"
    VISIBILITY = "visibility"
    PRECIPITATION_TYPE = "precipitationType"
    TOTAL_PRECIPITATION = "totalPrecipitationOrTotalWaterEquivalent"
    INTENSITY_OF_PRECIPITATION = "intensityOfPrecipitation"
    INTENSITY_OF_PHENOMENA = "intensityOfPhenomena"
    HORIZONTAL_VISIBILITY = "horizontalVisibility"
    SHORT_STATION_NAME = "shortStationName"
