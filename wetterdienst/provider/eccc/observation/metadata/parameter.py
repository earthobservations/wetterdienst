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
    class HOURLY(DatasetTreeCore):
        class OBSERVATIONS(Enum):
            TEMPERATURE_AIR_MEAN_2M = "temp (°c)"
            QUALITY_TEMPERATURE_AIR_MEAN_2M = "temp flag"
            TEMPERATURE_DEW_POINT_MEAN_2M = "dew point temp (°c)"
            QUALITY_TEMPERATURE_DEW_POINT_MEAN_2M = "dew point temp flag"
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

        TEMPERATURE_AIR_MEAN_2M = OBSERVATIONS.TEMPERATURE_AIR_MEAN_2M
        QUALITY_TEMPERATURE_AIR_MEAN_2M = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_DEW_POINT_MEAN_2M = OBSERVATIONS.TEMPERATURE_DEW_POINT_MEAN_2M
        QUALITY_TEMPERATURE_DEW_POINT_MEAN_2M = OBSERVATIONS.QUALITY_TEMPERATURE_DEW_POINT_MEAN_2M
        HUMIDITY = OBSERVATIONS.HUMIDITY
        QUALITY_HUMIDITY = OBSERVATIONS.QUALITY_HUMIDITY
        WIND_DIRECTION = OBSERVATIONS.WIND_DIRECTION
        QUALITY_WIND_DIRECTION = OBSERVATIONS.QUALITY_WIND_DIRECTION
        WIND_SPEED = OBSERVATIONS.WIND_SPEED
        QUALITY_WIND_SPEED = OBSERVATIONS.QUALITY_WIND_SPEED
        VISIBILITY_RANGE = OBSERVATIONS.VISIBILITY_RANGE
        QUALITY_VISIBILITY_RANGE = OBSERVATIONS.QUALITY_VISIBILITY_RANGE
        PRESSURE_AIR_SITE = OBSERVATIONS.PRESSURE_AIR_SITE
        QUALITY_PRESSURE_AIR_SITE = OBSERVATIONS.QUALITY_PRESSURE_AIR_SITE
        HUMIDEX = OBSERVATIONS.HUMIDEX
        QUALITY_HUMIDEX = OBSERVATIONS.QUALITY_HUMIDEX
        WIND_GUST_MAX = OBSERVATIONS.WIND_GUST_MAX
        QUALITY_WIND_GUST_MAX = OBSERVATIONS.QUALITY_WIND_GUST_MAX
        WEATHER = OBSERVATIONS.WEATHER

    class DAILY(DatasetTreeCore):
        class OBSERVATIONS(Enum):
            # Data Quality  quality of all variables?
            TEMPERATURE_AIR_MAX_2M = "max temp (°c)"
            QUALITY_TEMPERATURE_AIR_MAX_2M = "max temp flag"
            TEMPERATURE_AIR_MIN_2M = "min temp (°c)"
            QUALITY_TEMPERATURE_AIR_MIN_2M = "min temp flag"
            TEMPERATURE_AIR_MEAN_2M = "mean temp (°c)"
            QUALITY_TEMPERATURE_AIR_MEAN_2M = "mean temp flag"
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

        TEMPERATURE_AIR_MAX_2M = OBSERVATIONS.TEMPERATURE_AIR_MAX_2M
        QUALITY_TEMPERATURE_AIR_MAX_2M = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_AIR_MIN_2M = OBSERVATIONS.TEMPERATURE_AIR_MIN_2M
        QUALITY_TEMPERATURE_AIR_MIN_2M = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MIN_2M
        TEMPERATURE_AIR_MEAN_2M = OBSERVATIONS.TEMPERATURE_AIR_MEAN_2M
        QUALITY_TEMPERATURE_AIR_MEAN_2M = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MEAN_2M
        COUNT_DAYS_HEATING_DEGREE = OBSERVATIONS.COUNT_DAYS_HEATING_DEGREE
        QUALITY_COUNT_DAYS_HEATING_DEGREE = OBSERVATIONS.QUALITY_COUNT_DAYS_HEATING_DEGREE
        COUNT_DAYS_COOLING_DEGREE = OBSERVATIONS.COUNT_DAYS_COOLING_DEGREE
        QUALITY_COUNT_DAYS_COOLING_DEGREE = OBSERVATIONS.QUALITY_COUNT_DAYS_COOLING_DEGREE
        PRECIPITATION_HEIGHT_LIQUID = OBSERVATIONS.PRECIPITATION_HEIGHT_LIQUID
        QUALITY_PRECIPITATION_HEIGHT_LIQUID = OBSERVATIONS.QUALITY_PRECIPITATION_HEIGHT_LIQUID
        SNOW_DEPTH_NEW = OBSERVATIONS.SNOW_DEPTH_NEW
        QUALITY_SNOW_DEPTH_NEW = OBSERVATIONS.QUALITY_SNOW_DEPTH_NEW
        PRECIPITATION_HEIGHT = OBSERVATIONS.PRECIPITATION_HEIGHT
        QUALITY_PRECIPITATION_HEIGHT = OBSERVATIONS.QUALITY_PRECIPITATION_HEIGHT
        SNOW_DEPTH = OBSERVATIONS.SNOW_DEPTH
        QUALITY_SNOW_DEPTH = OBSERVATIONS.QUALITY_SNOW_DEPTH
        WIND_DIRECTION_GUST_MAX = OBSERVATIONS.WIND_DIRECTION_GUST_MAX
        QUALITY_WIND_DIRECTION_GUST_MAX = OBSERVATIONS.QUALITY_WIND_DIRECTION_GUST_MAX
        WIND_GUST_MAX = OBSERVATIONS.WIND_GUST_MAX
        QUALITY_WIND_GUST_MAX = OBSERVATIONS.QUALITY_WIND_GUST_MAX

    class MONTHLY(DatasetTreeCore):
        class OBSERVATIONS(Enum):
            TEMPERATURE_AIR_MAX_2M_MEAN = "mean max temp (°c)"
            QUALITY_TEMPERATURE_AIR_MAX_2M_MEAN = "mean max temp flag"
            TEMPERATURE_AIR_MIN_2M_MEAN = "mean min temp (°c)"
            QUALITY_TEMPERATURE_AIR_MIN_2M_MEAN = "mean min temp flag"
            TEMPERATURE_AIR_MEAN_2M = "mean temp (°c)"
            QUALITY_TEMPERATURE_AIR_MEAN_2M = "mean temp flag"
            TEMPERATURE_AIR_MAX_2M = "extr max temp (°c)"
            QUALITY_TEMPERATURE_AIR_MAX_2M = "extr max temp flag"
            TEMPERATURE_AIR_MIN_2M = "extr min temp (°c)"
            QUALITY_TEMPERATURE_AIR_MIN_2M = "extr min temp flag"
            PRECIPITATION_HEIGHT_LIQUID = "total rain (mm)"
            QUALITY_PRECIPITATION_HEIGHT_LIQUID = "total rain flag"
            SNOW_DEPTH_NEW = "total snow (cm)"
            QUALITY_SNOW_DEPTH_NEW = "total snow flag"
            PRECIPITATION_HEIGHT = "total precip (mm)"
            QUALITY_PRECIPITATION_HEIGHT = "total precip flag"
            # should name include previous day? how is it measured?
            SNOW_DEPTH = "snow grnd last day (cm)"
            QUALITY_SNOW_DEPTH = "snow grnd last day flag"
            WIND_DIRECTION_GUST_MAX = "dir of max gust (10s deg)"
            QUALITY_WIND_DIRECTION_GUST_MAX = "dir of max gust flag"
            WIND_GUST_MAX = "spd of max gust(km/h)"
            QUALITY_WIND_GUST_MAX = "spd of max gust flag"

        TEMPERATURE_AIR_MAX_2M_MEAN = OBSERVATIONS.TEMPERATURE_AIR_MAX_2M_MEAN
        QUALITY_TEMPERATURE_AIR_MAX_2M_MEAN = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MAX_2M_MEAN
        TEMPERATURE_AIR_MIN_2M_MEAN = OBSERVATIONS.TEMPERATURE_AIR_MIN_2M_MEAN
        QUALITY_TEMPERATURE_AIR_MIN_2M_MEAN = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MIN_2M_MEAN
        TEMPERATURE_AIR_MEAN_2M = OBSERVATIONS.TEMPERATURE_AIR_MEAN_2M
        QUALITY_TEMPERATURE_AIR_MEAN_2M = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_AIR_MAX_2M = OBSERVATIONS.TEMPERATURE_AIR_MAX_2M
        QUALITY_TEMPERATURE_AIR_MAX_2M = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_AIR_MIN_2M = OBSERVATIONS.TEMPERATURE_AIR_MIN_2M
        QUALITY_TEMPERATURE_AIR_MIN_2M = OBSERVATIONS.QUALITY_TEMPERATURE_AIR_MIN_2M
        PRECIPITATION_HEIGHT_LIQUID = OBSERVATIONS.PRECIPITATION_HEIGHT_LIQUID
        QUALITY_PRECIPITATION_HEIGHT_LIQUID = OBSERVATIONS.QUALITY_PRECIPITATION_HEIGHT_LIQUID
        SNOW_DEPTH_NEW = OBSERVATIONS.SNOW_DEPTH_NEW
        QUALITY_SNOW_DEPTH_NEW = OBSERVATIONS.QUALITY_SNOW_DEPTH_NEW
        PRECIPITATION_HEIGHT = OBSERVATIONS.PRECIPITATION_HEIGHT
        QUALITY_PRECIPITATION_HEIGHT = OBSERVATIONS.QUALITY_PRECIPITATION_HEIGHT
        SNOW_DEPTH = OBSERVATIONS.SNOW_DEPTH
        QUALITY_SNOW_DEPTH = OBSERVATIONS.QUALITY_SNOW_DEPTH
        WIND_DIRECTION_GUST_MAX = OBSERVATIONS.WIND_DIRECTION_GUST_MAX
        QUALITY_WIND_DIRECTION_GUST_MAX = OBSERVATIONS.QUALITY_WIND_DIRECTION_GUST_MAX
        WIND_GUST_MAX = OBSERVATIONS.WIND_GUST_MAX
        QUALITY_WIND_GUST_MAX = OBSERVATIONS.QUALITY_WIND_GUST_MAX

    class ANNUAL(DatasetTreeCore):
        class OBSERVATIONS(Enum):
            TEMPERATURE_AIR_MAX_2M_MEAN = "average max. temp. (°c)"
            TEMPERATURE_AIR_MIN_2M_MEAN = "average min. temp. (°c)"
            PRECIPITATION_FREQUENCY = "frequency of precip. (%)"
            TEMPERATURE_AIR_MAX_2M = "highest temp. (°c)"
            # 'highest temp.year'
            # 'highest temp. period'
            # 'highest temp. data quality'
            TEMPERATURE_AIR_MIN_2M = "lowest temp. (°c)"
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

        TEMPERATURE_AIR_MAX_2M_MEAN = OBSERVATIONS.TEMPERATURE_AIR_MAX_2M_MEAN
        TEMPERATURE_AIR_MIN_2M_MEAN = OBSERVATIONS.TEMPERATURE_AIR_MIN_2M_MEAN
        PRECIPITATION_FREQUENCY = OBSERVATIONS.PRECIPITATION_FREQUENCY
        TEMPERATURE_AIR_MAX_2M = OBSERVATIONS.TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_AIR_MIN_2M = OBSERVATIONS.TEMPERATURE_AIR_MIN_2M
        PRECIPITATION_HEIGHT_MAX = OBSERVATIONS.PRECIPITATION_HEIGHT_MAX
        PRECIPITATION_HEIGHT_LIQUID_MAX = OBSERVATIONS.PRECIPITATION_HEIGHT_LIQUID_MAX
        SNOW_DEPTH_NEW_MAX = OBSERVATIONS.SNOW_DEPTH_NEW_MAX
        SNOW_DEPTH_MAX = OBSERVATIONS.SNOW_DEPTH_MAX
