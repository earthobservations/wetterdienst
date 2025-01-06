# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.core.timeseries.metadata import DATASET_NAME_DEFAULT, build_metadata_model

# translate the above enums to dictionary based model
NoaaGhcnMetadata = {
    "name_short": "NOAA",
    "name_english": "National Oceanic And Atmospheric Administration",
    "name_local": "National Oceanic And Atmospheric Administration",
    "country": "United States Of America",
    "copyright": "© National Oceanic And Atmospheric Administration (NOAA), Global Historical Climatology Network",
    "url": "http://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/",
    "kind": "observation",
    "timezone": "America/New_York",
    "timezone_data": "dynamic",
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        # Relative humidity is calculated from air (dry bulb) temperature and dewpoint temperature
                        # (whole percent)
                        {
                            "name": "humidity",
                            "name_original": "relative_humidity",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        # total liquid precipitation (rain or melted snow) for past hour; a “T” in the measurement
                        # code column indicates a trace amount of precipitation (millimeters)
                        {
                            "name": "precipitation_height",
                            "name_original": "precipitation",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        # 3-hour total liquid precipitation (rain or melted snow) accumulation
                        # from FM12/SYNOP reports; a “T” in the measurement code column indicates a trace amount
                        # of precipitation (millimeters); accumulations can be reported over 3,6,9,12,15,18,21
                        # and 24 hours.
                        {
                            "name": "precipitation_height_last_3h",
                            "name_original": "precipitation_3_hour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_6h",
                            "name_original": "precipitation_6_hour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_9h",
                            "name_original": "precipitation_9_hour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_12h",
                            "name_original": "precipitation_12_hour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_15h",
                            "name_original": "precipitation_15_hour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_18h",
                            "name_original": "precipitation_18_hour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_21h",
                            "name_original": "precipitation_21_hour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_24h",
                            "name_original": "precipitation_24_hour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        # reduction estimates the pressure that would exist at sea level at a point directly below
                        # the station using a temperature profile based on temperatures that actually exist at the
                        # station (hPa)  # noqa: ERA001
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "sea_level_pressure",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        # the pressure that is observed at a specific elevation and is the true barometric pressure
                        # of a location. It is the pressure exerted by the atmosphere at a point as a result of
                        # gravity acting upon the "column" of air that lies directly above the point. (hPa)
                        {
                            "name": "pressure_air_site",
                            "name_original": "station_level_pressure",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        # change in atmospheric pressure measured at the beginning and end of a three-hour period;
                        # accompanied by tendency code in measurement code field (millibars/hPa)
                        {
                            "name": "pressure_air_site_delta_last_3h",
                            "name_original": "pressure_3hr_change",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        # the pressure "reduced" to mean sea level using the temperature profile of the "standard"
                        # atmosphere, which is representative of average conditions over the United States at 40
                        # degrees north latitude (millibars/hPa)  # noqa
                        {
                            "name": "pressure_air_site_reduced",
                            "name_original": "altimeter",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        # depth of snowpack on the ground (centimeters/m)
                        {
                            "name": "snow_depth",
                            "name_original": "snow_depth",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        # 2 meter (circa) Above Ground Level Air (dry bulb) Temperature (⁰C to tenths)
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "temperature",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # Dew Point Temperature (⁰C to tenths)
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dew_point_temperature",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # Wet bulb temperature (⁰C to tenths)
                        {
                            "name": "temperature_wet_mean_2m",
                            "name_original": "wet_bulb_temperature",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # horizontal distance at which an object can be seen and identified (kilometers)
                        {
                            "name": "visibility_range",
                            "name_original": "visibility",
                            "unit_type": "length_medium",
                            "unit": "kilometer",
                        },
                        # Wind Direction from true north using compass directions (e.g. 360=true north, 180=south,
                        # 270=west, etc.).
                        # Note: A direction of “000” is given for calm winds. (whole degrees)
                        {
                            "name": "wind_direction",
                            "name_original": "wind_direction",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        # Peak short duration (usually < 20 seconds) wind speed (meters per second) that exceeds the
                        # wind_speed average
                        {
                            "name": "wind_gust_max",
                            "name_original": "wind_gust",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        # Wind Speed (meters per second)
                        {
                            "name": "wind_speed",
                            "name_original": "wind_speed",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                    ],
                }
            ],
        },
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        # core parameters
                        # PRCP = Precipitation (mm or inches as per user preference,
                        #     inches to hundredths on Daily Form pdf file)
                        {
                            "name": "precipitation_height",
                            "name_original": "prcp",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        # SNOW = Snowfall (mm or inches as per user preference,
                        #     inches to tenths on Daily Form pdf file)
                        {
                            "name": "snow_depth_new",
                            "name_original": "snow",
                            "unit_type": "length_short",
                            "unit": "millimeter",
                        },
                        # SNWD = Snow depth (mm or inches as per user preference,
                        #     inches on Daily Form pdf file)
                        {
                            "name": "snow_depth",
                            "name_original": "snwd",
                            "unit_type": "length_short",
                            "unit": "millimeter",
                        },
                        # TMAX  = Maximum  temperature  (Fahrenheit or  Celsius  as
                        # per  user  preference,
                        #     Fahrenheit  to  tenths on Daily Form pdf file
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tmax",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # TMIN  =  Minimum  temperature  (Fahrenheit  or  Celsius  as
                        # per  user  preference,
                        #     Fahrenheit  to  tenths  on Daily Form pdf file
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tmin",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # derived from temperature_air_max_2m and temperature_air_min_2m
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tavg",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # additional parameters
                        # Average cloudiness midnight to midnight from 30-second ceilometer data (percent)
                        {
                            "name": "cloud_cover_total_midnight_to_midnight",
                            "name_original": "acmc",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        # Average cloudiness midnight to midnight from manual observation (percent)
                        {
                            "name": "cloud_cover_total_midnight_to_midnight_manual",
                            "name_original": "acmh",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        # Average cloudiness sunrise to sunset from 30-second ceilometer data (percent)
                        {
                            "name": "cloud_cover_total_sunrise_to_sunset",
                            "name_original": "acsc",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        # Average cloudiness sunrise to sunset from manual observation (percent)
                        {
                            "name": "cloud_cover_total_sunrise_to_sunset_manual",
                            "name_original": "acsh",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        # Average daily wind speed (meters per second or miles per hour as per user preference)
                        {
                            "name": "wind_speed",
                            "name_original": "awnd",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        # Number of days included in the multiday evaporation total (MDEV)
                        {
                            "name": "count_days_multiday_evaporation",
                            "name_original": "daev",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        # Number of days included in the multiday precipitation total (MDPR)
                        {
                            "name": "count_days_multiday_precipitation",
                            "name_original": "dapr",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        # Number of days included in the multiday snowfall total (MDSF)
                        {
                            "name": "count_days_multiday_snow_depth_new",
                            "name_original": "dasf",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        # Number of days included in the multiday minimum temperature (MDTN)
                        {
                            "name": "count_days_multiday_temperature_air_min_2m",
                            "name_original": "datn",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        # Number of days included in the multiday maximum temperature (MDTX)
                        {
                            "name": "count_days_multiday_temperature_air_max_2m",
                            "name_original": "datx",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        # Number of days included in the multiday wind movement (MDWM)
                        {
                            "name": "count_days_multiday_wind_movement",
                            "name_original": "dawm",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        # Number of days with non-zero precipitation included in multiday precipitation total (MDPR)
                        {
                            "name": "count_days_multiday_precipitation_height_gt_0mm",
                            "name_original": "dwpr",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        # Evaporation of water from evaporation pan (mm or inches as per user preference, or hundredths
                        # of inches on Daily Form pdf file)
                        {
                            "name": "evaporation_height",
                            "name_original": "evap",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        # time_wind_gust_max_1mile_or_1min (fmtm) is left out
                        # Base of frozen ground layer (cm or inches as per user preference)
                        {
                            "name": "frozen_ground_layer_base",
                            "name_original": "frgb",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        # Top of frozen ground layer (cm or inches as per user preference)
                        {
                            "name": "frozen_ground_layer_top",
                            "name_original": "frgt",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        # Thickness of frozen ground layer (cm or inches as per user preference)
                        {
                            "name": "frozen_ground_layer_thickness",
                            "name_original": "frth",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        # Difference between river and gauge height (cm or inches as per user preference)
                        {
                            "name": "distance_river_gauge_height",
                            "name_original": "gaht",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        # Multiday evaporation total (mm or inches as per user preference; use with DAEV)
                        {
                            "name": "evaporation_height_multiday",
                            "name_original": "mdev",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        # Multiday precipitation total (mm or inches as per user preference; use with DAPR and DWPR,
                        # if available)
                        {
                            "name": "precipitation_height_multiday",
                            "name_original": "mdpr",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        # Multiday snowfall total (mm or inches as per user preference)
                        {
                            "name": "snow_depth_new_multiday",
                            "name_original": "mdsf",
                            "unit_type": "length_short",
                            "unit": "millimeter",
                        },
                        # Multiday minimum temperature (Fahrenheit or Celsius as per user preference ; use with DATN)
                        {
                            "name": "temperature_air_min_2m_multiday",
                            "name_original": "mdtn",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # Multiday maximum temperature (Fahrenheit or Celsius as per user preference ; use with DATX)
                        {
                            "name": "temperature_air_max_2m_multiday",
                            "name_original": "mdtx",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # Multiday wind movement (miles or km as per user preference)
                        {
                            "name": "wind_movement_multiday",
                            "name_original": "mdwm",
                            "unit_type": "length_long",
                            "unit": "kilometer",
                        },
                        # Daily minimum temperature of water in an evaporation pan
                        # (Fahrenheit or Celsius as per user preference)
                        {
                            "name": "temperature_water_evaporation_pan_min",
                            "name_original": "mnpn",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # Daily maximum temperature of water in an evaporation pan
                        # (Fahrenheit or Celsius as per user preference)
                        {
                            "name": "temperature_water_evaporation_pan_max",
                            "name_original": "mxpn",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # time_wind_gust_max (pgtm) is left out
                        # Daily percent of possible sunshine (percent)
                        {
                            "name": "sunshine_duration_relative",
                            "name_original": "psun",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        # soil temperature
                        # ----------------------------------------------------------------------
                        # SN*# = Minimum soil temperature
                        # SX*# = Maximum soil temperature
                        #
                        #     where
                        #      * corresponds to a code for ground cover and
                        #      # corresponds to a code for soil depth (Fahrenheit or Celsius as
                        #      per user preference)
                        #
                        #     Ground cover codes include the following:
                        #         0 = unknown
                        #         1 = grass
                        #         2 = fallow
                        #         3 = bare ground
                        #         4 = brome grass
                        #         5 = sod
                        #         6 = straw mulch
                        #         7 = grass muck
                        #         8 = bare muck
                        #
                        #     Depth codes include the following:
                        #         1 = 5 cm
                        #         2 = 10 cm
                        #         3 = 20 cm
                        #         4 = 50 cm
                        #         5 = 100 cm
                        #         6 = 150 cm
                        #         7 = 180 cm
                        # 0 - unknown
                        {
                            "name": "temperature_soil_min_unknown_0_05m",
                            "name_original": "sn01",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_unknown_0_1m",
                            "name_original": "sn02",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_unknown_0_2m",
                            "name_original": "sn03",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_unknown_0_5m",
                            "name_original": "sn04",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_unknown_1m",
                            "name_original": "sn05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_unknown_1_5m",
                            "name_original": "sn06",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_unknown_1_8m",
                            "name_original": "sn07",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_unknown_0_05m",
                            "name_original": "sx01",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_unknown_0_1m",
                            "name_original": "sx02",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_unknown_0_2m",
                            "name_original": "sx03",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_unknown_0_5m",
                            "name_original": "sx04",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_unknown_1m",
                            "name_original": "sx05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_unknown_1_5m",
                            "name_original": "sx06",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_unknown_1_8m",
                            "name_original": "sx07",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # 1 - grass
                        {
                            "name": "temperature_soil_min_grass_0_05m",
                            "name_original": "sn11",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_0_1m",
                            "name_original": "sn12",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_0_2m",
                            "name_original": "sn13",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_0_5m",
                            "name_original": "sn14",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_1m",
                            "name_original": "sn15",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_1_5m",
                            "name_original": "sn16",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_1_8m",
                            "name_original": "sn17",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_0_05m",
                            "name_original": "sx11",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_0_1m",
                            "name_original": "sx12",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_0_2m",
                            "name_original": "sx13",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_0_5m",
                            "name_original": "sx14",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_1m",
                            "name_original": "sx15",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_1_5m",
                            "name_original": "sx16",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_1_8m",
                            "name_original": "sx17",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # 2 - fallow
                        {
                            "name": "temperature_soil_min_fallow_0_05m",
                            "name_original": "sn21",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_fallow_0_1m",
                            "name_original": "sn22",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_fallow_0_2m",
                            "name_original": "sn23",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_fallow_0_5m",
                            "name_original": "sn24",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_fallow_1m",
                            "name_original": "sn25",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_fallow_1_5m",
                            "name_original": "sn26",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_fallow_1_8m",
                            "name_original": "sn27",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_fallow_0_05m",
                            "name_original": "sx21",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_fallow_0_1m",
                            "name_original": "sx22",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_fallow_0_2m",
                            "name_original": "sx23",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_fallow_0_5m",
                            "name_original": "sx24",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_fallow_1m",
                            "name_original": "sx25",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_fallow_1_5m",
                            "name_original": "sx26",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_fallow_1_8m",
                            "name_original": "sx27",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # 3 - bare ground
                        {
                            "name": "temperature_soil_min_bare_ground_0_05m",
                            "name_original": "sn31",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_ground_0_1m",
                            "name_original": "sn32",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_ground_0_2m",
                            "name_original": "sn33",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_ground_0_5m",
                            "name_original": "sn34",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_ground_1m",
                            "name_original": "sn35",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_ground_1_5m",
                            "name_original": "sn36",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_ground_1_8m",
                            "name_original": "sn37",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_ground_0_05m",
                            "name_original": "sx31",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_ground_0_1m",
                            "name_original": "sx32",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_ground_0_2m",
                            "name_original": "sx33",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_ground_0_5m",
                            "name_original": "sx34",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_ground_1m",
                            "name_original": "sx35",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_ground_1_5m",
                            "name_original": "sx36",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_ground_1_8m",
                            "name_original": "sx37",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # 4 - brome grass
                        {
                            "name": "temperature_soil_min_brome_grass_0_05m",
                            "name_original": "sn41",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_brome_grass_0_1m",
                            "name_original": "sn42",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_brome_grass_0_2m",
                            "name_original": "sn43",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_brome_grass_0_5m",
                            "name_original": "sn44",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_brome_grass_1m",
                            "name_original": "sn45",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_brome_grass_1_5m",
                            "name_original": "sn46",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_brome_grass_1_8m",
                            "name_original": "sn47",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_brome_grass_0_05m",
                            "name_original": "sx41",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_brome_grass_0_1m",
                            "name_original": "sx42",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_brome_grass_0_2m",
                            "name_original": "sx43",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_brome_grass_0_5m",
                            "name_original": "sx44",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_brome_grass_1m",
                            "name_original": "sx45",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_brome_grass_1_5m",
                            "name_original": "sx46",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_brome_grass_1_8m",
                            "name_original": "sx47",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # 5 - sod
                        {
                            "name": "temperature_soil_min_sod_0_05m",
                            "name_original": "sn51",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_sod_0_1m",
                            "name_original": "sn52",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_sod_0_2m",
                            "name_original": "sn53",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_sod_0_5m",
                            "name_original": "sn54",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_sod_1m",
                            "name_original": "sn55",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_sod_1_5m",
                            "name_original": "sn56",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_sod_1_8m",
                            "name_original": "sn57",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_sod_0_05m",
                            "name_original": "sx51",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_sod_0_1m",
                            "name_original": "sx52",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_sod_0_2m",
                            "name_original": "sx53",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_sod_0_5m",
                            "name_original": "sx54",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_sod_1m",
                            "name_original": "sx55",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_sod_1_5m",
                            "name_original": "sx56",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_sod_1_8m",
                            "name_original": "sx57",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # 6 - straw mulch
                        {
                            "name": "temperature_soil_min_straw_mulch_0_05m",
                            "name_original": "sn61",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_straw_mulch_0_1m",
                            "name_original": "sn62",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_straw_mulch_0_2m",
                            "name_original": "sn63",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_straw_mulch_0_5m",
                            "name_original": "sn64",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_straw_mulch_1m",
                            "name_original": "sn65",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_straw_mulch_1_5m",
                            "name_original": "sn66",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_straw_mulch_1_8m",
                            "name_original": "sn67",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_straw_mulch_0_05m",
                            "name_original": "sx61",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_straw_mulch_0_1m",
                            "name_original": "sx62",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_straw_mulch_0_2m",
                            "name_original": "sx63",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_straw_mulch_0_5m",
                            "name_original": "sx64",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_straw_mulch_1m",
                            "name_original": "sx65",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_straw_mulch_1_5m",
                            "name_original": "sx66",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_straw_mulch_1_8m",
                            "name_original": "sx67",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # 7 - grass muck
                        {
                            "name": "temperature_soil_min_grass_muck_0_05m",
                            "name_original": "sn71",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_muck_0_1m",
                            "name_original": "sn72",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_muck_0_2m",
                            "name_original": "sn73",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_muck_0_5m",
                            "name_original": "sn74",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_muck_1m",
                            "name_original": "sn75",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_muck_1_5m",
                            "name_original": "sn76",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_grass_muck_1_8m",
                            "name_original": "sn77",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_muck_0_05m",
                            "name_original": "sx71",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_muck_0_1m",
                            "name_original": "sx72",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_muck_0_2m",
                            "name_original": "sx73",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_muck_0_5m",
                            "name_original": "sx74",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_muck_1m",
                            "name_original": "sx75",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_muck_1_5m",
                            "name_original": "sx76",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_grass_muck_1_8m",
                            "name_original": "sx77",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # 8 - bare muck
                        {
                            "name": "temperature_soil_min_bare_muck_0_05m",
                            "name_original": "sn81",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_muck_0_1m",
                            "name_original": "sn82",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_muck_0_2m",
                            "name_original": "sn83",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_muck_0_5m",
                            "name_original": "sn84",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_muck_1m",
                            "name_original": "sn85",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_muck_1_5m",
                            "name_original": "sn86",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_bare_muck_1_8m",
                            "name_original": "sn87",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_muck_0_05m",
                            "name_original": "sx81",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_muck_0_1m",
                            "name_original": "sx82",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_muck_0_2m",
                            "name_original": "sx83",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_muck_0_5m",
                            "name_original": "sx84",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_muck_1m",
                            "name_original": "sx85",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_muck_1_5m",
                            "name_original": "sx86",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_bare_muck_1_8m",
                            "name_original": "sx87",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # Thickness of ice on water (inches or mm as per user preference)
                        {
                            "name": "ice_on_water_thickness",
                            "name_original": "thic",
                            "unit_type": "length_short",
                            "unit": "millimeter",
                        },
                        # Temperature at the time of observation  (Fahrenheit or Celsius as per user preference)
                        {
                            "name": "temperature_air_2m",
                            "name_original": "tobs",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        # Daily total sunshine (minutes)
                        {
                            "name": "sunshine_duration",
                            "name_original": "tsun",
                            "unit_type": "time",
                            "unit": "minute",
                        },
                        # Direction of fastest 5-second wind (degrees)
                        {
                            "name": "wind_direction_gust_max_5sec",
                            "name_original": "wdf5",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        # Direction of fastest 1-minute wind (degrees)
                        {
                            "name": "wind_direction_gust_max_1min",
                            "name_original": "wdf1",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        # Direction of fastest 2-minute wind (degrees)
                        {
                            "name": "wind_direction_gust_max_2min",
                            "name_original": "wdf2",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        # Direction of peak wind gust (degrees)
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "wdfg",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        # Direction of highest instantaneous wind (degrees)
                        {
                            "name": "wind_direction_gust_max_instant",
                            "name_original": "wdfi",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        # Fastest mile wind direction (degrees)
                        {
                            "name": "wind_direction_gust_max_1mile",
                            "name_original": "wdfm",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        # 24-hour wind movement (km or miles as per user preference, miles on Daily Form pdf file)
                        {
                            "name": "wind_movement_24h",
                            "name_original": "wdmv",
                            "unit_type": "length_long",
                            "unit": "kilometer",
                        },
                        # Water equivalent of snow on the ground (inches or mm as per user preference)
                        {
                            "name": "water_equivalent_snow_depth",
                            "name_original": "wesd",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        # Water equivalent of snowfall (inches or mm as per user preference)
                        {
                            "name": "water_equivalent_snow_depth_new",
                            "name_original": "wesf",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        # Fastest 5-second wind speed (miles per hour or  meters per second as per user preference)
                        {
                            "name": "wind_gust_max_5sec",
                            "name_original": "wsf5",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        # Fastest 1-minute wind speed (miles per hour or  meters per second as per user preference)
                        {
                            "name": "wind_gust_max_1min",
                            "name_original": "wsf1",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        # Fastest 2-minute wind speed (miles per hour or  meters per second as per user preference)
                        {
                            "name": "wind_gust_max_2min",
                            "name_original": "wsf2",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        # Peak guest wind speed (miles per hour or  meters per second as per user preference)
                        {
                            "name": "wind_gust_max",
                            "name_original": "wsfg",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        # Highest instantaneous wind speed (miles per hour or  meters per second as per user preference)
                        {
                            "name": "wind_gust_max_instant",
                            "name_original": "wsfi",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        # Fastest mile wind speed (miles per hour or  meters per second as per user preference)
                        {
                            "name": "wind_gust_max_1mile",
                            "name_original": "wsfm",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        # weather types
                        # WT** = Weather Type where ** has one of the following values:
                        #     01 = Fog, ice fog, or freezing fog (may include heavy fog)
                        #     02 = Heavy fog or heaving freezing fog (not always distinguished from fog)
                        #     03 = Thunder
                        #     04 = Ice pellets, sleet, snow pellets, or small hail
                        #     05 = Hail (may include small hail)
                        #     06 = Glaze or rime
                        #     07 = Dust, volcanic ash, blowing dust, blowing sand, or blowing obstruction
                        #     08 = Smoke or haze
                        #     09 = Blowing or drifting snow
                        #     10 = Tornado, waterspout, or funnel cloud
                        #     11 = High or damaging winds
                        #     12 = Blowing spray
                        #     13 = Mist
                        #     14 = Drizzle
                        #     15 = Freezing drizzle
                        #     16 = Rain (may include freezing rain, drizzle, and freezing drizzle)
                        #     17 = Freezing rain
                        #     18 = Snow, snow pellets, snow grains, or ice crystals
                        #     19 = Unknown source of precipitation
                        #     21 = Ground fog
                        #     22 = Ice fog or freezing fog
                        {
                            "name": "weather_type_fog",
                            "name_original": "wt01",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_heavy_fog",
                            "name_original": "wt02",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_thunder",
                            "name_original": "wt03",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_ice_sleet_snow_hail",
                            "name_original": "wt04",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_hail",
                            "name_original": "wt05",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_glaze_rime",
                            "name_original": "wt06",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_dust_ash_sand",
                            "name_original": "wt07",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_smoke_haze",
                            "name_original": "wt08",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_blowing_drifting_snow",
                            "name_original": "wt09",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_tornado_waterspout",
                            "name_original": "wt10",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_high_damaging_winds",
                            "name_original": "wt11",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_blowing_spray",
                            "name_original": "wt12",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_mist",
                            "name_original": "wt13",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_drizzle",
                            "name_original": "wt14",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_freezing_drizzle",
                            "name_original": "wt15",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_rain",
                            "name_original": "wt16",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_freezing_rain",
                            "name_original": "wt17",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_snow_pellets_snow_grains_ice_crystals",
                            "name_original": "wt18",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_precipitation_unknown_source",
                            "name_original": "wt19",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_ground_fog",
                            "name_original": "wt21",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_ice_fog_freezing_fog",
                            "name_original": "wt22",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        # weather type vicinity
                        # WVxx = Weather in the Vicinity where “xx” has one of the following values
                        #     01 = Fog, ice fog, or freezing fog (may include heavy fog)
                        #     03 = Thunder
                        #     07 = Ash, dust, sand, or other blowing obstruction
                        #     18 = Snow or ice crystals
                        #     20 = Rain or snow shower
                        {
                            "name": "weather_type_vicinity_fog_any",
                            "name_original": "wv01",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_vicinity_thunder",
                            "name_original": "wv03",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_vicinity_dust_ash_sand",
                            "name_original": "wv07",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_vicinity_snow_ice_crystals",
                            "name_original": "wv18",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_type_vicinity_rain_snow_shower",
                            "name_original": "wv20",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                    ],
                }
            ],
        },
    ],
}
NoaaGhcnMetadata = build_metadata_model(NoaaGhcnMetadata, "NoaaGhcnMetadata")

DAILY_PARAMETER_MULTIPLICATION_FACTORS = {
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].precipitation_height.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].precipitation_height_multiday.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_air_max_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_air_max_2m_multiday.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_air_min_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_air_min_2m_multiday.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_air_mean_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].wind_speed.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].evaporation_height.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].evaporation_height_multiday.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_water_evaporation_pan_max.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_water_evaporation_pan_min.name_original: 1 / 10,
    # height definition similar to temperature with three digits
    # 0 - unknown
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_unknown_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_unknown_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_unknown_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_unknown_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_unknown_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_unknown_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_unknown_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_unknown_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_unknown_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_unknown_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_unknown_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_unknown_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_unknown_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_unknown_1_8m.name_original: 1 / 10,
    # 1 - grass
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_1_8m.name_original: 1 / 10,
    # 2 - fallow
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_fallow_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_fallow_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_fallow_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_fallow_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_fallow_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_fallow_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_fallow_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_fallow_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_fallow_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_fallow_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_fallow_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_fallow_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_fallow_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_fallow_1_8m.name_original: 1 / 10,
    # 3 - bare ground
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_ground_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_ground_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_ground_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_ground_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_ground_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_ground_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_ground_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_ground_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_ground_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_ground_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_ground_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_ground_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_ground_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_ground_1_8m.name_original: 1 / 10,
    # 4 - brome grass
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_brome_grass_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_brome_grass_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_brome_grass_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_brome_grass_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_brome_grass_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_brome_grass_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_brome_grass_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_brome_grass_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_brome_grass_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_brome_grass_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_brome_grass_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_brome_grass_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_brome_grass_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_brome_grass_1_8m.name_original: 1 / 10,
    # 5 - sod
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_sod_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_sod_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_sod_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_sod_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_sod_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_sod_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_sod_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_sod_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_sod_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_sod_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_sod_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_sod_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_sod_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_sod_1_8m.name_original: 1 / 10,
    # 6 - straw mulch
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_straw_mulch_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_straw_mulch_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_straw_mulch_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_straw_mulch_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_straw_mulch_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_straw_mulch_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_straw_mulch_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_straw_mulch_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_straw_mulch_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_straw_mulch_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_straw_mulch_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_straw_mulch_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_straw_mulch_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_straw_mulch_1_8m.name_original: 1 / 10,
    # 7 - grass muck
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_muck_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_muck_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_muck_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_muck_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_muck_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_muck_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_grass_muck_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_muck_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_muck_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_muck_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_muck_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_muck_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_muck_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_grass_muck_1_8m.name_original: 1 / 10,
    # 8 - bare muck
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_muck_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_muck_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_muck_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_muck_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_muck_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_muck_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_min_bare_muck_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_muck_0_05m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_muck_0_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_muck_0_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_muck_0_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_muck_1m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_muck_1_5m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_soil_max_bare_muck_1_8m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].ice_on_water_thickness.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].temperature_air_2m.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].water_equivalent_snow_depth.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].water_equivalent_snow_depth_new.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].wind_gust_max_5sec.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].wind_gust_max_1min.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].wind_gust_max_2min.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].wind_gust_max.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].wind_gust_max_instant.name_original: 1 / 10,
    NoaaGhcnMetadata.daily[DATASET_NAME_DEFAULT].wind_gust_max_1mile.name_original: 1 / 10,
}
