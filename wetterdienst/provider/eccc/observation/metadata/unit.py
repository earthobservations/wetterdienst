# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.unit import MetricUnit, OriginUnit, UnitEnum
from wetterdienst.util.parameter import DatasetTreeCore


class EcccObservationUnitOrigin(DatasetTreeCore):
    class HOURLY(UnitEnum):
        TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_200 = OriginUnit.DIMENSIONLESS
        TEMPERATURE_DEW_POINT_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_DEW_POINT_200 = OriginUnit.DIMENSIONLESS.value
        HUMIDITY = OriginUnit.PERCENT.value
        QUALITY_HUMIDITY = OriginUnit.DIMENSIONLESS.value
        WIND_DIRECTION = OriginUnit.WIND_DIRECTION.value
        QUALITY_WIND_DIRECTION = OriginUnit.DIMENSIONLESS.value
        WIND_SPEED = OriginUnit.KILOMETER_PER_HOUR.value
        QUALITY_WIND_SPEED = OriginUnit.DIMENSIONLESS.value
        VISIBILITY = OriginUnit.KILOMETER.value
        QUALITY_VISIBILITY = OriginUnit.DIMENSIONLESS.value
        PRESSURE_AIR_STATION_HEIGHT = OriginUnit.KILOPASCAL.value
        QUALITY_PRESSURE_AIR_STATION_HEIGHT = OriginUnit.DIMENSIONLESS.value
        HUMIDEX = OriginUnit.DIMENSIONLESS.value
        QUALITY_HUMIDEX = OriginUnit.DIMENSIONLESS.value
        WIND_GUST = OriginUnit.KILOMETER_PER_HOUR.value
        QUALITY_WIND_GUST = OriginUnit.DIMENSIONLESS.value
        WEATHER = OriginUnit.DIMENSIONLESS.value

    class DAILY(UnitEnum):
        # Data Quality  quality of all variables?
        TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_MAX_200 = OriginUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_MIN_200 = OriginUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_200 = OriginUnit.DIMENSIONLESS.value
        HEATING_DEGREE_DAYS = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_HEATING_DEGREE_DAYS = OriginUnit.DIMENSIONLESS.value
        COOLING_DEGREE_DAYS = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_COOLING_DEGREE_DAYS = OriginUnit.DIMENSIONLESS.value
        PRECIPITATION_HEIGHT_RAIN = OriginUnit.MILLIMETER.value
        QUALITY_PRECIPITATION_HEIGHT_RAIN = OriginUnit.DIMENSIONLESS.value
        SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value
        QUALITY_SNOW_DEPTH_NEW = OriginUnit.DIMENSIONLESS.value
        PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
        QUALITY_PRECIPITATION_HEIGHT = OriginUnit.DIMENSIONLESS.value
        SNOW_DEPTH = OriginUnit.CENTIMETER.value
        QUALITY_SNOW_DEPTH = OriginUnit.DIMENSIONLESS.value
        WIND_DIRECTION_MAX_VELOCITY = OriginUnit.WIND_DIRECTION.value
        QUALITY_WIND_DIRECTION_MAX_VELOCITY = OriginUnit.DIMENSIONLESS.value
        WIND_GUST_MAX = OriginUnit.KILOMETER_PER_HOUR.value
        QUALITY_WIND_GUST_MAX = OriginUnit.DIMENSIONLESS.value

    class MONTHLY(UnitEnum):
        TEMPERATURE_AIR_MAX_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_MAX_MEAN_200 = OriginUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_MIN_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_MIN_MEAN_200 = OriginUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_200 = OriginUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_MAX_200 = OriginUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value
        QUALITY_TEMPERATURE_AIR_MIN_200 = OriginUnit.DIMENSIONLESS.value
        PRECIPITATION_HEIGHT_RAIN = OriginUnit.MILLIMETER.value
        QUALITY_PRECIPITATION_HEIGHT_RAIN = OriginUnit.DIMENSIONLESS.value
        SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value
        QUALITY_SNOW_DEPTH_NEW = OriginUnit.DIMENSIONLESS.value
        PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
        QUALITY_PRECIPITATION_HEIGHT = OriginUnit.DIMENSIONLESS.value
        # should name include previous day? how is it measured?
        SNOW_DEPTH = OriginUnit.CENTIMETER.value
        QUALITY_SNOW_DEPTH = OriginUnit.DIMENSIONLESS.value
        WIND_DIRECTION_MAX_VELOCITY = OriginUnit.WIND_DIRECTION.value
        QUALITY_WIND_DIRECTION_MAX_VELOCITY = OriginUnit.DIMENSIONLESS.value
        WIND_GUST_MAX = OriginUnit.KILOMETER_PER_HOUR.value
        QUALITY_WIND_GUST_MAX = OriginUnit.DIMENSIONLESS.value

    class ANNUAL(UnitEnum):
        TEMPERATURE_AIR_MAX_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value
        TEMPERATURE_AIR_MIN_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value
        PRECIPITATION_FREQUENCY = OriginUnit.PERCENT.value
        TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value
        # 'highest temp.year'
        # 'highest temp. period'
        # 'highest temp. data quality'
        TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value
        # 'lowest temp. year'
        # 'lowest temp. period'
        # 'lowest temp. data quality'
        PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value
        # 'greatest precip. year'
        # 'greatest precip. period'
        # 'greatest precip. data quality'
        PRECIPITATION_HEIGHT_RAIN_MAX = OriginUnit.MILLIMETER.value
        # 'greatest rainfall year'
        # 'greatest rainfall period'
        # 'greatest rainfall data quality'
        SNOW_DEPTH_NEW_MAX = OriginUnit.CENTIMETER.value
        # 'greatest snowfall year'
        # 'greatest snowfall period'
        # 'greatest snowfall data quality'
        SNOW_DEPTH_MAX = OriginUnit.CENTIMETER.value
        # 'most snow on the ground year'
        # 'most snow on the ground period'
        # 'most snow on the ground data quality'


