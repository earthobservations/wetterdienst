from enum import Enum

from wetterdienst.util.column_names import WDDataColumnBase


class DWDObservationsOrigDataColumns(WDDataColumnBase):
    """
    Original data column names from DWD data
    Two anomalies:
    - daily/kl -> QN_3, QN_4
    - monthly/kl -> QN_4, QN_6
    - annual/kl -> QN_4, QN_6
    """

    # 1_minute
    class MINUTE_1(WDDataColumnBase):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "QN"
            PRECIPITATION_HEIGHT = "RS_01"
            PRECIPITATION_HEIGHT_DROPLET = "RTH_01"
            PRECIPITATION_HEIGHT_ROCKER = "RWH_01"
            PRECIPITATION_FORM = "RS_IND_01"  # int

    # 10_minutes
    class MINUTE_10(WDDataColumnBase):  # noqa
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
    class HOURLY(WDDataColumnBase):
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
    class SUBDAILY(WDDataColumnBase):  # noqa
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
    class DAILY(WDDataColumnBase):
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
    class MONTHLY(WDDataColumnBase):
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
    class ANNUAL(WDDataColumnBase):
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


class DWDObservationsDataColumns(WDDataColumnBase):
    """
    Original data column names from DWD data

    Two anomalies:
    - daily/kl -> QN_3, QN_4
    - monthly/kl -> QN_4, QN_6
    - annual/kl -> QN_4, QN_6
    """

    # 1_minute
    class MINUTE_1(WDDataColumnBase):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "QUALITY"
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            PRECIPITATION_HEIGHT_DROPLET = "PRECIPITATION_HEIGHT_DROPLET"
            PRECIPITATION_HEIGHT_ROCKER = "PRECIPITATION_HEIGHT_ROCKER"
            PRECIPITATION_FORM = "PRECIPITATION_FORM"  # int

    # 10_minutes
    class MINUTE_10(WDDataColumnBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "QUALITY"
            PRESSURE_AIR_STATION_HEIGHT = "PRESSURE_AIR_STATION_HEIGHT"
            TEMPERATURE_AIR_200 = "TEMPERATURE_AIR_200"
            TEMPERATURE_AIR_005 = "TEMPERATURE_AIR_005"
            HUMIDITY = "HUMIDITY"
            TEMPERATURE_DEW_POINT_200 = "TEMPERATURE_DEW_POINT_200"

        # extreme_temperature
        class TEMPERATURE_EXTREME(Enum):  # noqa
            QUALITY = "QUALITY"
            TEMPERATURE_AIR_MAX_200 = "TEMPERATURE_AIR_MAX_200"
            TEMPERATURE_AIR_MAX_005 = "TEMPERATURE_AIR_MAX_005"
            TEMPERATURE_AIR_MIN_200 = "TEMPERATURE_AIR_MIN_200"
            TEMPERATURE_AIR_MIN_005 = "TEMPERATURE_AIR_MIN_005"

        # extreme_wind
        class WIND_EXTREME(Enum):  # noqa
            QUALITY = "QUALITY"
            WIND_GUST_MAX = "WIND_GUST_MAX"
            WIND_SPEED_MIN = "WIND_SPEED_MIN"
            WIND_SPEED_ROLLING_MEAN_MAX = "WIND_SPEED_ROLLING_MEAN_MAX"
            WIND_DIRECTION_MAX_VELOCITY = "WIND_DIRECTION_MAX_VELOCITY"  # int

        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "QUALITY"
            PRECIPITATION_DURATION = "PRECIPITATION_DURATION"
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            PRECIPITATION_INDICATOR_WR = "PRECIPITATION_INDICATOR_WR"  # int

        # solar
        class SOLAR(Enum):
            QUALITY = "QUALITY"
            RADIATION_SKY_DIFFUSE = "RADIATION_SKY_DIFFUSE"
            RADIATION_GLOBAL = "RADIATION_GLOBAL"
            SUNSHINE_DURATION = "SUNSHINE_DURATION"
            RADIATION_SKY_LONG_WAVE = "RADIATION_SKY_LONG_WAVE"

        # wind
        class WIND(Enum):
            QUALITY = "QUALITY"
            WIND_SPEED = "WIND_SPEED"
            WIND_DIRECTION = "WIND_DIRECTION"

    # hourly
    class HOURLY(WDDataColumnBase):
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "QUALITY"
            TEMPERATURE_AIR_200 = "TEMPERATURE_AIR_200"
            HUMIDITY = "HUMIDITY"

        # cloud_type
        class CLOUD_TYPE(Enum):  # noqa
            QUALITY = "QUALITY"
            CLOUD_COVER_TOTAL = "CLOUD_COVER_TOTAL"  # int
            CLOUD_COVER_TOTAL_INDICATOR = "CLOUD_COVER_TOTAL_INDICATOR"  # str
            CLOUD_TYPE_LAYER1 = "CLOUD_TYPE_LAYER1"  # int
            CLOUD_TYPE_LAYER1_ABBREVIATION = "CLOUD_TYPE_LAYER1_ABBREVIATION"  # str
            CLOUD_HEIGHT_LAYER1 = "CLOUD_HEIGHT_LAYER1"
            CLOUD_COVER_LAYER1 = "CLOUD_COVER_LAYER1"  # int
            CLOUD_TYPE_LAYER2 = "CLOUD_TYPE_LAYER2"  # int
            CLOUD_TYPE_LAYER2_ABBREVIATION = "CLOUD_TYPE_LAYER2_ABBREVIATION"  # str
            CLOUD_HEIGHT_LAYER2 = "CLOUD_HEIGHT_LAYER2"
            CLOUD_COVER_LAYER2 = "CLOUD_COVER_LAYER2"  # int
            CLOUD_TYPE_LAYER3 = "CLOUD_TYPE_LAYER3"  # int
            CLOUD_TYPE_LAYER3_ABBREVIATION = "CLOUD_TYPE_LAYER3_ABBREVIATION"  # str
            CLOUD_HEIGHT_LAYER3 = "CLOUD_HEIGHT_LAYER3"
            CLOUD_COVER_LAYER3 = "CLOUD_COVER_LAYER3"  # int
            CLOUD_TYPE_LAYER4 = "CLOUD_TYPE_LAYER4"  # int
            CLOUD_TYPE_LAYER4_ABBREVIATION = "CLOUD_TYPE_LAYER4_ABBREVIATION"  # str
            CLOUD_HEIGHT_LAYER4 = "CLOUD_HEIGHT_LAYER4"
            CLOUD_COVER_LAYER4 = "CLOUD_COVER_LAYER4"  # int

        # cloudiness
        class CLOUDINESS(Enum):
            QUALITY = "QUALITY"
            CLOUD_COVER_TOTAL_INDICATOR = "CLOUD_COVER_TOTAL_INDICATOR"  # str
            CLOUD_COVER_TOTAL = "CLOUD_COVER_TOTAL"  # int

        # dew_point
        class DEW_POINT(Enum):  # noqa
            QUALITY = "QUALITY"
            TEMPERATURE_AIR_200 = "TEMPERATURE_AIR_200"
            TEMPERATURE_DEW_POINT_200 = "TEMPERATURE_DEW_POINT_200"

        # precipitation
        class PRECIPITATION(Enum):
            QUALITY = "QUALITY"
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            PRECIPITATION_INDICATOR = "PRECIPITATION_INDICATOR"  # int
            PRECIPITATION_FORM = "PRECIPITATION_FORM"  # int

        # pressure
        class PRESSURE(Enum):
            QUALITY = "QUALITY"
            PRESSURE_AIR_SEA_LEVEL = "PRESSURE_AIR_SEA_LEVEL"
            PRESSURE_AIR_STATION_HEIGHT = "PRESSURE_AIR_STATION_HEIGHT"

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "QUALITY"
            TEMPERATURE_SOIL_002 = "TEMPERATURE_SOIL_002"
            TEMPERATURE_SOIL_005 = "TEMPERATURE_SOIL_005"
            TEMPERATURE_SOIL_010 = "TEMPERATURE_SOIL_010"
            TEMPERATURE_SOIL_020 = "TEMPERATURE_SOIL_020"
            TEMPERATURE_SOIL_050 = "TEMPERATURE_SOIL_050"
            TEMPERATURE_SOIL_100 = "TEMPERATURE_SOIL_100"

        # solar
        class SOLAR(Enum):
            QUALITY = "QUALITY"
            END_OF_INTERVAL = "END_OF_INTERVAL"  # modified, does not exist in original
            RADIATION_SKY_LONG_WAVE = "RADIATION_SKY_LONG_WAVE"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "RADIATION_SKY_SHORT_WAVE_DIFFUSE"
            RADIATION_GLOBAL = "RADIATION_GLOBAL"
            SUNSHINE_DURATION = "SUNSHINE_DURATION"
            SUN_ZENITH = "SUN_ZENITH"
            TRUE_LOCAL_TIME = (
                "TRUE_LOCAL_TIME"  # original name was adjusted to this one
            )

        # sun
        class SUN(Enum):
            QUALITY = "QUALITY"
            SUNSHINE_DURATION = "SUNSHINE_DURATION"

        # visibility
        class VISIBILITY(Enum):
            QUALITY = "QUALITY"
            VISIBILITY_INDICATOR = "VISIBILITY_INDICATOR"  # str
            VISIBILITY = "VISIBILITY"  # int

        # wind
        class WIND(Enum):
            QUALITY = "QUALITY"
            WIND_SPEED = "WIND_SPEED"
            WIND_DIRECTION = "WIND_DIRECTION"  # int

        # wind_synop
        class WIND_SYNOPTIC(Enum):  # noqa
            QUALITY = "QUALITY"
            WIND_SPEED = "WIND_SPEED"
            WIND_DIRECTION = "WIND_DIRECTION"  # int

    # subdaily
    class SUBDAILY(WDDataColumnBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QUALITY = "QUALITY"
            TEMPERATURE_AIR_200 = "TEMPERATURE_AIR_200"
            HUMIDITY = "HUMIDITY"

        # cloudiness
        class CLOUDINESS(Enum):
            QUALITY = "QUALITY"
            CLOUD_COVER_TOTAL = "CLOUD_COVER_TOTAL"  # int
            CLOUD_DENSITY = "CLOUD_DENSITY"  # int

        # moisture
        class MOISTURE(Enum):
            QUALITY = "QUALITY"
            PRESSURE_VAPOR = "PRESSURE_VAPOR"
            TEMPERATURE_AIR_005 = "TEMPERATURE_AIR_005"
            TEMPERATURE_AIR_200 = "TEMPERATURE_AIR_200"
            HUMIDITY = "HUMIDITY"

        # pressure
        class PRESSURE(Enum):
            QUALITY = "QUALITY"
            PRESSURE_AIR = "PRESSURE_AIR"

        # soil
        class SOIL(Enum):
            QUALITY = "QUALITY"
            TEMPERATURE_SOIL_005 = "TEMPERATURE_SOIL_005"  # int

        # visibility
        class VISIBILITY(Enum):
            QUALITY = "QUALITY"
            VISIBILITY = "VISIBILITY"  # int

        # wind
        class WIND(Enum):
            QUALITY = "QUALITY"
            WIND_DIRECTION = "WIND_DIRECTION"  # int
            WIND_FORCE_BEAUFORT = "WIND_FORCE_BEAUFORT"  # int

    # Daily
    class DAILY(WDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_WIND = "QUALITY_WIND"
            WIND_GUST_MAX = "WIND_GUST_MAX"
            WIND_SPEED = "WIND_SPEED"
            QUALITY_GENERAL = (
                "QUALITY_GENERAL"  # special case here with two quality columns!
            )
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            PRECIPITATION_FORM = "PRECIPITATION_FORM"
            SUNSHINE_DURATION = "SUNSHINE_DURATION"
            SNOW_DEPTH = "SNOW_DEPTH"
            CLOUD_COVER_TOTAL = "CLOUD_COVER_TOTAL"
            PRESSURE_VAPOR = "PRESSURE_VAPOR"
            PRESSURE_AIR = "PRESSURE_AIR"
            TEMPERATURE_AIR_200 = "TEMPERATURE_AIR_200"
            HUMIDITY = "HUMIDITY"
            TEMPERATURE_AIR_MAX_200 = "TEMPERATURE_AIR_MAX_200"
            TEMPERATURE_AIR_MIN_200 = "TEMPERATURE_AIR_MIN_200"
            TEMPERATURE_AIR_MIN_005 = "TEMPERATURE_AIR_MIN_005"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "QUALITY"
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            PRECIPITATION_FORM = "PRECIPITATION_FORM"  # int
            SNOW_DEPTH = "SNOW_DEPTH"  # int
            SNOW_DEPTH_NEW = "SNOW_DEPTH_NEW"  # int

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QUALITY = "QUALITY"
            TEMPERATURE_SOIL_002 = "TEMPERATURE_SOIL_002"
            TEMPERATURE_SOIL_005 = "TEMPERATURE_SOIL_005"
            TEMPERATURE_SOIL_010 = "TEMPERATURE_SOIL_010"
            TEMPERATURE_SOIL_020 = "TEMPERATURE_SOIL_020"
            TEMPERATURE_SOIL_050 = "TEMPERATURE_SOIL_050"

        # solar
        class SOLAR(Enum):
            QUALITY = "QUALITY"
            RADIATION_SKY_LONG_WAVE = "RADIATION_SKY_LONG_WAVE"
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "RADIATION_SKY_SHORT_WAVE_DIFFUSE"
            RADIATION_SKY_SHORT_WAVE_DIRECT = "RADIATION_SKY_SHORT_WAVE_DIRECT"
            SUNSHINE_DURATION = "SUNSHINE_DURATION"

        # water_equiv
        class WATER_EQUIVALENT(Enum):  # noqa
            QUALITY = "QUALITY"
            SNOW_DEPTH_EXCELLED = "SNOW_DEPTH_EXCELLED"  # int
            SNOW_DEPTH = "SNOW_DEPTH"  # int
            WATER_EQUIVALENT_TOTAL_SNOW_DEPTH = "WATER_EQUIVALENT_TOTAL_SNOW_DEPTH"
            WATER_EQUIVALENT_SNOW = "WATER_EQUIVALENT_SNOW"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "QUALITY"
            FOG = "FOG"  # int
            THUNDER = "THUNDER"  # int
            STORM_STRONG_WIND = "STORM_STRONG_WIND"  # int
            STORM_STORMIER_WIND = "STORM_STORMIER_WIND"  # int
            DEW = "DEW"  # int
            GLAZE = "GLAZE"  # int
            RIPE = "RIPE"  # int
            SLEET = "SLEET"  # int
            HAIL = "HAIL"  # int

    # monthly
    class MONTHLY(WDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "QUALITY_GENERAL"
            CLOUD_COVER_TOTAL = "CLOUD_COVER_TOTAL"
            TEMPERATURE_AIR_200 = "TEMPERATURE_AIR_200"
            TEMPERATURE_AIR_MAX_MEAN_200 = "TEMPERATURE_AIR_MAX_MEAN_200"
            TEMPERATURE_AIR_MIN_MEAN_200 = "TEMPERATURE_AIR_MIN_MEAN_200"
            WIND_FORCE_BEAUFORT = "WIND_FORCE_BEAUFORT"
            TEMPERATURE_AIR_MAX_200 = "TEMPERATURE_AIR_MAX_200"
            WIND_GUST_MAX = "WIND_GUST_MAX"
            TEMPERATURE_AIR_MIN_200 = "TEMPERATURE_AIR_MIN_200"
            SUNSHINE_DURATION = "SUNSHINE_DURATION"
            QUALITY_PRECIPITATION = "QUALITY_PRECIPITATION"
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            PRECIPITATION_HEIGHT_MAX = "PRECIPITATION_HEIGHT_MAX"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "QUALITY"
            SNOW_DEPTH_NEW = "SNOW_DEPTH_NEW"  # int
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            SNOW_DEPTH = "SNOW_DEPTH"  # int
            PRECIPITATION_HEIGHT_MAX = "PRECIPITATION_HEIGHT_MAX"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "QUALITY"
            STORM_STRONG_WIND = "STORM_STRONG_WIND"  # int
            STORM_STORMIER_WIND = "STORM_STORMIER_WIND"  # int
            THUNDER = "THUNDER"  # int
            GLAZE = "GLAZE"  # int
            SLEET = "SLEET"  # int
            HAIL = "HAIL"  # int
            FOG = "FOG"  # int
            DEW = "DEW"  # int

    # annual
    class ANNUAL(WDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QUALITY_GENERAL = "QUALITY_GENERAL"
            CLOUD_COVER_TOTAL = "CLOUD_COVER_TOTAL"
            TEMPERATURE_AIR_200 = "TEMPERATURE_AIR_200"
            TEMPERATURE_AIR_MAX_MEAN_200 = "TEMPERATURE_AIR_MAX_MEAN_200"
            TEMPERATURE_AIR_MIN_MEAN_200 = "TEMPERATURE_AIR_MIN_MEAN_200"
            WIND_FORCE_BEAUFORT = "WIND_FORCE_BEAUFORT"
            SUNSHINE_DURATION = "SUNSHINE_DURATION"
            WIND_GUST_MAX = "WIND_GUST_MAX"
            TEMPERATURE_AIR_MAX_200 = "TEMPERATURE_AIR_MAX_200"
            TEMPERATURE_AIR_MIN_200 = "TEMPERATURE_AIR_MIN_200"
            QUALITY_PRECIPITATION = "QUALITY_PRECIPITATION"
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            PRECIPITATION_HEIGHT_MAX = "PRECIPITATION_HEIGHT_MAX"  #

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QUALITY = "QUALITY"
            SNOW_DEPTH_NEW = "SNOW_DEPTH_NEW"  # int
            PRECIPITATION_HEIGHT = "PRECIPITATION_HEIGHT"
            SNOW_DEPTH = "SNOW_DEPTH"  # int
            PRECIPITATION_HEIGHT_MAX = "PRECIPITATION_HEIGHT_MAX"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QUALITY = "QUALITY"
            STORM_STRONG_WIND = "STORM_STRONG_WIND"
            STORM_STORMIER_WIND = "STORM_STORMIER_WIND"
            THUNDER = "THUNDER"
            GLAZE = "GLAZE"
            SLEET = "SLEET"
            HAIL = "HAIL"
            FOG = "FOG"
            DEW = "DEW"
