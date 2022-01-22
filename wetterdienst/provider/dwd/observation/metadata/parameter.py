# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.metadata.dataset import DwdObservationDataset
from wetterdienst.util.parameter import DatasetTreeCore


class DwdObservationParameter(DatasetTreeCore):
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
        PRESSURE_AIR_SITE = "pp_10"
        TEMPERATURE_AIR_MEAN_200 = "tt_10"
        TEMPERATURE_AIR_MEAN_005 = "tm5_10"
        HUMIDITY = "rf_10"
        TEMPERATURE_DEW_POINT_MEAN_200 = "td_10"

        # extreme_temperature
        TEMPERATURE_AIR_MAX_200 = "tx_10"
        TEMPERATURE_AIR_MAX_005 = "tx5_10"
        TEMPERATURE_AIR_MIN_200 = "tn_10"
        TEMPERATURE_AIR_MIN_005 = "tn5_10"

        # extreme_wind
        WIND_GUST_MAX = "fx_10"
        WIND_SPEED_MIN = "fnx_10"
        WIND_SPEED_ROLLING_MEAN_MAX = "fmx_10"
        WIND_DIRECTION_GUST_MAX = "dx_10"  # int

        # precipitation
        PRECIPITATION_DURATION = "rws_dau_10"
        PRECIPITATION_HEIGHT = "rws_10"
        PRECIPITATION_INDICATOR_WR = "rws_ind_10"  # int

        # solar
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = "ds_10"
        RADIATION_GLOBAL = "gs_10"
        SUNSHINE_DURATION = "sd_10"
        RADIATION_SKY_LONG_WAVE = "ls_10"

        # wind
        WIND_SPEED = "ff_10"
        WIND_DIRECTION = "dd_10"

    # hourly
    class HOURLY(Enum):
        # air_temperature
        TEMPERATURE_AIR_MEAN_200 = "tt_tu"
        HUMIDITY = "rf_tu"

        # cloud_type
        CLOUD_COVER_TOTAL = "v_n"  # int
        CLOUD_TYPE_LAYER1 = "v_s1_cs"  # int
        CLOUD_HEIGHT_LAYER1 = "v_s1_hhs"
        CLOUD_COVER_LAYER1 = "v_s1_ns"  # int
        CLOUD_TYPE_LAYER2 = "v_s2_cs"  # int
        CLOUD_HEIGHT_LAYER2 = "v_s2_hhs"
        CLOUD_COVER_LAYER2 = "v_s2_ns"  # int
        CLOUD_TYPE_LAYER3 = "v_s3_cs"  # int
        CLOUD_HEIGHT_LAYER3 = "v_s3_hhs"
        CLOUD_COVER_LAYER3 = "v_s3_ns"  # int
        CLOUD_TYPE_LAYER4 = "v_s4_cs"  # int
        CLOUD_HEIGHT_LAYER4 = "v_s4_hhs"
        CLOUD_COVER_LAYER4 = "v_s4_ns"  # int

        # dew_point
        TEMPERATURE_DEW_POINT_MEAN_200 = "td"

        # precipitation
        PRECIPITATION_HEIGHT = "r1"
        PRECIPITATION_INDICATOR = "rs_ind"  # int
        PRECIPITATION_FORM = "wrtr"  # int

        # pressure
        PRESSURE_AIR_SEA_LEVEL = "p"
        PRESSURE_AIR_SITE = "p0"

        # soil_temperature
        TEMPERATURE_SOIL_MEAN_002 = "v_te002"
        TEMPERATURE_SOIL_MEAN_005 = "v_te005"
        TEMPERATURE_SOIL_MEAN_010 = "v_te010"
        TEMPERATURE_SOIL_MEAN_020 = "v_te020"
        TEMPERATURE_SOIL_MEAN_050 = "v_te050"
        TEMPERATURE_SOIL_MEAN_100 = "v_te100"

        # solar
        RADIATION_SKY_LONG_WAVE = "atmo_lberg"
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = "fd_lberg"
        RADIATION_GLOBAL = "fg_lberg"
        SUNSHINE_DURATION = "sd_lberg"
        SUN_ZENITH_ANGLE = "zenit"

        # visibility
        VISIBILITY_INDICATOR = "v_vv_i"  # str
        VISIBILITY = "v_vv"  # int

        # wind
        WIND_SPEED = "f"
        WIND_DIRECTION = "d"  # int

        HUMIDITY_ABSOLUTE = "absf_std"
        PRESSURE_VAPOR = "vp_std"
        TEMPERATURE_WET_MEAN_200 = "tf_std"

    # subdaily
    class SUBDAILY(Enum):  # noqa
        # air_temperature
        TEMPERATURE_AIR_MEAN_200 = "tt_ter"
        HUMIDITY = "rf_ter"

        # cloudiness
        CLOUD_COVER_TOTAL = "n_ter"  # int
        CLOUD_DENSITY = "cd_ter"  # int

        # moisture
        PRESSURE_VAPOR = "vp_ter"
        TEMPERATURE_AIR_MEAN_005 = "e_tf_ter"

        # pressure
        PRESSURE_AIR_SITE = "pp_ter"

        # soil
        TEMPERATURE_SOIL_MEAN_005 = "ek_ter"  # int

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
        PRESSURE_AIR_SITE = "pm"
        TEMPERATURE_AIR_MEAN_200 = "tmk"
        HUMIDITY = "upm"
        TEMPERATURE_AIR_MAX_200 = "txk"
        TEMPERATURE_AIR_MIN_200 = "tnk"
        TEMPERATURE_AIR_MIN_005 = "tgk"

        # more_precip
        SNOW_DEPTH_NEW = "nsh_tag"  # int

        # soil_temperature
        TEMPERATURE_SOIL_MEAN_002 = "v_te002m"
        TEMPERATURE_SOIL_MEAN_005 = "v_te005m"
        TEMPERATURE_SOIL_MEAN_010 = "v_te010m"
        TEMPERATURE_SOIL_MEAN_020 = "v_te020m"
        TEMPERATURE_SOIL_MEAN_050 = "v_te050m"
        TEMPERATURE_SOIL_MEAN_100 = "v_te050m"

        # solar
        RADIATION_SKY_LONG_WAVE = "atmo_strahl"
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = "fd_strahl"
        RADIATION_SKY_SHORT_WAVE_DIRECT = "fg_strahl"

        # water_equiv
        SNOW_DEPTH_EXCELLED = "ash_6"  # int
        WATER_EQUIVALENT_SNOW_DEPTH = "wash_6"
        WATER_EQUIVALENT_SNOW_DEPTH_EXCELLED = "waas_6"

        # weather_phenomena
        COUNT_WEATHER_TYPE_FOG = "nebel"  # int
        COUNT_WEATHER_TYPE_THUNDER = "gewitter"  # int
        COUNT_WEATHER_TYPE_STORM_STRONG_WIND = "sturm_6"  # int
        COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = "sturm_8"  # int
        COUNT_WEATHER_TYPE_DEW = "tau"  # int
        COUNT_WEATHER_TYPE_GLAZE = "glatteis"  # int
        COUNT_WEATHER_TYPE_RIPE = "reif"  # int
        COUNT_WEATHER_TYPE_SLEET = "graupel"  # int
        COUNT_WEATHER_TYPE_HAIL = "hagel"  # int

    # monthly
    class MONTHLY(Enum):
        # kl
        CLOUD_COVER_TOTAL = "mo_n"
        TEMPERATURE_AIR_MEAN_200 = "mo_tt"
        TEMPERATURE_AIR_MAX_200_MEAN = "mo_tx"
        TEMPERATURE_AIR_MIN_200_MEAN = "mo_tn"
        WIND_FORCE_BEAUFORT = "mo_fk"
        TEMPERATURE_AIR_MAX_200 = "mx_tx"
        WIND_GUST_MAX = "mx_fx"
        TEMPERATURE_AIR_MIN_200 = "mx_tn"
        SUNSHINE_DURATION = "mo_sd_s"
        PRECIPITATION_HEIGHT = "mo_rr"
        PRECIPITATION_HEIGHT_MAX = "mx_rs"

        # more_precip
        SNOW_DEPTH_NEW = "mo_nsh"  # int
        SNOW_DEPTH = "mo_sh_s"  # int

        # weather_phenomena
        COUNT_WEATHER_TYPE_STORM_STRONG_WIND = "mo_sturm_6"  # int
        COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = "mo_sturm_8"  # int
        COUNT_WEATHER_TYPE_THUNDER = "mo_gewitter"  # int
        COUNT_WEATHER_TYPE_GLAZE = "mo_glatteis"  # int
        COUNT_WEATHER_TYPE_SLEET = "mo_graupel"  # int
        COUNT_WEATHER_TYPE_HAIL = "mo_hagel"  # int
        COUNT_WEATHER_TYPE_FOG = "mo_nebel"  # int
        COUNT_WEATHER_TYPE_DEW = "mo_tau"  # int

    # annual
    class ANNUAL(Enum):
        # kl
        CLOUD_COVER_TOTAL = "ja_n"
        TEMPERATURE_AIR_MEAN_200 = "ja_tt"
        TEMPERATURE_AIR_MAX_200_MEAN = "ja_tx"
        TEMPERATURE_AIR_MIN_200_MEAN = "ja_tn"
        WIND_FORCE_BEAUFORT = "ja_fk"
        SUNSHINE_DURATION = "ja_sd_s"
        WIND_GUST_MAX = "ja_mx_fx"
        TEMPERATURE_AIR_MAX_200 = "ja_mx_tx"
        TEMPERATURE_AIR_MIN_200 = "ja_mx_tn"
        PRECIPITATION_HEIGHT = "ja_rr"
        PRECIPITATION_HEIGHT_MAX = "ja_mx_rs"

        # more_precip
        SNOW_DEPTH_NEW = "ja_nsh"  # int
        SNOW_DEPTH = "ja_sh_s"  # int

        # weather_phenomena
        COUNT_WEATHER_TYPE_STORM_STRONG_WIND = "ja_sturm_6"  # int
        COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = "ja_sturm_8"  # int
        COUNT_WEATHER_TYPE_THUNDER = "ja_gewitter"  # int
        COUNT_WEATHER_TYPE_GLAZE = "ja_glatteis"  # int
        COUNT_WEATHER_TYPE_SLEET = "ja_graupel"  # int
        COUNT_WEATHER_TYPE_HAIL = "ja_hagel"  # int
        COUNT_WEATHER_TYPE_FOG = "ja_nebel"  # int
        COUNT_WEATHER_TYPE_DEW = "ja_tau"  # int