class EcccObservationUnitSI(DatasetTreeCore):
    class HOURLY(UnitEnum):
        TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_200 = MetricUnit.DIMENSIONLESS
        TEMPERATURE_DEW_POINT_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_DEW_POINT_200 = MetricUnit.DIMENSIONLESS.value
        HUMIDITY = MetricUnit.PERCENT.value
        QUALITY_HUMIDITY = MetricUnit.DIMENSIONLESS.value
        WIND_DIRECTION = MetricUnit.WIND_DIRECTION.value
        QUALITY_WIND_DIRECTION = MetricUnit.DIMENSIONLESS.value
        WIND_SPEED = MetricUnit.METER_PER_SECOND.value
        QUALITY_WIND_SPEED = MetricUnit.DIMENSIONLESS.value
        VISIBILITY = MetricUnit.METER.value
        QUALITY_VISIBILITY = MetricUnit.DIMENSIONLESS.value
        PRESSURE_AIR_STATION_HEIGHT = MetricUnit.PASCAL.value
        QUALITY_PRESSURE_AIR_STATION_HEIGHT = MetricUnit.DIMENSIONLESS.value
        HUMIDEX = MetricUnit.DIMENSIONLESS.value
        QUALITY_HUMIDEX = MetricUnit.DIMENSIONLESS.value
        WIND_GUST = MetricUnit.METER_PER_SECOND.value
        QUALITY_WIND_GUST = MetricUnit.DIMENSIONLESS.value
        WEATHER = MetricUnit.DIMENSIONLESS.value

    class DAILY(UnitEnum):
        # Data Quality  quality of all variables?
        TEMPERATURE_AIR_MAX_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_MAX_200 = MetricUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_MIN_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_MIN_200 = MetricUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_200 = MetricUnit.DIMENSIONLESS.value
        HEATING_DEGREE_DAYS = MetricUnit.DEGREE_KELVIN.value
        QUALITY_HEATING_DEGREE_DAYS = MetricUnit.DIMENSIONLESS.value
        COOLING_DEGREE_DAYS = MetricUnit.DEGREE_KELVIN.value
        QUALITY_COOLING_DEGREE_DAYS = MetricUnit.DIMENSIONLESS.value
        PRECIPITATION_HEIGHT_RAIN = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
        QUALITY_PRECIPITATION_HEIGHT_RAIN = MetricUnit.DIMENSIONLESS.value
        SNOW_DEPTH_NEW = MetricUnit.METER.value
        QUALITY_SNOW_DEPTH_NEW = MetricUnit.DIMENSIONLESS.value
        PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
        QUALITY_PRECIPITATION_HEIGHT = MetricUnit.DIMENSIONLESS.value
        SNOW_DEPTH = MetricUnit.METER.value
        QUALITY_SNOW_DEPTH = MetricUnit.DIMENSIONLESS.value
        WIND_DIRECTION_MAX_VELOCITY = MetricUnit.WIND_DIRECTION.value
        QUALITY_WIND_DIRECTION_MAX_VELOCITY = MetricUnit.DIMENSIONLESS.value
        WIND_GUST_MAX = MetricUnit.METER_PER_SECOND.value
        QUALITY_WIND_GUST_MAX = MetricUnit.DIMENSIONLESS.value

    class MONTHLY(UnitEnum):
        TEMPERATURE_AIR_MAX_MEAN_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_MAX_MEAN_200 = MetricUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_MIN_MEAN_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_MIN_MEAN_200 = MetricUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_200 = MetricUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_MAX_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_MAX_200 = MetricUnit.DIMENSIONLESS.value
        TEMPERATURE_AIR_MIN_200 = MetricUnit.DEGREE_KELVIN.value
        QUALITY_TEMPERATURE_AIR_MIN_200 = MetricUnit.DIMENSIONLESS.value
        PRECIPITATION_HEIGHT_RAIN = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
        QUALITY_PRECIPITATION_HEIGHT_RAIN = MetricUnit.DIMENSIONLESS.value
        SNOW_DEPTH_NEW = MetricUnit.METER.value
        QUALITY_SNOW_DEPTH_NEW = MetricUnit.DIMENSIONLESS.value
        PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
        QUALITY_PRECIPITATION_HEIGHT = MetricUnit.DIMENSIONLESS.value
        # should name include previous day? how is it measured?
        SNOW_DEPTH = MetricUnit.METER.value
        QUALITY_SNOW_DEPTH = MetricUnit.DIMENSIONLESS.value
        WIND_DIRECTION_MAX_VELOCITY = MetricUnit.WIND_DIRECTION.value
        QUALITY_WIND_DIRECTION_MAX_VELOCITY = MetricUnit.DIMENSIONLESS.value
        WIND_GUST_MAX = MetricUnit.METER_PER_SECOND.value
        QUALITY_WIND_GUST_MAX = MetricUnit.DIMENSIONLESS.value

    class ANNUAL(UnitEnum):
        TEMPERATURE_AIR_MAX_MEAN_200 = MetricUnit.DEGREE_KELVIN.value
        TEMPERATURE_AIR_MIN_MEAN_200 = MetricUnit.DEGREE_KELVIN.value
        PRECIPITATION_FREQUENCY = MetricUnit.PERCENT.value
        TEMPERATURE_AIR_MAX_200 = MetricUnit.DEGREE_KELVIN.value
        # 'highest temp.year'
        # 'highest temp. period'
        # 'highest temp. data quality'
        TEMPERATURE_AIR_MIN_200 = MetricUnit.DEGREE_KELVIN.value
        # 'lowest temp. year'
        # 'lowest temp. period'
        # 'lowest temp. data quality'
        PRECIPITATION_HEIGHT_MAX = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
        # 'greatest precip. year'
        # 'greatest precip. period'
        # 'greatest precip. data quality'
        PRECIPITATION_HEIGHT_RAIN_MAX = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
        # 'greatest rainfall year'
        # 'greatest rainfall period'
        # 'greatest rainfall data quality'
        SNOW_DEPTH_NEW_MAX = MetricUnit.METER.value
        # 'greatest snowfall year'
        # 'greatest snowfall period'
        # 'greatest snowfall data quality'
        SNOW_DEPTH_MAX = MetricUnit.METER.value
        # 'most snow on the ground year'
        # 'most snow on the ground period'
        # 'most snow on the ground data quality'
