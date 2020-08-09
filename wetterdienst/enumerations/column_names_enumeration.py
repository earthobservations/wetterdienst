from enum import Enum


class DWDOrigMetaColumns(Enum):
    """ Original meta column names from DWD data """

    STATION_ID = "STATIONS_ID"
    DATE = "MESS_DATUM"
    FROM_DATE = "VON_DATUM"
    TO_DATE = "BIS_DATUM"
    FROM_DATE_ALTERNATIVE = "MESS_DATUM_BEGINN"
    TO_DATE_ALTERNATIVE = "MESS_DATUM_ENDE"
    STATION_HEIGHT = "STATIONSHOEHE"
    LATITUDE = "GEOBREITE"
    LATITUDE_ALTERNATIVE = "GEOGR.BREITE"
    LONGITUDE = "GEOLAENGE"
    LONGITUDE_ALTERNATIVE = "GEOGR.LAENGE"
    STATION_NAME = "STATIONSNAME"
    STATE = "BUNDESLAND"


class DWDMetaColumns(Enum):
    """ Overhauled column names for metadata fields """

    STATION_ID = "STATION_ID"
    DATE = "DATE"
    FROM_DATE = "FROM_DATE"
    TO_DATE = "TO_DATE"
    STATION_HEIGHT = "STATION_HEIGHT"
    LATITUDE = "LAT"
    LONGITUDE = "LON"
    STATION_NAME = "STATION_NAME"
    STATE = "STATE"
    EOR = "EOR"
    # Extra column names
    FILENAME = "FILENAME"
    HAS_FILE = "HAS_FILE"
    FILEID = "FILEID"
    # Columns used for tidy data
    # Column for quality
    PARAMETER = "PARAMETER"
    ELEMENT = "ELEMENT"
    VALUE = "VALUE"
    QUALITY = "QUALITY"
    # Columns used for RADOLAN
    PERIOD_TYPE = "PERIOD_TYPE"
    DATETIME = "DATETIME"


# https://stackoverflow.com/questions/33727217/subscriptable-objects-in-class
class _GetAttrMeta(type):
    def __getitem__(cls, x):
        return getattr(cls, x)


class _DWDDataColumnBase(metaclass=_GetAttrMeta):
    pass


