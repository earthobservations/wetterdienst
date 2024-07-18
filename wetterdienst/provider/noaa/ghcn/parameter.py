# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.util.parameter import DatasetTreeCore


class NoaaGhcnParameter(DatasetTreeCore):
    """NOAA Global Historical Climatology Network Parameters"""

    class HOURLY(DatasetTreeCore):
        class HOURLY(Enum):
            # Relative humidity is calculated from air (dry bulb) temperature and dewpoint temperature (whole percent)
            HUMIDITY = "relative_humidity"
            # total liquid precipitation (rain or melted snow) for past hour; a “T” in the measurement code column
            # indicates a trace amount of precipitation (millimeters)
            PRECIPITATION_HEIGHT = "precipitation"
            # 3-hour total liquid precipitation (rain or melted snow) accumulation
            # from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount
            # of precipitation (millimeters); accumulations can be reported over 3,6,9,12,15,18,21 and 24 hours.
            PRECIPITATION_HEIGHT_LAST_3H = "precipitation_3_hour"
            PRECIPITATION_HEIGHT_LAST_6H = "precipitation_6_hour"
            PRECIPITATION_HEIGHT_LAST_9H = "precipitation_9_hour"
            PRECIPITATION_HEIGHT_LAST_12H = "precipitation_12_hour"
            PRECIPITATION_HEIGHT_LAST_15H = "precipitation_15_hour"
            PRECIPITATION_HEIGHT_LAST_18H = "precipitation_18_hour"
            PRECIPITATION_HEIGHT_LAST_21H = "precipitation_21_hour"
            PRECIPITATION_HEIGHT_LAST_24H = "precipitation_24_hour"
            # reduction estimates the pressure that would exist at sea level at a point directly below the station
            # using a temperature profile based on temperatures that actually exist at the station (hPa)
            PRESSURE_AIR_SEA_LEVEL = "sea_level_pressure"
            # the pressure that is observed at a specific elevation and is the true barometric pressure of a location.
            # It is the pressure exerted by the atmosphere at a point as a result of gravity acting upon the "column" of
            # air that lies directly above the point. (hPa)
            PRESSURE_AIR_SITE = "station_level_pressure"
            # change in atmospheric pressure measured at the beginning and end of a three-hour period;
            # accompanied by tendency code in measurement code field (millibars/hPa)
            PRESSURE_AIR_SITE_DELTA_LAST_3H = "pressure_3hr_change"
            # the pressure "reduced" to mean sea level using the temperature profile of the "standard" atmosphere,
            # which is representative of average conditions over the United States at 40 degrees north
            # latitude (millibars/hPa)  # noqa
            PRESSURE_AIR_SITE_REDUCED = "altimeter"
            # depth of snowpack on the ground (centimeters/m)
            SNOW_DEPTH = "snow_depth"
            # 2 meter (circa) Above Ground Level Air (dry bulb) Temperature (⁰C to tenths)
            TEMPERATURE_AIR_MEAN_2M = "temperature"
            # Dew Point Temperature (⁰C to tenths)
            TEMPERATURE_DEW_POINT_MEAN_2M = "dew_point_temperature"
            # Wet bulb temperature (⁰C to tenths)
            TEMPERATURE_WET_MEAN_2M = "wet_bulb_temperature"
            # horizontal distance at which an object can be seen and identified (kilometers)
            VISIBILITY_RANGE = "visibility"
            # Wind Direction from true north using compass directions (e.g. 360=true north, 180=south, 270=west, etc.).
            # Note: A direction of “000” is given for calm winds. (whole degrees)
            WIND_DIRECTION = "wind_direction"
            # Peak short duration (usually < 20 seconds) wind speed (meters per second) that exceeds the wind_speed
            # average
            WIND_GUST_MAX = "wind_gust"
            # Wind Speed (meters per second)
            WIND_SPEED = "wind_speed"

            # the following are left out for now
            # pres_wx_mw1
            # pres_wx_mw2
            # pres_wx_mw3
            # pres_wx_au1
            # pres_wx_au2
            # pres_wx_au3
            # pres_wx_aw1
            # pres_wx_aw2
            # pres_wx_aw3
            # sky_cover_1
            # sky_cover_2
            # sky_cover_3
            # sky_cover_baseht_1
            # sky_cover_baseht_2
            # sky_cover_baseht_3

        HUMIDITY = HOURLY.HUMIDITY
        PRECIPITATION_HEIGHT = HOURLY.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_LAST_3H = HOURLY.PRECIPITATION_HEIGHT_LAST_3H
        PRECIPITATION_HEIGHT_LAST_6H = HOURLY.PRECIPITATION_HEIGHT_LAST_6H
        PRECIPITATION_HEIGHT_LAST_9H = HOURLY.PRECIPITATION_HEIGHT_LAST_9H
        PRECIPITATION_HEIGHT_LAST_12H = HOURLY.PRECIPITATION_HEIGHT_LAST_12H
        PRECIPITATION_HEIGHT_LAST_15H = HOURLY.PRECIPITATION_HEIGHT_LAST_15H
        PRECIPITATION_HEIGHT_LAST_18H = HOURLY.PRECIPITATION_HEIGHT_LAST_18H
        PRECIPITATION_HEIGHT_LAST_21H = HOURLY.PRECIPITATION_HEIGHT_LAST_21H
        PRECIPITATION_HEIGHT_LAST_24H = HOURLY.PRECIPITATION_HEIGHT_LAST_24H
        PRESSURE_AIR_SEA_LEVEL = HOURLY.PRESSURE_AIR_SEA_LEVEL
        PRESSURE_AIR_SITE = HOURLY.PRESSURE_AIR_SITE
        PRESSURE_AIR_SITE_DELTA_LAST_3H = HOURLY.PRESSURE_AIR_SITE_DELTA_LAST_3H
        PRESSURE_AIR_SITE_REDUCED = HOURLY.PRESSURE_AIR_SITE_REDUCED
        SNOW_DEPTH = HOURLY.SNOW_DEPTH
        TEMPERATURE_AIR_MEAN_2M = HOURLY.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_DEW_POINT_MEAN_2M = HOURLY.TEMPERATURE_DEW_POINT_MEAN_2M
        TEMPERATURE_WET_MEAN_2M = HOURLY.TEMPERATURE_WET_MEAN_2M
        VISIBILITY_RANGE = HOURLY.VISIBILITY_RANGE
        WIND_DIRECTION = HOURLY.WIND_DIRECTION
        WIND_GUST_MAX = HOURLY.WIND_GUST_MAX
        WIND_SPEED = HOURLY.WIND_SPEED

    class DAILY(DatasetTreeCore):
        class DAILY(Enum):
            # The five core values are:

            # PRCP = Precipitation (mm or inches as per user preference,
            #     inches to hundredths on Daily Form pdf file)
            PRECIPITATION_HEIGHT = "prcp"
            # SNOW = Snowfall (mm or inches as per user preference,
            #     inches to tenths on Daily Form pdf file)
            SNOW_DEPTH_NEW = "snow"
            # SNWD = Snow depth (mm or inches as per user preference,
            #     inches on Daily Form pdf file)
            SNOW_DEPTH = "snwd"
            # TMAX  = Maximum  temperature  (Fahrenheit or  Celsius  as
            # per  user  preference,
            #     Fahrenheit  to  tenths on Daily Form pdf file
            TEMPERATURE_AIR_MAX_2M = "tmax"
            # TMIN  =  Minimum  temperature  (Fahrenheit  or  Celsius  as
            # per  user  preference,
            #     Fahrenheit  to  tenths  on Daily Form pdf file
            TEMPERATURE_AIR_MIN_2M = "tmin"
            # DERIVED PARAMETER
            TEMPERATURE_AIR_MEAN_2M = "tavg"  # tmean = (tmax + tmin) / 2

            # Additional parameters:

            # Average cloudiness midnight to midnight from 30-second ceilometer data (percent)
            CLOUD_COVER_TOTAL_MIDNIGHT_TO_MIDNIGHT = "acmc"  # ceilometer
            # Average cloudiness midnight to midnight from manual observation (percent)
            CLOUD_COVER_TOTAL_MIDNIGHT_TO_MIDNIGHT_MANUAL = "acmh"  # manual
            # Average cloudiness sunrise to sunset from 30-second ceilometer data (percent)
            CLOUD_COVER_TOTAL_SUNRISE_TO_SUNSET = "acsc"  # ceilometer
            # Average cloudiness sunrise to sunset from manual observation (percent)
            CLOUD_COVER_TOTAL_SUNRISE_TO_SUNSET_MANUAL = "acsh"  # manual
            # TODO: use one CLOUD_COVER_TOTAL parameter that builds one time series
            #  from the multiple existing parameters
            # TODO: cloud cover total is usually measured on a daily basis ending at midnight
            #  so this is a synonym for midnight-to-midnight

            # Average daily wind speed (meters per second or miles per hour as per user preference)
            WIND_SPEED = "awnd"  # m/s
            # Number of days included in the multiday evaporation total (MDEV)
            COUNT_DAYS_MULTIDAY_EVAPORATION = "daev"
            # Number of days included in the multiday precipitation total (MDPR)
            COUNT_DAYS_MULTIDAY_PRECIPITATION = "dapr"
            # Number of days included in the multiday snowfall total (MDSF)
            COUNT_DAYS_MULTIDAY_SNOW_DEPTH_NEW = "dasf"
            # Number of days included in the multiday minimum temperature (MDTN)
            COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MIN_2M = "datn"
            # Number of days included in the multiday maximum temperature (MDTX)
            COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MAX_2M = "datx"
            # Number of days included in the multiday wind movement (MDWM)
            COUNT_DAYS_MULTIDAY_WIND_MOVEMENT = "dawm"  # TODO: what network of parameter ?
            # Number of days with non-zero precipitation included in multiday precipitation total (MDPR)
            COUNT_DAYS_MULTIDAY_PRECIPITATION_HEIGHT_GT_0MM = "dwpr"
            # Evaporation of water from evaporation pan (mm or inches as per user preference, or hundredths of inches
            # on Daily Form pdf file)
            EVAPORATION_HEIGHT = "evap"  # from evaporation pan, mm
            # Time of fastest mile or fastest 1-minute wind (hours and minutes, i.e., HHMM)
            TIME_WIND_GUST_MAX_1MILE_OR_1MIN = "fmtm"  # HH:MM
            # Base of frozen ground layer (cm or inches as per user preference)
            FROZEN_GROUND_LAYER_BASE = "frgb"  # cm
            # Top of frozen ground layer (cm or inches as per user preference)
            FROZEN_GROUND_LAYER_TOP = "frgt"
            # Thickness of frozen ground layer (cm or inches as per user preference)
            FROZEN_GROUND_LAYER_THICKNESS = "frth"
            # Difference between river and gauge height (cm or inches as per user preference)
            DISTANCE_RIVER_GAUGE_HEIGHT = "gaht"
            # Multiday evaporation total (mm or inches as per user preference; use with DAEV)
            EVAPORATION_HEIGHT_MULTIDAY = "mdev"
            # Multiday precipitation total (mm or inches as per user preference; use with DAPR and DWPR, if available)
            PRECIPITATION_HEIGHT_MULTIDAY = "mdpr"
            # Multiday snowfall total (mm or inches as per user preference)
            SNOW_DEPTH_NEW_MULTIDAY = "mdsf"
            # Multiday minimum temperature (Fahrenheit or Celsius as per user preference ; use with DATN)
            TEMPERATURE_AIR_MIN_2M_MULTIDAY = "mdtn"
            # Multiday maximum temperature (Fahrenheit or Celsius as per user preference ; use with DATX)
            TEMPERATURE_AIR_MAX_2M_MULTIDAY = "mdtx"
            # Multiday wind movement (miles or km as per user preference)
            WIND_MOVEMENT_MULTIDAY = "mdwm"  # km
            # Daily minimum temperature of water in an evaporation pan (Fahrenheit or Celsius as per user preference)
            TEMPERATURE_WATER_EVAPORATION_PAN_MIN = "mnpn"
            # Daily maximum temperature of water in an evaporation pan  (Fahrenheit or Celsius as per user preference)
            TEMPERATURE_WATER_EVAPORATION_PAN_MAX = "mxpn"
            # Peak gust time (hours and minutes, i.e., HHMM)
            TIME_WIND_GUST_MAX = "pgtm"
            # Daily percent of possible sunshine (percent)
            SUNSHINE_DURATION_RELATIVE = "psun"

            # TODO:
            #  Currently we have a combination of
            #  8 x 7 = 56 possible soil temperature parameters
            #  that's a lot...
            #  Maybe:
            #  The soil type - if of interest - should be known already by the user
            #  thus the soil type should be of secondary interest and can be moved to
            #  quality secondary or whatever similar
            #  what is left is only the depth of the measurement, which is required
            #  as without it the temperature is somewhat irrelevant
            """
            ----------------------------------------------------------------------
            SN*# = Minimum soil temperature
            SX*# = Maximum soil temperature

                where
                 * corresponds to a code for ground cover and
                 # corresponds to a code for soil depth (Fahrenheit or Celsius as
                 per user preference)

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
            TEMPERATURE_SOIL_MIN_UNKNOWN_0_05M = "sn01"  # °C
            TEMPERATURE_SOIL_MIN_UNKNOWN_0_1M = "sn02"  # °C
            TEMPERATURE_SOIL_MIN_UNKNOWN_0_2M = "sn03"  # °C
            TEMPERATURE_SOIL_MIN_UNKNOWN_0_5M = "sn04"  # °C
            TEMPERATURE_SOIL_MIN_UNKNOWN_1M = "sn05"  # °C
            TEMPERATURE_SOIL_MIN_UNKNOWN_1_5M = "sn06"  # °C
            TEMPERATURE_SOIL_MIN_UNKNOWN_1_8M = "sn07"  # °C

            TEMPERATURE_SOIL_MAX_UNKNOWN_0_05M = "sx01"  # °C
            TEMPERATURE_SOIL_MAX_UNKNOWN_0_1M = "sx02"  # °C
            TEMPERATURE_SOIL_MAX_UNKNOWN_0_2M = "sx03"  # °C
            TEMPERATURE_SOIL_MAX_UNKNOWN_0_5M = "sx04"  # °C
            TEMPERATURE_SOIL_MAX_UNKNOWN_1M = "sx05"  # °C
            TEMPERATURE_SOIL_MAX_UNKNOWN_1_5M = "sx06"  # °C
            TEMPERATURE_SOIL_MAX_UNKNOWN_1_8M = "sx07"  # °C

            # 1 - grass
            TEMPERATURE_SOIL_MIN_GRASS_0_05M = "sn11"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_0_1M = "sn12"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_0_2M = "sn13"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_0_5M = "sn14"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_1M = "sn15"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_1_5M = "sn16"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_1_8M = "sn17"  # °C

            TEMPERATURE_SOIL_MAX_GRASS_0_05M = "sx11"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_0_1M = "sx12"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_0_2M = "sx13"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_0_5M = "sx14"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_1M = "sx15"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_1_5M = "sx16"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_1_8M = "sx17"  # °C

            # 2 - fallow
            TEMPERATURE_SOIL_MIN_FALLOW_0_05M = "sn21"  # °C
            TEMPERATURE_SOIL_MIN_FALLOW_0_1M = "sn22"  # °C
            TEMPERATURE_SOIL_MIN_FALLOW_0_2M = "sn23"  # °C
            TEMPERATURE_SOIL_MIN_FALLOW_0_5M = "sn24"  # °C
            TEMPERATURE_SOIL_MIN_FALLOW_1M = "sn25"  # °C
            TEMPERATURE_SOIL_MIN_FALLOW_1_5M = "sn26"  # °C
            TEMPERATURE_SOIL_MIN_FALLOW_1_8M = "sn27"  # °C

            TEMPERATURE_SOIL_MAX_FALLOW_0_05M = "sx21"  # °C
            TEMPERATURE_SOIL_MAX_FALLOW_0_1M = "sx22"  # °C
            TEMPERATURE_SOIL_MAX_FALLOW_0_2M = "sx23"  # °C
            TEMPERATURE_SOIL_MAX_FALLOW_0_5M = "sx24"  # °C
            TEMPERATURE_SOIL_MAX_FALLOW_1M = "sx25"  # °C
            TEMPERATURE_SOIL_MAX_FALLOW_1_5M = "sx26"  # °C
            TEMPERATURE_SOIL_MAX_FALLOW_1_8M = "sx27"  # °C

            # 3 - bare ground
            TEMPERATURE_SOIL_MIN_BARE_GROUND_0_05M = "sn31"  # °C
            TEMPERATURE_SOIL_MIN_BARE_GROUND_0_1M = "sn32"  # °C
            TEMPERATURE_SOIL_MIN_BARE_GROUND_0_2M = "sn33"  # °C
            TEMPERATURE_SOIL_MIN_BARE_GROUND_0_5M = "sn34"  # °C
            TEMPERATURE_SOIL_MIN_BARE_GROUND_1M = "sn35"  # °C
            TEMPERATURE_SOIL_MIN_BARE_GROUND_1_5M = "sn36"  # °C
            TEMPERATURE_SOIL_MIN_BARE_GROUND_1_8M = "sn37"  # °C

            TEMPERATURE_SOIL_MAX_BARE_GROUND_0_05M = "sx31"  # °C
            TEMPERATURE_SOIL_MAX_BARE_GROUND_0_1M = "sx32"  # °C
            TEMPERATURE_SOIL_MAX_BARE_GROUND_0_2M = "sx33"  # °C
            TEMPERATURE_SOIL_MAX_BARE_GROUND_0_5M = "sx34"  # °C
            TEMPERATURE_SOIL_MAX_BARE_GROUND_1M = "sx35"  # °C
            TEMPERATURE_SOIL_MAX_BARE_GROUND_1_5M = "sx36"  # °C
            TEMPERATURE_SOIL_MAX_BARE_GROUND_1_8M = "sx37"  # °C

            # 4 - brome grass
            TEMPERATURE_SOIL_MIN_BROME_GRASS_0_05M = "sn41"  # °C
            TEMPERATURE_SOIL_MIN_BROME_GRASS_0_1M = "sn42"  # °C
            TEMPERATURE_SOIL_MIN_BROME_GRASS_0_2M = "sn43"  # °C
            TEMPERATURE_SOIL_MIN_BROME_GRASS_0_5M = "sn44"  # °C
            TEMPERATURE_SOIL_MIN_BROME_GRASS_1M = "sn45"  # °C
            TEMPERATURE_SOIL_MIN_BROME_GRASS_1_5M = "sn46"  # °C
            TEMPERATURE_SOIL_MIN_BROME_GRASS_1_8M = "sn47"  # °C

            TEMPERATURE_SOIL_MAX_BROME_GRASS_0_05M = "sx41"  # °C
            TEMPERATURE_SOIL_MAX_BROME_GRASS_0_1M = "sx42"  # °C
            TEMPERATURE_SOIL_MAX_BROME_GRASS_0_2M = "sx43"  # °C
            TEMPERATURE_SOIL_MAX_BROME_GRASS_0_5M = "sx44"  # °C
            TEMPERATURE_SOIL_MAX_BROME_GRASS_1M = "sx45"  # °C
            TEMPERATURE_SOIL_MAX_BROME_GRASS_1_5M = "sx46"  # °C
            TEMPERATURE_SOIL_MAX_BROME_GRASS_1_8M = "sx47"  # °C

            # 5 - sod
            TEMPERATURE_SOIL_MIN_SOD_0_05M = "sn51"  # °C
            TEMPERATURE_SOIL_MIN_SOD_0_1M = "sn52"  # °C
            TEMPERATURE_SOIL_MIN_SOD_0_2M = "sn53"  # °C
            TEMPERATURE_SOIL_MIN_SOD_0_5M = "sn54"  # °C
            TEMPERATURE_SOIL_MIN_SOD_1M = "sn55"  # °C
            TEMPERATURE_SOIL_MIN_SOD_1_5M = "sn56"  # °C
            TEMPERATURE_SOIL_MIN_SOD_1_8M = "sn57"  # °C

            TEMPERATURE_SOIL_MAX_SOD_0_05M = "sx51"  # °C
            TEMPERATURE_SOIL_MAX_SOD_0_1M = "sx52"  # °C
            TEMPERATURE_SOIL_MAX_SOD_0_2M = "sx53"  # °C
            TEMPERATURE_SOIL_MAX_SOD_0_5M = "sx54"  # °C
            TEMPERATURE_SOIL_MAX_SOD_1M = "sx55"  # °C
            TEMPERATURE_SOIL_MAX_SOD_1_5M = "sx56"  # °C
            TEMPERATURE_SOIL_MAX_SOD_1_8M = "sx57"  # °C

            # 6 - straw mulch
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_05M = "sn61"  # °C
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_1M = "sn62"  # °C
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_2M = "sn63"  # °C
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_5M = "sn64"  # °C
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_1M = "sn65"  # °C
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_5M = "sn66"  # °C
            TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_8M = "sn67"  # °C

            TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_05M = "sx61"  # °C
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_1M = "sx62"  # °C
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_2M = "sx63"  # °C
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_5M = "sx64"  # °C
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_1M = "sx65"  # °C
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_5M = "sx66"  # °C
            TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_8M = "sx67"  # °C

            # 7 - grass muck
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_05M = "sn71"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_1M = "sn72"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_2M = "sn73"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_5M = "sn74"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_1M = "sn75"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_5M = "sn76"  # °C
            TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_8M = "sn77"  # °C

            TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_05M = "sx71"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_1M = "sx72"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_2M = "sx73"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_5M = "sx74"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_1M = "sx75"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_5M = "sx76"  # °C
            TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_8M = "sx77"  # °C

            # 8 - bare muck
            TEMPERATURE_SOIL_MIN_BARE_MUCK_0_05M = "sn81"  # °C
            TEMPERATURE_SOIL_MIN_BARE_MUCK_0_1M = "sn82"  # °C
            TEMPERATURE_SOIL_MIN_BARE_MUCK_0_2M = "sn83"  # °C
            TEMPERATURE_SOIL_MIN_BARE_MUCK_0_5M = "sn84"  # °C
            TEMPERATURE_SOIL_MIN_BARE_MUCK_1M = "sn85"  # °C
            TEMPERATURE_SOIL_MIN_BARE_MUCK_1_5M = "sn86"  # °C
            TEMPERATURE_SOIL_MIN_BARE_MUCK_1_8M = "sn87"  # °C

            TEMPERATURE_SOIL_MAX_BARE_MUCK_0_05M = "sx81"  # °C
            TEMPERATURE_SOIL_MAX_BARE_MUCK_0_1M = "sx82"  # °C
            TEMPERATURE_SOIL_MAX_BARE_MUCK_0_2M = "sx83"  # °C
            TEMPERATURE_SOIL_MAX_BARE_MUCK_0_5M = "sx84"  # °C
            TEMPERATURE_SOIL_MAX_BARE_MUCK_1M = "sx85"  # °C
            TEMPERATURE_SOIL_MAX_BARE_MUCK_1_5M = "sx86"  # °C
            TEMPERATURE_SOIL_MAX_BARE_MUCK_1_8M = "sx87"  # °C

            # Thickness of ice on water (inches or mm as per user preference)
            ICE_ON_WATER_THICKNESS = "thic"
            # Temperature at the time of observation  (Fahrenheit or Celsius as per user preference)
            TEMPERATURE_AIR_2M = "tobs"
            # Daily total sunshine (minutes)
            SUNSHINE_DURATION = "tsun"
            # Direction of fastest 5-second wind (degrees)
            WIND_DIRECTION_GUST_MAX_5SEC = "wdf5"
            # Direction of fastest 1-minute wind (degrees)
            WIND_DIRECTION_GUST_MAX_1MIN = "wdf1"
            # Direction of fastest 2-minute wind (degrees)
            WIND_DIRECTION_GUST_MAX_2MIN = "wdf2"
            # Direction of peak wind gust (degrees)
            WIND_DIRECTION_GUST_MAX = "wdfg"
            # Direction of highest instantaneous wind (degrees)
            WIND_DIRECTION_GUST_MAX_INSTANT = "wdfi"
            # Fastest mile wind direction (degrees)
            WIND_DIRECTION_GUST_MAX_1MILE = "wdfm"
            # 24-hour wind movement (km or miles as per user preference, miles on Daily Form pdf file)
            WIND_MOVEMENT_24H = "wdmv"
            # Water equivalent of snow on the ground (inches or mm as per user preference)
            WATER_EQUIVALENT_SNOW_DEPTH = "wesd"
            # Water equivalent of snowfall (inches or mm as per user preference)
            WATER_EQUIVALENT_SNOW_DEPTH_NEW = "wesf"
            # Fastest 5-second wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_5SEC = "wsf5"
            # Fastest 1-minute wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_1MIN = "wsf1"
            # Fastest 2-minute wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_2MIN = "wsf2"
            # Peak guest wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX = "wsfg"
            # Highest instantaneous wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_INSTANT = "wsfi"
            # Fastest mile wind speed (miles per hour or  meters per second as per user preference)
            WIND_GUST_MAX_1MILE = "wsfm"

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
            WEATHER_TYPE_FOG = "wt01"
            WEATHER_TYPE_HEAVY_FOG = "wt02"
            WEATHER_TYPE_THUNDER = "wt03"
            WEATHER_TYPE_ICE_SLEET_SNOW_HAIL = "wt04"
            WEATHER_TYPE_HAIL = "wt05"
            WEATHER_TYPE_GLAZE_RIME = "wt06"
            WEATHER_TYPE_DUST_ASH_SAND = "wt07"
            WEATHER_TYPE_SMOKE_HAZE = "wt08"
            WEATHER_TYPE_BLOWING_DRIFTING_SNOW = "wt09"
            WEATHER_TYPE_TORNADO_WATERSPOUT = "wt10"
            WEATHER_TYPE_HIGH_DAMAGING_WINDS = "wt11"
            WEATHER_TYPE_BLOWING_SPRAY = "wt12"
            WEATHER_TYPE_MIST = "wt13"
            WEATHER_TYPE_DRIZZLE = "wt14"
            WEATHER_TYPE_FREEZING_DRIZZLE = "wt15"
            WEATHER_TYPE_RAIN = "wt16"
            WEATHER_TYPE_FREEZING_RAIN = "wt17"
            WEATHER_TYPE_SNOW_PELLETS_SNOW_GRAINS_ICE_CRYSTALS = "wt18"
            WEATHER_TYPE_PRECIPITATION_UNKNOWN_SOURCE = "wt19"
            WEATHER_TYPE_GROUND_FOG = "wt21"
            WEATHER_TYPE_ICE_FOG_FREEZING_FOG = "wt22"

            """
            WVxx = Weather in the Vicinity where “xx” has one of the following values
                01 = Fog, ice fog, or freezing fog (may include heavy fog)
                03 = Thunder
                07 = Ash, dust, sand, or other blowing obstruction
                18 = Snow or ice crystals
                20 = Rain or snow shower
            """
            WEATHER_TYPE_VICINITY_FOG_ANY = "wv01"
            WEATHER_TYPE_VICINITY_THUNDER = "wv03"
            WEATHER_TYPE_VICINITY_DUST_ASH_SAND = "wv07"
            WEATHER_TYPE_VICINITY_SNOW_ICE_CRYSTALS = "wv18"
            WEATHER_TYPE_VICINITY_RAIN_SNOW_SHOWER = "wv20"

        PRECIPITATION_HEIGHT = DAILY.PRECIPITATION_HEIGHT
        SNOW_DEPTH_NEW = DAILY.SNOW_DEPTH_NEW
        SNOW_DEPTH = DAILY.SNOW_DEPTH
        TEMPERATURE_AIR_MAX_2M = DAILY.TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_AIR_MIN_2M = DAILY.TEMPERATURE_AIR_MIN_2M
        TEMPERATURE_AIR_MEAN_2M = DAILY.TEMPERATURE_AIR_MEAN_2M
        CLOUD_COVER_TOTAL_MIDNIGHT_TO_MIDNIGHT = DAILY.CLOUD_COVER_TOTAL_MIDNIGHT_TO_MIDNIGHT
        CLOUD_COVER_TOTAL_MIDNIGHT_TO_MIDNIGHT_MANUAL = DAILY.CLOUD_COVER_TOTAL_MIDNIGHT_TO_MIDNIGHT_MANUAL
        CLOUD_COVER_TOTAL_SUNRISE_TO_SUNSET = DAILY.CLOUD_COVER_TOTAL_SUNRISE_TO_SUNSET
        CLOUD_COVER_TOTAL_SUNRISE_TO_SUNSET_MANUAL = DAILY.CLOUD_COVER_TOTAL_SUNRISE_TO_SUNSET_MANUAL
        WIND_SPEED = DAILY.WIND_SPEED
        COUNT_DAYS_MULTIDAY_EVAPORATION = DAILY.COUNT_DAYS_MULTIDAY_EVAPORATION
        COUNT_DAYS_MULTIDAY_PRECIPITATION = DAILY.COUNT_DAYS_MULTIDAY_PRECIPITATION
        COUNT_DAYS_MULTIDAY_SNOW_DEPTH_NEW = DAILY.COUNT_DAYS_MULTIDAY_SNOW_DEPTH_NEW
        COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MIN_2M = DAILY.COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MIN_2M
        COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MAX_2M = DAILY.COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MAX_2M
        COUNT_DAYS_MULTIDAY_WIND_MOVEMENT = DAILY.COUNT_DAYS_MULTIDAY_WIND_MOVEMENT
        COUNT_DAYS_MULTIDAY_PRECIPITATION_HEIGHT_GT_0MM = DAILY.COUNT_DAYS_MULTIDAY_PRECIPITATION_HEIGHT_GT_0MM
        EVAPORATION_HEIGHT = DAILY.EVAPORATION_HEIGHT
        TIME_WIND_GUST_MAX_1MILE_OR_1MIN = DAILY.TIME_WIND_GUST_MAX_1MILE_OR_1MIN
        FROZEN_GROUND_LAYER_BASE = DAILY.FROZEN_GROUND_LAYER_BASE
        FROZEN_GROUND_LAYER_TOP = DAILY.FROZEN_GROUND_LAYER_TOP
        FROZEN_GROUND_LAYER_THICKNESS = DAILY.FROZEN_GROUND_LAYER_THICKNESS
        DISTANCE_RIVER_GAUGE_HEIGHT = DAILY.DISTANCE_RIVER_GAUGE_HEIGHT
        EVAPORATION_HEIGHT_MULTIDAY = DAILY.EVAPORATION_HEIGHT_MULTIDAY
        PRECIPITATION_HEIGHT_MULTIDAY = DAILY.PRECIPITATION_HEIGHT_MULTIDAY
        SNOW_DEPTH_NEW_MULTIDAY = DAILY.SNOW_DEPTH_NEW_MULTIDAY
        TEMPERATURE_AIR_MIN_2M_MULTIDAY = DAILY.TEMPERATURE_AIR_MIN_2M_MULTIDAY
        TEMPERATURE_AIR_MAX_2M_MULTIDAY = DAILY.TEMPERATURE_AIR_MAX_2M_MULTIDAY
        WIND_MOVEMENT_MULTIDAY = DAILY.WIND_MOVEMENT_MULTIDAY
        TEMPERATURE_WATER_EVAPORATION_PAN_MIN = DAILY.TEMPERATURE_WATER_EVAPORATION_PAN_MIN
        TEMPERATURE_WATER_EVAPORATION_PAN_MAX = DAILY.TEMPERATURE_WATER_EVAPORATION_PAN_MAX
        TIME_WIND_GUST_MAX = DAILY.TIME_WIND_GUST_MAX
        SUNSHINE_DURATION_RELATIVE = DAILY.SUNSHINE_DURATION_RELATIVE
        TEMPERATURE_SOIL_MIN_UNKNOWN_0_05M = DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_0_05M
        TEMPERATURE_SOIL_MIN_UNKNOWN_0_1M = DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_0_1M
        TEMPERATURE_SOIL_MIN_UNKNOWN_0_2M = DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_0_2M
        TEMPERATURE_SOIL_MIN_UNKNOWN_0_5M = DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_0_5M
        TEMPERATURE_SOIL_MIN_UNKNOWN_1M = DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_1M
        TEMPERATURE_SOIL_MIN_UNKNOWN_1_5M = DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_1_5M
        TEMPERATURE_SOIL_MIN_UNKNOWN_1_8M = DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_1_8M
        TEMPERATURE_SOIL_MAX_UNKNOWN_0_05M = DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_0_05M
        TEMPERATURE_SOIL_MAX_UNKNOWN_0_1M = DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_0_1M
        TEMPERATURE_SOIL_MAX_UNKNOWN_0_2M = DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_0_2M
        TEMPERATURE_SOIL_MAX_UNKNOWN_0_5M = DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_0_5M
        TEMPERATURE_SOIL_MAX_UNKNOWN_1M = DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_1M
        TEMPERATURE_SOIL_MAX_UNKNOWN_1_5M = DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_1_5M
        TEMPERATURE_SOIL_MAX_UNKNOWN_1_8M = DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_1_8M
        TEMPERATURE_SOIL_MIN_GRASS_0_05M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_0_05M
        TEMPERATURE_SOIL_MIN_GRASS_0_1M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_0_1M
        TEMPERATURE_SOIL_MIN_GRASS_0_2M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_0_2M
        TEMPERATURE_SOIL_MIN_GRASS_0_5M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_0_5M
        TEMPERATURE_SOIL_MIN_GRASS_1M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_1M
        TEMPERATURE_SOIL_MIN_GRASS_1_5M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_1_5M
        TEMPERATURE_SOIL_MIN_GRASS_1_8M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_1_8M
        TEMPERATURE_SOIL_MAX_GRASS_0_05M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_0_05M
        TEMPERATURE_SOIL_MAX_GRASS_0_1M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_0_1M
        TEMPERATURE_SOIL_MAX_GRASS_0_2M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_0_2M
        TEMPERATURE_SOIL_MAX_GRASS_0_5M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_0_5M
        TEMPERATURE_SOIL_MAX_GRASS_1M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_1M
        TEMPERATURE_SOIL_MAX_GRASS_1_5M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_1_5M
        TEMPERATURE_SOIL_MAX_GRASS_1_8M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_1_8M
        TEMPERATURE_SOIL_MIN_FALLOW_0_05M = DAILY.TEMPERATURE_SOIL_MIN_FALLOW_0_05M
        TEMPERATURE_SOIL_MIN_FALLOW_0_1M = DAILY.TEMPERATURE_SOIL_MIN_FALLOW_0_1M
        TEMPERATURE_SOIL_MIN_FALLOW_0_2M = DAILY.TEMPERATURE_SOIL_MIN_FALLOW_0_2M
        TEMPERATURE_SOIL_MIN_FALLOW_0_5M = DAILY.TEMPERATURE_SOIL_MIN_FALLOW_0_5M
        TEMPERATURE_SOIL_MIN_FALLOW_1M = DAILY.TEMPERATURE_SOIL_MIN_FALLOW_1M
        TEMPERATURE_SOIL_MIN_FALLOW_1_5M = DAILY.TEMPERATURE_SOIL_MIN_FALLOW_1_5M
        TEMPERATURE_SOIL_MIN_FALLOW_1_8M = DAILY.TEMPERATURE_SOIL_MIN_FALLOW_1_8M
        TEMPERATURE_SOIL_MAX_FALLOW_0_05M = DAILY.TEMPERATURE_SOIL_MAX_FALLOW_0_05M
        TEMPERATURE_SOIL_MAX_FALLOW_0_1M = DAILY.TEMPERATURE_SOIL_MAX_FALLOW_0_1M
        TEMPERATURE_SOIL_MAX_FALLOW_0_2M = DAILY.TEMPERATURE_SOIL_MAX_FALLOW_0_2M
        TEMPERATURE_SOIL_MAX_FALLOW_0_5M = DAILY.TEMPERATURE_SOIL_MAX_FALLOW_0_5M
        TEMPERATURE_SOIL_MAX_FALLOW_1M = DAILY.TEMPERATURE_SOIL_MAX_FALLOW_1M
        TEMPERATURE_SOIL_MAX_FALLOW_1_5M = DAILY.TEMPERATURE_SOIL_MAX_FALLOW_1_5M
        TEMPERATURE_SOIL_MAX_FALLOW_1_8M = DAILY.TEMPERATURE_SOIL_MAX_FALLOW_1_8M
        TEMPERATURE_SOIL_MIN_BARE_GROUND_0_05M = DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_0_05M
        TEMPERATURE_SOIL_MIN_BARE_GROUND_0_1M = DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_0_1M
        TEMPERATURE_SOIL_MIN_BARE_GROUND_0_2M = DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_0_2M
        TEMPERATURE_SOIL_MIN_BARE_GROUND_0_5M = DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_0_5M
        TEMPERATURE_SOIL_MIN_BARE_GROUND_1M = DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_1M
        TEMPERATURE_SOIL_MIN_BARE_GROUND_1_5M = DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_1_5M
        TEMPERATURE_SOIL_MIN_BARE_GROUND_1_8M = DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_1_8M
        TEMPERATURE_SOIL_MAX_BARE_GROUND_0_05M = DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_0_05M
        TEMPERATURE_SOIL_MAX_BARE_GROUND_0_1M = DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_0_1M
        TEMPERATURE_SOIL_MAX_BARE_GROUND_0_2M = DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_0_2M
        TEMPERATURE_SOIL_MAX_BARE_GROUND_0_5M = DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_0_5M
        TEMPERATURE_SOIL_MAX_BARE_GROUND_1M = DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_1M
        TEMPERATURE_SOIL_MAX_BARE_GROUND_1_5M = DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_1_5M
        TEMPERATURE_SOIL_MAX_BARE_GROUND_1_8M = DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_1_8M
        TEMPERATURE_SOIL_MIN_BROME_GRASS_0_05M = DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_0_05M
        TEMPERATURE_SOIL_MIN_BROME_GRASS_0_1M = DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_0_1M
        TEMPERATURE_SOIL_MIN_BROME_GRASS_0_2M = DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_0_2M
        TEMPERATURE_SOIL_MIN_BROME_GRASS_0_5M = DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_0_5M
        TEMPERATURE_SOIL_MIN_BROME_GRASS_1M = DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_1M
        TEMPERATURE_SOIL_MIN_BROME_GRASS_1_5M = DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_1_5M
        TEMPERATURE_SOIL_MIN_BROME_GRASS_1_8M = DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_1_8M
        TEMPERATURE_SOIL_MAX_BROME_GRASS_0_05M = DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_0_05M
        TEMPERATURE_SOIL_MAX_BROME_GRASS_0_1M = DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_0_1M
        TEMPERATURE_SOIL_MAX_BROME_GRASS_0_2M = DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_0_2M
        TEMPERATURE_SOIL_MAX_BROME_GRASS_0_5M = DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_0_5M
        TEMPERATURE_SOIL_MAX_BROME_GRASS_1M = DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_1M
        TEMPERATURE_SOIL_MAX_BROME_GRASS_1_5M = DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_1_5M
        TEMPERATURE_SOIL_MAX_BROME_GRASS_1_8M = DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_1_8M
        TEMPERATURE_SOIL_MIN_SOD_0_05M = DAILY.TEMPERATURE_SOIL_MIN_SOD_0_05M
        TEMPERATURE_SOIL_MIN_SOD_0_1M = DAILY.TEMPERATURE_SOIL_MIN_SOD_0_1M
        TEMPERATURE_SOIL_MIN_SOD_0_2M = DAILY.TEMPERATURE_SOIL_MIN_SOD_0_2M
        TEMPERATURE_SOIL_MIN_SOD_0_5M = DAILY.TEMPERATURE_SOIL_MIN_SOD_0_5M
        TEMPERATURE_SOIL_MIN_SOD_1M = DAILY.TEMPERATURE_SOIL_MIN_SOD_1M
        TEMPERATURE_SOIL_MIN_SOD_1_5M = DAILY.TEMPERATURE_SOIL_MIN_SOD_1_5M
        TEMPERATURE_SOIL_MIN_SOD_1_8M = DAILY.TEMPERATURE_SOIL_MIN_SOD_1_8M
        TEMPERATURE_SOIL_MAX_SOD_0_05M = DAILY.TEMPERATURE_SOIL_MAX_SOD_0_05M
        TEMPERATURE_SOIL_MAX_SOD_0_1M = DAILY.TEMPERATURE_SOIL_MAX_SOD_0_1M
        TEMPERATURE_SOIL_MAX_SOD_0_2M = DAILY.TEMPERATURE_SOIL_MAX_SOD_0_2M
        TEMPERATURE_SOIL_MAX_SOD_0_5M = DAILY.TEMPERATURE_SOIL_MAX_SOD_0_5M
        TEMPERATURE_SOIL_MAX_SOD_1M = DAILY.TEMPERATURE_SOIL_MAX_SOD_1M
        TEMPERATURE_SOIL_MAX_SOD_1_5M = DAILY.TEMPERATURE_SOIL_MAX_SOD_1_5M
        TEMPERATURE_SOIL_MAX_SOD_1_8M = DAILY.TEMPERATURE_SOIL_MAX_SOD_1_8M
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_05M = DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_05M
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_1M = DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_1M
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_2M = DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_2M
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_5M = DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_5M
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_1M = DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_1M
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_5M = DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_5M
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_8M = DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_8M
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_05M = DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_05M
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_1M = DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_1M
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_2M = DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_2M
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_5M = DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_5M
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_1M = DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_1M
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_5M = DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_5M
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_8M = DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_8M
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_05M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_05M
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_1M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_1M
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_2M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_2M
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_5M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_5M
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_1M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_1M
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_5M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_5M
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_8M = DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_8M
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_05M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_05M
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_1M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_1M
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_2M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_2M
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_5M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_5M
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_1M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_1M
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_5M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_5M
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_8M = DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_8M
        TEMPERATURE_SOIL_MIN_BARE_MUCK_0_05M = DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_0_05M
        TEMPERATURE_SOIL_MIN_BARE_MUCK_0_1M = DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_0_1M
        TEMPERATURE_SOIL_MIN_BARE_MUCK_0_2M = DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_0_2M
        TEMPERATURE_SOIL_MIN_BARE_MUCK_0_5M = DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_0_5M
        TEMPERATURE_SOIL_MIN_BARE_MUCK_1M = DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_1M
        TEMPERATURE_SOIL_MIN_BARE_MUCK_1_5M = DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_1_5M
        TEMPERATURE_SOIL_MIN_BARE_MUCK_1_8M = DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_1_8M
        TEMPERATURE_SOIL_MAX_BARE_MUCK_0_05M = DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_0_05M
        TEMPERATURE_SOIL_MAX_BARE_MUCK_0_1M = DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_0_1M
        TEMPERATURE_SOIL_MAX_BARE_MUCK_0_2M = DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_0_2M
        TEMPERATURE_SOIL_MAX_BARE_MUCK_0_5M = DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_0_5M
        TEMPERATURE_SOIL_MAX_BARE_MUCK_1M = DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_1M
        TEMPERATURE_SOIL_MAX_BARE_MUCK_1_5M = DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_1_5M
        TEMPERATURE_SOIL_MAX_BARE_MUCK_1_8M = DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_1_8M
        ICE_ON_WATER_THICKNESS = DAILY.ICE_ON_WATER_THICKNESS
        TEMPERATURE_AIR_2M = DAILY.TEMPERATURE_AIR_2M
        SUNSHINE_DURATION = DAILY.SUNSHINE_DURATION
        WIND_DIRECTION_GUST_MAX_5SEC = DAILY.WIND_DIRECTION_GUST_MAX_5SEC
        WIND_DIRECTION_GUST_MAX_1MIN = DAILY.WIND_DIRECTION_GUST_MAX_1MIN
        WIND_DIRECTION_GUST_MAX_2MIN = DAILY.WIND_DIRECTION_GUST_MAX_2MIN
        WIND_DIRECTION_GUST_MAX = DAILY.WIND_DIRECTION_GUST_MAX
        WIND_DIRECTION_GUST_MAX_INSTANT = DAILY.WIND_DIRECTION_GUST_MAX_INSTANT
        WIND_DIRECTION_GUST_MAX_1MILE = DAILY.WIND_DIRECTION_GUST_MAX_1MILE
        WIND_MOVEMENT_24H = DAILY.WIND_MOVEMENT_24H
        WATER_EQUIVALENT_SNOW_DEPTH = DAILY.WATER_EQUIVALENT_SNOW_DEPTH
        WATER_EQUIVALENT_SNOW_DEPTH_NEW = DAILY.WATER_EQUIVALENT_SNOW_DEPTH_NEW
        WIND_GUST_MAX_5SEC = DAILY.WIND_GUST_MAX_5SEC
        WIND_GUST_MAX_1MIN = DAILY.WIND_GUST_MAX_1MIN
        WIND_GUST_MAX_2MIN = DAILY.WIND_GUST_MAX_2MIN
        WIND_GUST_MAX = DAILY.WIND_GUST_MAX
        WIND_GUST_MAX_INSTANT = DAILY.WIND_GUST_MAX_INSTANT
        WIND_GUST_MAX_1MILE = DAILY.WIND_GUST_MAX_1MILE
        WEATHER_TYPE_FOG = DAILY.WEATHER_TYPE_FOG
        WEATHER_TYPE_HEAVY_FOG = DAILY.WEATHER_TYPE_HEAVY_FOG
        WEATHER_TYPE_THUNDER = DAILY.WEATHER_TYPE_THUNDER
        WEATHER_TYPE_ICE_SLEET_SNOW_HAIL = DAILY.WEATHER_TYPE_ICE_SLEET_SNOW_HAIL
        WEATHER_TYPE_HAIL = DAILY.WEATHER_TYPE_HAIL
        WEATHER_TYPE_GLAZE_RIME = DAILY.WEATHER_TYPE_GLAZE_RIME
        WEATHER_TYPE_DUST_ASH_SAND = DAILY.WEATHER_TYPE_DUST_ASH_SAND
        WEATHER_TYPE_SMOKE_HAZE = DAILY.WEATHER_TYPE_SMOKE_HAZE
        WEATHER_TYPE_BLOWING_DRIFTING_SNOW = DAILY.WEATHER_TYPE_BLOWING_DRIFTING_SNOW
        WEATHER_TYPE_TORNADO_WATERSPOUT = DAILY.WEATHER_TYPE_TORNADO_WATERSPOUT
        WEATHER_TYPE_HIGH_DAMAGING_WINDS = DAILY.WEATHER_TYPE_HIGH_DAMAGING_WINDS
        WEATHER_TYPE_BLOWING_SPRAY = DAILY.WEATHER_TYPE_BLOWING_SPRAY
        WEATHER_TYPE_MIST = DAILY.WEATHER_TYPE_MIST
        WEATHER_TYPE_DRIZZLE = DAILY.WEATHER_TYPE_DRIZZLE
        WEATHER_TYPE_FREEZING_DRIZZLE = DAILY.WEATHER_TYPE_FREEZING_DRIZZLE
        WEATHER_TYPE_RAIN = DAILY.WEATHER_TYPE_RAIN
        WEATHER_TYPE_FREEZING_RAIN = DAILY.WEATHER_TYPE_FREEZING_RAIN
        WEATHER_TYPE_SNOW_PELLETS_SNOW_GRAINS_ICE_CRYSTALS = DAILY.WEATHER_TYPE_SNOW_PELLETS_SNOW_GRAINS_ICE_CRYSTALS
        WEATHER_TYPE_PRECIPITATION_UNKNOWN_SOURCE = DAILY.WEATHER_TYPE_PRECIPITATION_UNKNOWN_SOURCE
        WEATHER_TYPE_GROUND_FOG = DAILY.WEATHER_TYPE_GROUND_FOG
        WEATHER_TYPE_ICE_FOG_FREEZING_FOG = DAILY.WEATHER_TYPE_ICE_FOG_FREEZING_FOG
        WEATHER_TYPE_VICINITY_FOG_ANY = DAILY.WEATHER_TYPE_VICINITY_FOG_ANY
        WEATHER_TYPE_VICINITY_THUNDER = DAILY.WEATHER_TYPE_VICINITY_THUNDER
        WEATHER_TYPE_VICINITY_DUST_ASH_SAND = DAILY.WEATHER_TYPE_VICINITY_DUST_ASH_SAND
        WEATHER_TYPE_VICINITY_SNOW_ICE_CRYSTALS = DAILY.WEATHER_TYPE_VICINITY_SNOW_ICE_CRYSTALS
        WEATHER_TYPE_VICINITY_RAIN_SNOW_SHOWER = DAILY.WEATHER_TYPE_VICINITY_RAIN_SNOW_SHOWER


DAILY_PARAMETER_MULTIPLICATION_FACTORS = {
    NoaaGhcnParameter.DAILY.PRECIPITATION_HEIGHT.value: 1 / 10,
    NoaaGhcnParameter.DAILY.PRECIPITATION_HEIGHT_MULTIDAY.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MAX_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MAX_2M_MULTIDAY.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MIN_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MIN_2M_MULTIDAY.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MEAN_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_SPEED.value: 1 / 10,
    NoaaGhcnParameter.DAILY.EVAPORATION_HEIGHT.value: 1 / 10,
    NoaaGhcnParameter.DAILY.EVAPORATION_HEIGHT_MULTIDAY.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_WATER_EVAPORATION_PAN_MAX.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_WATER_EVAPORATION_PAN_MIN.value: 1 / 10,
    # Height definition similar to temperature with three digits
    # 0 - unknown
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_1_8M.value: 1 / 10,
    # 1 - grass
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_1_8M.value: 1 / 10,
    # 2 - fallow
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_1_8M.value: 1 / 10,
    # 3 - bare ground
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_1_8M.value: 1 / 10,
    # 4 - brome grass
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_0_05M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_0_1M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_0_2M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_0_5M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_1M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_1_5M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_1_8M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_0_05M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_0_1M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_0_2M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_0_5M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_1M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_1_5M: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_1_8M: 1 / 10,
    # 5 - sod
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_1_8M.value: 1 / 10,
    # 6 - straw mulch
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_1_8M.value: 1 / 10,
    # 7 - grass muck
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_1_8M.value: 1 / 10,
    # 8 - bare muck
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_0_05M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_0_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_0_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_0_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_1M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_1_5M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_1_8M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.ICE_ON_WATER_THICKNESS.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_2M.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WATER_EQUIVALENT_SNOW_DEPTH.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WATER_EQUIVALENT_SNOW_DEPTH_NEW.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_5SEC.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_1MIN.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_2MIN.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_INSTANT.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_1MILE.value: 1 / 10,
}
