# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.parameter import WDParameterStructureBase


class DwdObservationParameter(WDParameterStructureBase):
    # Following DWDObsParameterSetStructure
    # 1_minute
    class MINUTE_1(Enum):  # noqa
        # precipitation
        PRECIPITATION_HEIGHT = "rs_01"
        PRECIPITATION_HEIGHT_DROPLET = "rth_01"
        PRECIPITATION_HEIGHT_ROCKER = "rwh_01"
        PRECIPITATION_FORM = "rs_ind_01"  # int

    # 10_minutes
    class MINUTE_10(Enum):  # noqa
        # air_temperature
        PRESSURE_AIR_STATION_HEIGHT = "pp_10"
        TEMPERATURE_AIR_200 = "tt_10"
        TEMPERATURE_AIR_005 = "tm5_10"
        HUMIDITY = "rf_10"
        TEMPERATURE_DEW_POINT_200 = "td_10"

        # extreme_temperature
        TEMPERATURE_AIR_MAX_200 = "tx_10"
        TEMPERATURE_AIR_MAX_005 = "tx5_10"
        TEMPERATURE_AIR_MIN_200 = "tn_10"
        TEMPERATURE_AIR_MIN_005 = "tn5_10"

        # extreme_wind
        WIND_GUST_MAX = "fx_10"
        WIND_SPEED_MIN = "fnx_10"
        WIND_SPEED_ROLLING_MEAN_MAX = "fmx_10"
        WIND_DIRECTION_MAX_VELOCITY = "dx_10"  # int

        # precipitation
        PRECIPITATION_DURATION = "rws_dau_10"
        PRECIPITATION_HEIGHT = "rws_10"
        PRECIPITATION_INDICATOR_WR = "rws_ind_10"  # int

        # solar
        RADIATION_SKY_DIFFUSE = "ds_10"
        RADIATION_GLOBAL = "gs_10"
        SUNSHINE_DURATION = "sd_10"
        RADIATION_SKY_LONG_WAVE = "ls_10"

        # wind
        WIND_SPEED = "ff_10"
        WIND_DIRECTION = "dd_10"

    # hourly
    class HOURLY(Enum):
        # air_temperature
        TEMPERATURE_AIR_200 = "tt_tu"
        HUMIDITY = "rf_tu"

        # cloud_type
        CLOUD_COVER_TOTAL = "v_n"  # int
        CLOUD_COVER_TOTAL_INDICATOR = "v_n_i"  # str
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
        # CLOUD_COVER_TOTAL_INDICATOR = "v_n_i"  # str
        # CLOUD_COVER_TOTAL = "v_n"  # int

        # dew_point
        # TEMPERATURE_AIR_200 = "tt"
        TEMPERATURE_DEW_POINT_200 = "td"

        # precipitation
        PRECIPITATION_HEIGHT = "r1"
        PRECIPITATION_INDICATOR = "rs_ind"  # int
        PRECIPITATION_FORM = "wrtr"  # int

        # pressure
        PRESSURE_AIR_SEA_LEVEL = "p"
        PRESSURE_AIR_STATION_HEIGHT = "p0"

        # soil_temperature
        TEMPERATURE_SOIL_002 = "v_te002"
        TEMPERATURE_SOIL_005 = "v_te005"
        TEMPERATURE_SOIL_010 = "v_te010"
        TEMPERATURE_SOIL_020 = "v_te020"
        TEMPERATURE_SOIL_050 = "v_te050"
        TEMPERATURE_SOIL_100 = "v_te100"

        # solar
        END_OF_INTERVAL = "end_of_interval"  # modified, does not exist in original
        RADIATION_SKY_LONG_WAVE = "atmo_lberg"
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = "fd_lberg"
        RADIATION_GLOBAL = "fg_lberg"
        SUNSHINE_DURATION = "sd_lberg"
        SUN_ZENITH = "zenit"
        TRUE_LOCAL_TIME = "true_local_time"  # original name was adjusted to this one

        # sun
        # SUNSHINE_DURATION = "sd_so"

        # visibility
        VISIBILITY_INDICATOR = "v_vv_i"  # str
        VISIBILITY = "v_vv"  # int

        # wind
        WIND_SPEED = "f"
        WIND_DIRECTION = "d"  # int

        # wind_synop
        # WIND_SPEED = "ff"
        # WIND_DIRECTION = "dd"  # int

    # subdaily
    class SUBDAILY(Enum):  # noqa
        # air_temperature
        TEMPERATURE_AIR_200 = "tt_ter"
        HUMIDITY = "rf_ter"

        # cloudiness
        CLOUD_COVER_TOTAL = "n_ter"  # int
        CLOUD_DENSITY = "cd_ter"  # int

        # moisture
        PRESSURE_VAPOR = "vp_ter"
        TEMPERATURE_AIR_005 = "e_tf_ter"
        # TEMPERATURE_AIR_200 = "tf_ter"
        # HUMIDITY = "rf_ter"

        # pressure
        PRESSURE_AIR = "pp_ter"

        # soil
        TEMPERATURE_SOIL_005 = "ek_ter"  # int

        # visibility
        VISIBILITY = "vk_ter"  # int

        # wind
        WIND_DIRECTION = "dk_ter"  # int
        WIND_FORCE_BEAUFORT = "fk_ter"  # int

    # Daily
    class DAILY(Enum):
        # kl
        WIND_GUST_MAX = "fx"
        WIND_SPEED = "fm"
        PRECIPITATION_HEIGHT = "rsk"
        PRECIPITATION_FORM = "rskf"
        SUNSHINE_DURATION = "sdk"
        SNOW_DEPTH = "shk_tag"
        CLOUD_COVER_TOTAL = "nm"
        PRESSURE_VAPOR = "vpm"
        PRESSURE_AIR = "pm"
        TEMPERATURE_AIR_200 = "tmk"
        HUMIDITY = "upm"
        TEMPERATURE_AIR_MAX_200 = "txk"
        TEMPERATURE_AIR_MIN_200 = "tnk"
        TEMPERATURE_AIR_MIN_005 = "tgk"

        # more_precip
        # PRECIPITATION_HEIGHT = "rs"
        # PRECIPITATION_FORM = "rsf"  # int
        # SNOW_DEPTH = "sh_tag"  # int
        SNOW_DEPTH_NEW = "nsh_tag"  # int

        # soil_temperature
        TEMPERATURE_SOIL_002 = "v_te002m"
        TEMPERATURE_SOIL_005 = "v_te005m"
        TEMPERATURE_SOIL_010 = "v_te010m"
        TEMPERATURE_SOIL_020 = "v_te020m"
        TEMPERATURE_SOIL_050 = "v_te050m"

        # solar
        RADIATION_SKY_LONG_WAVE = "atmo_strahl"
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = "fd_strahl"
        RADIATION_SKY_SHORT_WAVE_DIRECT = "fg_strahl"
        # SUNSHINE_DURATION = "sd_strahl"

        # water_equiv
        SNOW_DEPTH_EXCELLED = "ash_6"  # int
        # SNOW_DEPTH = "sh_tag"  # int
        WATER_EQUIVALENT_TOTAL_SNOW_DEPTH = "wash_6"
        WATER_EQUIVALENT_SNOW = "waas_6"

        # weather_phenomena
        FOG = "nebel"  # int
        THUNDER = "gewitter"  # int
        STORM_STRONG_WIND = "sturm_6"  # int
        STORM_STORMIER_WIND = "sturm_8"  # int
        DEW = "tau"  # int
        GLAZE = "glatteis"  # int
        RIPE = "reif"  # int
        SLEET = "graupel"  # int
        HAIL = "hagel"  # int

    # monthly
    class MONTHLY(Enum):
        # kl
        CLOUD_COVER_TOTAL = "mo_n"
        TEMPERATURE_AIR_200 = "mo_tt"
        TEMPERATURE_AIR_MAX_MEAN_200 = "mo_tx"
        TEMPERATURE_AIR_MIN_MEAN_200 = "mo_tn"
        WIND_FORCE_BEAUFORT = "mo_fk"
        TEMPERATURE_AIR_MAX_200 = "mx_tx"
        WIND_GUST_MAX = "mx_fx"
        TEMPERATURE_AIR_MIN_200 = "mx_tn"
        SUNSHINE_DURATION = "mo_sd_s"
        PRECIPITATION_HEIGHT = "mo_rr"
        PRECIPITATION_HEIGHT_MAX = "mx_rs"

        # more_precip
        SNOW_DEPTH_NEW = "mo_nsh"  # int
        # PRECIPITATION_HEIGHT = "mo_rr"
        SNOW_DEPTH = "mo_sh_s"  # int
        # PRECIPITATION_HEIGHT_MAX = "mx_rs"

        # weather_phenomena
        STORM_STRONG_WIND = "mo_sturm_6"  # int
        STORM_STORMIER_WIND = "mo_sturm_8"  # int
        THUNDER = "mo_gewitter"  # int
        GLAZE = "mo_glatteis"  # int
        SLEET = "mo_graupel"  # int
        HAIL = "mo_hagel"  # int
        FOG = "mo_nebel"  # int
        DEW = "mo_tau"  # int

    # annual
    class ANNUAL(Enum):
        # kl
        CLOUD_COVER_TOTAL = "ja_n"
        TEMPERATURE_AIR_200 = "ja_tt"
        TEMPERATURE_AIR_MAX_MEAN_200 = "ja_tx"
        TEMPERATURE_AIR_MIN_MEAN_200 = "ja_tn"
        WIND_FORCE_BEAUFORT = "ja_fk"
        SUNSHINE_DURATION = "ja_sd_s"
        WIND_GUST_MAX = "ja_mx_fx"
        TEMPERATURE_AIR_MAX_200 = "ja_mx_tx"
        TEMPERATURE_AIR_MIN_200 = "ja_mx_tn"
        PRECIPITATION_HEIGHT = "ja_rr"
        PRECIPITATION_HEIGHT_MAX = "ja_mx_rs"

        # more_precip
        SNOW_DEPTH_NEW = "ja_nsh"  # int
        # PRECIPITATION_HEIGHT = "ja_rr"
        SNOW_DEPTH = "ja_sh_s"  # int
        # PRECIPITATION_HEIGHT_MAX = "ja_mx_rs"

        # weather_phenomena
        STORM_STRONG_WIND = "ja_sturm_6"  # int
        STORM_STORMIER_WIND = "ja_sturm_8"  # int
        THUNDER = "ja_gewitter"  # int
        GLAZE = "ja_glatteis"  # int
        SLEET = "ja_graupel"  # int
        HAIL = "ja_hagel"  # int
        FOG = "ja_nebel"  # int
        DEW = "ja_tau"  # int


