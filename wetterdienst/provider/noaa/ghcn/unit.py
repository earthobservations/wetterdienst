# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.

from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.parameter import DatasetTreeCore


class NoaaGhcnUnit(DatasetTreeCore):
    """NOAA Global Historical Climatology Network Parameters"""

    class HOURLY(DatasetTreeCore):
        class HOURLY(UnitEnum):
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_3H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_6H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_9H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_12H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_15H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_18H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_21H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_24H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SITE_DELTA_LAST_3H = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SITE_REDUCED = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_DEW_POINT_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_WET_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            VISIBILITY_RANGE = OriginUnit.KILOMETER.value, SIUnit.METER.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

    class DAILY(DatasetTreeCore):
        class DAILY(UnitEnum):
            # The five core values are:

            # Precipitation (mm or inches as per user preference, inches to hundredths on Daily Form pdf file)
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Snowfall (mm or inches as per user preference, inches to tenths on Daily Form pdf file)
            SNOW_DEPTH_NEW = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Snow depth (mm or inches as per user preference, inches on Daily Form pdf file)
            SNOW_DEPTH = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Maximum  temperature  (Fahrenheit or  Celsius  as per  user  preference,
            # Fahrenheit  to  tenths on Daily Form pdf file
            TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            # Minimum  temperature  (Fahrenheit  or  Celsius as per  user  preference,
            # Fahrenheit  to  tenths  on Daily Form pdf file
            TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # Additional parameters:

            # Average cloudiness midnight to midnight from 30-second ceilometer data (percent)
            CLOUD_COVER_TOTAL_MIDNIGHT_TO_MIDNIGHT = (
                OriginUnit.PERCENT.value,
                SIUnit.PERCENT.value,
            )
            # Average cloudiness midnight to midnight from manual observation (percent)
            CLOUD_COVER_TOTAL_MIDNIGHT_TO_MIDNIGHT_MANUAL = (
                OriginUnit.PERCENT.value,
                SIUnit.PERCENT.value,
            )
            # Average cloudiness sunrise to sunset from 30-second ceilometer data (percent)
            CLOUD_COVER_TOTAL_SUNRISE_TO_SUNSET = (
                OriginUnit.PERCENT.value,
                SIUnit.PERCENT.value,
            )
            # Average cloudiness sunrise to sunset from manual observation (percent)
            CLOUD_COVER_TOTAL_SUNRISE_TO_SUNSET_MANUAL = (
                OriginUnit.PERCENT.value,
                SIUnit.PERCENT.value,
            )
            # TODO: use one CLOUD_COVER_TOTAL parameter that builds one time series
            #  from the multiple existing parameters
            #  cloud cover total is usually measured on a daily basis ending at midnight
            #  so this is a synonym for midnight-to-midnight

            # Average daily wind speed (meters per second or miles per hour as per user preference)
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            # Number of days included in the multiday evaporation total (MDEV)
            COUNT_DAYS_MULTIDAY_EVAPORATION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # Number of days included in the multiday precipitation total (MDPR)
            COUNT_DAYS_MULTIDAY_PRECIPITATION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # Number of days included in the multiday snowfall total (MDSF)
            COUNT_DAYS_MULTIDAY_SNOW_DEPTH_NEW = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # Number of days included in the multiday minimum temperature (MDTN)
            COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # Number of days included in the multiday maximum temperature (MDTX)
            COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # Number of days included in the multiday wind movement (MDWM)
            COUNT_DAYS_MULTIDAY_WIND_MOVEMENT = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # Number of days with non-zero precipitation included in multiday precipitation total (MDPR)
            COUNT_DAYS_MULTIDAY_PRECIPITATION_HEIGHT_GT_0MM = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # Evaporation of water from evaporation pan (mm or inches as per user preference, or hundredths of inches
            # on Daily Form pdf file)
            EVAPORATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Time of fastest mile or fastest 1-minute wind (hours and minutes, i.e., HHMM)
            TIME_WIND_GUST_MAX_1MILE_OR_1MIN = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            # Base of frozen ground layer (cm or inches as per user preference)
            FROZEN_GROUND_LAYER_BASE = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            # Top of frozen ground layer (cm or inches as per user preference)
            FROZEN_GROUND_LAYER_TOP = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            # Thickness of frozen ground layer (cm or inches as per user preference)
            FROZEN_GROUND_LAYER_THICKNESS = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            # Difference between river and gauge height (cm or inches as per user preference)
            DISTANCE_RIVER_GAUGE_HEIGHT = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            # Multiday evaporation total (mm or inches as per user preference; use with DAEV)
            EVAPORATION_HEIGHT_MULTIDAY = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Multiday precipitation total (mm or inches as per user preference; use with DAPR and DWPR, if available)
            PRECIPITATION_HEIGHT_MULTIDAY = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Multiday snowfall total (mm or inches as per user preference)
            SNOW_DEPTH_NEW_MULTIDAY = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Multiday minimum temperature (Fahrenheit or Celsius as per user preference ; use with DATN)
            TEMPERATURE_AIR_MIN_2M_MULTIDAY = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            # Multiday maximum temperature (Fahrenheit or Celsius as per user preference ; use with DATX)
            TEMPERATURE_AIR_MAX_2M_MULTIDAY = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            # Multiday wind movement (miles or km as per user preference)
            WIND_MOVEMENT_MULTIDAY = OriginUnit.KILOMETER.value, SIUnit.METER.value
            # Daily minimum temperature of water in an evaporation pan (Fahrenheit or Celsius as per user preference)
            TEMPERATURE_WATER_EVAPORATION_PAN_MIN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            # Daily maximum temperature of water in an evaporation pan (Fahrenheit or Celsius as per user preference)
            TEMPERATURE_WATER_EVAPORATION_PAN_MAX = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            # Peak gust time (hours and minutes, i.e., HHMM)
            TIME_WIND_GUST_MAX = OriginUnit.SECOND.value, SIUnit.SECOND.value
            # Daily percent of possible sunshine (percent)
            SUNSHINE_DURATION_RELATIVE = OriginUnit.PERCENT.value, SIUnit.PERCENT.value

            """
            ----------------------------------------------------------------------
            SN*# = Minimum soil temperature
            SX*# = Maximum soil temperature

                where
                 * corresponds to a code for ground cover and
                 # corresponds to a code for soil depth (Fahrenheit or Celsius
                 as per user preference)

                Ground cover codes include the following:
                    0 = unknown
                    1 = grass
                    2 = fallow
                    3 = bare ground
                    4 = brome grass
                    5 = sod
                    6 = straw mulch
                    7 = grass muck
                    8 = bare muck

                Depth codes include the following:
                    1 = 5 cm
                    2 = 10 cm
                    3 = 20 cm
                    4 = 50 cm
                    5 = 100 cm
                    6 = 150 cm
                    7 = 180 cm
            """

            # Height definition similar to temperature with three digits
            # 0 - unknown
            TEMPERATURE_SOIL_MIN_UNKNOWN_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_UNKNOWN_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_UNKNOWN_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_UNKNOWN_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_UNKNOWN_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_UNKNOWN_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_UNKNOWN_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_UNKNOWN_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_UNKNOWN_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_UNKNOWN_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_UNKNOWN_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_UNKNOWN_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_UNKNOWN_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_UNKNOWN_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # 1 - grass
            TEMPERATURE_SOIL_MIN_GRASS_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_GRASS_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # 2 - fallow
            TEMPERATURE_SOIL_MIN_FALLOW_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_FALLOW_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_FALLOW_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_FALLOW_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_FALLOW_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_FALLOW_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_FALLOW_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_FALLOW_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_FALLOW_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_FALLOW_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_FALLOW_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_FALLOW_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_FALLOW_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_FALLOW_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # 3 - bare ground
            TEMPERATURE_SOIL_MIN_BARE_GROUND_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_GROUND_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_GROUND_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_GROUND_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_GROUND_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_GROUND_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_GROUND_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_BARE_GROUND_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_GROUND_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_GROUND_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_GROUND_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_GROUND_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_GROUND_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_GROUND_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # 4 - brome grass
            TEMPERATURE_SOIL_MIN_BROME_GRASS_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BROME_GRASS_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BROME_GRASS_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BROME_GRASS_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BROME_GRASS_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BROME_GRASS_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BROME_GRASS_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_BROME_GRASS_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BROME_GRASS_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BROME_GRASS_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BROME_GRASS_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BROME_GRASS_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BROME_GRASS_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BROME_GRASS_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # 5 - sod
            TEMPERATURE_SOIL_MIN_SOD_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_SOD_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_SOD_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_SOD_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_SOD_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_SOD_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_SOD_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_SOD_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_SOD_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_SOD_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_SOD_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_SOD_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_SOD_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_SOD_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # 6 - straw mulch
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # 7 - grass muck
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # 8 - bare muck
            TEMPERATURE_SOIL_MIN_BARE_MUCK_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_MUCK_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_MUCK_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_MUCK_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_MUCK_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_MUCK_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MIN_BARE_MUCK_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            TEMPERATURE_SOIL_MAX_BARE_MUCK_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_MUCK_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_MUCK_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_MUCK_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_MUCK_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_MUCK_1_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MAX_BARE_MUCK_1_8M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

            # Thickness of ice on water (inches or mm as per user preference)
            ICE_ON_WATER_THICKNESS = OriginUnit.MILLIMETER.value, SIUnit.METER.value
            # Temperature at the time of observation  (Fahrenheit or Celsius as per user preference)
            TEMPERATURE_AIR_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            # Daily total sunshine (minutes)
            SUNSHINE_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value
            # Direction of fastest 5-second wind (degrees)
            WIND_DIRECTION_GUST_MAX_5SEC = (
                OriginUnit.DEGREE.value,
                SIUnit.WIND_DIRECTION.value,
            )
            # Direction of fastest 1-minute wind (degrees)
            WIND_DIRECTION_GUST_MAX_1MIN = (
                OriginUnit.DEGREE.value,
                SIUnit.WIND_DIRECTION.value,
            )
            # Direction of fastest 2-minute wind (degrees)
            WIND_DIRECTION_GUST_MAX_2MIN = (
                OriginUnit.DEGREE.value,
                SIUnit.WIND_DIRECTION.value,
            )
            # Direction of peak wind gust (degrees)
            WIND_DIRECTION_GUST_MAX = (
                OriginUnit.DEGREE.value,
                SIUnit.WIND_DIRECTION.value,
            )
            # Direction of highest instantaneous wind (degrees)
            WIND_DIRECTION_GUST_MAX_INSTANT = (
                OriginUnit.DEGREE.value,
                SIUnit.WIND_DIRECTION.value,
            )
            # Fastest mile wind direction (degrees)
            WIND_DIRECTION_GUST_MAX_1MILE = (
                OriginUnit.DEGREE.value,
                SIUnit.WIND_DIRECTION.value,
            )
            # 24-hour wind movement (km or miles as per user preference, miles on Daily Form pdf file)
            WIND_MOVEMENT_24H = OriginUnit.KILOMETER.value, SIUnit.METER.value
            # Water equivalent of snow on the ground (inches or mm as per user preference)
            WATER_EQUIVALENT_SNOW_DEPTH = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Water equivalent of snowfall (inches or mm as per user preference)
            WATER_EQUIVALENT_SNOW_DEPTH_NEW = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            # Fastest 1-minute wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_5SEC = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            # Fastest 2-minute wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_1MIN = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            # Fastest 5-second wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_2MIN = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            # Peak guest wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            # Highest instantaneous wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_INSTANT = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            # Fastest mile wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_1MILE = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )

            """
            WT** = Weather Type where ** has one of the following values:
                01 = Fog, ice fog, or freezing fog (may include heavy fog)
                02 = Heavy fog or heaving freezing fog (not always distinguished from fog)
                03 = Thunder
                04 = Ice pellets, sleet, snow pellets, or small hail
                05 = Hail (may include small hail)
                06 = Glaze or rime
                07 = Dust, volcanic ash, blowing dust, blowing sand, or blowing obstruction
                08 = Smoke or haze
                09 = Blowing or drifting snow
                10 = Tornado, waterspout, or funnel cloud
                11 = High or damaging winds
                12 = Blowing spray
                13 = Mist
                14 = Drizzle
                15 = Freezing drizzle
                16 = Rain (may include freezing rain, drizzle, and freezing drizzle)
                17 = Freezing rain
                18 = Snow, snow pellets, snow grains, or ice crystals
                19 = Unknown source of precipitation
                21 = Ground fog
                22 = Ice fog or freezing fog
            """
            WEATHER_TYPE_FOG = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WEATHER_TYPE_HEAVY_FOG = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_THUNDER = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_ICE_SLEET_SNOW_HAIL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_HAIL = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WEATHER_TYPE_GLAZE_RIME = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_DUST_ASH_SAND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_SMOKE_HAZE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_BLOWING_DRIFTING_SNOW = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_TORNADO_WATERSPOUT = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_HIGH_DAMAGING_WINDS = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_BLOWING_SPRAY = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_MIST = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WEATHER_TYPE_DRIZZLE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_FREEZING_DRIZZLE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_RAIN = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WEATHER_TYPE_FREEZING_RAIN = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_SNOW_PELLETS_SNOW_GRAINS_ICE_CRYSTALS = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_PRECIPITATION_UNKNOWN_SOURCE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_GROUND_FOG = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_ICE_FOG_FREEZING_FOG = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

            """
            WVxx = Weather in the Vicinity where “xx” has one of the following values
                01 = Fog, ice fog, or freezing fog (may include heavy fog)
                03 = Thunder
                07 = Ash, dust, sand, or other blowing obstruction
                18 = Snow or ice crystals
                20 = Rain or snow shower
            """
            WEATHER_TYPE_VICINITY_FOG_ANY = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_VICINITY_THUNDER = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_VICINITY_DUST_ASH_SAND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_VICINITY_SNOW_ICE_CRYSTALS = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WEATHER_TYPE_VICINITY_RAIN_SNOW_SHOWER = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