class DWDOrigDataColumns(_DWDDataColumnBase):
    """
    Original data column names from DWD data
    - two anomalies:
        - daily/kl -> QN_3, QN_4
        - monthly/kl -> QN_4, QN_6
        - annual/kl -> QN_4, QN_6
    """

    # 1_minute
    class MINUTE_1(_DWDDataColumnBase):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QN = "QN"
            RS_01 = "RS_01"
            RTH_01 = "RTH_01"
            RWH_01 = "RWH_01"
            RS_IND_01 = "RS_IND_01"  # int

    # 10_minutes
    class MINUTES_10(_DWDDataColumnBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QN = "QN"
            PP_10 = "PP_10"
            TT_10 = "TT_10"
            TM5_10 = "TM5_10"
            RF_10 = "RF_10"
            TD_10 = "TD_10"

        # extreme_temperature
        class TEMPERATURE_EXTREME(Enum):  # noqa
            QN = "QN"
            TX_10 = "TX_10"
            TX5_10 = "TX5_10"
            TN_10 = "TN_10"
            TN5_10 = "TN5_10"

        # extreme_wind
        class WIND_EXTREME(Enum):  # noqa
            QN = "QN"
            FX_10 = "FX_10"
            FNX_10 = "FNX_10"
            FMX_10 = "FMX_10"
            DX_10 = "DX_10"  # int

        # precipitation
        class PRECIPITATION(Enum):
            QN = "QN"
            RWS_DAU_10 = "RWS_DAU_10"
            RWS_10 = "RWS_10"
            RWS_IND_10 = "RWS_IND_10"  # int

        # solar
        class SOLAR(Enum):
            QN = "QN"
            DS_10 = "DS_10"
            GS_10 = "GS_10"
            SD_10 = "SD_10"
            LS_10 = "LS_10"

        # wind
        class WIND(Enum):
            QN = "QN"
            FF_10 = "FF_10"
            DD_10 = "DD_10"

    # hourly
    class HOURLY(_DWDDataColumnBase):
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QN_9 = "QN_9"
            TT_TU = "TT_TU"
            RF_TU = "RF_TU"

        # cloud_type
        class CLOUD_TYPE(Enum):  # noqa
            QN_8 = "QN_8"
            V_N = "V_N"  # int
            V_N_I = "V_N_I"  # str
            V_S1_CS = "V_S1_CS"  # int
            V_S1_CSA = "V_S1_CSA"  # str
            V_S1_HHS = "V_S1_HHS"
            V_S1_NS = "V_S1_NS"  # int
            V_S2_CS = "V_S2_CS"  # int
            V_S2_CSA = "V_S2_CSA"  # str
            V_S2_HHS = "V_S2_HHS"
            V_S2_NS = "V_S2_NS"  # int
            V_S3_CS = "V_S3_CS"  # int
            V_S3_CSA = "V_S3_CSA"  # str
            V_S3_HHS = "V_S3_HHS"
            V_S3_NS = "V_S3_NS"  # int
            V_S4_CS = "V_S4_CS"  # int
            V_S4_CSA = "V_S4_CSA"  # str
            V_S4_HHS = "V_S4_HHS"
            V_S4_NS = "V_S4_NS"  # int

        # cloudiness
        class CLOUDINESS(Enum):
            QN_8 = "QN_8"
            V_N_I = "V_N_I"  # str
            V_N = "V_N"  # int

        # dew_point
        class DEW_POINT(Enum):  # noqa
            QN_8 = "QN_8"
            TT = "TT"
            TD = "TD"

        # precipitation
        class PRECIPITATION(Enum):
            QN_8 = "QN_8"
            R1 = "R1"
            RS_IND = "RS_IND"  # int
            WRTR = "WRTR"  # int

        # pressure
        class PRESSURE(Enum):
            QN_8 = "QN_8"
            P = "P"
            P0 = "P0"

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QN_2 = "QN_2"
            V_TE002 = "V_TE002"
            V_TE005 = "V_TE005"
            V_TE010 = "V_TE010"
            V_TE020 = "V_TE020"
            V_TE050 = "V_TE050"
            V_TE100 = "V_TE100"

        # solar
        class SOLAR(Enum):
            QN_592 = "QN_592"
            END_OF_INTERVAL = "END_OF_INTERVAL"  # modified, does not exist in original
            ATMO_LBERG = "ATMO_LBERG"
            FD_LBERG = "FD_LBERG"
            FG_LBERG = "FG_LBERG"
            SD_LBERG = "SD_LBERG"
            ZENIT = "ZENIT"
            TRUE_LOCAL_TIME = (
                "TRUE_LOCAL_TIME"  # original name was adjusted to this one
            )

        # sun
        class SUN(Enum):
            QN_7 = "QN_7"
            SD_SO = "SD_SO"

        # visibility
        class VISIBILITY(Enum):
            QN_8 = "QN_8"
            V_VV_I = "V_VV_I"  # str
            V_VV = "V_VV"  # int

        # wind
        class WIND(Enum):
            QN_3 = "QN_3"
            F = "F"
            D = "D"  # int

        # wind_synop
        class WIND_SYNOPTIC(Enum):  # noqa
            QN_8 = "QN_8"
            FF = "FF"
            DD = "DD"  # int

    # subdaily
    class SUBDAILY(_DWDDataColumnBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QN_4 = "QN_4"
            TT_TER = "TT_TER"
            RF_TER = "RF_TER"

        # cloudiness
        class CLOUDINESS(Enum):
            QN_4 = "QN_4"
            N_TER = "N_TER"  # int
            CD_TER = "CD_TER"  # int

        # moisture
        class MOISTURE(Enum):
            QN_4 = "QN_4"
            VP_TER = "VP_TER"
            E_TF_TER = "E_TF_TER"
            TF_TER = "TF_TER"
            RF_TER = "RF_TER"

        # pressure
        class PRESSURE(Enum):
            QN_4 = "QN_4"
            PP_TER = "PP_TER"

        # soil
        class SOIL(Enum):
            QN_4 = "QN_4"
            EK_TER = "EK_TER"  # int

        # visibility
        class VISIBILITY(Enum):
            QN_4 = "QN_4"
            VK_TER = "VK_TER"  # int

        # wind
        class WIND(Enum):
            QN_4 = "QN_4"
            DK_TER = "DK_TER"  # int
            FK_TER = "FK_TER"  # int

    # Daily
    class DAILY(_DWDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QN_3 = "QN_3"
            FX = "FX"
            FM = "FM"
            QN_4 = "QN_4"  # special case here with two quality columns!
            RSK = "RSK"
            RSKF = "RSKF"
            SDK = "SDK"
            SHK_TAG = "SHK_TAG"
            NM = "NM"
            VPM = "VPM"
            PM = "PM"
            TMK = "TMK"
            UPM = "UPM"
            TXK = "TXK"
            TNK = "TNK"
            TGK = "TGK"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QN_6 = "QN_6"
            RS = "RS"
            RSF = "RSF"  # int
            SH_TAG = "SH_TAG"  # int
            NSH_TAG = "NSH_TAG"  # int

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QN_2 = "QN_2"
            V_TE002M = "V_TE002M"
            V_TE005M = "V_TE005M"
            V_TE010M = "V_TE010M"
            V_TE020M = "V_TE020M"
            V_TE050M = "V_TE050M"

        # solar
        class SOLAR(Enum):
            QN_592 = "QN_592"
            ATMO_STRAHL = "ATMO_STRAHL"
            FD_STRAHL = "FD_STRAHL"
            FG_STRAHL = "FG_STRAHL"
            SD_STRAHL = "SD_STRAHL"

        # water_equiv
        class WATER_EQUIVALENT(Enum):  # noqa
            QN_6 = "QN_6"
            ASH_6 = "ASH_6"  # int
            SH_TAG = "SH_TAG"  # int
            WASH_6 = "WASH_6"
            WAAS_6 = "WAAS_6"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QN_4 = "QN_4"
            NEBEL = "NEBEL"  # int
            GEWITTER = "GEWITTER"  # int
            STURM_6 = "STURM_6"  # int
            STURM_8 = "STURM_8"  # int
            TAU = "TAU"  # int
            GLATTEIS = "GLATTEIS"  # int
            REIF = "REIF"  # int
            GRAUPEL = "GRAUPEL"  # int
            HAGEL = "HAGEL"  # int

    # monthly
    class MONTHLY(_DWDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QN_4 = "QN_4"
            MO_N = "MO_N"
            MO_TT = "MO_TT"
            MO_TX = "MO_TX"
            MO_TN = "MO_TN"
            MO_FK = "MO_FK"
            MX_TX = "MX_TX"
            MX_FX = "MX_FX"
            MX_TN = "MX_TN"
            MO_SD_S = "MO_SD_S"
            QN_6 = "QN_6"
            MO_RR = "MO_RR"
            MX_RS = "MX_RS"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QN_6 = "QN_6"
            MO_NSH = "MO_NSH"  # int
            MO_RR = "MO_RR"
            MO_SH_S = "MO_SH_S"  # int
            MX_RS = "MX_RS"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QN_4 = "QN_4"
            MO_STURM_6 = "MO_STURM_6"  # int
            MO_STURM_8 = "MO_STURM_8"  # int
            MO_GEWITTER = "MO_GEWITTER"  # int
            MO_GLATTEIS = "MO_GLATTEIS"  # int
            MO_GRAUPEL = "MO_GRAUPEL"  # int
            MO_HAGEL = "MO_HAGEL"  # int
            MO_NEBEL = "MO_NEBEL"  # int
            MO_TAU = "MO_TAU"  # int

    # annual
    class ANNUAL(_DWDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QN_4 = "QN_4"
            JA_N = "JA_N"
            JA_TT = "JA_TT"
            JA_TX = "JA_TX"
            JA_TN = "JA_TN"
            JA_FK = "JA_FK"
            JA_SD_S = "JA_SD_S"
            JA_MX_FX = "JA_MX_FX"
            JA_MX_TX = "JA_MX_TX"
            JA_MX_TN = "JA_MX_TN"
            QN_6 = "QN_6"
            JA_RR = "JA_RR"
            JA_MX_RS = "JA_MX_RS"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QN_6 = "QN_6"
            JA_NSH = "JA_NSH"  # int
            JA_RR = "JA_RR"
            JA_SH_S = "JA_SH_S"  # int
            JA_MX_RS = "JA_MX_RS"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QN_4 = "QN_4"
            JA_STURM_6 = "JA_STURM_6"  # int
            JA_STURM_8 = "JA_STURM_8"  # int
            JA_GEWITTER = "JA_GEWITTER"  # int
            JA_GLATTEIS = "JA_GLATTEIS"  # int
            JA_GRAUPEL = "JA_GRAUPEL"  # int
            JA_HAGEL = "JA_HAGEL"  # int
            JA_NEBEL = "JA_NEBEL"  # int
            JA_TAU = "JA_TAU"  # int


class DWDDataColumns(_DWDDataColumnBase):
    """
    Original data column names from DWD data
    - two anomalies:
        - daily/kl -> QN_3, QN_4
        - monthly/kl -> QN_4, QN_6
        - annual/kl -> QN_4, QN_6
    """

    # 1_minute
    class MINUTE_1(_DWDDataColumnBase):  # noqa
        # precipitation
        class PRECIPITATION(Enum):
            QN = "QUALITY"
            RS_01 = "PRECIPITATION_HEIGHT"
            RTH_01 = "PRECIPITATION_HEIGHT_DROPLET"
            RWH_01 = "PRECIPITATION_HEIGHT_ROCKER"
            RS_IND_01 = "PRECIPITATION_FORM"  # int

    # 10_minutes
    class MINUTES_10(_DWDDataColumnBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QN = "QUALITY"
            PP_10 = "PRESSURE_AIR_STATION_HEIGHT"
            TT_10 = "TEMPERATURE_AIR_200"
            TM5_10 = "TEMPERATURE_AIR_005"
            RF_10 = "HUMIDITY"
            TD_10 = "TEMPERATURE_DEW_POINT_200"

        # extreme_temperature
        class TEMPERATURE_EXTREME(Enum):  # noqa
            QN = "QUALITY"
            TX_10 = "TEMPERATURE_AIR_MAX_200"
            TX5_10 = "TEMPERATURE_AIR_MAX_005"
            TN_10 = "TEMPERATURE_AIR_MIN_200"
            TN5_10 = "TEMPERATURE_AIR_MIN_005"

        # extreme_wind
        class WIND_EXTREME(Enum):  # noqa
            QN = "QUALITY"
            FX_10 = "WIND_GUST_MAX"
            FNX_10 = "WIND_VELOCITY_MIN"
            FMX_10 = "WIND_VELOCITY_ROLLING_MEAN_MAX"
            DX_10 = "WIND_DIRECTION_MAX_VELOCITY"  # int

        # precipitation
        class PRECIPITATION(Enum):
            QN = "QUALITY"
            RWS_DAU_10 = "PRECIPITATION_DURATION"
            RWS_10 = "PRECIPITATION_HEIGHT"
            RWS_IND_10 = "PRECIPITATION_INDICATOR_WR"  # int

        # solar
        class SOLAR(Enum):
            QN = "QUALITY"
            DS_10 = "RADIATION_SKY_DIFFUSE"
            GS_10 = "RADIATION_GLOBAL"
            SD_10 = "SUNSHINE_DURATION"
            LS_10 = "RADIATION_SKY_LONG_WAVE"

        # wind
        class WIND(Enum):
            QN = "QUALITY"
            FF_10 = "WIND_VELOCITY"
            DD_10 = "WIND_DIRECTION"

    # hourly
    class HOURLY(_DWDDataColumnBase):
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QN_9 = "QUALITY"
            TT_TU = "TEMPERATURE_AIR_200"
            RF_TU = "HUMIDITY"

        # cloud_type
        class CLOUD_TYPE(Enum):  # noqa
            QN_8 = "QUALITY"
            V_N = "CLOUD_COVERAGE_TOTAL"  # int
            V_N_I = "CLOUD_COVERAGE_TOTAL_INDICATOR"  # str
            V_S1_CS = "CLOUD_TYPE_LAYER1"  # int
            V_S1_CSA = "CLOUD_TYPE_LAYER1_ABBREVIATION"  # str
            V_S1_HHS = "CLOUD_HEIGHT_LAYER1"
            V_S1_NS = "CLOUD_COVERAGE_LAYER1"  # int
            V_S2_CS = "CLOUD_TYPE_LAYER2"  # int
            V_S2_CSA = "CLOUD_TYPE_LAYER2_ABBREVIATION"  # str
            V_S2_HHS = "CLOUD_HEIGHT_LAYER2"
            V_S2_NS = "CLOUD_COVERAGE_LAYER2"  # int
            V_S3_CS = "CLOUD_TYPE_LAYER3"  # int
            V_S3_CSA = "CLOUD_TYPE_LAYER3_ABBREVIATION"  # str
            V_S3_HHS = "CLOUD_HEIGHT_LAYER3"
            V_S3_NS = "CLOUD_COVERAGE_LAYER3"  # int
            V_S4_CS = "CLOUD_TYPE_LAYER4"  # int
            V_S4_CSA = "CLOUD_TYPE_LAYER4_ABBREVIATION"  # str
            V_S4_HHS = "CLOUD_HEIGHT_LAYER4"
            V_S4_NS = "CLOUD_COVERAGE_LAYER4"  # int

        # cloudiness
        class CLOUDINESS(Enum):
            QN_8 = "QUALITY"
            V_N_I = "CLOUD_COVERAGE_TOTAL_INDICATOR"  # str
            V_N = "CLOUD_COVERAGE_TOTAL"  # int

        # dew_point
        class DEW_POINT(Enum):  # noqa
            QN_8 = "QUALITY"
            TT = "TEMPERATURE_AIR_200"
            TD = "TEMPERATURE_DEW_POINT_200"

        # precipitation
        class PRECIPITATION(Enum):
            QN_8 = "QUALITY"
            R1 = "PRECIPITATION_HEIGHT"
            RS_IND = "PRECIPITATION_INDICATOR_T/F"  # int
            WRTR = "PRECIPITATION_FORM"  # int

        # pressure
        class PRESSURE(Enum):
            QN_8 = "QUALITY"
            P = "PRESSURE_AIR_SEA_LEVEL"
            P0 = "PRESSURE_AIR_STATION_HEIGHT"

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QN_2 = "QUALITY"
            V_TE002 = "TEMPERATURE_SOIL_002"
            V_TE005 = "TEMPERATURE_SOIL_005"
            V_TE010 = "TEMPERATURE_SOIL_010"
            V_TE020 = "TEMPERATURE_SOIL_020"
            V_TE050 = "TEMPERATURE_SOIL_050"
            V_TE100 = "TEMPERATURE_SOIL_100"

        # solar
        class SOLAR(Enum):
            QN_592 = "QUALITY"
            END_OF_INTERVAL = "END_OF_INTERVAL"  # modified, does not exist in original
            ATMO_LBERG = "RADIATION_SKY_LONG_WAVE"
            FD_LBERG = "RADIATION_SKY_SHORT_WAVE_DIFFUSE"
            FG_LBERG = "RADIATION_GLOBAL"
            SD_LBERG = "SUNSHINE_DURATION"
            ZENIT = "SUN_ZENITH"
            TRUE_LOCAL_TIME = (
                "TRUE_LOCAL_TIME"  # original name was adjusted to this one
            )

        # sun
        class SUN(Enum):
            QN_7 = "QUALITY"
            SD_SO = "SUNSHINE_DURATION"

        # visibility
        class VISIBILITY(Enum):
            QN_8 = "QUALITY"
            V_VV_I = "VISIBILITY_INDICATOR"  # str
            V_VV = "VISIBILITY"  # int

        # wind
        class WIND(Enum):
            QN_3 = "QUALITY"
            F = "WIND_VELOCITY"
            D = "WIND_DIRECTION"  # int

        # wind_synop
        class WIND_SYNOPTIC(Enum):  # noqa
            QN_8 = "QUALITY"
            FF = "WIND_VELOCITY"
            DD = "WIND_DIRECTION"  # int

    # subdaily
    class SUBDAILY(_DWDDataColumnBase):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(Enum):  # noqa
            QN_4 = "QUALITY"
            TT_TER = "TEMPERATURE_AIR_200"
            RF_TER = "HUMIDITY"

        # cloudiness
        class CLOUDINESS(Enum):
            QN_4 = "QUALITY"
            N_TER = "CLOUD_COVERAGE_TOTAL"  # int
            CD_TER = "CLOUD_DENSITY"  # int

        # moisture
        class MOISTURE(Enum):
            QN_4 = "QUALITY"
            VP_TER = "PRESSURE_VAPOR"
            E_TF_TER = "TEMPERATURE_AIR_005"
            TF_TER = "TEMPERATURE_AIR_200"
            RF_TER = "HUMIDITY"

        # pressure
        class PRESSURE(Enum):
            QN_4 = "QUALITY"
            PP_TER = "PRESSURE_AIR"

        # soil
        class SOIL(Enum):
            QN_4 = "QUALITY"
            EK_TER = "TEMPERATURE_SOIL_005"  # int

        # visibility
        class VISIBILITY(Enum):
            QN_4 = "QUALITY"
            VK_TER = "VISIBILITY"  # int

        # wind
        class WIND(Enum):
            QN_4 = "QUALITY"
            DK_TER = "WIND_DIRECTION"  # int
            FK_TER = "WIND_FORCE_BEAUFORT"  # int

    # Daily
    class DAILY(_DWDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QN_3 = "QUALITY_WIND"
            FX = "WIND_GUST_MAX"
            FM = "WIND_VELOCITY"
            QN_4 = "QUALITY_GENERAL"  # special case here with two quality columns!
            RSK = "PRECIPITATION_HEIGHT"
            RSKF = "PRECIPITATION_FORM"
            SDK = "SUNSHINE_DURATION"
            SHK_TAG = "SNOW_DEPTH"
            NM = "CLOUD_COVERAGE_TOTAL"
            VPM = "PRESSURE_VAPOR"
            PM = "PRESSURE_AIR"
            TMK = "TEMPERATURE_AIR_200"
            UPM = "HUMIDITY"
            TXK = "TEMPERATURE_AIR_MAX_200"
            TNK = "TEMPERATURE_AIR_MIN_200"
            TGK = "TEMPERATURE_AIR_MIN_005"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QN_6 = "QUALITY"
            RS = "PRECIPITATION_HEIGHT"
            RSF = "PRECIPITATION_FORM"  # int
            SH_TAG = "SNOW_DEPTH"  # int
            NSH_TAG = "SNOW_DEPTH_NEW"  # int

        # soil_temperature
        class TEMPERATURE_SOIL(Enum):  # noqa
            QN_2 = "QUALITY"
            V_TE002M = "TEMPERATURE_SOIL_002"
            V_TE005M = "TEMPERATURE_SOIL_005"
            V_TE010M = "TEMPERATURE_SOIL_010"
            V_TE020M = "TEMPERATURE_SOIL_020"
            V_TE050M = "TEMPERATURE_SOIL_050"

        # solar
        class SOLAR(Enum):
            QN_592 = "QUALITY"
            ATMO_STRAHL = "RADIATION_SKY_LONG_WAVE"
            FD_STRAHL = "RADIATION_SKY_SHORT_WAVE_DIFFUSE"
            FG_STRAHL = "RADIATION_SKY_SHORT_WAVE_DIRECT"
            SD_STRAHL = "SUNSHINE_DURATION"

        # water_equiv
        class WATER_EQUIVALENT(Enum):  # noqa
            QN_6 = "QUALITY"
            ASH_6 = "SNOW_DEPTH_EXCELLED"  # int
            SH_TAG = "SNOW_DEPTH"  # int
            WASH_6 = "WATER_EQUIVALENT_TOTAL_SNOW_DEPTH"
            WAAS_6 = "WATER_EQUIVALENT_SNOW"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QN_4 = "QUALITY"
            NEBEL = "FOG"  # int
            GEWITTER = "THUNDER"  # int
            STURM_6 = "STORM_STRONG_WIND"  # int
            STURM_8 = "STORM_STORMIER_WIND"  # int
            TAU = "DEW"  # int
            GLATTEIS = "GLAZE"  # int
            REIF = "RIPE"  # int
            GRAUPEL = "SLEET"  # int
            HAGEL = "HAIL"  # int

    # monthly
    class MONTHLY(_DWDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QN_4 = "QUALITY_GENERAL"
            MO_N = "CLOUD_COVERAGE_TOTAL"
            MO_TT = "TEMPERATURE_AIR_200"
            MO_TX = "TEMPERATURE_AIR_MAX_MEAN_200"
            MO_TN = "TEMPERATURE_AIR_MIN_MEAN_200"
            MO_FK = "WIND_FORCE_BEAUFORT"
            MX_TX = "TEMPERATURE_AIR_MAX_200"
            MX_FX = "WIND_GUST_MAX"
            MX_TN = "TEMPERATURE_AIR_MIN_200"
            MO_SD_S = "SUNSHINE_DURATION"
            QN_6 = "QUALITY_PRECIPITATION"
            MO_RR = "PRECIPITATION_HEIGHT"
            MX_RS = "PRECIPITATION_HEIGHT_MAX"

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QN_6 = "QUALITY"
            MO_NSH = "SNOW_DEPTH_NEW"  # int
            MO_RR = "PRECIPITATION_HEIGHT"
            MO_SH_S = "SNOW_DEPTH"  # int
            MX_RS = "PRECIPITATION_HEIGHT_MAX"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QN_4 = "QUALITY"
            MO_STURM_6 = "STORM_STRONG_WIND"  # int
            MO_STURM_8 = "STORM_STORMIER_WIND"  # int
            MO_GEWITTER = "THUNDER"  # int
            MO_GLATTEIS = "GLAZE"  # int
            MO_GRAUPEL = "SLEET"  # int
            MO_HAGEL = "HAIL"  # int
            MO_NEBEL = "FOG"  # int
            MO_TAU = "DEW"  # int

    # annual
    class ANNUAL(_DWDDataColumnBase):
        # kl
        class CLIMATE_SUMMARY(Enum):  # noqa
            QN_4 = "QUALITY_GENERAL"
            JA_N = "CLOUD_COVERAGE_TOTAL"
            JA_TT = "TEMPERATURE_AIR_200"
            JA_TX = "TEMPERATURE_AIR_MAX_MEAN_200"
            JA_TN = "TEMPERATURE_AIR_MIN_MEAN_200"
            JA_FK = "WIND_FORCE_BEAUFORT"
            JA_SD_S = "SUNSHINE_DURATION"
            JA_MX_FX = "WIND_GUST_MAX"
            JA_MX_TX = "TEMPERATURE_AIR_MAX_200"
            JA_MX_TN = "TEMPERATURE_AIR_MIN_200"
            QN_6 = "QUALITY_PRECIPITATION"
            JA_RR = "PRECIPITATION_HEIGHT"
            JA_MX_RS = "PRECIPITATION_HEIGHT_MAX"  #

        # more_precip
        class PRECIPITATION_MORE(Enum):  # noqa
            QN_6 = "QUALITY"
            JA_NSH = "SNOW_DEPTH_NEW"  # int
            JA_RR = "PRECIPITATION_HEIGHT"
            JA_SH_S = "SNOW_DEPTH"  # int
            JA_MX_RS = "PRECIPITATION_HEIGHT_MAX"

        # weather_phenomena
        class WEATHER_PHENOMENA(Enum):  # noqa
            QN_4 = "QUALITY"
            JA_STURM_6 = "STORM_STRONG_WIND"
            JA_STURM_8 = "STORM_STORMIER_WIND"
            JA_GEWITTER = "THUNDER"
            JA_GLATTEIS = "GLAZE"
            JA_GRAUPEL = "SLEET"
            JA_HAGEL = "HAIL"
            JA_NEBEL = "FOG"
            JA_TAU = "DEW"
