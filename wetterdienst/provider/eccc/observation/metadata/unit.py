# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.parameter import DatasetTreeCore


class EcccObservationUnit(DatasetTreeCore):
    class HOURLY(DatasetTreeCore):
        class HOURLY(UnitEnum):
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            TEMPERATURE_DEW_POINT_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_DEW_POINT_MEAN_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            QUALITY_HUMIDITY = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WIND_DIRECTION = (
                OriginUnit.WIND_DIRECTION.value,
                SIUnit.WIND_DIRECTION.value,
            )
            QUALITY_WIND_DIRECTION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WIND_SPEED = (
                OriginUnit.KILOMETER_PER_HOUR.value,
                SIUnit.METER_PER_SECOND.value,
            )
            QUALITY_WIND_SPEED = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            VISIBILITY_RANGE = OriginUnit.KILOMETER.value, SIUnit.METER.value
            QUALITY_VISIBILITY_RANGE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRESSURE_AIR_SITE = (
                OriginUnit.KILOPASCAL.value,
                SIUnit.PASCAL.value,
            )
            QUALITY_PRESSURE_AIR_SITE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            HUMIDEX = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            QUALITY_HUMIDEX = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_GUST_MAX = (
                OriginUnit.KILOMETER_PER_HOUR.value,
                SIUnit.METER_PER_SECOND.value,
            )
            QUALITY_WIND_GUST_MAX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value

    class DAILY(DatasetTreeCore):
        class DAILY(UnitEnum):
            # Data Quality  quality of all variables?
            TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_DAYS_HEATING_DEGREE = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_COUNT_DAYS_HEATING_DEGREE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_DAYS_COOLING_DEGREE = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_COUNT_DAYS_COOLING_DEGREE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRECIPITATION_HEIGHT_LIQUID = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            QUALITY_PRECIPITATION_HEIGHT_LIQUID = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            QUALITY_SNOW_DEPTH_NEW = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            QUALITY_PRECIPITATION_HEIGHT = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            QUALITY_SNOW_DEPTH = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WIND_DIRECTION_GUST_MAX = (
                OriginUnit.WIND_DIRECTION.value,
                SIUnit.WIND_DIRECTION.value,
            )
            QUALITY_WIND_DIRECTION_GUST_MAX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WIND_GUST_MAX = (
                OriginUnit.KILOMETER_PER_HOUR.value,
                SIUnit.METER_PER_SECOND.value,
            )
            QUALITY_WIND_GUST_MAX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

    class MONTHLY(DatasetTreeCore):
        class MONTHLY(UnitEnum):
            TEMPERATURE_AIR_MAX_2M_MEAN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MAX_2M_MEAN = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            TEMPERATURE_AIR_MIN_2M_MEAN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MIN_2M_MEAN = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRECIPITATION_HEIGHT_LIQUID = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            QUALITY_PRECIPITATION_HEIGHT_LIQUID = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            QUALITY_SNOW_DEPTH_NEW = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            QUALITY_PRECIPITATION_HEIGHT = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # should name include previous day? how is it measured?
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            QUALITY_SNOW_DEPTH = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WIND_DIRECTION_GUST_MAX = (
                OriginUnit.WIND_DIRECTION.value,
                SIUnit.WIND_DIRECTION.value,
            )
            QUALITY_WIND_DIRECTION_GUST_MAX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WIND_GUST_MAX = (
                OriginUnit.KILOMETER_PER_HOUR.value,
                SIUnit.METER_PER_SECOND.value,
            )
            QUALITY_WIND_GUST_MAX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

    class ANNUAL(DatasetTreeCore):
        class ANNUAL(UnitEnum):
            TEMPERATURE_AIR_MAX_2M_MEAN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_2M_MEAN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            PRECIPITATION_FREQUENCY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            # 'highest temp.year'
            # 'highest temp. period'
            # 'highest temp. data quality'
            TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            # 'lowest temp. year'
            # 'lowest temp. period'
            # 'lowest temp. data quality'
            PRECIPITATION_HEIGHT_MAX = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # 'greatest precip. year'
            # 'greatest precip. period'
            # 'greatest precip. data quality'
            PRECIPITATION_HEIGHT_LIQUID_MAX = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # 'greatest rainfall year'
            # 'greatest rainfall period'
            # 'greatest rainfall data quality'
            SNOW_DEPTH_NEW_MAX = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            # 'greatest snowfall year'
            # 'greatest snowfall period'
            # 'greatest snowfall data quality'
            SNOW_DEPTH_MAX = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            # 'most snow on the ground year'
            # 'most snow on the ground period'
            # 'most snow on the ground data quality'
