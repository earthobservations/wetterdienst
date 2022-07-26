# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.util.parameter import DatasetTreeCore


class NoaaGhcnParameter(DatasetTreeCore):
    """NOAA Global Historical Climatology Network Parameters"""

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
        TEMPERATURE_AIR_MAX_200 = "tmax"
        # TMIN  =  Minimum  temperature  (Fahrenheit  or  Celsius  as
        # per  user  preference,
        #     Fahrenheit  to  tenths  on Daily Form pdf file
        TEMPERATURE_AIR_MIN_200 = "tmin"
        # DERIVED PARAMETER
        TEMPERATURE_AIR_MEAN_200 = "tavg"  # tmean = (tmax + tmin) / 2

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
        COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MIN_200 = "datn"
        # Number of days included in the multiday maximum temperature (MDTX)
        COUNT_DAYS_MULTIDAY_TEMPERATURE_AIR_MAX_200 = "datx"
        # Number of days included in the multiday wind movement (MDWM)
        COUNT_DAYS_MULTIDAY_WIND_MOVEMENT = "dawm"  # TODO: what network of parameter ?
        # Number of days with non-zero precipitation included in multiday precipitation total (MDPR)
        COUNT_DAYS_MULTIDAY_PRECIPITATION_HEIGHT_GT_0 = "dwpr"
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
        TEMPERATURE_AIR_MIN_200_MULTIDAY = "mdtn"
        # Multiday maximum temperature (Fahrenheit or Celsius as per user preference ; use with DATX)
        TEMPERATURE_AIR_MAX_200_MULTIDAY = "mdtx"
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
        TEMPERATURE_SOIL_MIN_UNKNOWN_005 = "sn01"  # °C
        TEMPERATURE_SOIL_MIN_UNKNOWN_010 = "sn02"  # °C
        TEMPERATURE_SOIL_MIN_UNKNOWN_020 = "sn03"  # °C
        TEMPERATURE_SOIL_MIN_UNKNOWN_050 = "sn04"  # °C
        TEMPERATURE_SOIL_MIN_UNKNOWN_100 = "sn05"  # °C
        TEMPERATURE_SOIL_MIN_UNKNOWN_150 = "sn06"  # °C
        TEMPERATURE_SOIL_MIN_UNKNOWN_180 = "sn07"  # °C

        TEMPERATURE_SOIL_MAX_UNKNOWN_005 = "sx01"  # °C
        TEMPERATURE_SOIL_MAX_UNKNOWN_010 = "sx02"  # °C
        TEMPERATURE_SOIL_MAX_UNKNOWN_020 = "sx03"  # °C
        TEMPERATURE_SOIL_MAX_UNKNOWN_050 = "sx04"  # °C
        TEMPERATURE_SOIL_MAX_UNKNOWN_100 = "sx05"  # °C
        TEMPERATURE_SOIL_MAX_UNKNOWN_150 = "sx06"  # °C
        TEMPERATURE_SOIL_MAX_UNKNOWN_180 = "sx07"  # °C

        # 1 - grass
        TEMPERATURE_SOIL_MIN_GRASS_005 = "sn11"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_010 = "sn12"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_020 = "sn13"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_050 = "sn14"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_100 = "sn15"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_150 = "sn16"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_180 = "sn17"  # °C

        TEMPERATURE_SOIL_MAX_GRASS_005 = "sx11"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_010 = "sx12"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_020 = "sx13"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_050 = "sx14"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_100 = "sx15"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_150 = "sx16"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_180 = "sx17"  # °C

        # 2 - fallow
        TEMPERATURE_SOIL_MIN_FALLOW_005 = "sn21"  # °C
        TEMPERATURE_SOIL_MIN_FALLOW_010 = "sn22"  # °C
        TEMPERATURE_SOIL_MIN_FALLOW_020 = "sn23"  # °C
        TEMPERATURE_SOIL_MIN_FALLOW_050 = "sn24"  # °C
        TEMPERATURE_SOIL_MIN_FALLOW_100 = "sn25"  # °C
        TEMPERATURE_SOIL_MIN_FALLOW_150 = "sn26"  # °C
        TEMPERATURE_SOIL_MIN_FALLOW_180 = "sn27"  # °C

        TEMPERATURE_SOIL_MAX_FALLOW_005 = "sx21"  # °C
        TEMPERATURE_SOIL_MAX_FALLOW_010 = "sx22"  # °C
        TEMPERATURE_SOIL_MAX_FALLOW_020 = "sx23"  # °C
        TEMPERATURE_SOIL_MAX_FALLOW_050 = "sx24"  # °C
        TEMPERATURE_SOIL_MAX_FALLOW_100 = "sx25"  # °C
        TEMPERATURE_SOIL_MAX_FALLOW_150 = "sx26"  # °C
        TEMPERATURE_SOIL_MAX_FALLOW_180 = "sx27"  # °C

        # 3 - bare ground
        TEMPERATURE_SOIL_MIN_BARE_GROUND_005 = "sn31"  # °C
        TEMPERATURE_SOIL_MIN_BARE_GROUND_010 = "sn32"  # °C
        TEMPERATURE_SOIL_MIN_BARE_GROUND_020 = "sn33"  # °C
        TEMPERATURE_SOIL_MIN_BARE_GROUND_050 = "sn34"  # °C
        TEMPERATURE_SOIL_MIN_BARE_GROUND_100 = "sn35"  # °C
        TEMPERATURE_SOIL_MIN_BARE_GROUND_150 = "sn36"  # °C
        TEMPERATURE_SOIL_MIN_BARE_GROUND_180 = "sn37"  # °C

        TEMPERATURE_SOIL_MAX_BARE_GROUND_005 = "sx31"  # °C
        TEMPERATURE_SOIL_MAX_BARE_GROUND_010 = "sx32"  # °C
        TEMPERATURE_SOIL_MAX_BARE_GROUND_020 = "sx33"  # °C
        TEMPERATURE_SOIL_MAX_BARE_GROUND_050 = "sx34"  # °C
        TEMPERATURE_SOIL_MAX_BARE_GROUND_100 = "sx35"  # °C
        TEMPERATURE_SOIL_MAX_BARE_GROUND_150 = "sx36"  # °C
        TEMPERATURE_SOIL_MAX_BARE_GROUND_180 = "sx37"  # °C

        # 4 - brome grass
        TEMPERATURE_SOIL_MIN_BROME_GRASS_005 = "sn41"  # °C
        TEMPERATURE_SOIL_MIN_BROME_GRASS_010 = "sn42"  # °C
        TEMPERATURE_SOIL_MIN_BROME_GRASS_020 = "sn43"  # °C
        TEMPERATURE_SOIL_MIN_BROME_GRASS_050 = "sn44"  # °C
        TEMPERATURE_SOIL_MIN_BROME_GRASS_100 = "sn45"  # °C
        TEMPERATURE_SOIL_MIN_BROME_GRASS_150 = "sn46"  # °C
        TEMPERATURE_SOIL_MIN_BROME_GRASS_180 = "sn47"  # °C

        TEMPERATURE_SOIL_MAX_BROME_GRASS_005 = "sx41"  # °C
        TEMPERATURE_SOIL_MAX_BROME_GRASS_010 = "sx42"  # °C
        TEMPERATURE_SOIL_MAX_BROME_GRASS_020 = "sx43"  # °C
        TEMPERATURE_SOIL_MAX_BROME_GRASS_050 = "sx44"  # °C
        TEMPERATURE_SOIL_MAX_BROME_GRASS_100 = "sx45"  # °C
        TEMPERATURE_SOIL_MAX_BROME_GRASS_150 = "sx46"  # °C
        TEMPERATURE_SOIL_MAX_BROME_GRASS_180 = "sx47"  # °C

        # 5 - sod
        TEMPERATURE_SOIL_MIN_SOD_005 = "sn51"  # °C
        TEMPERATURE_SOIL_MIN_SOD_010 = "sn52"  # °C
        TEMPERATURE_SOIL_MIN_SOD_020 = "sn53"  # °C
        TEMPERATURE_SOIL_MIN_SOD_050 = "sn54"  # °C
        TEMPERATURE_SOIL_MIN_SOD_100 = "sn55"  # °C
        TEMPERATURE_SOIL_MIN_SOD_150 = "sn56"  # °C
        TEMPERATURE_SOIL_MIN_SOD_180 = "sn57"  # °C

        TEMPERATURE_SOIL_MAX_SOD_005 = "sx51"  # °C
        TEMPERATURE_SOIL_MAX_SOD_010 = "sx52"  # °C
        TEMPERATURE_SOIL_MAX_SOD_020 = "sx53"  # °C
        TEMPERATURE_SOIL_MAX_SOD_050 = "sx54"  # °C
        TEMPERATURE_SOIL_MAX_SOD_100 = "sx55"  # °C
        TEMPERATURE_SOIL_MAX_SOD_150 = "sx56"  # °C
        TEMPERATURE_SOIL_MAX_SOD_180 = "sx57"  # °C

        # 6 - straw mulch
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_005 = "sn61"  # °C
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_010 = "sn62"  # °C
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_020 = "sn63"  # °C
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_050 = "sn64"  # °C
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_100 = "sn65"  # °C
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_150 = "sn66"  # °C
        TEMPERATURE_SOIL_MIN_STRAW_MULCH_180 = "sn67"  # °C

        TEMPERATURE_SOIL_MAX_STRAW_MULCH_005 = "sx61"  # °C
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_010 = "sx62"  # °C
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_020 = "sx63"  # °C
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_050 = "sx64"  # °C
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_100 = "sx65"  # °C
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_150 = "sx66"  # °C
        TEMPERATURE_SOIL_MAX_STRAW_MULCH_180 = "sx67"  # °C

        # 7 - grass muck
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_005 = "sn71"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_010 = "sn72"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_020 = "sn73"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_050 = "sn74"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_100 = "sn75"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_150 = "sn76"  # °C
        TEMPERATURE_SOIL_MIN_GRASS_MUCK_180 = "sn77"  # °C

        TEMPERATURE_SOIL_MAX_GRASS_MUCK_005 = "sx71"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_010 = "sx72"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_020 = "sx73"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_050 = "sx74"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_100 = "sx75"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_150 = "sx76"  # °C
        TEMPERATURE_SOIL_MAX_GRASS_MUCK_180 = "sx77"  # °C

        # 8 - bare muck
        TEMPERATURE_SOIL_MIN_BARE_MUCK_005 = "sn81"  # °C
        TEMPERATURE_SOIL_MIN_BARE_MUCK_010 = "sn82"  # °C
        TEMPERATURE_SOIL_MIN_BARE_MUCK_020 = "sn83"  # °C
        TEMPERATURE_SOIL_MIN_BARE_MUCK_050 = "sn84"  # °C
        TEMPERATURE_SOIL_MIN_BARE_MUCK_100 = "sn85"  # °C
        TEMPERATURE_SOIL_MIN_BARE_MUCK_150 = "sn86"  # °C
        TEMPERATURE_SOIL_MIN_BARE_MUCK_180 = "sn87"  # °C

        TEMPERATURE_SOIL_MAX_BARE_MUCK_005 = "sx81"  # °C
        TEMPERATURE_SOIL_MAX_BARE_MUCK_010 = "sx82"  # °C
        TEMPERATURE_SOIL_MAX_BARE_MUCK_020 = "sx83"  # °C
        TEMPERATURE_SOIL_MAX_BARE_MUCK_050 = "sx84"  # °C
        TEMPERATURE_SOIL_MAX_BARE_MUCK_100 = "sx85"  # °C
        TEMPERATURE_SOIL_MAX_BARE_MUCK_150 = "sx86"  # °C
        TEMPERATURE_SOIL_MAX_BARE_MUCK_180 = "sx87"  # °C

        # Thickness of ice on water (inches or mm as per user preference)
        ICE_ON_WATER_THICKNESS = "thic"
        # Temperature at the time of observation  (Fahrenheit or Celsius as per user preference)
        TEMPERATURE_AIR_200 = "tobs"
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
        WIND_MOVEMENT_24HOUR = "wdmv"
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


