# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.util.parameter import DatasetTreeCore


class EccObservationDataset(Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    # ANNUAL = "annual"


class EccObservationDatasetTree(DatasetTreeCore):
    class HOURLY(Enum):
        TEMPERATURE_AIR_200 = "Temp (°C)"
        QUALITY_TEMPERATURE_AIR_200 = "Temp Flag"
        TEMPERATURE_DEW_POINT_200 = "Dew Point Temp (°C)"
        QUALITY_TEMPERATURE_DEW_POINT_200 = "Dew Point Temp Flag"
        HUMIDITY = "Rel Hum (%)"
        QUALITY_HUMIDITY = "Rel Hum Flag"
        WIND_DIRECTION = "Wind Dir (10s deg)"
        QUALITY_WIND_DIRECTION = "Wind Dir Flag"
        WIND_SPREED = "Wind Spd (km/h)"
        QUALITY_WIND_SPEED = "Wind Spd Flag"
        VISIBILITY = "Visibility (km)"
        QUALITY_VISIBILITY = "Visibility Flag"
        PRESSURE_AIR_STATION_HEIGHT = "Stn Press (kPa)"
        QUALITY_PRESSURE_AIR_STATION_HEIGHT = "Stn Press Flag"
        HUMIDEX = "Hmdx"
        QUALITY_HUMIDEX = "Hmdx Flag"
        WIND_GUST = "Wind Chill"
        QUALITY_WIND_GUST = "Wind Chill Flag"
        WEATHER = "Weather"

    class DAILY(Enum):
        # Data Quality  quality of all variables?
        TEMPERATURE_AIR_MAX_200 = "Max Temp (°C)"
        QUALITY_TEMPERATURE_AIR_MAX_200 = "Max Temp Flag"
        TEMPERATURE_AIR_MIN_200 = "Min Temp (°C)"
        QUALITY_TEMPERATURE_AIR_MIN_200 = "Min Temp Flag"
        TEMPERATURE_AIR_MEAN_200 = "Mean Temp (°C)"
        QUALITY_TEMPERATURE_AIR_MEAN_200 = "Mean Temp Flag"
        HEATING_DEGREE_DAYS = "Heat Deg Days (°C)"
        QUALITY_HEATING_DEGREE_DAYS = "Heat Deg Days Flag"
        COOLING_DEGREE_DAYS = "Cool Deg Days (°C)"
        QUALITY_COOLING_DEGREE_DAYS = "Cool Deg Days Flag"
        PRECIPITATION_HEIGHT_RAIN = "Total Rain (mm)"  # rain
        QUALITY_PRECIPITATION_HEIGHT_RAIN = "Total Rain Flag"
        SNOW_DEPTH_NEW = "Total Snow (cm)"  # new snow?
        QUALITY_SNOW_DEPTH_NEW = "Total Snow Flag"
        PRECIPITATION_HEIGHT = "Total Precip (mm)"  # rain + snow?
        QUALITY_PRECIPITATION_HEIGHT = "Total Precip Flag"
        SNOW_DEPTH = "Snow on Grnd (cm)"
        QUALITY_SNOW_DEPTH = "Snow on Grnd Flag"
        WIND_DIRECTION_MAX_VELOCITY = "Dir of Max Gust (10s deg)"
        QUALITY_WIND_DIRECTION_MAX_VELOCITY = "Dir of Max Gust Flag"
        WIND_GUST_MAX = "Spd of Max Gust (km/h)"
        QUALITY_WIND_GUST_MAX = "Spd of Max Gust Flag"

    class MONTHLY(Enum):
        TEMPERATURE_AIR_MAX_MEAN_200 = "Mean Max Temp (°C)"
        QUALITY_TEMPERATURE_AIR_MAX_MEAN_200 = "Mean Max Temp Flag"
        TEMPERATURE_AIR_MIN_MEAN_200 = "Mean Min Temp (°C)"
        QUALITY_TEMPERATURE_AIR_MIN_MEAN_200 = "Mean Min Temp Flag"
        TEMPERATURE_AIR_200 = "Mean Temp (°C)"
        QUALITY_TEMPERATURE_AIR_200 = "Mean Temp Flag"
        TEMPERATURE_AIR_MAX_200 = "Extr Max Temp (°C)"
        QUALITY_TEMPERATURE_AIR_MAX_200 = "Extr Max Temp Flag"
        TEMPERATURE_AIR_MIN_200 = "Extr Min Temp (°C)"
        QUALITY_TEMPERATURE_AIR_MIN_200 = "Extr Min Temp Flag"
        PRECIPITATION_HEIGHT_RAIN = "Total Rain (mm)"
        QUALITY_PRECIPITATION_HEIGHT_RAIN = "Total Rain Flag"
        SNOW_DEPTH_NEW = "Total Snow (cm)"
        QUALITY_SNOW_DEPTH_NEW = "Total Snow Flag"
        PRECIPITATION_HEIGHT = "Total Precip (mm)"
        QUALITY_PRECIPITATION_HEIGHT = "Total Precip Flag"
        # should name include previous day? how is it measured?
        SNOW_DEPTH = "Snow Grnd Last Day (cm)"
        QUALITY_SNOW_DEPTH = "Snow Grnd Last Day Flag"
        WIND_DIRECTION_MAX_VELOCITY = "Dir of Max Gust (10's deg)"
        QUALITY_WIND_DIRECTION_MAX_VELOCITY = "Dir of Max Gust Flag"
        WIND_GUST_MAX = "Spd of Max Gust(km/h)"
        QUALITY_WIND_GUST_MAX = "Spd of Max Gust Flag"

    class ANNUAL(Enum):
        TEMPERATURE_AIR_MAX_MEAN_200 = "Average Max. Temp. (°C)"
        TEMPERATURE_AIR_MIN_MEAN_200 = "Average Min. Temp. (°C)"
        PRECIPITATION_FREQUENCY = "Frequency of Precip. (%)"
        TEMPERATURE_AIR_MAX_200 = "Highest Temp. (°C)"
        # 'Highest Temp.Year'
        # 'Highest Temp. Period'
        # 'Highest Temp. Data Quality'
        TEMPERATURE_AIR_MIN_200 = "Lowest Temp. (°C)"
        # 'Lowest Temp. Year'
        # 'Lowest Temp. Period'
        # 'Lowest Temp. Data Quality'
        PRECIPITATION_HEIGHT_MAX = "Greatest Precip. (mm)"
        # 'Greatest Precip. Year'
        # 'Greatest Precip. Period'
        # 'Greatest Precip. Data Quality'
        PRECIPITATION_HEIGHT_RAIN_MAX = "Greatest Rainfall (mm)"
        # 'Greatest Rainfall Year'
        # 'Greatest Rainfall Period'
        # 'Greatest Rainfall Data Quality'
        SNOW_DEPTH_NEW_MAX = "Greatest Snowfall (cm)"
        # 'Greatest Snowfall Year'
        # 'Greatest Snowfall Period'
        # 'Greatest Snowfall Data Quality'
        SNOW_DEPTH_MAX = "Most Snow on the Ground (cm)"
        # 'Most Snow on the Ground Year'
        # 'Most Snow on the Ground Period'
        # 'Most Snow on the Ground Data Quality'