class DwdObservationDatasetStructure(WDParameterStructureBase):
    """
    Original data column names from DWD data
    Two anomalies:
    - daily/kl -> QN_3, QN_4
    - monthly/kl -> QN_4, QN_6
    - annual/kl -> QN_4, QN_6
    """

    # 1_minute
    class MINUTE_1(WDParameterStructureBase):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn"
            PRECIPITATION_HEIGHT = "rs_01"
            PRECIPITATION_HEIGHT_DROPLET = "rth_01"
            PRECIPITATION_HEIGHT_ROCKER = "rwh_01"
            PRECIPITATION_FORM = "rs_ind_01"  # int

    # 10_minutes
    class MINUTE_10(WDParameterStructureBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn"
            PRESSURE_AIR_STATION_HEIGHT = "pp_10"
            TEMPERATURE_AIR_200 = "tt_10"
            TEMPERATURE_AIR_005 = "tm5_10"
            HUMIDITY = "rf_10"
            TEMPERATURE_DEW_POINT_200 = "td_10"

        # extreme_temperature
        class TEMPERATURE_EXTREME(Enum):  # noqa
            QUALITY = "qn"
            TEMPERATURE_AIR_MAX_200 = "tx_10"
            TEMPERATURE_AIR_MAX_005 = "tx5_10"
            TEMPERATURE_AIR_MIN_200 = "tn_10"
            TEMPERATURE_AIR_MIN_005 = "tn5_10"

        # extreme_wind
        class WIND_EXTREME(Enum):  # noqa
            QUALITY = "qn"
            WIND_GUST_MAX = "fx_10"
            WIND_SPEED_MIN = "fnx_10"
            WIND_SPEED_ROLLING_MEAN_MAX = "fmx_10"
            WIND_DIRECTION_MAX_VELOCITY = "dx_10"  # int

        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn"
            PRECIPITATION_DURATION = "rws_dau_10"
            PRECIPITATION_HEIGHT = "rws_10"
            PRECIPITATION_INDICATOR_WR = "rws_ind_10"  # int

        # solar
        class SOLAR(Enum):
            QUALITY = "qn"
            RADIATION_SKY_DIFFUSE = "ds_10"
            RADIATION_GLOBAL = "gs_10"
            SUNSHINE_DURATION = "sd_10"
            RADIATION_SKY_LONG_WAVE = "ls_10"

        # wind
        class WIND(Enum):
            QUALITY = "qn"
            WIND_SPEED = "ff_10"
            WIND_DIRECTION = "dd_10"

    # hourly
    class HOURLY(WDParameterStructureBase):
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn_9"
            TEMPERATURE_AIR_200 = "tt_tu"
            HUMIDITY = "rf_tu"

        # cloud_type
        class CLOUD_TYPE(Enum):  # noqa
            QUALITY = "qn_8"
            CLOUD_COVER_TOTAL = "v_n"  # int
            CLOUD_COVER_TOTAL_INDICATOR = "v_n_i"  # str
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
            CLOUD_COVER_TOTAL_INDICATOR = "v_n_i"  # str
            CLOUD_COVER_TOTAL = "v_n"  # int

        # dew_point
        class DEW_POINT(Enum):  # noqa
            QUALITY = "qn_8"
            TEMPERATURE_AIR_200 = "tt"
            TEMPERATURE_DEW_POINT_200 = "td"

        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn_8"
            PRECIPITATION_HEIGHT = "r1"
            PRECIPITATION_INDICATOR = "rs_ind"  # int
            PRECIPITATION_FORM = "wrtr"  # int

        # pressure
        class PRESSURE(Enum):
            QUALITY = "qn_8"
            PRESSURE_AIR_SEA_LEVEL = "p"
            PRESSURE_AIR_STATION_HEIGHT = "p0"

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "qn_2"
            TEMPERATURE_SOIL_002 = "v_te002"
            TEMPERATURE_SOIL_005 = "v_te005"
            TEMPERATURE_SOIL_010 = "v_te010"
            TEMPERATURE_SOIL_020 = "v_te020"
            TEMPERATURE_SOIL_050 = "v_te050"
            TEMPERATURE_SOIL_100 = "v_te100"

        # solar
        class SOLAR(Enum):
            QUALITY = "qn_592"
            END_OF_INTERVAL = "end_of_interval"  # modified, does not exist in original
            RADIATION_SKY_LONG_WAVE = "atmo_lberg"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "fd_lberg"
            RADIATION_GLOBAL = "fg_lberg"
            SUNSHINE_DURATION = "sd_lberg"
            SUN_ZENITH = "zenit"
            TRUE_LOCAL_TIME = (
                "true_local_time"  # original name was adjusted to this one
            )

        # sun
        class SUN(Enum):
            QUALITY = "qn_7"
            SUNSHINE_DURATION = "sd_so"

        # visibility
        class VISIBILITY(Enum):
            QUALITY = "qn_8"
            VISIBILITY_INDICATOR = "v_vv_i"  # str
            VISIBILITY = "v_vv"  # int

        # wind
        class WIND(Enum):
            QUALITY = "qn_3"
            WIND_SPEED = "f"
            WIND_DIRECTION = "d"  # int

        # wind_synop
        class WIND_SYNOPTIC(Enum):  # noqa
            QUALITY = "qn_8"
            WIND_SPEED = "ff"
            WIND_DIRECTION = "dd"  # int

    # subdaily
    class SUBDAILY(WDParameterStructureBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn_4"
            TEMPERATURE_AIR_200 = "tt_ter"
            HUMIDITY = "rf_ter"

        # cloudiness
        class CLOUDINESS(Enum):
            QUALITY = "qn_4"
            CLOUD_COVER_TOTAL = "n_ter"  # int
            CLOUD_DENSITY = "cd_ter"  # int

        # moisture
        class MOISTURE(Enum):
            QUALITY = "qn_4"
            PRESSURE_VAPOR = "vp_ter"
            TEMPERATURE_AIR_005 = "e_tf_ter"
            TEMPERATURE_AIR_200 = "tf_ter"
            HUMIDITY = "rf_ter"

        # pressure
        class PRESSURE(Enum):
            QUALITY = "qn_4"
            PRESSURE_AIR = "pp_ter"

        # soil
        class SOIL(Enum):
            QUALITY = "qn_4"
            TEMPERATURE_SOIL_005 = "ek_ter"  # int

        # visibility
        class VISIBILITY(Enum):
            QUALITY = "qn_4"
            VISIBILITY = "vk_ter"  # int

        # wind
        class WIND(Enum):
            QUALITY = "qn_4"
            WIND_DIRECTION = "dk_ter"  # int
            WIND_FORCE_BEAUFORT = "fk_ter"  # int

    # Daily
    class DAILY(WDParameterStructureBase):
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
            PRESSURE_AIR = "pm"
            TEMPERATURE_AIR_200 = "tmk"
            HUMIDITY = "upm"
            TEMPERATURE_AIR_MAX_200 = "txk"
            TEMPERATURE_AIR_MIN_200 = "tnk"
            TEMPERATURE_AIR_MIN_005 = "tgk"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "qn_6"
            PRECIPITATION_HEIGHT = "rs"
            PRECIPITATION_FORM = "rsf"  # int
            SNOW_DEPTH = "sh_tag"  # int
            SNOW_DEPTH_NEW = "nsh_tag"  # int

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "qn_2"
            TEMPERATURE_SOIL_002 = "v_te002m"
            TEMPERATURE_SOIL_005 = "v_te005m"
            TEMPERATURE_SOIL_010 = "v_te010m"
            TEMPERATURE_SOIL_020 = "v_te020m"
            TEMPERATURE_SOIL_050 = "v_te050m"

        # solar
        class SOLAR(Enum):
            QUALITY = "qn_592"
            RADIATION_SKY_LONG_WAVE = "atmo_strahl"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "fd_strahl"
            RADIATION_SKY_SHORT_WAVE_DIRECT = "fg_strahl"
            SUNSHINE_DURATION = "sd_strahl"

        # water_equiv
        class WATER_EQUIVALENT(Enum):  # noqa
            QN_6 = "qn_6"
            SNOW_DEPTH_EXCELLED = "ash_6"  # int
            SNOW_DEPTH = "sh_tag"  # int
            WATER_EQUIVALENT_TOTAL_SNOW_DEPTH = "wash_6"
            WATER_EQUIVALENT_SNOW = "waas_6"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "qn_4"
            FOG = "nebel"  # int
            THUNDER = "gewitter"  # int
            STORM_STRONG_WIND = "sturm_6"  # int
            STORM_STORMIER_WIND = "sturm_8"  # int
            DEW = "tau"  # int
            GLAZE = "glatteis"  # int
            RIPE = "reif"  # int
            SLEET = "graupel"  # int
            HAIL = "hagel"  # int

    # monthly
    class MONTHLY(WDParameterStructureBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "qn_4"
            CLOUD_COVER_TOTAL = "mo_n"
            TEMPERATURE_AIR_200 = "mo_tt"
            TEMPERATURE_AIR_MAX_MEAN_200 = "mo_tx"
            TEMPERATURE_AIR_MIN_MEAN_200 = "mo_tn"
            WIND_FORCE_BEAUFORT = "mo_fk"
            TEMPERATURE_AIR_MAX_200 = "mx_tx"
            WIND_GUST_MAX = "mx_fx"
            TEMPERATURE_AIR_MIN_200 = "mx_tn"
            SUNSHINE_DURATION = "mo_sd_s"
            QUALITY_PRECIPITATION = "qn_6"
            PRECIPITATION_HEIGHT = "mo_rr"
            PRECIPITATION_HEIGHT_MAX = "mx_rs"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "qn_6"
            SNOW_DEPTH_NEW = "mo_nsh"  # int
            PRECIPITATION_HEIGHT = "mo_rr"
            SNOW_DEPTH = "mo_sh_s"  # int
            PRECIPITATION_HEIGHT_MAX = "mx_rs"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "qn_4"
            STORM_STRONG_WIND = "mo_sturm_6"  # int
            STORM_STORMIER_WIND = "mo_sturm_8"  # int
            THUNDER = "mo_gewitter"  # int
            GLAZE = "mo_glatteis"  # int
            SLEET = "mo_graupel"  # int
            HAIL = "mo_hagel"  # int
            FOG = "mo_nebel"  # int
            DEW = "mo_tau"  # int

    # annual
    class ANNUAL(WDParameterStructureBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "qn_4"
            CLOUD_COVER_TOTAL = "ja_n"
            TEMPERATURE_AIR_200 = "ja_tt"
            TEMPERATURE_AIR_MAX_MEAN_200 = "ja_tx"
            TEMPERATURE_AIR_MIN_MEAN_200 = "ja_tn"
            WIND_FORCE_BEAUFORT = "ja_fk"
            SUNSHINE_DURATION = "ja_sd_s"
            WIND_GUST_MAX = "ja_mx_fx"
            TEMPERATURE_AIR_MAX_200 = "ja_mx_tx"
            TEMPERATURE_AIR_MIN_200 = "ja_mx_tn"
            QUALITY_PRECIPITATION = "qn_6"
            PRECIPITATION_HEIGHT = "ja_rr"
            PRECIPITATION_HEIGHT_MAX = "ja_mx_rs"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "qn_6"
            SNOW_DEPTH_NEW = "ja_nsh"  # int
            PRECIPITATION_HEIGHT = "ja_rr"
            SNOW_DEPTH = "ja_sh_s"  # int
            PRECIPITATION_HEIGHT_MAX = "ja_mx_rs"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "qn_4"
            STORM_STRONG_WIND = "ja_sturm_6"  # int
            STORM_STORMIER_WIND = "ja_sturm_8"  # int
            THUNDER = "ja_gewitter"  # int
            GLAZE = "ja_glatteis"  # int
            SLEET = "ja_graupel"  # int
            HAIL = "ja_hagel"  # int
            FOG = "ja_nebel"  # int
            DEW = "ja_tau"  # int


PARAMETER_TO_DATASET_MAPPING = {
    Resolution.MINUTE_1: {
        # precipitation
        DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT: DwdObservationDatasetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT,
        DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT_DROPLET: DwdObservationDatasetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT_DROPLET,
        DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT_ROCKER: DwdObservationDatasetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT_ROCKER,
        DwdObservationParameter.MINUTE_1.PRECIPITATION_FORM: DwdObservationDatasetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM,
    },
    Resolution.MINUTE_10: {
        # air_temperature
        DwdObservationParameter.MINUTE_10.PRESSURE_AIR_STATION_HEIGHT: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_AIR.PRESSURE_AIR_STATION_HEIGHT,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_200: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_AIR.TEMPERATURE_AIR_200,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_005: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_AIR.TEMPERATURE_AIR_005,
        DwdObservationParameter.MINUTE_10.HUMIDITY: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_AIR.HUMIDITY,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_DEW_POINT_200: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_AIR.TEMPERATURE_DEW_POINT_200,
        # extreme_temperature
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MAX_200: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_EXTREME.TEMPERATURE_AIR_MAX_200,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MAX_005: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_EXTREME.TEMPERATURE_AIR_MAX_005,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MIN_200: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_EXTREME.TEMPERATURE_AIR_MIN_200,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MIN_005: DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_EXTREME.TEMPERATURE_AIR_MIN_005,
        # extreme_wind
        DwdObservationParameter.MINUTE_10.WIND_GUST_MAX: DwdObservationDatasetStructure.MINUTE_10.WIND_EXTREME.WIND_GUST_MAX,
        DwdObservationParameter.MINUTE_10.WIND_SPEED_MIN: DwdObservationDatasetStructure.MINUTE_10.WIND_EXTREME.WIND_SPEED_MIN,
        DwdObservationParameter.MINUTE_10.WIND_SPEED_ROLLING_MEAN_MAX: DwdObservationDatasetStructure.MINUTE_10.WIND_EXTREME.WIND_SPEED_ROLLING_MEAN_MAX,
        DwdObservationParameter.MINUTE_10.WIND_DIRECTION_MAX_VELOCITY: DwdObservationDatasetStructure.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_MAX_VELOCITY,
        # precipitation
        DwdObservationParameter.MINUTE_10.PRECIPITATION_DURATION: DwdObservationDatasetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_DURATION,
        DwdObservationParameter.MINUTE_10.PRECIPITATION_HEIGHT: DwdObservationDatasetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        DwdObservationParameter.MINUTE_10.PRECIPITATION_INDICATOR_WR: DwdObservationDatasetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR,
        # solar
        DwdObservationParameter.MINUTE_10.RADIATION_SKY_DIFFUSE: DwdObservationDatasetStructure.MINUTE_10.SOLAR.RADIATION_SKY_DIFFUSE,
        DwdObservationParameter.MINUTE_10.RADIATION_GLOBAL: DwdObservationDatasetStructure.MINUTE_10.SOLAR.RADIATION_GLOBAL,
        DwdObservationParameter.MINUTE_10.SUNSHINE_DURATION: DwdObservationDatasetStructure.MINUTE_10.SOLAR.SUNSHINE_DURATION,
        DwdObservationParameter.MINUTE_10.RADIATION_SKY_LONG_WAVE: DwdObservationDatasetStructure.MINUTE_10.SOLAR.RADIATION_SKY_LONG_WAVE,
        # wind
        DwdObservationParameter.MINUTE_10.WIND_SPEED: DwdObservationDatasetStructure.MINUTE_10.WIND.WIND_SPEED,
        DwdObservationParameter.MINUTE_10.WIND_DIRECTION: DwdObservationDatasetStructure.MINUTE_10.WIND.WIND_DIRECTION,
    },
    Resolution.HOURLY: {
        # air_temperature
        DwdObservationParameter.HOURLY.TEMPERATURE_AIR_200: DwdObservationDatasetStructure.HOURLY.TEMPERATURE_AIR.TEMPERATURE_AIR_200,
        DwdObservationParameter.HOURLY.HUMIDITY: DwdObservationDatasetStructure.HOURLY.TEMPERATURE_AIR.HUMIDITY,
        # cloudiness
        DwdObservationParameter.HOURLY.CLOUD_COVER_TOTAL: DwdObservationDatasetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL,
        DwdObservationParameter.HOURLY.CLOUD_COVER_TOTAL_INDICATOR: DwdObservationDatasetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR,
        # cloud_type
        # DwdObservationParameter.HOURLY.CLOUD_COVER_TOTAL: DwdObservationParameterSet.CLOUD_TYPE,
        # DwdObservationParameter.HOURLY.CLOUD_COVER_TOTAL_INDICATOR: DwdObservationParameterSet.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER1: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER1_ABBREVIATION: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION,
        DwdObservationParameter.HOURLY.CLOUD_HEIGHT_LAYER1: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_HEIGHT_LAYER1,
        DwdObservationParameter.HOURLY.CLOUD_COVER_LAYER1: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER2: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER2_ABBREVIATION: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION,
        DwdObservationParameter.HOURLY.CLOUD_HEIGHT_LAYER2: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_HEIGHT_LAYER2,
        DwdObservationParameter.HOURLY.CLOUD_COVER_LAYER2: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER3: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER3_ABBREVIATION: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION,
        DwdObservationParameter.HOURLY.CLOUD_HEIGHT_LAYER3: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_HEIGHT_LAYER3,
        DwdObservationParameter.HOURLY.CLOUD_COVER_LAYER3: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER4: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER4_ABBREVIATION: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION,
        DwdObservationParameter.HOURLY.CLOUD_HEIGHT_LAYER4: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_HEIGHT_LAYER4,
        DwdObservationParameter.HOURLY.CLOUD_COVER_LAYER4: DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4,
        # dew_point
        # TEMPERATURE_AIR_200: "tt"
        DwdObservationParameter.HOURLY.TEMPERATURE_DEW_POINT_200: DwdObservationDatasetStructure.HOURLY.DEW_POINT.TEMPERATURE_DEW_POINT_200,
        # precipitation
        DwdObservationParameter.HOURLY.PRECIPITATION_HEIGHT: DwdObservationDatasetStructure.HOURLY.PRECIPITATION.PRECIPITATION_HEIGHT,
        DwdObservationParameter.HOURLY.PRECIPITATION_INDICATOR: DwdObservationDatasetStructure.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR,
        DwdObservationParameter.HOURLY.PRECIPITATION_FORM: DwdObservationDatasetStructure.HOURLY.PRECIPITATION.PRECIPITATION_FORM,
        # pressure
        DwdObservationParameter.HOURLY.PRESSURE_AIR_SEA_LEVEL: DwdObservationDatasetStructure.HOURLY.PRESSURE.PRESSURE_AIR_SEA_LEVEL,
        DwdObservationParameter.HOURLY.PRESSURE_AIR_STATION_HEIGHT: DwdObservationDatasetStructure.HOURLY.PRESSURE.PRESSURE_AIR_STATION_HEIGHT,
        # soil_temperature
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_002: DwdObservationDatasetStructure.HOURLY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_002,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_005: DwdObservationDatasetStructure.HOURLY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_005,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_010: DwdObservationDatasetStructure.HOURLY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_010,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_020: DwdObservationDatasetStructure.HOURLY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_020,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_050: DwdObservationDatasetStructure.HOURLY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_050,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_100: DwdObservationDatasetStructure.HOURLY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_100,
        # sun
        DwdObservationParameter.HOURLY.SUNSHINE_DURATION: DwdObservationDatasetStructure.HOURLY.SUN.SUNSHINE_DURATION,
        # solar
        DwdObservationParameter.HOURLY.END_OF_INTERVAL: DwdObservationDatasetStructure.HOURLY.SOLAR.END_OF_INTERVAL,
        DwdObservationParameter.HOURLY.RADIATION_SKY_LONG_WAVE: DwdObservationDatasetStructure.HOURLY.SOLAR.RADIATION_SKY_LONG_WAVE,
        DwdObservationParameter.HOURLY.RADIATION_SKY_SHORT_WAVE_DIFFUSE: DwdObservationDatasetStructure.HOURLY.SOLAR.RADIATION_SKY_SHORT_WAVE_DIFFUSE,
        DwdObservationParameter.HOURLY.RADIATION_GLOBAL: DwdObservationDatasetStructure.HOURLY.SOLAR.RADIATION_GLOBAL,
        # DwdObservationParameter.HOURLY.SUNSHINE_DURATION:                 DwdObservationParameterSetStructure.HOURLY.SOLAR.SUNSHINE_DURATION,
        DwdObservationParameter.HOURLY.SUN_ZENITH: DwdObservationDatasetStructure.HOURLY.SOLAR.SUN_ZENITH,
        DwdObservationParameter.HOURLY.TRUE_LOCAL_TIME: DwdObservationDatasetStructure.HOURLY.SOLAR.TRUE_LOCAL_TIME,
        # visibility
        DwdObservationParameter.HOURLY.VISIBILITY_INDICATOR: DwdObservationDatasetStructure.HOURLY.VISIBILITY.VISIBILITY_INDICATOR,
        DwdObservationParameter.HOURLY.VISIBILITY: DwdObservationDatasetStructure.HOURLY.VISIBILITY.VISIBILITY,
        # wind
        DwdObservationParameter.HOURLY.WIND_SPEED: DwdObservationDatasetStructure.HOURLY.WIND.WIND_SPEED,
        DwdObservationParameter.HOURLY.WIND_DIRECTION: DwdObservationDatasetStructure.HOURLY.WIND.WIND_DIRECTION,
        # wind_synop
        # DwdObservationParameter.HOURLY.WIND_SPEED: "ff"
        # DwdObservationParameter.HOURLY.WIND_DIRECTION: "dd"  # int
    },
    Resolution.SUBDAILY: {
        # air_temperature
        DwdObservationParameter.SUBDAILY.TEMPERATURE_AIR_200: DwdObservationDatasetStructure.SUBDAILY.TEMPERATURE_AIR.TEMPERATURE_AIR_200,
        DwdObservationParameter.SUBDAILY.HUMIDITY: DwdObservationDatasetStructure.SUBDAILY.TEMPERATURE_AIR.HUMIDITY,
        # cloudiness
        DwdObservationParameter.SUBDAILY.CLOUD_COVER_TOTAL: DwdObservationDatasetStructure.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL,
        DwdObservationParameter.SUBDAILY.CLOUD_DENSITY: DwdObservationDatasetStructure.SUBDAILY.CLOUDINESS.CLOUD_DENSITY,
        # moisture
        DwdObservationParameter.SUBDAILY.PRESSURE_VAPOR: DwdObservationDatasetStructure.SUBDAILY.MOISTURE.PRESSURE_VAPOR,
        DwdObservationParameter.SUBDAILY.TEMPERATURE_AIR_005: DwdObservationDatasetStructure.SUBDAILY.MOISTURE.TEMPERATURE_AIR_005,
        # TEMPERATURE_AIR_200: "tf_ter"
        # HUMIDITY: "rf_ter"
        # pressure
        DwdObservationParameter.SUBDAILY.PRESSURE_AIR: DwdObservationDatasetStructure.SUBDAILY.PRESSURE.PRESSURE_AIR,
        # soil
        DwdObservationParameter.SUBDAILY.TEMPERATURE_SOIL_005: DwdObservationDatasetStructure.SUBDAILY.SOIL.TEMPERATURE_SOIL_005,
        # visibility
        DwdObservationParameter.SUBDAILY.VISIBILITY: DwdObservationDatasetStructure.SUBDAILY.VISIBILITY.VISIBILITY,
        # wind
        DwdObservationParameter.SUBDAILY.WIND_DIRECTION: DwdObservationDatasetStructure.SUBDAILY.WIND.WIND_DIRECTION,
        DwdObservationParameter.SUBDAILY.WIND_FORCE_BEAUFORT: DwdObservationDatasetStructure.SUBDAILY.WIND.WIND_FORCE_BEAUFORT,
    },
    Resolution.DAILY: {
        # more_precip
        DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT: DwdObservationDatasetStructure.DAILY.PRECIPITATION_MORE.PRECIPITATION_HEIGHT,
        DwdObservationParameter.DAILY.PRECIPITATION_FORM: DwdObservationDatasetStructure.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM,
        DwdObservationParameter.DAILY.SNOW_DEPTH: DwdObservationDatasetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH,
        DwdObservationParameter.DAILY.SNOW_DEPTH_NEW: DwdObservationDatasetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW,
        # solar
        DwdObservationParameter.DAILY.RADIATION_SKY_LONG_WAVE: DwdObservationDatasetStructure.DAILY.SOLAR.RADIATION_SKY_LONG_WAVE,
        DwdObservationParameter.DAILY.RADIATION_SKY_SHORT_WAVE_DIFFUSE: DwdObservationDatasetStructure.DAILY.SOLAR.RADIATION_SKY_SHORT_WAVE_DIFFUSE,
        DwdObservationParameter.DAILY.RADIATION_SKY_SHORT_WAVE_DIRECT: DwdObservationDatasetStructure.DAILY.SOLAR.RADIATION_SKY_SHORT_WAVE_DIRECT,
        DwdObservationParameter.DAILY.SUNSHINE_DURATION: DwdObservationDatasetStructure.DAILY.SOLAR.SUNSHINE_DURATION,
        # kl
        DwdObservationParameter.DAILY.WIND_GUST_MAX: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.WIND_GUST_MAX,
        DwdObservationParameter.DAILY.WIND_SPEED: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.WIND_SPEED,
        # DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT: "rsk",
        # DwdObservationParameter.DAILY.PRECIPITATION_FORM: "rskf",
        # DwdObservationParameter.DAILY.SUNSHINE_DURATION: DwdObservationParameterSet.CLIMATE_SUMMARY,
        # DwdObservationParameter.DAILY.SNOW_DEPTH: "shk_tag",
        DwdObservationParameter.DAILY.CLOUD_COVER_TOTAL: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.CLOUD_COVER_TOTAL,
        DwdObservationParameter.DAILY.PRESSURE_VAPOR: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.PRESSURE_VAPOR,
        DwdObservationParameter.DAILY.PRESSURE_AIR: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.PRESSURE_AIR,
        DwdObservationParameter.DAILY.TEMPERATURE_AIR_200: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.TEMPERATURE_AIR_200,
        DwdObservationParameter.DAILY.HUMIDITY: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.HUMIDITY,
        DwdObservationParameter.DAILY.TEMPERATURE_AIR_MAX_200: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_200,
        DwdObservationParameter.DAILY.TEMPERATURE_AIR_MIN_200: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_200,
        DwdObservationParameter.DAILY.TEMPERATURE_AIR_MIN_005: DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_005,
        # soil_temperature
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_002: DwdObservationDatasetStructure.DAILY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_002,
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_005: DwdObservationDatasetStructure.DAILY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_005,
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_010: DwdObservationDatasetStructure.DAILY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_010,
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_020: DwdObservationDatasetStructure.DAILY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_020,
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_050: DwdObservationDatasetStructure.DAILY.TEMPERATURE_SOIL.TEMPERATURE_SOIL_050,
        # water_equiv
        DwdObservationParameter.DAILY.SNOW_DEPTH_EXCELLED: DwdObservationDatasetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED,
        # SNOW_DEPTH: "sh_tag"  # int
        DwdObservationParameter.DAILY.WATER_EQUIVALENT_TOTAL_SNOW_DEPTH: DwdObservationDatasetStructure.DAILY.WATER_EQUIVALENT.WATER_EQUIVALENT_TOTAL_SNOW_DEPTH,
        DwdObservationParameter.DAILY.WATER_EQUIVALENT_SNOW: DwdObservationDatasetStructure.DAILY.WATER_EQUIVALENT.WATER_EQUIVALENT_SNOW,
        # weather_phenomena
        DwdObservationParameter.DAILY.FOG: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.FOG,
        DwdObservationParameter.DAILY.THUNDER: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.THUNDER,
        DwdObservationParameter.DAILY.STORM_STRONG_WIND: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.STORM_STRONG_WIND,
        DwdObservationParameter.DAILY.STORM_STORMIER_WIND: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.STORM_STORMIER_WIND,
        DwdObservationParameter.DAILY.DEW: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.DEW,
        DwdObservationParameter.DAILY.GLAZE: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.GLAZE,
        DwdObservationParameter.DAILY.RIPE: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.RIPE,
        DwdObservationParameter.DAILY.SLEET: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.SLEET,
        DwdObservationParameter.DAILY.HAIL: DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.HAIL,
    },
    Resolution.MONTHLY: {
        # more_precip
        DwdObservationParameter.MONTHLY.SNOW_DEPTH_NEW: DwdObservationDatasetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW,
        DwdObservationParameter.MONTHLY.PRECIPITATION_HEIGHT: DwdObservationDatasetStructure.MONTHLY.PRECIPITATION_MORE.PRECIPITATION_HEIGHT,
        DwdObservationParameter.MONTHLY.SNOW_DEPTH: DwdObservationDatasetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH,
        DwdObservationParameter.MONTHLY.PRECIPITATION_HEIGHT_MAX: DwdObservationDatasetStructure.MONTHLY.PRECIPITATION_MORE.PRECIPITATION_HEIGHT_MAX,
        # kl
        DwdObservationParameter.MONTHLY.CLOUD_COVER_TOTAL: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.CLOUD_COVER_TOTAL,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_200: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.TEMPERATURE_AIR_200,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MAX_MEAN_200: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_MEAN_200,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MIN_MEAN_200: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_MEAN_200,
        DwdObservationParameter.MONTHLY.WIND_FORCE_BEAUFORT: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.WIND_FORCE_BEAUFORT,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MAX_200: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_200,
        DwdObservationParameter.MONTHLY.WIND_GUST_MAX: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.WIND_GUST_MAX,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MIN_200: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_200,
        DwdObservationParameter.MONTHLY.SUNSHINE_DURATION: DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.SUNSHINE_DURATION,
        # DwdObservationParameter.MONTHLY.PRECIPITATION_HEIGHT: DwdObservationParameterSet.CLIMATE_SUMMARY,
        # DwdObservationParameter.MONTHLY.PRECIPITATION_HEIGHT_MAX: DwdObservationParameterSet.CLIMATE_SUMMARY,
        # weather_phenomena
        DwdObservationParameter.MONTHLY.STORM_STRONG_WIND: DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STRONG_WIND,
        DwdObservationParameter.MONTHLY.STORM_STORMIER_WIND: DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STORMIER_WIND,
        DwdObservationParameter.MONTHLY.THUNDER: DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.THUNDER,
        DwdObservationParameter.MONTHLY.GLAZE: DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.GLAZE,
        DwdObservationParameter.MONTHLY.SLEET: DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.SLEET,
        DwdObservationParameter.MONTHLY.HAIL: DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.HAIL,
        DwdObservationParameter.MONTHLY.FOG: DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.FOG,
        DwdObservationParameter.MONTHLY.DEW: DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.DEW,
    },
    Resolution.ANNUAL: {
        # more_precip
        DwdObservationParameter.ANNUAL.SNOW_DEPTH_NEW: DwdObservationDatasetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW,
        DwdObservationParameter.ANNUAL.PRECIPITATION_HEIGHT: DwdObservationDatasetStructure.ANNUAL.PRECIPITATION_MORE.PRECIPITATION_HEIGHT,
        DwdObservationParameter.ANNUAL.SNOW_DEPTH: DwdObservationDatasetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH,
        DwdObservationParameter.ANNUAL.PRECIPITATION_HEIGHT_MAX: DwdObservationDatasetStructure.ANNUAL.PRECIPITATION_MORE.PRECIPITATION_HEIGHT_MAX,
        # kl
        DwdObservationParameter.ANNUAL.CLOUD_COVER_TOTAL: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.CLOUD_COVER_TOTAL,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_200: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.TEMPERATURE_AIR_200,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MAX_MEAN_200: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_MEAN_200,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MIN_MEAN_200: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_MEAN_200,
        DwdObservationParameter.ANNUAL.WIND_FORCE_BEAUFORT: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.WIND_FORCE_BEAUFORT,
        DwdObservationParameter.ANNUAL.SUNSHINE_DURATION: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.SUNSHINE_DURATION,
        DwdObservationParameter.ANNUAL.WIND_GUST_MAX: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.WIND_GUST_MAX,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MAX_200: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_200,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MIN_200: DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_200,
        # DwdObservationParameter.ANNUAL.PRECIPITATION_HEIGHT: "ja_rr",
        # DwdObservationParameter.ANNUAL.PRECIPITATION_HEIGHT_MAX: "ja_mx_rs",
        # weather_phenomena
        DwdObservationParameter.ANNUAL.STORM_STRONG_WIND: DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STRONG_WIND,
        DwdObservationParameter.ANNUAL.STORM_STORMIER_WIND: DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STORMIER_WIND,
        DwdObservationParameter.ANNUAL.THUNDER: DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.THUNDER,
        DwdObservationParameter.ANNUAL.GLAZE: DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.GLAZE,
        DwdObservationParameter.ANNUAL.SLEET: DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.SLEET,
        DwdObservationParameter.ANNUAL.HAIL: DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.HAIL,
        DwdObservationParameter.ANNUAL.FOG: DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.FOG,
        DwdObservationParameter.ANNUAL.DEW: DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.DEW,
    },
}
