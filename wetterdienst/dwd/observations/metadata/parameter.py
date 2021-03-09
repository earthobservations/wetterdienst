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
        PRECIPITATION_HEIGHT = "RS_01"
        PRECIPITATION_HEIGHT_DROPLET = "RTH_01"
        PRECIPITATION_HEIGHT_ROCKER = "RWH_01"
        PRECIPITATION_FORM = "RS_IND_01"  # int

    # 10_minutes
    class MINUTE_10(Enum):  # noqa
        # air_temperature
        PRESSURE_AIR_STATION_HEIGHT = "PP_10"
        TEMPERATURE_AIR_200 = "TT_10"
        TEMPERATURE_AIR_005 = "TM5_10"
        HUMIDITY = "RF_10"
        TEMPERATURE_DEW_POINT_200 = "TD_10"

        # extreme_temperature
        TEMPERATURE_AIR_MAX_200 = "TX_10"
        TEMPERATURE_AIR_MAX_005 = "TX5_10"
        TEMPERATURE_AIR_MIN_200 = "TN_10"
        TEMPERATURE_AIR_MIN_005 = "TN5_10"

        # extreme_wind
        WIND_GUST_MAX = "FX_10"
        WIND_SPEED_MIN = "FNX_10"
        WIND_SPEED_ROLLING_MEAN_MAX = "FMX_10"
        WIND_DIRECTION_MAX_VELOCITY = "DX_10"  # int

        # precipitation
        PRECIPITATION_DURATION = "RWS_DAU_10"
        PRECIPITATION_HEIGHT = "RWS_10"
        PRECIPITATION_INDICATOR_WR = "RWS_IND_10"  # int

        # solar
        RADIATION_SKY_DIFFUSE = "DS_10"
        RADIATION_GLOBAL = "GS_10"
        SUNSHINE_DURATION = "SD_10"
        RADIATION_SKY_LONG_WAVE = "LS_10"

        # wind
        WIND_SPEED = "FF_10"
        WIND_DIRECTION = "DD_10"

    # hourly
    class HOURLY(Enum):
        # air_temperature
        TEMPERATURE_AIR_200 = "TT_TU"
        HUMIDITY = "RF_TU"

        # cloud_type
        CLOUD_COVER_TOTAL = "V_N"  # int
        CLOUD_COVER_TOTAL_INDICATOR = "V_N_I"  # str
        CLOUD_TYPE_LAYER1 = "V_S1_CS"  # int
        CLOUD_TYPE_LAYER1_ABBREVIATION = "V_S1_CSA"  # str
        CLOUD_HEIGHT_LAYER1 = "V_S1_HHS"
        CLOUD_COVER_LAYER1 = "V_S1_NS"  # int
        CLOUD_TYPE_LAYER2 = "V_S2_CS"  # int
        CLOUD_TYPE_LAYER2_ABBREVIATION = "V_S2_CSA"  # str
        CLOUD_HEIGHT_LAYER2 = "V_S2_HHS"
        CLOUD_COVER_LAYER2 = "V_S2_NS"  # int
        CLOUD_TYPE_LAYER3 = "V_S3_CS"  # int
        CLOUD_TYPE_LAYER3_ABBREVIATION = "V_S3_CSA"  # str
        CLOUD_HEIGHT_LAYER3 = "V_S3_HHS"
        CLOUD_COVER_LAYER3 = "V_S3_NS"  # int
        CLOUD_TYPE_LAYER4 = "V_S4_CS"  # int
        CLOUD_TYPE_LAYER4_ABBREVIATION = "V_S4_CSA"  # str
        CLOUD_HEIGHT_LAYER4 = "V_S4_HHS"
        CLOUD_COVER_LAYER4 = "V_S4_NS"  # int

        # cloudiness
        # CLOUD_COVER_TOTAL_INDICATOR = "V_N_I"  # str
        # CLOUD_COVER_TOTAL = "V_N"  # int

        # dew_point
        # TEMPERATURE_AIR_200 = "TT"
        TEMPERATURE_DEW_POINT_200 = "TD"

        # precipitation
        PRECIPITATION_HEIGHT = "R1"
        PRECIPITATION_INDICATOR = "RS_IND"  # int
        PRECIPITATION_FORM = "WRTR"  # int

        # pressure
        PRESSURE_AIR_SEA_LEVEL = "P"
        PRESSURE_AIR_STATION_HEIGHT = "P0"

        # soil_temperature
        TEMPERATURE_SOIL_002 = "V_TE002"
        TEMPERATURE_SOIL_005 = "V_TE005"
        TEMPERATURE_SOIL_010 = "V_TE010"
        TEMPERATURE_SOIL_020 = "V_TE020"
        TEMPERATURE_SOIL_050 = "V_TE050"
        TEMPERATURE_SOIL_100 = "V_TE100"

        # solar
        END_OF_INTERVAL = "END_OF_INTERVAL"  # modified, does not exist in original
        RADIATION_SKY_LONG_WAVE = "ATMO_LBERG"
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = "FD_LBERG"
        RADIATION_GLOBAL = "FG_LBERG"
        SUNSHINE_DURATION = "SD_LBERG"
        SUN_ZENITH = "ZENIT"
        TRUE_LOCAL_TIME = "TRUE_LOCAL_TIME"  # original name was adjusted to this one

        # sun
        # SUNSHINE_DURATION = "SD_SO"

        # visibility
        VISIBILITY_INDICATOR = "V_VV_I"  # str
        VISIBILITY = "V_VV"  # int

        # wind
        WIND_SPEED = "F"
        WIND_DIRECTION = "D"  # int

        # wind_synop
        # WIND_SPEED = "FF"
        # WIND_DIRECTION = "DD"  # int

    # subdaily
    class SUBDAILY(Enum):  # noqa
        # air_temperature
        TEMPERATURE_AIR_200 = "TT_TER"
        HUMIDITY = "RF_TER"

        # cloudiness
        CLOUD_COVER_TOTAL = "N_TER"  # int
        CLOUD_DENSITY = "CD_TER"  # int

        # moisture
        PRESSURE_VAPOR = "VP_TER"
        TEMPERATURE_AIR_005 = "E_TF_TER"
        # TEMPERATURE_AIR_200 = "TF_TER"
        # HUMIDITY = "RF_TER"

        # pressure
        PRESSURE_AIR = "PP_TER"

        # soil
        TEMPERATURE_SOIL_005 = "EK_TER"  # int

        # visibility
        VISIBILITY = "VK_TER"  # int

        # wind
        WIND_DIRECTION = "DK_TER"  # int
        WIND_FORCE_BEAUFORT = "FK_TER"  # int

    # Daily
    class DAILY(Enum):
        # kl
        WIND_GUST_MAX = "FX"
        WIND_SPEED = "FM"
        PRECIPITATION_HEIGHT = "RSK"
        PRECIPITATION_FORM = "RSKF"
        SUNSHINE_DURATION = "SDK"
        SNOW_DEPTH = "SHK_TAG"
        CLOUD_COVER_TOTAL = "NM"
        PRESSURE_VAPOR = "VPM"
        PRESSURE_AIR = "PM"
        TEMPERATURE_AIR_200 = "TMK"
        HUMIDITY = "UPM"
        TEMPERATURE_AIR_MAX_200 = "TXK"
        TEMPERATURE_AIR_MIN_200 = "TNK"
        TEMPERATURE_AIR_MIN_005 = "TGK"

        # more_precip
        # PRECIPITATION_HEIGHT = "RS"
        # PRECIPITATION_FORM = "RSF"  # int
        # SNOW_DEPTH = "SH_TAG"  # int
        SNOW_DEPTH_NEW = "NSH_TAG"  # int

        # soil_temperature
        TEMPERATURE_SOIL_002 = "V_TE002M"
        TEMPERATURE_SOIL_005 = "V_TE005M"
        TEMPERATURE_SOIL_010 = "V_TE010M"
        TEMPERATURE_SOIL_020 = "V_TE020M"
        TEMPERATURE_SOIL_050 = "V_TE050M"

        # solar
        RADIATION_SKY_LONG_WAVE = "ATMO_STRAHL"
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = "FD_STRAHL"
        RADIATION_SKY_SHORT_WAVE_DIRECT = "FG_STRAHL"
        # SUNSHINE_DURATION = "SD_STRAHL"

        # water_equiv
        SNOW_DEPTH_EXCELLED = "ASH_6"  # int
        # SNOW_DEPTH = "SH_TAG"  # int
        WATER_EQUIVALENT_TOTAL_SNOW_DEPTH = "WASH_6"
        WATER_EQUIVALENT_SNOW = "WAAS_6"

        # weather_phenomena
        FOG = "NEBEL"  # int
        THUNDER = "GEWITTER"  # int
        STORM_STRONG_WIND = "STURM_6"  # int
        STORM_STORMIER_WIND = "STURM_8"  # int
        DEW = "TAU"  # int
        GLAZE = "GLATTEIS"  # int
        RIPE = "REIF"  # int
        SLEET = "GRAUPEL"  # int
        HAIL = "HAGEL"  # int

    # monthly
    class MONTHLY(Enum):
        # kl
        CLOUD_COVER_TOTAL = "MO_N"
        TEMPERATURE_AIR_200 = "MO_TT"
        TEMPERATURE_AIR_MAX_MEAN_200 = "MO_TX"
        TEMPERATURE_AIR_MIN_MEAN_200 = "MO_TN"
        WIND_FORCE_BEAUFORT = "MO_FK"
        TEMPERATURE_AIR_MAX_200 = "MX_TX"
        WIND_GUST_MAX = "MX_FX"
        TEMPERATURE_AIR_MIN_200 = "MX_TN"
        SUNSHINE_DURATION = "MO_SD_S"
        PRECIPITATION_HEIGHT = "MO_RR"
        PRECIPITATION_HEIGHT_MAX = "MX_RS"

        # more_precip
        SNOW_DEPTH_NEW = "MO_NSH"  # int
        # PRECIPITATION_HEIGHT = "MO_RR"
        SNOW_DEPTH = "MO_SH_S"  # int
        # PRECIPITATION_HEIGHT_MAX = "MX_RS"

        # weather_phenomena
        STORM_STRONG_WIND = "MO_STURM_6"  # int
        STORM_STORMIER_WIND = "MO_STURM_8"  # int
        THUNDER = "MO_GEWITTER"  # int
        GLAZE = "MO_GLATTEIS"  # int
        SLEET = "MO_GRAUPEL"  # int
        HAIL = "MO_HAGEL"  # int
        FOG = "MO_NEBEL"  # int
        DEW = "MO_TAU"  # int

    # annual
    class ANNUAL(Enum):
        # kl
        CLOUD_COVER_TOTAL = "JA_N"
        TEMPERATURE_AIR_200 = "JA_TT"
        TEMPERATURE_AIR_MAX_MEAN_200 = "JA_TX"
        TEMPERATURE_AIR_MIN_MEAN_200 = "JA_TN"
        WIND_FORCE_BEAUFORT = "JA_FK"
        SUNSHINE_DURATION = "JA_SD_S"
        WIND_GUST_MAX = "JA_MX_FX"
        TEMPERATURE_AIR_MAX_200 = "JA_MX_TX"
        TEMPERATURE_AIR_MIN_200 = "JA_MX_TN"
        PRECIPITATION_HEIGHT = "JA_RR"
        PRECIPITATION_HEIGHT_MAX = "JA_MX_RS"

        # more_precip
        SNOW_DEPTH_NEW = "JA_NSH"  # int
        # PRECIPITATION_HEIGHT = "JA_RR"
        SNOW_DEPTH = "JA_SH_S"  # int
        # PRECIPITATION_HEIGHT_MAX = "JA_MX_RS"

        # weather_phenomena
        STORM_STRONG_WIND = "JA_STURM_6"  # int
        STORM_STORMIER_WIND = "JA_STURM_8"  # int
        THUNDER = "JA_GEWITTER"  # int
        GLAZE = "JA_GLATTEIS"  # int
        SLEET = "JA_GRAUPEL"  # int
        HAIL = "JA_HAGEL"  # int
        FOG = "JA_NEBEL"  # int
        DEW = "JA_TAU"  # int


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
            QUALITY = "QN"
            PRECIPITATION_HEIGHT = "RS_01"
            PRECIPITATION_HEIGHT_DROPLET = "RTH_01"
            PRECIPITATION_HEIGHT_ROCKER = "RWH_01"
            PRECIPITATION_FORM = "RS_IND_01"  # int

    # 10_minutes
    class MINUTE_10(WDParameterStructureBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "QN"
            PRESSURE_AIR_STATION_HEIGHT = "PP_10"
            TEMPERATURE_AIR_200 = "TT_10"
            TEMPERATURE_AIR_005 = "TM5_10"
            HUMIDITY = "RF_10"
            TEMPERATURE_DEW_POINT_200 = "TD_10"

        # extreme_temperature
        class TEMPERATURE_EXTREME(Enum):  # noqa
            QUALITY = "QN"
            TEMPERATURE_AIR_MAX_200 = "TX_10"
            TEMPERATURE_AIR_MAX_005 = "TX5_10"
            TEMPERATURE_AIR_MIN_200 = "TN_10"
            TEMPERATURE_AIR_MIN_005 = "TN5_10"

        # extreme_wind
        class WIND_EXTREME(Enum):  # noqa
            QUALITY = "QN"
            WIND_GUST_MAX = "FX_10"
            WIND_SPEED_MIN = "FNX_10"
            WIND_SPEED_ROLLING_MEAN_MAX = "FMX_10"
            WIND_DIRECTION_MAX_VELOCITY = "DX_10"  # int

        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "QN"
            PRECIPITATION_DURATION = "RWS_DAU_10"
            PRECIPITATION_HEIGHT = "RWS_10"
            PRECIPITATION_INDICATOR_WR = "RWS_IND_10"  # int

        # solar
        class SOLAR(Enum):
            QUALITY = "QN"
            RADIATION_SKY_DIFFUSE = "DS_10"
            RADIATION_GLOBAL = "GS_10"
            SUNSHINE_DURATION = "SD_10"
            RADIATION_SKY_LONG_WAVE = "LS_10"

        # wind
        class WIND(Enum):
            QUALITY = "QN"
            WIND_SPEED = "FF_10"
            WIND_DIRECTION = "DD_10"

    # hourly
    class HOURLY(WDParameterStructureBase):
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "QN_9"
            TEMPERATURE_AIR_200 = "TT_TU"
            HUMIDITY = "RF_TU"

        # cloud_type
        class CLOUD_TYPE(Enum):  # noqa
            QUALITY = "QN_8"
            CLOUD_COVER_TOTAL = "V_N"  # int
            CLOUD_COVER_TOTAL_INDICATOR = "V_N_I"  # str
            CLOUD_TYPE_LAYER1 = "V_S1_CS"  # int
            CLOUD_TYPE_LAYER1_ABBREVIATION = "V_S1_CSA"  # str
            CLOUD_HEIGHT_LAYER1 = "V_S1_HHS"
            CLOUD_COVER_LAYER1 = "V_S1_NS"  # int
            CLOUD_TYPE_LAYER2 = "V_S2_CS"  # int
            CLOUD_TYPE_LAYER2_ABBREVIATION = "V_S2_CSA"  # str
            CLOUD_HEIGHT_LAYER2 = "V_S2_HHS"
            CLOUD_COVER_LAYER2 = "V_S2_NS"  # int
            CLOUD_TYPE_LAYER3 = "V_S3_CS"  # int
            CLOUD_TYPE_LAYER3_ABBREVIATION = "V_S3_CSA"  # str
            CLOUD_HEIGHT_LAYER3 = "V_S3_HHS"
            CLOUD_COVER_LAYER3 = "V_S3_NS"  # int
            CLOUD_TYPE_LAYER4 = "V_S4_CS"  # int
            CLOUD_TYPE_LAYER4_ABBREVIATION = "V_S4_CSA"  # str
            CLOUD_HEIGHT_LAYER4 = "V_S4_HHS"
            CLOUD_COVER_LAYER4 = "V_S4_NS"  # int

        # cloudiness
        class CLOUDINESS(Enum):
            QUALITY = "QN_8"
            CLOUD_COVER_TOTAL_INDICATOR = "V_N_I"  # str
            CLOUD_COVER_TOTAL = "V_N"  # int

        # dew_point
        class DEW_POINT(Enum):  # noqa
            QUALITY = "QN_8"
            TEMPERATURE_AIR_200 = "TT"
            TEMPERATURE_DEW_POINT_200 = "TD"

        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "QN_8"
            PRECIPITATION_HEIGHT = "R1"
            PRECIPITATION_INDICATOR = "RS_IND"  # int
            PRECIPITATION_FORM = "WRTR"  # int

        # pressure
        class PRESSURE(Enum):
            QUALITY = "QN_8"
            PRESSURE_AIR_SEA_LEVEL = "P"
            PRESSURE_AIR_STATION_HEIGHT = "P0"

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "QN_2"
            TEMPERATURE_SOIL_002 = "V_TE002"
            TEMPERATURE_SOIL_005 = "V_TE005"
            TEMPERATURE_SOIL_010 = "V_TE010"
            TEMPERATURE_SOIL_020 = "V_TE020"
            TEMPERATURE_SOIL_050 = "V_TE050"
            TEMPERATURE_SOIL_100 = "V_TE100"

        # solar
        class SOLAR(Enum):
            QUALITY = "QN_592"
            END_OF_INTERVAL = "END_OF_INTERVAL"  # modified, does not exist in original
            RADIATION_SKY_LONG_WAVE = "ATMO_LBERG"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "FD_LBERG"
            RADIATION_GLOBAL = "FG_LBERG"
            SUNSHINE_DURATION = "SD_LBERG"
            SUN_ZENITH = "ZENIT"
            TRUE_LOCAL_TIME = (
                "TRUE_LOCAL_TIME"  # original name was adjusted to this one
            )

        # sun
        class SUN(Enum):
            QUALITY = "QN_7"
            SUNSHINE_DURATION = "SD_SO"

        # visibility
        class VISIBILITY(Enum):
            QUALITY = "QN_8"
            VISIBILITY_INDICATOR = "V_VV_I"  # str
            VISIBILITY = "V_VV"  # int

        # wind
        class WIND(Enum):
            QUALITY = "QN_3"
            WIND_SPEED = "F"
            WIND_DIRECTION = "D"  # int

        # wind_synop
        class WIND_SYNOPTIC(Enum):  # noqa
            QUALITY = "QN_8"
            WIND_SPEED = "FF"
            WIND_DIRECTION = "DD"  # int

    # subdaily
    class SUBDAILY(WDParameterStructureBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "QN_4"
            TEMPERATURE_AIR_200 = "TT_TER"
            HUMIDITY = "RF_TER"

        # cloudiness
        class CLOUDINESS(Enum):
            QUALITY = "QN_4"
            CLOUD_COVER_TOTAL = "N_TER"  # int
            CLOUD_DENSITY = "CD_TER"  # int

        # moisture
        class MOISTURE(Enum):
            QUALITY = "QN_4"
            PRESSURE_VAPOR = "VP_TER"
            TEMPERATURE_AIR_005 = "E_TF_TER"
            TEMPERATURE_AIR_200 = "TF_TER"
            HUMIDITY = "RF_TER"

        # pressure
        class PRESSURE(Enum):
            QUALITY = "QN_4"
            PRESSURE_AIR = "PP_TER"

        # soil
        class SOIL(Enum):
            QUALITY = "QN_4"
            TEMPERATURE_SOIL_005 = "EK_TER"  # int

        # visibility
        class VISIBILITY(Enum):
            QUALITY = "QN_4"
            VISIBILITY = "VK_TER"  # int

        # wind
        class WIND(Enum):
            QUALITY = "QN_4"
            WIND_DIRECTION = "DK_TER"  # int
            WIND_FORCE_BEAUFORT = "FK_TER"  # int

    # Daily
    class DAILY(WDParameterStructureBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_WIND = "QN_3"
            WIND_GUST_MAX = "FX"
            WIND_SPEED = "FM"
            QUALITY_GENERAL = "QN_4"  # special case here with two quality columns!
            PRECIPITATION_HEIGHT = "RSK"
            PRECIPITATION_FORM = "RSKF"
            SUNSHINE_DURATION = "SDK"
            SNOW_DEPTH = "SHK_TAG"
            CLOUD_COVER_TOTAL = "NM"
            PRESSURE_VAPOR = "VPM"
            PRESSURE_AIR = "PM"
            TEMPERATURE_AIR_200 = "TMK"
            HUMIDITY = "UPM"
            TEMPERATURE_AIR_MAX_200 = "TXK"
            TEMPERATURE_AIR_MIN_200 = "TNK"
            TEMPERATURE_AIR_MIN_005 = "TGK"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "QN_6"
            PRECIPITATION_HEIGHT = "RS"
            PRECIPITATION_FORM = "RSF"  # int
            SNOW_DEPTH = "SH_TAG"  # int
            SNOW_DEPTH_NEW = "NSH_TAG"  # int

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "QN_2"
            TEMPERATURE_SOIL_002 = "V_TE002M"
            TEMPERATURE_SOIL_005 = "V_TE005M"
            TEMPERATURE_SOIL_010 = "V_TE010M"
            TEMPERATURE_SOIL_020 = "V_TE020M"
            TEMPERATURE_SOIL_050 = "V_TE050M"

        # solar
        class SOLAR(Enum):
            QUALITY = "QN_592"
            RADIATION_SKY_LONG_WAVE = "ATMO_STRAHL"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "FD_STRAHL"
            RADIATION_SKY_SHORT_WAVE_DIRECT = "FG_STRAHL"
            SUNSHINE_DURATION = "SD_STRAHL"

        # water_equiv
        class WATER_EQUIVALENT(Enum):  # noqa
            QN_6 = "QN_6"
            SNOW_DEPTH_EXCELLED = "ASH_6"  # int
            SNOW_DEPTH = "SH_TAG"  # int
            WATER_EQUIVALENT_TOTAL_SNOW_DEPTH = "WASH_6"
            WATER_EQUIVALENT_SNOW = "WAAS_6"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "QN_4"
            FOG = "NEBEL"  # int
            THUNDER = "GEWITTER"  # int
            STORM_STRONG_WIND = "STURM_6"  # int
            STORM_STORMIER_WIND = "STURM_8"  # int
            DEW = "TAU"  # int
            GLAZE = "GLATTEIS"  # int
            RIPE = "REIF"  # int
            SLEET = "GRAUPEL"  # int
            HAIL = "HAGEL"  # int

    # monthly
    class MONTHLY(WDParameterStructureBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "QN_4"
            CLOUD_COVER_TOTAL = "MO_N"
            TEMPERATURE_AIR_200 = "MO_TT"
            TEMPERATURE_AIR_MAX_MEAN_200 = "MO_TX"
            TEMPERATURE_AIR_MIN_MEAN_200 = "MO_TN"
            WIND_FORCE_BEAUFORT = "MO_FK"
            TEMPERATURE_AIR_MAX_200 = "MX_TX"
            WIND_GUST_MAX = "MX_FX"
            TEMPERATURE_AIR_MIN_200 = "MX_TN"
            SUNSHINE_DURATION = "MO_SD_S"
            QUALITY_PRECIPITATION = "QN_6"
            PRECIPITATION_HEIGHT = "MO_RR"
            PRECIPITATION_HEIGHT_MAX = "MX_RS"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "QN_6"
            SNOW_DEPTH_NEW = "MO_NSH"  # int
            PRECIPITATION_HEIGHT = "MO_RR"
            SNOW_DEPTH = "MO_SH_S"  # int
            PRECIPITATION_HEIGHT_MAX = "MX_RS"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "QN_4"
            STORM_STRONG_WIND = "MO_STURM_6"  # int
            STORM_STORMIER_WIND = "MO_STURM_8"  # int
            THUNDER = "MO_GEWITTER"  # int
            GLAZE = "MO_GLATTEIS"  # int
            SLEET = "MO_GRAUPEL"  # int
            HAIL = "MO_HAGEL"  # int
            FOG = "MO_NEBEL"  # int
            DEW = "MO_TAU"  # int

    # annual
    class ANNUAL(WDParameterStructureBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "QN_4"
            CLOUD_COVER_TOTAL = "JA_N"
            TEMPERATURE_AIR_200 = "JA_TT"
            TEMPERATURE_AIR_MAX_MEAN_200 = "JA_TX"
            TEMPERATURE_AIR_MIN_MEAN_200 = "JA_TN"
            WIND_FORCE_BEAUFORT = "JA_FK"
            SUNSHINE_DURATION = "JA_SD_S"
            WIND_GUST_MAX = "JA_MX_FX"
            TEMPERATURE_AIR_MAX_200 = "JA_MX_TX"
            TEMPERATURE_AIR_MIN_200 = "JA_MX_TN"
            QUALITY_PRECIPITATION = "QN_6"
            PRECIPITATION_HEIGHT = "JA_RR"
            PRECIPITATION_HEIGHT_MAX = "JA_MX_RS"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "QN_6"
            SNOW_DEPTH_NEW = "JA_NSH"  # int
            PRECIPITATION_HEIGHT = "JA_RR"
            SNOW_DEPTH = "JA_SH_S"  # int
            PRECIPITATION_HEIGHT_MAX = "JA_MX_RS"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "QN_4"
            STORM_STRONG_WIND = "JA_STURM_6"  # int
            STORM_STORMIER_WIND = "JA_STURM_8"  # int
            THUNDER = "JA_GEWITTER"  # int
            GLAZE = "JA_GLATTEIS"  # int
            SLEET = "JA_GRAUPEL"  # int
            HAIL = "JA_HAGEL"  # int
            FOG = "JA_NEBEL"  # int
            DEW = "JA_TAU"  # int


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
        # TEMPERATURE_AIR_200: "TT"
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
        # DwdObservationParameter.HOURLY.WIND_SPEED: "FF"
        # DwdObservationParameter.HOURLY.WIND_DIRECTION: "DD"  # int
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
        # TEMPERATURE_AIR_200: "TF_TER"
        # HUMIDITY: "RF_TER"
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
        # DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT: "RSK",
        # DwdObservationParameter.DAILY.PRECIPITATION_FORM: "RSKF",
        # DwdObservationParameter.DAILY.SUNSHINE_DURATION: DwdObservationParameterSet.CLIMATE_SUMMARY,
        # DwdObservationParameter.DAILY.SNOW_DEPTH: "SHK_TAG",
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
        # SNOW_DEPTH: "SH_TAG"  # int
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
        # DwdObservationParameter.ANNUAL.PRECIPITATION_HEIGHT: "JA_RR",
        # DwdObservationParameter.ANNUAL.PRECIPITATION_HEIGHT_MAX: "JA_MX_RS",
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