PARAMETER_MULTIPLICATION_FACTORS = {
    NoaaGhcnParameter.DAILY.PRECIPITATION_HEIGHT.value: 1 / 10,
    NoaaGhcnParameter.DAILY.PRECIPITATION_HEIGHT_MULTIDAY.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MAX_200.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MAX_200_MULTIDAY.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MIN_200.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MIN_200_MULTIDAY.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MEAN_200.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_SPEED.value: 1 / 10,
    NoaaGhcnParameter.DAILY.EVAPORATION_HEIGHT.value: 1 / 10,
    NoaaGhcnParameter.DAILY.EVAPORATION_HEIGHT_MULTIDAY.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_WATER_EVAPORATION_PAN_MAX.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_WATER_EVAPORATION_PAN_MIN.value: 1 / 10,
    # Height definition similar to temperature with three digits
    # 0 - unknown
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_UNKNOWN_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_UNKNOWN_180.value: 1 / 10,
    # 1 - grass
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_180.value: 1 / 10,
    # 2 - fallow
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_FALLOW_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_FALLOW_180.value: 1 / 10,
    # 3 - bare ground
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_GROUND_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_GROUND_180.value: 1 / 10,
    # 4 - brome grass
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_005: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_010: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_020: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_050: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_100: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_150: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BROME_GRASS_180: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_005: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_010: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_020: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_050: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_100: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_150: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BROME_GRASS_180: 1 / 10,
    # 5 - sod
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_SOD_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_SOD_180.value: 1 / 10,
    # 6 - straw mulch
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_STRAW_MULCH_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_STRAW_MULCH_180.value: 1 / 10,
    # 7 - grass muck
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_GRASS_MUCK_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_GRASS_MUCK_180.value: 1 / 10,
    # 8 - bare muck
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MIN_BARE_MUCK_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_005.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_010.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_020.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_050.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_100.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_150.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_SOIL_MAX_BARE_MUCK_180.value: 1 / 10,
    NoaaGhcnParameter.DAILY.ICE_ON_WATER_THICKNESS.value: 1 / 10,
    NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_200.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WATER_EQUIVALENT_SNOW_DEPTH.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WATER_EQUIVALENT_SNOW_DEPTH_NEW.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_5SEC.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_1MIN.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_2MIN.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_INSTANT.value: 1 / 10,
    NoaaGhcnParameter.DAILY.WIND_GUST_MAX_1MILE.value: 1 / 10,
}
