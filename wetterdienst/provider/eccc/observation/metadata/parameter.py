# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.provider.eccc.observation.metadata.dataset import (
    EccObservationDatasetTree,
)
from wetterdienst.util.parameter import DatasetTreeCore


class EccObservationParameter(DatasetTreeCore):
    class HOURLY(Enum):
        TEMPERATURE_AIR_200 = EccObservationDatasetTree.HOURLY.TEMPERATURE_AIR_200.value
        TEMPERATURE_DEW_POINT_200 = (
            EccObservationDatasetTree.HOURLY.TEMPERATURE_DEW_POINT_200.value
        )
        HUMIDITY = EccObservationDatasetTree.HOURLY.HUMIDITY.value
        WIND_DIRECTION = EccObservationDatasetTree.HOURLY.WIND_DIRECTION.value
        WIND_SPREED = EccObservationDatasetTree.HOURLY.WIND_SPREED.value
        VISIBILITY = EccObservationDatasetTree.HOURLY.VISIBILITY.value
        PRESSURE_AIR_STATION_HEIGHT = (
            EccObservationDatasetTree.HOURLY.PRESSURE_AIR_STATION_HEIGHT.value
        )
        HUMIDEX = EccObservationDatasetTree.HOURLY.HUMIDEX.value
        WIND_GUST = EccObservationDatasetTree.HOURLY.WIND_GUST.value

    class DAILY(Enum):
        # Data Quality  quality of all variables?
        TEMPERATURE_AIR_MAX_200 = (
            EccObservationDatasetTree.DAILY.TEMPERATURE_AIR_MAX_200.value
        )
        TEMPERATURE_AIR_MIN_200 = (
            EccObservationDatasetTree.DAILY.TEMPERATURE_AIR_MIN_200.value
        )
        TEMPERATURE_AIR_200 = EccObservationDatasetTree.DAILY.TEMPERATURE_AIR_200.value
        HEATING_DEGREE_DAYS = EccObservationDatasetTree.DAILY.HEATING_DEGREE_DAYS.value
        COOLING_DEGREE_DAYS = EccObservationDatasetTree.DAILY.COOLING_DEGREE_DAYS.value
        PRECIPITATION_HEIGHT_RAIN = (
            EccObservationDatasetTree.DAILY.PRECIPITATION_HEIGHT_RAIN.value
        )  # rain
        SNOW_DEPTH_NEW = (
            EccObservationDatasetTree.DAILY.SNOW_DEPTH_NEW.value
        )  # new snow?
        PRECIPITATION_HEIGHT = (
            EccObservationDatasetTree.DAILY.PRECIPITATION_HEIGHT.value
        )  # rain + snow?
        SNOW_DEPTH = EccObservationDatasetTree.DAILY.SNOW_DEPTH.value
        WIND_DIRECTION_MAX_VELOCITY = (
            EccObservationDatasetTree.DAILY.WIND_DIRECTION_MAX_VELOCITY.value
        )
        WIND_GUST_MAX = EccObservationDatasetTree.DAILY.WIND_GUST_MAX.value

    class MONTHLY(Enum):
        TEMPERATURE_AIR_MAX_MEAN_200 = (
            EccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_MAX_MEAN_200.value
        )
        TEMPERATURE_AIR_MIN_MEAN_200 = (
            EccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_MIN_MEAN_200.value
        )
        TEMPERATURE_AIR_200 = (
            EccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_200.value
        )
        TEMPERATURE_AIR_MAX_200 = (
            EccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_MAX_200.value
        )
        TEMPERATURE_AIR_MIN_200 = (
            EccObservationDatasetTree.MONTHLY.TEMPERATURE_AIR_MIN_200.value
        )
        PRECIPITATION_HEIGHT_RAIN = (
            EccObservationDatasetTree.MONTHLY.PRECIPITATION_HEIGHT_RAIN.value
        )
        SNOW_DEPTH_NEW = EccObservationDatasetTree.MONTHLY.SNOW_DEPTH_NEW.value
        PRECIPITATION_HEIGHT = (
            EccObservationDatasetTree.MONTHLY.PRECIPITATION_HEIGHT.value
        )
        SNOW_DEPTH = (
            EccObservationDatasetTree.MONTHLY.SNOW_DEPTH.value
        )  # should name include previous day? how is it measured?
        WIND_DIRECTION_MAX_VELOCITY = (
            EccObservationDatasetTree.MONTHLY.WIND_DIRECTION_MAX_VELOCITY.value
        )
        WIND_GUST_MAX = EccObservationDatasetTree.MONTHLY.WIND_GUST_MAX.value

    class ANNUAL(Enum):
        TEMPERATURE_AIR_MAX_MEAN_200 = (
            EccObservationDatasetTree.ANNUAL.TEMPERATURE_AIR_MAX_MEAN_200.value
        )
        TEMPERATURE_AIR_MIN_MEAN_200 = (
            EccObservationDatasetTree.ANNUAL.TEMPERATURE_AIR_MIN_MEAN_200.value
        )
        # PRECIPITATION_FREQUENCY =
        # EccObservationDatasetTree.ANNUAL.PRECIPITATION_FREQUENCY.value
        TEMPERATURE_AIR_MAX_200 = (
            EccObservationDatasetTree.ANNUAL.TEMPERATURE_AIR_MAX_200.value
        )
        # 'Highest Temp.Year'
        # 'Highest Temp. Period'
        # 'Highest Temp. Data Quality'
        TEMPERATURE_AIR_MIN_200 = (
            EccObservationDatasetTree.ANNUAL.TEMPERATURE_AIR_MIN_200.value
        )
        # 'Lowest Temp. Year'
        # 'Lowest Temp. Period'
        # 'Lowest Temp. Data Quality'
        PRECIPITATION_HEIGHT_MAX = (
            EccObservationDatasetTree.ANNUAL.PRECIPITATION_HEIGHT_MAX.value
        )
        # 'Greatest Precip. Year'
        # 'Greatest Precip. Period'
        # 'Greatest Precip. Data Quality'
        PRECIPITATION_HEIGHT_RAIN_MAX = (
            EccObservationDatasetTree.ANNUAL.PRECIPITATION_HEIGHT_RAIN_MAX.value
        )
        # 'Greatest Rainfall Year'
        # 'Greatest Rainfall Period'
        # 'Greatest Rainfall Data Quality'
        SNOW_DEPTH_NEW_MAX = EccObservationDatasetTree.ANNUAL.SNOW_DEPTH_NEW_MAX.value
        # 'Greatest Snowfall Year'
        # 'Greatest Snowfall Period'
        # 'Greatest Snowfall Data Quality'
        SNOW_DEPTH_MAX = EccObservationDatasetTree.ANNUAL.SNOW_DEPTH_MAX.value
        # 'Most Snow on the Ground Year'
        # 'Most Snow on the Ground Period'
        # 'Most Snow on the Ground Data Quality'
