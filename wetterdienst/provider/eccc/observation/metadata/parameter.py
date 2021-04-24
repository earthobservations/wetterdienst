# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.provider.eccc.observation.metadata.dataset import (
    EcccObservationDatasetTree,
)
from wetterdienst.util.parameter import DatasetTreeCore


class EcccObservationParameter(DatasetTreeCore):
    class HOURLY(Enum):
        TEMPERATURE_AIR_200 = (
            EcccObservationDatasetTree.HOURLY.TEMPERATURE_AIR_200.value
        )
        TEMPERATURE_DEW_POINT_200 = (
            EcccObservationDatasetTree.HOURLY.TEMPERATURE_DEW_POINT_200.value
        )
        HUMIDITY = EcccObservationDatasetTree.HOURLY.HUMIDITY.value
        WIND_DIRECTION = EcccObservationDatasetTree.HOURLY.WIND_DIRECTION.value
        WIND_SPEED = EcccObservationDatasetTree.HOURLY.WIND_SPEED.value
        VISIBILITY = EcccObservationDatasetTree.HOURLY.VISIBILITY.value
        PRESSURE_AIR_STATION_HEIGHT = (
            EcccObservationDatasetTree.HOURLY.PRESSURE_AIR_STATION_HEIGHT.value
        )
        HUMIDEX = EcccObservationDatasetTree.HOURLY.HUMIDEX.value
        WIND_GUST = EcccObservationDatasetTree.HOURLY.WIND_GUST.value

    class DAILY(Enum):
        # Data Quality  quality of all variables?
        TEMPERATURE_AIR_MAX_200 = (
            EcccObservationDatasetTree.DAILY.TEMPERATURE_AIR_MAX_200.value
        )
        TEMPERATURE_AIR_MIN_200 = (
            EcccObservationDatasetTree.DAILY.TEMPERATURE_AIR_MIN_200.value
        )
        TEMPERATURE_AIR_200 = EcccObservationDatasetTree.DAILY.TEMPERATURE_AIR_200.value
        HEATING_DEGREE_DAYS = EcccObservationDatasetTree.DAILY.HEATING_DEGREE_DAYS.value
        COOLING_DEGREE_DAYS = EcccObservationDatasetTree.DAILY.COOLING_DEGREE_DAYS.value
        PRECIPITATION_HEIGHT_RAIN = (
            EcccObservationDatasetTree.DAILY.PRECIPITATION_HEIGHT_RAIN.value
        )  # rain
        SNOW_DEPTH_NEW = (
            EcccObservationDatasetTree.DAILY.SNOW_DEPTH_NEW.value
        )  # new snow?
        PRECIPITATION_HEIGHT = (
            EcccObservationDatasetTree.DAILY.PRECIPITATION_HEIGHT.value
        )  # rain + snow?
        SNOW_DEPTH = EcccObservationDatasetTree.DAILY.SNOW_DEPTH.value
        WIND_DIRECTION_MAX_VELOCITY = (
            EcccObservationDatasetTree.DAILY.WIND_DIRECTION_MAX_VELOCITY.value
        )
        WIND_GUST_MAX = EcccObservationDatasetTree.DAILY.WIND_GUST_MAX.value

    class MONTHLY(Enum):
        TEMPERATURE_AIR_MAX_MEAN_200 = (
            EcccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_MAX_MEAN_200.value
        )
        TEMPERATURE_AIR_MIN_MEAN_200 = (
            EcccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_MIN_MEAN_200.value
        )
        TEMPERATURE_AIR_200 = (
            EcccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_200.value
        )
        TEMPERATURE_AIR_MAX_200 = (
            EcccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_MAX_200.value
        )
        TEMPERATURE_AIR_MIN_200 = (
            EcccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_MIN_200.value
        )
        PRECIPITATION_HEIGHT_RAIN = (
            EcccObservationDatasetTree.MONTHLY.PRECIPITATION_HEIGHT_RAIN.value
        )
        SNOW_DEPTH_NEW = EcccObservationDatasetTree.MONTHLY.SNOW_DEPTH_NEW.value
        PRECIPITATION_HEIGHT = (
            EcccObservationDatasetTree.MONTHLY.PRECIPITATION_HEIGHT.value
        )
        SNOW_DEPTH = (
            EcccObservationDatasetTree.MONTHLY.SNOW_DEPTH.value
        )  # should name include previous day? how is it measured?
        WIND_DIRECTION_MAX_VELOCITY = (
            EcccObservationDatasetTree.MONTHLY.WIND_DIRECTION_MAX_VELOCITY.value
        )
        WIND_GUST_MAX = EcccObservationDatasetTree.MONTHLY.WIND_GUST_MAX.value

    class ANNUAL(Enum):
        TEMPERATURE_AIR_MAX_MEAN_200 = (
            EcccObservationDatasetTree.ANNUAL.TEMPERATURE_AIR_MAX_MEAN_200.value
        )
        TEMPERATURE_AIR_MIN_MEAN_200 = (
            EcccObservationDatasetTree.ANNUAL.TEMPERATURE_AIR_MIN_MEAN_200.value
        )
        # PRECIPITATION_FREQUENCY =
        # EccObservationDatasetTree.ANNUAL.PRECIPITATION_FREQUENCY.value
        TEMPERATURE_AIR_MAX_200 = (
            EcccObservationDatasetTree.ANNUAL.TEMPERATURE_AIR_MAX_200.value
        )
        # 'Highest Temp.Year'
        # 'Highest Temp. Period'
        # 'Highest Temp. Data Quality'
        TEMPERATURE_AIR_MIN_200 = (
            EcccObservationDatasetTree.ANNUAL.TEMPERATURE_AIR_MIN_200.value
        )
        # 'Lowest Temp. Year'
        # 'Lowest Temp. Period'
        # 'Lowest Temp. Data Quality'
        PRECIPITATION_HEIGHT_MAX = (
            EcccObservationDatasetTree.ANNUAL.PRECIPITATION_HEIGHT_MAX.value
        )
        # 'Greatest Precip. Year'
        # 'Greatest Precip. Period'
        # 'Greatest Precip. Data Quality'
        PRECIPITATION_HEIGHT_RAIN_MAX = (
            EcccObservationDatasetTree.ANNUAL.PRECIPITATION_HEIGHT_RAIN_MAX.value
        )
        # 'Greatest Rainfall Year'
        # 'Greatest Rainfall Period'
        # 'Greatest Rainfall Data Quality'
        SNOW_DEPTH_NEW_MAX = EcccObservationDatasetTree.ANNUAL.SNOW_DEPTH_NEW_MAX.value
        # 'Greatest Snowfall Year'
        # 'Greatest Snowfall Period'
        # 'Greatest Snowfall Data Quality'
        SNOW_DEPTH_MAX = EcccObservationDatasetTree.ANNUAL.SNOW_DEPTH_MAX.value
        # 'Most Snow on the Ground Year'
        # 'Most Snow on the Ground Period'
        # 'Most Snow on the Ground Data Quality'
