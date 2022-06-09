# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.util.parameter import DatasetTreeCore


class EcccObservationDataset(Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class EcccObservationParameter(DatasetTreeCore):
    class HOURLY(Enum):
        TEMPERATURE_AIR_MEAN_200 = "temp (°c)"
        QUALITY_TEMPERATURE_AIR_MEAN_200 = "temp flag"
        TEMPERATURE_DEW_POINT_MEAN_200 = "dew point temp (°c)"
        QUALITY_TEMPERATURE_DEW_POINT_MEAN_200 = "dew point temp flag"
        HUMIDITY = "rel hum (%)"
        QUALITY_HUMIDITY = "rel hum flag"
        WIND_DIRECTION = "wind dir (10s deg)"
        QUALITY_WIND_DIRECTION = "wind dir flag"
        WIND_SPEED = "wind spd (km/h)"
        QUALITY_WIND_SPEED = "wind spd flag"
        VISIBILITY_RANGE = "visibility (km)"
        QUALITY_VISIBILITY_RANGE = "visibility flag"
        PRESSURE_AIR_SITE = "stn press (kpa)"
        QUALITY_PRESSURE_AIR_SITE = "stn press flag"
        HUMIDEX = "hmdx"
        QUALITY_HUMIDEX = "hmdx flag"
        WIND_GUST_MAX = "wind chill"
        QUALITY_WIND_GUST_MAX = "wind chill flag"
        WEATHER = "weather"

    class DAILY(Enum):
        # Data Quality  quality of all variables?
        TEMPERATURE_AIR_MAX_200 = "max temp (°c)"
        QUALITY_TEMPERATURE_AIR_MAX_200 = "max temp flag"
        TEMPERATURE_AIR_MIN_200 = "min temp (°c)"
        QUALITY_TEMPERATURE_AIR_MIN_200 = "min temp flag"
        TEMPERATURE_AIR_MEAN_200 = "mean temp (°c)"
        QUALITY_TEMPERATURE_AIR_MEAN_200 = "mean temp flag"
        COUNT_DAYS_HEATING_DEGREE = "heat deg days (°c)"
        QUALITY_COUNT_DAYS_HEATING_DEGREE = "heat deg days flag"
        COUNT_DAYS_COOLING_DEGREE = "cool deg days (°c)"
        QUALITY_COUNT_DAYS_COOLING_DEGREE = "cool deg days flag"
        PRECIPITATION_HEIGHT_LIQUID = "total rain (mm)"  # rain
        QUALITY_PRECIPITATION_HEIGHT_LIQUID = "total rain flag"
        SNOW_DEPTH_NEW = "total snow (cm)"  # new snow?
        QUALITY_SNOW_DEPTH_NEW = "total snow flag"
        PRECIPITATION_HEIGHT = "total precip (mm)"  # rain + snow?
        QUALITY_PRECIPITATION_HEIGHT = "total precip flag"
        SNOW_DEPTH = "snow on grnd (cm)"
        QUALITY_SNOW_DEPTH = "snow on grnd flag"
        WIND_DIRECTION_GUST_MAX = "dir of max gust (10s deg)"
        QUALITY_WIND_DIRECTION_GUST_MAX = "dir of max gust flag"
        WIND_GUST_MAX = "spd of max gust (km/h)"
        QUALITY_WIND_GUST_MAX = "spd of max gust flag"

    class MONTHLY(Enum):
        TEMPERATURE_AIR_MAX_200_MEAN = "mean max temp (°c)"
        QUALITY_TEMPERATURE_AIR_MAX_200_MEAN = "mean max temp flag"
        TEMPERATURE_AIR_MIN_200_MEAN = "mean min temp (°c)"
        QUALITY_TEMPERATURE_AIR_MIN_200_MEAN = "mean min temp flag"
        TEMPERATURE_AIR_MEAN_200 = "mean temp (°c)"
        QUALITY_TEMPERATURE_AIR_MEAN_200 = "mean temp flag"
        TEMPERATURE_AIR_MAX_200 = "extr max temp (°c)"
        QUALITY_TEMPERATURE_AIR_MAX_200 = "extr max temp flag"
        TEMPERATURE_AIR_MIN_200 = "extr min temp (°c)"
        QUALITY_TEMPERATURE_AIR_MIN_200 = "extr min temp flag"
        PRECIPITATION_HEIGHT_LIQUID = "total rain (mm)"
        QUALITY_PRECIPITATION_HEIGHT_LIQUID = "total rain flag"
        SNOW_DEPTH_NEW = "total snow (cm)"
        QUALITY_SNOW_DEPTH_NEW = "total snow flag"
        PRECIPITATION_HEIGHT = "total precip (mm)"
        QUALITY_PRECIPITATION_HEIGHT = "total precip flag"
        # should name include previous day? how is it measured?
        SNOW_DEPTH = "snow grnd last day (cm)"
        QUALITY_SNOW_DEPTH = "snow grnd last day flag"
        WIND_DIRECTION_GUST_MAX = "dir of max gust (10's deg)"
        QUALITY_WIND_DIRECTION_GUST_MAX = "dir of max gust flag"
        WIND_GUST_MAX = "spd of max gust(km/h)"
        QUALITY_WIND_GUST_MAX = "spd of max gust flag"

    class ANNUAL(Enum):
        TEMPERATURE_AIR_MAX_200_MEAN = "average max. temp. (°c)"
        TEMPERATURE_AIR_MIN_200_MEAN = "average min. temp. (°c)"
        PRECIPITATION_FREQUENCY = "frequency of precip. (%)"
        TEMPERATURE_AIR_MAX_200 = "highest temp. (°c)"
        # 'highest temp.year'
        # 'highest temp. period'
        # 'highest temp. data quality'
        TEMPERATURE_AIR_MIN_200 = "lowest temp. (°c)"
        # 'lowest temp. year'
        # 'lowest temp. period'
        # 'lowest temp. data quality'
        PRECIPITATION_HEIGHT_MAX = "greatest precip. (mm)"
        # 'greatest precip. year'
        # 'greatest precip. period'
        # 'greatest precip. data quality'
        PRECIPITATION_HEIGHT_LIQUID_MAX = "greatest rainfall (mm)"
        # 'greatest rainfall year'
        # 'greatest rainfall period'
        # 'greatest rainfall data quality'
        SNOW_DEPTH_NEW_MAX = "greatest snowfall (cm)"
        # 'greatest snowfall year'
        # 'greatest snowfall period'
        # 'greatest snowfall data quality'
        SNOW_DEPTH_MAX = "most snow on the ground (cm)"
        # 'most snow on the ground year'
        # 'most snow on the ground period'
        # 'most snow on the ground data quality'
