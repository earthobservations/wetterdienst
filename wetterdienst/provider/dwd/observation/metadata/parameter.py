# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.util.parameter import DatasetTreeCore


class DwdObservationParameter(DatasetTreeCore):
    # 1_minute
    class MINUTE_1(DatasetTreeCore):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn"
            PRECIPITATION_HEIGHT = "rs_01"
            PRECIPITATION_HEIGHT_DROPLET = "rth_01"
            PRECIPITATION_HEIGHT_ROCKER = "rwh_01"
            PRECIPITATION_INDEX = "rs_ind_01"  # int

        PRECIPITATION_HEIGHT = PRECIPITATION.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_DROPLET = PRECIPITATION.PRECIPITATION_HEIGHT_DROPLET
        PRECIPITATION_HEIGHT_ROCKER = PRECIPITATION.PRECIPITATION_HEIGHT_ROCKER
        PRECIPITATION_INDEX = PRECIPITATION.PRECIPITATION_INDEX

    # 5_minutes
    class MINUTE_5(DatasetTreeCore):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn_5min"
            PRECIPITATION_INDEX = "rs_ind_05"  # int
            PRECIPITATION_HEIGHT = "rs_05"
            PRECIPITATION_HEIGHT_DROPLET = "rth_05"
            PRECIPITATION_HEIGHT_ROCKER = "rwh_05"

        PRECIPITATION_INDEX = PRECIPITATION.PRECIPITATION_INDEX
        PRECIPITATION_HEIGHT = PRECIPITATION.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_DROPLET = PRECIPITATION.PRECIPITATION_HEIGHT_DROPLET
        PRECIPITATION_HEIGHT_ROCKER = PRECIPITATION.PRECIPITATION_HEIGHT_ROCKER

    # 10_minutes
    class MINUTE_10(DatasetTreeCore):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn"
            PRECIPITATION_DURATION = "rws_dau_10"
            PRECIPITATION_HEIGHT = "rws_10"
            PRECIPITATION_INDEX = "rws_ind_10"  # int

        # solar
        class SOLAR(Enum):
            QUALITY = "qn"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "ds_10"
            RADIATION_GLOBAL = "gs_10"
            SUNSHINE_DURATION = "sd_10"
            RADIATION_SKY_LONG_WAVE = "ls_10"

        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn"
            PRESSURE_AIR_SITE = "pp_10"
            TEMPERATURE_AIR_MEAN_200 = "tt_10"
            TEMPERATURE_AIR_MEAN_005 = "tm5_10"
            HUMIDITY = "rf_10"
            TEMPERATURE_DEW_POINT_MEAN_200 = "td_10"

        AIR_TEMPERATURE = TEMPERATURE_AIR

        # extreme_temperature
        class TEMPERATURE_EXTREME(Enum):  # noqa
            QUALITY = "qn"
            TEMPERATURE_AIR_MAX_200 = "tx_10"
            TEMPERATURE_AIR_MAX_005 = "tx5_10"
            TEMPERATURE_AIR_MIN_200 = "tn_10"
            TEMPERATURE_AIR_MIN_005 = "tn5_10"

        EXTREME_TEMPERATURE = TEMPERATURE_EXTREME

        # wind
        class WIND(Enum):
            QUALITY = "qn"
            WIND_SPEED = "ff_10"
            WIND_DIRECTION = "dd_10"

        # extreme_wind
        class WIND_EXTREME(Enum):  # noqa
            QUALITY = "qn"
            WIND_GUST_MAX = "fx_10"
            WIND_SPEED_MIN = "fnx_10"
            WIND_SPEED_ROLLING_MEAN_MAX = "fmx_10"
            WIND_DIRECTION_GUST_MAX = "dx_10"  # int

        EXTREME_WIND = WIND_EXTREME

        # air_temperature
        PRESSURE_AIR_SITE = TEMPERATURE_AIR.PRESSURE_AIR_SITE
        TEMPERATURE_AIR_MEAN_200 = TEMPERATURE_AIR.TEMPERATURE_AIR_MEAN_200
        TEMPERATURE_AIR_MEAN_005 = TEMPERATURE_AIR.TEMPERATURE_AIR_MEAN_005
        HUMIDITY = TEMPERATURE_AIR.HUMIDITY
        TEMPERATURE_DEW_POINT_MEAN_200 = TEMPERATURE_AIR.TEMPERATURE_DEW_POINT_MEAN_200

        # extreme_temperature
        TEMPERATURE_AIR_MAX_200 = TEMPERATURE_EXTREME.TEMPERATURE_AIR_MAX_200
        TEMPERATURE_AIR_MAX_005 = TEMPERATURE_EXTREME.TEMPERATURE_AIR_MAX_005
        TEMPERATURE_AIR_MIN_200 = TEMPERATURE_EXTREME.TEMPERATURE_AIR_MIN_200
        TEMPERATURE_AIR_MIN_005 = TEMPERATURE_EXTREME.TEMPERATURE_AIR_MIN_005

        # extreme_wind
        WIND_GUST_MAX = WIND_EXTREME.WIND_GUST_MAX
        WIND_SPEED_MIN = WIND_EXTREME.WIND_SPEED_MIN
        WIND_SPEED_ROLLING_MEAN_MAX = WIND_EXTREME.WIND_SPEED_ROLLING_MEAN_MAX
        WIND_DIRECTION_GUST_MAX = WIND_EXTREME.WIND_DIRECTION_GUST_MAX

        # precipitation
        PRECIPITATION_DURATION = PRECIPITATION.PRECIPITATION_DURATION
        PRECIPITATION_HEIGHT = PRECIPITATION.PRECIPITATION_HEIGHT
        PRECIPITATION_INDEX = PRECIPITATION.PRECIPITATION_INDEX

        # solar
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = SOLAR.RADIATION_SKY_SHORT_WAVE_DIFFUSE
        RADIATION_GLOBAL = SOLAR.RADIATION_GLOBAL
        SUNSHINE_DURATION = SOLAR.SUNSHINE_DURATION
        RADIATION_SKY_LONG_WAVE = SOLAR.RADIATION_SKY_LONG_WAVE

        # wind
        WIND_SPEED = WIND.WIND_SPEED
        WIND_DIRECTION = WIND.WIND_DIRECTION

    # hourly
    class HOURLY(DatasetTreeCore):
        # cloud_type
        class CLOUD_TYPE(Enum):  # noqa
            QUALITY = "qn_8"
            CLOUD_COVER_TOTAL = "v_n"  # int
            CLOUD_COVER_TOTAL_INDEX = "v_n_i"  # str
            CLOUD_TYPE_LAYER1 = "v_s1_cs"  # int
            CLOUD_TYPE_LAYER1_ABBREVIATION = "v_s1_csa"  # str
            CLOUD_HEIGHT_LAYER1 = "v_s1_hhs"
            CLOUD_COVER_LAYER1 = "v_s1_ns"  # int
            CLOUD_TYPE_LAYER2 = "v_s2_cs"  # int
            CLOUD_TYPE_LAYER2_ABBREVIATION = "v_s2_csa"  # str
            CLOUD_HEIGHT_LAYER2 = "v_s2_hhs"
            CLOUD_COVER_LAYER2 = "v_s2_ns"  # int
            CLOUD_TYPE_LAYER3 = "v_s3_cs"  # int
            CLOUD_TYPE_LAYER3_ABBREVIATION = "v_s3_csa"  # str
            CLOUD_HEIGHT_LAYER3 = "v_s3_hhs"
            CLOUD_COVER_LAYER3 = "v_s3_ns"  # int
            CLOUD_TYPE_LAYER4 = "v_s4_cs"  # int
            CLOUD_TYPE_LAYER4_ABBREVIATION = "v_s4_csa"  # str
            CLOUD_HEIGHT_LAYER4 = "v_s4_hhs"
            CLOUD_COVER_LAYER4 = "v_s4_ns"  # int

        # cloudiness
        class CLOUDINESS(Enum):
            QUALITY = "qn_8"
            CLOUD_COVER_TOTAL_INDEX = "v_n_i"  # str
            CLOUD_COVER_TOTAL = "v_n"  # int

        # dew_point
        class DEW_POINT(Enum):  # noqa
            QUALITY = "qn_8"
            TEMPERATURE_AIR_MEAN_200 = "tt"
            TEMPERATURE_DEW_POINT_MEAN_200 = "td"

        # moisture
        class MOISTURE(Enum):
            QUALITY = "qn_4"
            HUMIDITY_ABSOLUTE = "absf_std"
            PRESSURE_VAPOR = "vp_std"
            TEMPERATURE_WET_MEAN_200 = "tf_std"
            PRESSURE_AIR_SITE = "p_std"
            TEMPERATURE_AIR_MEAN_200 = "tt_std"
            HUMIDITY = "rf_std"
            TEMPERATURE_DEW_POINT_MEAN_200 = "td_std"

        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn_8"
            PRECIPITATION_HEIGHT = "r1"
            PRECIPITATION_INDEX = "rs_ind"  # int
            PRECIPITATION_FORM = "wrtr"  # int

        # pressure
        class PRESSURE(Enum):
            QUALITY = "qn_8"
            PRESSURE_AIR_SEA_LEVEL = "p"
            PRESSURE_AIR_SITE = "p0"

        # solar
        class SOLAR(Enum):
            QUALITY = "qn_592"
            END_OF_INTERVAL = "end_of_interval"  # modified, does not exist in original
            RADIATION_SKY_LONG_WAVE = "atmo_lberg"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "fd_lberg"
            RADIATION_GLOBAL = "fg_lberg"
            SUNSHINE_DURATION = "sd_lberg"
            SUN_ZENITH_ANGLE = "zenit"
            TRUE_LOCAL_TIME = "true_local_time"  # original name was adjusted to this one

        # sun
        class SUN(Enum):
            QUALITY = "qn_7"
            SUNSHINE_DURATION = "sd_so"

        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn_9"
            TEMPERATURE_AIR_MEAN_200 = "tt_tu"
            HUMIDITY = "rf_tu"

        AIR_TEMPERATURE = TEMPERATURE_AIR

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "qn_2"
            TEMPERATURE_SOIL_MEAN_002 = "v_te002"
            TEMPERATURE_SOIL_MEAN_005 = "v_te005"
            TEMPERATURE_SOIL_MEAN_010 = "v_te010"
            TEMPERATURE_SOIL_MEAN_020 = "v_te020"
            TEMPERATURE_SOIL_MEAN_050 = "v_te050"
            TEMPERATURE_SOIL_MEAN_100 = "v_te100"

        SOIL_TEMPERATURE = TEMPERATURE_SOIL

        # visibility
        class VISIBILITY(Enum):
            QUALITY = "qn_8"
            VISIBILITY_RANGE_INDEX = "v_vv_i"  # str
            VISIBILITY_RANGE = "v_vv"  # int

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):
            QUALITY = "qn_8"
            WEATHER = "ww"
            WEATHER_TEXT = "ww_text"

        # wind
        class WIND(Enum):
            QUALITY = "qn_3"
            WIND_SPEED = "f"
            WIND_DIRECTION = "d"  # int

        # extreme_wind
        class WIND_EXTREME(Enum):  # noqa
            QUALITY = "qn_8"
            WIND_GUST_MAX = "fx_911"

        EXTREME_WIND = WIND_EXTREME

        # wind_synop
        class WIND_SYNOPTIC(Enum):  # noqa
            QUALITY = "qn_8"
            WIND_SPEED = "ff"
            WIND_DIRECTION = "dd"  # int

        WIND_SYNOP = WIND_SYNOPTIC

        # URBAN DATASETS #
        class URBAN_PRECIPITATION(Enum):  # noqa
            QUALITY = "qualitaets_niveau"
            PRECIPITATION_HEIGHT = "niederschlagshoehe"

        class URBAN_PRESSURE(Enum):  # noqa
            QUALITY = "qualitaets_niveau"
            PRESSURE_AIR_SITE = "luftdruck_stationshoehe"

        class URBAN_SUN(Enum):  # noqa
            QUALITY = "qualitaets_niveau"
            SUNSHINE_DURATION = "sonnenscheindauer"

        class URBAN_TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qualitaets_niveau"
            TEMPERATURE_AIR_MEAN_200 = "lufttemperatur"
            HUMIDITY = "rel_feuchte"

        URBAN_AIR_TEMPERATURE = URBAN_TEMPERATURE_AIR

        class URBAN_TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "qualitaets_niveau"
            TEMPERATURE_SOIL_MEAN_005 = "erdbt_005"
            TEMPERATURE_SOIL_MEAN_010 = "erdbt_010"
            TEMPERATURE_SOIL_MEAN_020 = "erdbt_020"
            TEMPERATURE_SOIL_MEAN_050 = "erdbt_050"
            TEMPERATURE_SOIL_MEAN_100 = "erdbt_100"

        URBAN_SOIL_TEMPERATURE = URBAN_TEMPERATURE_SOIL

        class URBAN_WIND(Enum):  # noqa
            QUALITY = "qualitaets_niveau"
            WIND_SPEED = "windgeschwindigkeit"
            WIND_DIRECTION = "windrichtung"  # int

        # air_temperature
        TEMPERATURE_AIR_MEAN_200 = TEMPERATURE_AIR.TEMPERATURE_AIR_MEAN_200
        HUMIDITY = TEMPERATURE_AIR.HUMIDITY

        # cloud_type
        CLOUD_TYPE_LAYER1 = CLOUD_TYPE.CLOUD_TYPE_LAYER1
        CLOUD_HEIGHT_LAYER1 = CLOUD_TYPE.CLOUD_HEIGHT_LAYER1
        CLOUD_COVER_LAYER1 = CLOUD_TYPE.CLOUD_COVER_LAYER1
        CLOUD_TYPE_LAYER2 = CLOUD_TYPE.CLOUD_TYPE_LAYER2
        CLOUD_HEIGHT_LAYER2 = CLOUD_TYPE.CLOUD_HEIGHT_LAYER2
        CLOUD_COVER_LAYER2 = CLOUD_TYPE.CLOUD_COVER_LAYER2
        CLOUD_TYPE_LAYER3 = CLOUD_TYPE.CLOUD_TYPE_LAYER3
        CLOUD_HEIGHT_LAYER3 = CLOUD_TYPE.CLOUD_HEIGHT_LAYER3
        CLOUD_COVER_LAYER3 = CLOUD_TYPE.CLOUD_COVER_LAYER3
        CLOUD_TYPE_LAYER4 = CLOUD_TYPE.CLOUD_TYPE_LAYER4
        CLOUD_HEIGHT_LAYER4 = CLOUD_TYPE.CLOUD_HEIGHT_LAYER4
        CLOUD_COVER_LAYER4 = CLOUD_TYPE.CLOUD_COVER_LAYER4

        # cloudiness
        CLOUD_COVER_TOTAL = CLOUDINESS.CLOUD_COVER_TOTAL
        CLOUD_COVER_TOTAL_INDEX = CLOUDINESS.CLOUD_COVER_TOTAL_INDEX

        # dew_point
        TEMPERATURE_DEW_POINT_MEAN_200 = DEW_POINT.TEMPERATURE_DEW_POINT_MEAN_200

        # extreme_wind
        WIND_GUST_MAX = WIND_EXTREME.WIND_GUST_MAX

        # moisture
        HUMIDITY_ABSOLUTE = MOISTURE.HUMIDITY_ABSOLUTE
        PRESSURE_VAPOR = MOISTURE.PRESSURE_VAPOR
        TEMPERATURE_WET_MEAN_200 = MOISTURE.TEMPERATURE_WET_MEAN_200

        # precipitation
        PRECIPITATION_HEIGHT = PRECIPITATION.PRECIPITATION_HEIGHT
        PRECIPITATION_INDEX = PRECIPITATION.PRECIPITATION_INDEX
        PRECIPITATION_FORM = PRECIPITATION.PRECIPITATION_FORM

        # pressure
        PRESSURE_AIR_SEA_LEVEL = PRESSURE.PRESSURE_AIR_SEA_LEVEL
        PRESSURE_AIR_SITE = PRESSURE.PRESSURE_AIR_SITE

        # soil_temperature
        TEMPERATURE_SOIL_MEAN_002 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_002
        TEMPERATURE_SOIL_MEAN_005 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_005
        TEMPERATURE_SOIL_MEAN_010 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_010
        TEMPERATURE_SOIL_MEAN_020 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_020
        TEMPERATURE_SOIL_MEAN_050 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_050
        TEMPERATURE_SOIL_MEAN_100 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_100

        # solar
        RADIATION_SKY_LONG_WAVE = SOLAR.RADIATION_SKY_LONG_WAVE
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = SOLAR.RADIATION_SKY_SHORT_WAVE_DIFFUSE
        RADIATION_GLOBAL = SOLAR.RADIATION_GLOBAL
        SUN_ZENITH_ANGLE = SOLAR.SUN_ZENITH_ANGLE

        # sun
        SUNSHINE_DURATION = SUN.SUNSHINE_DURATION

        # visibility
        VISIBILITY_RANGE_INDEX = VISIBILITY.VISIBILITY_RANGE_INDEX
        VISIBILITY_RANGE = VISIBILITY.VISIBILITY_RANGE

        # weather phenomena
        WEATHER = WEATHER_PHENOMENA.WEATHER

        # wind
        WIND_SPEED = WIND.WIND_SPEED
        WIND_DIRECTION = WIND.WIND_DIRECTION

    # subdaily
    class SUBDAILY(DatasetTreeCore):  # noqa
        # cloudiness
        class CLOUDINESS(Enum):
            QUALITY = "qn_4"
            CLOUD_COVER_TOTAL = "n_ter"  # int
            CLOUD_DENSITY = "cd_ter"  # int

        # moisture
        class MOISTURE(Enum):
            QUALITY = "qn_4"
            PRESSURE_VAPOR = "vp_ter"
            TEMPERATURE_AIR_MEAN_005 = "e_tf_ter"
            TEMPERATURE_AIR_MEAN_200 = "tf_ter"
            HUMIDITY = "rf_ter"

        # pressure
        class PRESSURE(Enum):
            QUALITY = "qn_4"
            PRESSURE_AIR_SITE = "pp_ter"

        # soil
        class SOIL(Enum):
            QUALITY = "qn_4"
            TEMPERATURE_SOIL_MEAN_005 = "ek_ter"  # int

        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn_4"
            TEMPERATURE_AIR_MEAN_200 = "tt_ter"
            HUMIDITY = "rf_ter"

        AIR_TEMPERATURE = TEMPERATURE_AIR

        # visibility
        class VISIBILITY(Enum):
            QUALITY = "qn_4"
            VISIBILITY_RANGE = "vk_ter"  # int

        # wind
        class WIND(Enum):
            QUALITY = "qn_4"
            WIND_DIRECTION = "dk_ter"  # int
            WIND_FORCE_BEAUFORT = "fk_ter"  # int

        # extreme_wind
        class WIND_EXTREME(Enum):
            QUALITY_3 = "qn_8_3"
            WIND_GUST_MAX_LAST_3H = "fx_911_3"
            QUALITY_6 = "qn_8_6"
            WIND_GUST_MAX_LAST_6H = "fx_911_6"

        EXTREME_WIND = WIND_EXTREME

        # air_temperature
        TEMPERATURE_AIR_MEAN_200 = TEMPERATURE_AIR.TEMPERATURE_AIR_MEAN_200
        HUMIDITY = TEMPERATURE_AIR.HUMIDITY

        # cloudiness
        CLOUD_COVER_TOTAL = CLOUDINESS.CLOUD_COVER_TOTAL
        CLOUD_DENSITY = CLOUDINESS.CLOUD_DENSITY

        # extreme_wind
        WIND_GUST_MAX_LAST_3H = WIND_EXTREME.WIND_GUST_MAX_LAST_3H
        WIND_GUST_MAX_LAST_6H = WIND_EXTREME.WIND_GUST_MAX_LAST_6H

        # moisture
        PRESSURE_VAPOR = MOISTURE.PRESSURE_VAPOR
        TEMPERATURE_AIR_MEAN_005 = MOISTURE.TEMPERATURE_AIR_MEAN_005

        # pressure
        PRESSURE_AIR_SITE = PRESSURE.PRESSURE_AIR_SITE

        # soil
        TEMPERATURE_SOIL_MEAN_005 = SOIL.TEMPERATURE_SOIL_MEAN_005

        # visibility
        VISIBILITY_RANGE = VISIBILITY.VISIBILITY_RANGE

        # wind
        WIND_DIRECTION = WIND.WIND_DIRECTION
        WIND_FORCE_BEAUFORT = WIND.WIND_FORCE_BEAUFORT

    # Daily
    class DAILY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_WIND = "qn_3"
            WIND_GUST_MAX = "fx"
            WIND_SPEED = "fm"
            QUALITY_GENERAL = "qn_4"  # special case here with two quality columns!
            PRECIPITATION_HEIGHT = "rsk"
            PRECIPITATION_FORM = "rskf"
            SUNSHINE_DURATION = "sdk"
            SNOW_DEPTH = "shk_tag"
            CLOUD_COVER_TOTAL = "nm"
            PRESSURE_VAPOR = "vpm"
            PRESSURE_AIR_SITE = "pm"
            TEMPERATURE_AIR_MEAN_200 = "tmk"
            HUMIDITY = "upm"
            TEMPERATURE_AIR_MAX_200 = "txk"
            TEMPERATURE_AIR_MIN_200 = "tnk"
            TEMPERATURE_AIR_MIN_005 = "tgk"

        KL = CLIMATE_SUMMARY

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "qn_6"
            PRECIPITATION_HEIGHT = "rs"
            PRECIPITATION_FORM = "rsf"  # int
            SNOW_DEPTH = "sh_tag"  # int
            SNOW_DEPTH_NEW = "nsh_tag"  # int

        MORE_PRECIP = PRECIPITATION_MORE

        # solar
        class SOLAR(Enum):
            QUALITY = "qn_592"
            RADIATION_SKY_LONG_WAVE = "atmo_strahl"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "fd_strahl"
            RADIATION_GLOBAL = "fg_strahl"
            SUNSHINE_DURATION = "sd_strahl"

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "qn_2"
            TEMPERATURE_SOIL_MEAN_002 = "v_te002m"
            TEMPERATURE_SOIL_MEAN_005 = "v_te005m"
            TEMPERATURE_SOIL_MEAN_010 = "v_te010m"
            TEMPERATURE_SOIL_MEAN_020 = "v_te020m"
            TEMPERATURE_SOIL_MEAN_050 = "v_te050m"
            TEMPERATURE_SOIL_MEAN_100 = "v_te100m"

        SOIL_TEMPERATURE = TEMPERATURE_SOIL

        # water_equiv
        class WATER_EQUIVALENT(Enum):  # noqa
            QN_6 = "qn_6"
            SNOW_DEPTH_EXCELLED = "ash_6"  # int
            SNOW_DEPTH = "sh_tag"  # int
            WATER_EQUIVALENT_SNOW_DEPTH = "wash_6"
            WATER_EQUIVALENT_SNOW_DEPTH_EXCELLED = "waas_6"

        WATER_EQUIV = WATER_EQUIVALENT

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "qn_4"
            COUNT_WEATHER_TYPE_FOG = "nebel"  # int
            COUNT_WEATHER_TYPE_THUNDER = "gewitter"  # int
            COUNT_WEATHER_TYPE_STORM_STRONG_WIND = "sturm_6"  # int
            COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = "sturm_8"  # int
            COUNT_WEATHER_TYPE_DEW = "tau"  # int
            COUNT_WEATHER_TYPE_GLAZE = "glatteis"  # int
            COUNT_WEATHER_TYPE_RIPE = "reif"  # int
            COUNT_WEATHER_TYPE_SLEET = "graupel"  # int
            COUNT_WEATHER_TYPE_HAIL = "hagel"  # int

        # more_weather_phenomena
        class WEATHER_PHENOMENA_MORE(Enum):  # noqa
            QUALITY = "qn_6"
            COUNT_WEATHER_TYPE_SLEET = "rr_graupel"  # int
            COUNT_WEATHER_TYPE_HAIL = "rr_hagel"  # int
            COUNT_WEATHER_TYPE_FOG = "rr_nebel"  # int
            COUNT_WEATHER_TYPE_THUNDER = "rr_gewitter"  # int

        MORE_WEATHER_PHENOMENA = WEATHER_PHENOMENA_MORE

        # kl
        WIND_GUST_MAX = CLIMATE_SUMMARY.WIND_GUST_MAX
        WIND_SPEED = CLIMATE_SUMMARY.WIND_SPEED
        PRECIPITATION_HEIGHT = CLIMATE_SUMMARY.PRECIPITATION_HEIGHT
        PRECIPITATION_FORM = CLIMATE_SUMMARY.PRECIPITATION_FORM
        SUNSHINE_DURATION = CLIMATE_SUMMARY.SUNSHINE_DURATION
        SNOW_DEPTH = CLIMATE_SUMMARY.SNOW_DEPTH
        CLOUD_COVER_TOTAL = CLIMATE_SUMMARY.CLOUD_COVER_TOTAL
        PRESSURE_VAPOR = CLIMATE_SUMMARY.PRESSURE_VAPOR
        PRESSURE_AIR_SITE = CLIMATE_SUMMARY.PRESSURE_AIR_SITE
        TEMPERATURE_AIR_MEAN_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MEAN_200
        HUMIDITY = CLIMATE_SUMMARY.HUMIDITY
        TEMPERATURE_AIR_MAX_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_200
        TEMPERATURE_AIR_MIN_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_200
        TEMPERATURE_AIR_MIN_005 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_005

        # more_precip
        SNOW_DEPTH_NEW = PRECIPITATION_MORE.SNOW_DEPTH_NEW

        # soil_temperature
        TEMPERATURE_SOIL_MEAN_002 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_002
        TEMPERATURE_SOIL_MEAN_005 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_005
        TEMPERATURE_SOIL_MEAN_010 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_010
        TEMPERATURE_SOIL_MEAN_020 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_020
        TEMPERATURE_SOIL_MEAN_050 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_050
        TEMPERATURE_SOIL_MEAN_100 = TEMPERATURE_SOIL.TEMPERATURE_SOIL_MEAN_100

        # solar
        RADIATION_SKY_LONG_WAVE = SOLAR.RADIATION_SKY_LONG_WAVE
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = SOLAR.RADIATION_SKY_SHORT_WAVE_DIFFUSE
        RADIATION_GLOBAL = SOLAR.RADIATION_GLOBAL

        # water_equiv
        SNOW_DEPTH_EXCELLED = WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED
        WATER_EQUIVALENT_SNOW_DEPTH = WATER_EQUIVALENT.WATER_EQUIVALENT_SNOW_DEPTH
        WATER_EQUIVALENT_SNOW_DEPTH_EXCELLED = WATER_EQUIVALENT.WATER_EQUIVALENT_SNOW_DEPTH_EXCELLED

        # weather_phenomena
        COUNT_WEATHER_TYPE_FOG = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_FOG
        COUNT_WEATHER_TYPE_THUNDER = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_THUNDER
        COUNT_WEATHER_TYPE_STORM_STRONG_WIND = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STRONG_WIND
        COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND
        COUNT_WEATHER_TYPE_DEW = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_DEW
        COUNT_WEATHER_TYPE_GLAZE = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_GLAZE
        COUNT_WEATHER_TYPE_RIPE = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_RIPE
        COUNT_WEATHER_TYPE_SLEET = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_SLEET
        COUNT_WEATHER_TYPE_HAIL = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_HAIL

    # monthly
    class MONTHLY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "qn_4"
            CLOUD_COVER_TOTAL = "mo_n"
            TEMPERATURE_AIR_MEAN_200 = "mo_tt"
            TEMPERATURE_AIR_MAX_200_MEAN = "mo_tx"
            TEMPERATURE_AIR_MIN_200_MEAN = "mo_tn"
            SUNSHINE_DURATION = "mo_sd_s"
            WIND_FORCE_BEAUFORT = "mo_fk"
            TEMPERATURE_AIR_MAX_200 = "mx_tx"
            WIND_GUST_MAX = "mx_fx"
            TEMPERATURE_AIR_MIN_200 = "mx_tn"
            QUALITY_PRECIPITATION = "qn_6"
            PRECIPITATION_HEIGHT = "mo_rr"
            PRECIPITATION_HEIGHT_MAX = "mx_rs"

        KL = CLIMATE_SUMMARY

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "qn_6"
            SNOW_DEPTH_NEW = "mo_nsh"  # int
            PRECIPITATION_HEIGHT = "mo_rr"
            SNOW_DEPTH = "mo_sh_s"  # int
            PRECIPITATION_HEIGHT_MAX = "mx_rs"

        MORE_PRECIP = PRECIPITATION_MORE

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "qn_4"
            COUNT_WEATHER_TYPE_STORM_STRONG_WIND = "mo_sturm_6"  # int
            COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = "mo_sturm_8"  # int
            COUNT_WEATHER_TYPE_THUNDER = "mo_gewitter"  # int
            COUNT_WEATHER_TYPE_GLAZE = "mo_glatteis"  # int
            COUNT_WEATHER_TYPE_SLEET = "mo_graupel"  # int
            COUNT_WEATHER_TYPE_HAIL = "mo_hagel"  # int
            COUNT_WEATHER_TYPE_FOG = "mo_nebel"  # int
            COUNT_WEATHER_TYPE_DEW = "mo_tau"  # int

        # kl
        CLOUD_COVER_TOTAL = CLIMATE_SUMMARY.CLOUD_COVER_TOTAL
        TEMPERATURE_AIR_MEAN_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MEAN_200
        TEMPERATURE_AIR_MAX_200_MEAN = CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_200_MEAN
        TEMPERATURE_AIR_MIN_200_MEAN = CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_200_MEAN
        WIND_FORCE_BEAUFORT = CLIMATE_SUMMARY.WIND_FORCE_BEAUFORT
        TEMPERATURE_AIR_MAX_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_200
        WIND_GUST_MAX = CLIMATE_SUMMARY.WIND_GUST_MAX
        TEMPERATURE_AIR_MIN_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_200
        SUNSHINE_DURATION = CLIMATE_SUMMARY.SUNSHINE_DURATION
        PRECIPITATION_HEIGHT = CLIMATE_SUMMARY.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_MAX = CLIMATE_SUMMARY.PRECIPITATION_HEIGHT_MAX

        # more_precip
        SNOW_DEPTH_NEW = PRECIPITATION_MORE.SNOW_DEPTH_NEW
        SNOW_DEPTH = PRECIPITATION_MORE.SNOW_DEPTH

        # weather_phenomena
        COUNT_WEATHER_TYPE_STORM_STRONG_WIND = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STRONG_WIND
        COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND
        COUNT_WEATHER_TYPE_THUNDER = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_THUNDER
        COUNT_WEATHER_TYPE_GLAZE = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_GLAZE
        COUNT_WEATHER_TYPE_SLEET = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_SLEET
        COUNT_WEATHER_TYPE_HAIL = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_HAIL
        COUNT_WEATHER_TYPE_FOG = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_FOG
        COUNT_WEATHER_TYPE_DEW = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_DEW

    # annual
    class ANNUAL(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "qn_4"
            CLOUD_COVER_TOTAL = "ja_n"
            TEMPERATURE_AIR_MEAN_200 = "ja_tt"
            TEMPERATURE_AIR_MAX_200_MEAN = "ja_tx"
            TEMPERATURE_AIR_MIN_200_MEAN = "ja_tn"
            SUNSHINE_DURATION = "ja_sd_s"
            WIND_FORCE_BEAUFORT = "ja_fk"
            WIND_GUST_MAX = "ja_mx_fx"
            TEMPERATURE_AIR_MAX_200 = "ja_mx_tx"
            TEMPERATURE_AIR_MIN_200 = "ja_mx_tn"
            QUALITY_PRECIPITATION = "qn_6"
            PRECIPITATION_HEIGHT = "ja_rr"
            PRECIPITATION_HEIGHT_MAX = "ja_mx_rs"

        KL = CLIMATE_SUMMARY

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "qn_6"
            SNOW_DEPTH_NEW = "ja_nsh"  # int
            PRECIPITATION_HEIGHT = "ja_rr"
            SNOW_DEPTH = "ja_sh_s"  # int
            PRECIPITATION_HEIGHT_MAX = "ja_mx_rs"

        MORE_PRECIP = PRECIPITATION_MORE

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "qn_4"
            COUNT_WEATHER_TYPE_STORM_STRONG_WIND = "ja_sturm_6"  # int
            COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = "ja_sturm_8"  # int
            COUNT_WEATHER_TYPE_THUNDER = "ja_gewitter"  # int
            COUNT_WEATHER_TYPE_GLAZE = "ja_glatteis"  # int
            COUNT_WEATHER_TYPE_SLEET = "ja_graupel"  # int
            COUNT_WEATHER_TYPE_HAIL = "ja_hagel"  # int
            COUNT_WEATHER_TYPE_FOG = "ja_nebel"  # int
            COUNT_WEATHER_TYPE_DEW = "ja_tau"  # int

        # kl
        CLOUD_COVER_TOTAL = CLIMATE_SUMMARY.CLOUD_COVER_TOTAL
        TEMPERATURE_AIR_MEAN_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MEAN_200
        TEMPERATURE_AIR_MAX_200_MEAN = CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_200_MEAN
        TEMPERATURE_AIR_MIN_200_MEAN = CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_200_MEAN
        WIND_FORCE_BEAUFORT = CLIMATE_SUMMARY.WIND_FORCE_BEAUFORT
        SUNSHINE_DURATION = CLIMATE_SUMMARY.SUNSHINE_DURATION
        WIND_GUST_MAX = CLIMATE_SUMMARY.WIND_GUST_MAX
        TEMPERATURE_AIR_MAX_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_200
        TEMPERATURE_AIR_MIN_200 = CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_200
        PRECIPITATION_HEIGHT = CLIMATE_SUMMARY.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_MAX = CLIMATE_SUMMARY.PRECIPITATION_HEIGHT_MAX

        # more_precip
        SNOW_DEPTH_NEW = PRECIPITATION_MORE.SNOW_DEPTH_NEW
        SNOW_DEPTH = PRECIPITATION_MORE.SNOW_DEPTH

        # weather_phenomena
        COUNT_WEATHER_TYPE_STORM_STRONG_WIND = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STRONG_WIND
        COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND
        COUNT_WEATHER_TYPE_THUNDER = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_THUNDER
        COUNT_WEATHER_TYPE_GLAZE = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_GLAZE
        COUNT_WEATHER_TYPE_SLEET = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_SLEET
        COUNT_WEATHER_TYPE_HAIL = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_HAIL
        COUNT_WEATHER_TYPE_FOG = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_FOG
        COUNT_WEATHER_TYPE_DEW = WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_DEW