class DwdObservationDatasetTree(DatasetTreeCore):
    """
    Original data column names from DWD data
    Two anomalies:
    - daily/kl -> QN_3, QN_4
    - monthly/kl -> QN_4, QN_6
    - annual/kl -> QN_4, QN_6
    """

    # 1_minute
    class MINUTE_1(DatasetTreeCore):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn"
            PRECIPITATION_HEIGHT = "rs_01"
            PRECIPITATION_HEIGHT_DROPLET = "rth_01"
            PRECIPITATION_HEIGHT_ROCKER = "rwh_01"
            PRECIPITATION_FORM = "rs_ind_01"  # int

    # 10_minutes
    class MINUTE_10(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn"
            PRESSURE_AIR_SITE = "pp_10"
            TEMPERATURE_AIR_MEAN_200 = "tt_10"
            TEMPERATURE_AIR_MEAN_005 = "tm5_10"
            HUMIDITY = "rf_10"
            TEMPERATURE_DEW_POINT_MEAN_200 = "td_10"

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
            WIND_DIRECTION_GUST_MAX = "dx_10"  # int

        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "qn"
            PRECIPITATION_DURATION = "rws_dau_10"
            PRECIPITATION_HEIGHT = "rws_10"
            PRECIPITATION_INDICATOR_WR = "rws_ind_10"  # int

        # solar
        class SOLAR(Enum):
            QUALITY = "qn"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "ds_10"
            RADIATION_GLOBAL = "gs_10"
            SUNSHINE_DURATION = "sd_10"
            RADIATION_SKY_LONG_WAVE = "ls_10"

        # wind
        class WIND(Enum):
            QUALITY = "qn"
            WIND_SPEED = "ff_10"
            WIND_DIRECTION = "dd_10"

    # hourly
    class HOURLY(DatasetTreeCore):
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn_9"
            TEMPERATURE_AIR_MEAN_200 = "tt_tu"
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
            TEMPERATURE_AIR_MEAN_200 = "tt"
            TEMPERATURE_DEW_POINT_MEAN_200 = "td"

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
            PRESSURE_AIR_SITE = "p0"

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "qn_2"
            TEMPERATURE_SOIL_MEAN_002 = "v_te002"
            TEMPERATURE_SOIL_MEAN_005 = "v_te005"
            TEMPERATURE_SOIL_MEAN_010 = "v_te010"
            TEMPERATURE_SOIL_MEAN_020 = "v_te020"
            TEMPERATURE_SOIL_MEAN_050 = "v_te050"
            TEMPERATURE_SOIL_MEAN_100 = "v_te100"

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
        class SUNSHINE_DURATION(Enum):
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

        class MOISTURE(Enum):
            QUALITY = "qn_4"
            HUMIDITY_ABSOLUTE = "absf_std"
            PRESSURE_VAPOR = "vp_std"
            TEMPERATURE_WET_MEAN_200 = "tf_std"
            PRESSURE_AIR_SITE = "p_std"
            TEMPERATURE_AIR_MEAN_200 = "tt_std"
            HUMIDITY = "rf_std"
            TEMPERATURE_DEW_POINT_MEAN_200 = "td_std"

    # subdaily
    class SUBDAILY(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "qn_4"
            TEMPERATURE_AIR_MEAN_200 = "tt_ter"
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
            TEMPERATURE_SOIL_MEAN_002 = "v_te002m"
            TEMPERATURE_SOIL_MEAN_005 = "v_te005m"
            TEMPERATURE_SOIL_MEAN_010 = "v_te010m"
            TEMPERATURE_SOIL_MEAN_020 = "v_te020m"
            TEMPERATURE_SOIL_MEAN_050 = "v_te050m"
            TEMPERATURE_SOIL_MEAN_100 = "v_te100m"

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
            WATER_EQUIVALENT_SNOW_DEPTH = "wash_6"
            WATER_EQUIVALENT_SNOW_DEPTH_EXCELLED = "waas_6"

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

    # monthly
    class MONTHLY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "qn_4"
            CLOUD_COVER_TOTAL = "mo_n"
            TEMPERATURE_AIR_MEAN_200 = "mo_tt"
            TEMPERATURE_AIR_MAX_200_MEAN = "mo_tx"
            TEMPERATURE_AIR_MIN_200_MEAN = "mo_tn"
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
            COUNT_WEATHER_TYPE_STORM_STRONG_WIND = "mo_sturm_6"  # int
            COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = "mo_sturm_8"  # int
            COUNT_WEATHER_TYPE_THUNDER = "mo_gewitter"  # int
            COUNT_WEATHER_TYPE_GLAZE = "mo_glatteis"  # int
            COUNT_WEATHER_TYPE_SLEET = "mo_graupel"  # int
            COUNT_WEATHER_TYPE_HAIL = "mo_hagel"  # int
            COUNT_WEATHER_TYPE_FOG = "mo_nebel"  # int
            COUNT_WEATHER_TYPE_DEW = "mo_tau"  # int

    # annual
    class ANNUAL(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "qn_4"
            CLOUD_COVER_TOTAL = "ja_n"
            TEMPERATURE_AIR_MEAN_200 = "ja_tt"
            TEMPERATURE_AIR_MAX_200_MEAN = "ja_tx"
            TEMPERATURE_AIR_MIN_200_MEAN = "ja_tn"
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
            COUNT_WEATHER_TYPE_STORM_STRONG_WIND = "ja_sturm_6"  # int
            COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = "ja_sturm_8"  # int
            COUNT_WEATHER_TYPE_THUNDER = "ja_gewitter"  # int
            COUNT_WEATHER_TYPE_GLAZE = "ja_glatteis"  # int
            COUNT_WEATHER_TYPE_SLEET = "ja_graupel"  # int
            COUNT_WEATHER_TYPE_HAIL = "ja_hagel"  # int
            COUNT_WEATHER_TYPE_FOG = "ja_nebel"  # int
            COUNT_WEATHER_TYPE_DEW = "ja_tau"  # int


PARAMETER_TO_DATASET_MAPPING = {
    Resolution.MINUTE_1: {
        # precipitation
        DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT: DwdObservationDataset.PRECIPITATION,
        DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT_DROPLET: DwdObservationDataset.PRECIPITATION,
        DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT_ROCKER: DwdObservationDataset.PRECIPITATION,
        DwdObservationParameter.MINUTE_1.PRECIPITATION_FORM: DwdObservationDataset.PRECIPITATION,
    },
    Resolution.MINUTE_10: {
        # air_temperature
        DwdObservationParameter.MINUTE_10.PRESSURE_AIR_SITE: DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MEAN_200: DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MEAN_005: DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationParameter.MINUTE_10.HUMIDITY: DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_DEW_POINT_MEAN_200: DwdObservationDataset.TEMPERATURE_AIR,
        # extreme_temperature
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MAX_200: DwdObservationDataset.TEMPERATURE_EXTREME,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MAX_005: DwdObservationDataset.TEMPERATURE_EXTREME,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MIN_200: DwdObservationDataset.TEMPERATURE_EXTREME,
        DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR_MIN_005: DwdObservationDataset.TEMPERATURE_EXTREME,
        # extreme_wind
        DwdObservationParameter.MINUTE_10.WIND_GUST_MAX: DwdObservationDataset.WIND_EXTREME,
        DwdObservationParameter.MINUTE_10.WIND_SPEED_MIN: DwdObservationDataset.WIND_EXTREME,
        DwdObservationParameter.MINUTE_10.WIND_SPEED_ROLLING_MEAN_MAX: DwdObservationDataset.WIND_EXTREME,
        DwdObservationParameter.MINUTE_10.WIND_DIRECTION_GUST_MAX: DwdObservationDataset.WIND_EXTREME,
        # precipitation
        DwdObservationParameter.MINUTE_10.PRECIPITATION_DURATION: DwdObservationDataset.PRECIPITATION,
        DwdObservationParameter.MINUTE_10.PRECIPITATION_HEIGHT: DwdObservationDataset.PRECIPITATION,
        DwdObservationParameter.MINUTE_10.PRECIPITATION_INDICATOR_WR: DwdObservationDataset.PRECIPITATION,
        # solar
        DwdObservationParameter.MINUTE_10.RADIATION_SKY_SHORT_WAVE_DIFFUSE: DwdObservationDataset.SOLAR,
        DwdObservationParameter.MINUTE_10.RADIATION_GLOBAL: DwdObservationDataset.SOLAR,
        DwdObservationParameter.MINUTE_10.SUNSHINE_DURATION: DwdObservationDataset.SOLAR,
        DwdObservationParameter.MINUTE_10.RADIATION_SKY_LONG_WAVE: DwdObservationDataset.SOLAR,
        # wind
        DwdObservationParameter.MINUTE_10.WIND_SPEED: DwdObservationDataset.WIND,
        DwdObservationParameter.MINUTE_10.WIND_DIRECTION: DwdObservationDataset.WIND,
    },
    Resolution.HOURLY: {
        # air_temperature
        DwdObservationParameter.HOURLY.TEMPERATURE_AIR_MEAN_200: DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationParameter.HOURLY.HUMIDITY: DwdObservationDataset.TEMPERATURE_AIR,
        # cloudiness
        DwdObservationParameter.HOURLY.CLOUD_COVER_TOTAL: DwdObservationDataset.CLOUDINESS,
        # cloud_type
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER1: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_HEIGHT_LAYER1: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_COVER_LAYER1: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER2: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_HEIGHT_LAYER2: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_COVER_LAYER2: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER3: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_HEIGHT_LAYER3: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_COVER_LAYER3: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_TYPE_LAYER4: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_HEIGHT_LAYER4: DwdObservationDataset.CLOUD_TYPE,
        DwdObservationParameter.HOURLY.CLOUD_COVER_LAYER4: DwdObservationDataset.CLOUD_TYPE,
        # dew_point
        DwdObservationParameter.HOURLY.TEMPERATURE_DEW_POINT_MEAN_200: DwdObservationDataset.DEW_POINT,
        # precipitation
        DwdObservationParameter.HOURLY.PRECIPITATION_HEIGHT: DwdObservationDataset.PRECIPITATION,
        DwdObservationParameter.HOURLY.PRECIPITATION_INDICATOR: DwdObservationDataset.PRECIPITATION,
        DwdObservationParameter.HOURLY.PRECIPITATION_FORM: DwdObservationDataset.PRECIPITATION,
        # pressure
        DwdObservationParameter.HOURLY.PRESSURE_AIR_SEA_LEVEL: DwdObservationDataset.PRESSURE,
        DwdObservationParameter.HOURLY.PRESSURE_AIR_SITE: DwdObservationDataset.PRESSURE,
        # soil_temperature
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_MEAN_002: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_MEAN_005: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_MEAN_010: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_MEAN_020: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_MEAN_050: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.HOURLY.TEMPERATURE_SOIL_MEAN_100: DwdObservationDataset.TEMPERATURE_SOIL,
        # sun
        DwdObservationParameter.HOURLY.SUNSHINE_DURATION: DwdObservationDataset.SUNSHINE_DURATION,
        # solar
        DwdObservationParameter.HOURLY.RADIATION_SKY_LONG_WAVE: DwdObservationDataset.SOLAR,
        DwdObservationParameter.HOURLY.RADIATION_SKY_SHORT_WAVE_DIFFUSE: DwdObservationDataset.SOLAR,
        DwdObservationParameter.HOURLY.RADIATION_GLOBAL: DwdObservationDataset.SOLAR,
        DwdObservationParameter.HOURLY.SUN_ZENITH_ANGLE: DwdObservationDataset.SOLAR,
        # visibility
        DwdObservationParameter.HOURLY.VISIBILITY_INDICATOR: DwdObservationDataset.VISIBILITY,
        DwdObservationParameter.HOURLY.VISIBILITY: DwdObservationDataset.VISIBILITY,
        # wind
        DwdObservationParameter.HOURLY.WIND_SPEED: DwdObservationDataset.WIND,
        DwdObservationParameter.HOURLY.WIND_DIRECTION: DwdObservationDataset.WIND,
        # moisture
        DwdObservationParameter.HOURLY.HUMIDITY_ABSOLUTE: DwdObservationDataset.MOISTURE,
        DwdObservationParameter.HOURLY.PRESSURE_VAPOR: DwdObservationDataset.MOISTURE,
        DwdObservationParameter.HOURLY.TEMPERATURE_WET_MEAN_200: DwdObservationDataset.MOISTURE,
        DwdObservationParameter.HOURLY.PRESSURE_AIR_SITE: DwdObservationDataset.MOISTURE,
    },
    Resolution.SUBDAILY: {
        # air_temperature
        DwdObservationParameter.SUBDAILY.TEMPERATURE_AIR_MEAN_200: DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationParameter.SUBDAILY.HUMIDITY: DwdObservationDataset.TEMPERATURE_AIR,
        # cloudiness
        DwdObservationParameter.SUBDAILY.CLOUD_COVER_TOTAL: DwdObservationDataset.CLOUDINESS,
        DwdObservationParameter.SUBDAILY.CLOUD_DENSITY: DwdObservationDataset.CLOUDINESS,
        # moisture
        DwdObservationParameter.SUBDAILY.PRESSURE_VAPOR: DwdObservationDataset.MOISTURE,
        DwdObservationParameter.SUBDAILY.TEMPERATURE_AIR_MEAN_005: DwdObservationDataset.MOISTURE,
        # pressure
        DwdObservationParameter.SUBDAILY.PRESSURE_AIR_SITE: DwdObservationDataset.PRESSURE,
        # soil
        DwdObservationParameter.SUBDAILY.TEMPERATURE_SOIL_MEAN_005: DwdObservationDataset.SOIL,
        # visibility
        DwdObservationParameter.SUBDAILY.VISIBILITY: DwdObservationDataset.VISIBILITY,
        # wind
        DwdObservationParameter.SUBDAILY.WIND_DIRECTION: DwdObservationDataset.WIND,
        DwdObservationParameter.SUBDAILY.WIND_FORCE_BEAUFORT: DwdObservationDataset.WIND,
    },
    Resolution.DAILY: {
        # more_precip
        DwdObservationParameter.DAILY.SNOW_DEPTH_NEW: DwdObservationDataset.PRECIPITATION_MORE,
        # solar
        DwdObservationParameter.DAILY.RADIATION_SKY_LONG_WAVE: DwdObservationDataset.SOLAR,
        DwdObservationParameter.DAILY.RADIATION_SKY_SHORT_WAVE_DIFFUSE: DwdObservationDataset.SOLAR,
        DwdObservationParameter.DAILY.RADIATION_SKY_SHORT_WAVE_DIRECT: DwdObservationDataset.SOLAR,
        DwdObservationParameter.DAILY.SUNSHINE_DURATION: DwdObservationDataset.SOLAR,
        # kl
        DwdObservationParameter.DAILY.WIND_GUST_MAX: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.WIND_SPEED: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.PRECIPITATION_FORM: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.SNOW_DEPTH: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.CLOUD_COVER_TOTAL: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.PRESSURE_VAPOR: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.PRESSURE_AIR_SITE: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.TEMPERATURE_AIR_MEAN_200: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.HUMIDITY: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.TEMPERATURE_AIR_MAX_200: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.TEMPERATURE_AIR_MIN_200: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.DAILY.TEMPERATURE_AIR_MIN_005: DwdObservationDataset.CLIMATE_SUMMARY,
        # soil_temperature
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_MEAN_002: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_MEAN_005: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_MEAN_010: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_MEAN_020: DwdObservationDataset.TEMPERATURE_SOIL,
        DwdObservationParameter.DAILY.TEMPERATURE_SOIL_MEAN_050: DwdObservationDataset.TEMPERATURE_SOIL,
        # water_equiv
        DwdObservationParameter.DAILY.SNOW_DEPTH_EXCELLED: DwdObservationDataset.WATER_EQUIVALENT,
        DwdObservationParameter.DAILY.WATER_EQUIVALENT_SNOW_DEPTH: DwdObservationDataset.WATER_EQUIVALENT,
        DwdObservationParameter.DAILY.WATER_EQUIVALENT_SNOW_DEPTH_EXCELLED: DwdObservationDataset.WATER_EQUIVALENT,
        # weather_phenomena
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_FOG: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_THUNDER: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_STORM_STRONG_WIND: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_DEW: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_GLAZE: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_RIPE: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_SLEET: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.DAILY.COUNT_WEATHER_TYPE_HAIL: DwdObservationDataset.WEATHER_PHENOMENA,
    },
    Resolution.MONTHLY: {
        # more_precip
        DwdObservationParameter.MONTHLY.SNOW_DEPTH_NEW: DwdObservationDataset.PRECIPITATION_MORE,
        DwdObservationParameter.MONTHLY.PRECIPITATION_HEIGHT: DwdObservationDataset.PRECIPITATION_MORE,
        DwdObservationParameter.MONTHLY.SNOW_DEPTH: DwdObservationDataset.PRECIPITATION_MORE,
        DwdObservationParameter.MONTHLY.PRECIPITATION_HEIGHT_MAX: DwdObservationDataset.PRECIPITATION_MORE,
        # kl
        DwdObservationParameter.MONTHLY.CLOUD_COVER_TOTAL: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MEAN_200: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MAX_200_MEAN: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MIN_200_MEAN: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.MONTHLY.WIND_FORCE_BEAUFORT: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MAX_200: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.MONTHLY.WIND_GUST_MAX: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.MONTHLY.TEMPERATURE_AIR_MIN_200: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.MONTHLY.SUNSHINE_DURATION: DwdObservationDataset.CLIMATE_SUMMARY,
        # weather_phenomena
        DwdObservationParameter.MONTHLY.COUNT_WEATHER_TYPE_STORM_STRONG_WIND: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.MONTHLY.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.MONTHLY.COUNT_WEATHER_TYPE_THUNDER: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.MONTHLY.COUNT_WEATHER_TYPE_GLAZE: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.MONTHLY.COUNT_WEATHER_TYPE_SLEET: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.MONTHLY.COUNT_WEATHER_TYPE_HAIL: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.MONTHLY.COUNT_WEATHER_TYPE_FOG: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.MONTHLY.COUNT_WEATHER_TYPE_DEW: DwdObservationDataset.WEATHER_PHENOMENA,
    },
    Resolution.ANNUAL: {
        # more_precip
        DwdObservationParameter.ANNUAL.SNOW_DEPTH_NEW: DwdObservationDataset.PRECIPITATION_MORE,
        DwdObservationParameter.ANNUAL.PRECIPITATION_HEIGHT: DwdObservationDataset.PRECIPITATION_MORE,
        DwdObservationParameter.ANNUAL.SNOW_DEPTH: DwdObservationDataset.PRECIPITATION_MORE,
        DwdObservationParameter.ANNUAL.PRECIPITATION_HEIGHT_MAX: DwdObservationDataset.PRECIPITATION_MORE,
        # kl
        DwdObservationParameter.ANNUAL.CLOUD_COVER_TOTAL: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MEAN_200: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MAX_200_MEAN: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MIN_200_MEAN: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.ANNUAL.WIND_FORCE_BEAUFORT: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.ANNUAL.SUNSHINE_DURATION: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.ANNUAL.WIND_GUST_MAX: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MAX_200: DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationParameter.ANNUAL.TEMPERATURE_AIR_MIN_200: DwdObservationDataset.CLIMATE_SUMMARY,
        # weather_phenomena
        DwdObservationParameter.ANNUAL.COUNT_WEATHER_TYPE_STORM_STRONG_WIND: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.ANNUAL.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.ANNUAL.COUNT_WEATHER_TYPE_THUNDER: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.ANNUAL.COUNT_WEATHER_TYPE_GLAZE: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.ANNUAL.COUNT_WEATHER_TYPE_SLEET: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.ANNUAL.COUNT_WEATHER_TYPE_HAIL: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.ANNUAL.COUNT_WEATHER_TYPE_FOG: DwdObservationDataset.WEATHER_PHENOMENA,
        DwdObservationParameter.ANNUAL.COUNT_WEATHER_TYPE_DEW: DwdObservationDataset.WEATHER_PHENOMENA,
    },
}
