# -*- coding: utf-8 -*-
# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Union

import polars as pl

from wetterdienst import Parameter, Settings
from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore


class GeosphereObservationResolution(Enum):
    MINUTE_10 = Resolution.MINUTE_10.value
    HOURLY = Resolution.HOURLY.value
    DAILY = Resolution.DAILY.value
    MONTHLY = Resolution.MONTHLY.value


class GeosphereObservationPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class GeosphereObservationParameter(DatasetTreeCore):
    class MINUTE_10(DatasetTreeCore):
        class MINUTE_10(Enum):
            HUMIDITY = "RF"  # Relative Feuchte %
            PRECIPITATION_HEIGHT = "RR"  # Niederschlag mm
            PRESSURE_AIR_SITE = "P"  # Luftdruck hPa
            PRESSURE_AIR_SEA_LEVEL = "P0"  # Reduzierter Luftdruck hPa
            RADIATION_GLOBAL = "GSX"  # Globalstrahlung W/m²
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "HSX"  # Himmelsstrahlung/Diffusstrahlung in W/m²
            SNOW_DEPTH = "SH"  # Gesamtschneehöhe aus Schneepegelmessung cm
            SUNSHINE_DURATION = "SO"  # Sonnenscheindauer s
            TEMPERATURE_AIR_MAX_005 = "TSMAX"  # Lufttemperaturmaximum in 5cm °C
            TEMPERATURE_AIR_MAX_200 = "TLMAX"  # Lufttemperaturmaximum in 2m °C
            TEMPERATURE_AIR_MEAN_005 = "TS"  # Lufttemperatur in 5cm °C
            TEMPERATURE_AIR_MEAN_200 = "TL"  # Lufttemperatur in 2m °C
            TEMPERATURE_AIR_MIN_005 = "TSMIN"  # Lufttemperaturminimum in 5cm °C
            TEMPERATURE_AIR_MIN_200 = "TLMIN"  # Lufttemperaturminimum in 2m °C
            TEMPERATURE_DEW_POINT_MEAN_200 = "TP"  # Taupunkt °C
            TEMPERATURE_SOIL_MEAN_010 = "TB1"  # Erdbodentemperatur in 10cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_020 = "TB2"  # Erdbodentemperatur in 20cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_050 = "TB3"  # Erdbodentemperatur in 50cm Tiefe °C
            WIND_DIRECTION = "DD"  # Windrichtung °
            WIND_DIRECTION_GUST_MAX = "DDX"  # Windrichtung zum Böenspitzenwert °
            WIND_GUST_MAX = "FFX"  # maximale Windgeschwindigkeit m/s
            WIND_SPEED = "FF"  # vektorielle Windgeschwindigkeit m/s
            # Not (yet) implemented parameters:
            #     DDX_FLAG	Qualitätsflag der Windrichtung der maximalen Windgeschwindigkeit	code
            #     DD_FLAG	Qualitätsflag der Windrichtung	code
            #     FFAM	arithmetische Windgeschwindigkeit	m/s
            #     FFAM_FLAG	Qualitätsflag der arithmetischen Windgeschwindigkeit	code
            #     FFX_FLAG	Qualitätsflag der maximalen Windgeschwindigkeit	code
            #     FF_FLAG	Qualitätsflag der Windgeschwindigkeit	code
            #     GSX_FLAG	Qualitätsflag der Globalstrahlung	code
            #     HSR	Himmelsstrahlung/Diffusstrahlung in mV	mV
            #     HSR_FLAG	Qualitätsflag der Diffusstrahlung in mV	code
            #     HSX_FLAG	Qualitätsflag der Diffusstrahlung in W/m²	code
            #     P0_FLAG	Qualitätsflag des reduzierten Drucks	code
            #     P_FLAG	Qualitätsflag des Drucks	code
            #     QFLAG	Qualitätsflag	Code
            #     RF_FLAG	Qualitätsflag der relatvien Feuchte	code
            #     RRM	Niederschlagsmelder	min
            #     RRM_FLAG	Qualitätsflag der 10 Minuten Summe des Regenmelders	code
            #     RR_FLAG	Qualitätsflag der 10 Minuten Summe des Niederschlags	code
            #     SH_FLAG	Qualitätsflag der Gesamtschneehöhe	code
            #     SO_FLAG	Qualitätsflag der Sonnenscheindauer	code
            #     TB1_FLAG	Qualitätsflag der Erdbodentemperatur in 10 cm	code
            #     TB2_FLAG	Qualitätsflag der Erdbodentemperatur in 20 cm	code
            #     TB3_FLAG	Qualitätsflag der Erdbodentemperatur in 50 cm	code
            #     TLMAX_FLAG	Qualitätsflag des Lufttemperaturmaximums in 2m	code
            #     TLMIN_FLAG	Qualitätsflag des Lufttemperaturminimums in 2m	code
            #     TL_FLAG	Qualitätsflag der Lufttemperatur in 2m	code
            #     TP_FLAG	Qualitätsflag des Taupunkts	code
            #     TSMAX_FLAG	Qualitätsflag des Lufttemperaturmaximums in 5cm	code
            #     TSMIN_FLAG	Qualitätsflag des Lufttemperaturminimums in 5cm	code
            #     TS_FLAG	Qualitätsflag der Lufttemperatur in 5cm	code
            #     ZEITX	Zeitpunkt der maximalen Windgeschwindigkeit
            #     ZEITX_FLAG	Qualitätsflag des Zeitpunkts der maximalen Windgeschwindigkeit	code

        HUMIDITY = MINUTE_10.HUMIDITY
        PRECIPITATION_HEIGHT = MINUTE_10.PRECIPITATION_HEIGHT
        PRESSURE_AIR_SITE = MINUTE_10.PRESSURE_AIR_SITE
        PRESSURE_AIR_SEA_LEVEL = MINUTE_10.PRESSURE_AIR_SEA_LEVEL
        RADIATION_GLOBAL = MINUTE_10.RADIATION_GLOBAL
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = MINUTE_10.RADIATION_SKY_SHORT_WAVE_DIFFUSE
        SNOW_DEPTH = MINUTE_10.SNOW_DEPTH
        SUNSHINE_DURATION = MINUTE_10.SUNSHINE_DURATION
        TEMPERATURE_AIR_MAX_005 = MINUTE_10.TEMPERATURE_AIR_MAX_005
        TEMPERATURE_AIR_MAX_200 = MINUTE_10.TEMPERATURE_AIR_MAX_200
        TEMPERATURE_AIR_MEAN_005 = MINUTE_10.TEMPERATURE_AIR_MEAN_005
        TEMPERATURE_AIR_MEAN_200 = MINUTE_10.TEMPERATURE_AIR_MEAN_200
        TEMPERATURE_AIR_MIN_005 = MINUTE_10.TEMPERATURE_AIR_MIN_005
        TEMPERATURE_AIR_MIN_200 = MINUTE_10.TEMPERATURE_AIR_MIN_200
        TEMPERATURE_DEW_POINT_MEAN_200 = MINUTE_10.TEMPERATURE_DEW_POINT_MEAN_200
        TEMPERATURE_SOIL_MEAN_010 = MINUTE_10.TEMPERATURE_SOIL_MEAN_010
        TEMPERATURE_SOIL_MEAN_020 = MINUTE_10.TEMPERATURE_SOIL_MEAN_020
        TEMPERATURE_SOIL_MEAN_050 = MINUTE_10.TEMPERATURE_SOIL_MEAN_050
        WIND_DIRECTION = MINUTE_10.WIND_DIRECTION
        WIND_DIRECTION_GUST_MAX = MINUTE_10.WIND_DIRECTION_GUST_MAX
        WIND_GUST_MAX = MINUTE_10.WIND_GUST_MAX
        WIND_SPEED = MINUTE_10.WIND_SPEED

    class HOURLY(DatasetTreeCore):
        class HOURLY(Enum):
            HUMIDITY = "FFX"  # Relative Feuchte %
            PRECIPITATION_DURATION = "RSD"  # Niederschlagsdauer min
            PRECIPITATION_HEIGHT = "RSX"  # Niederschlag mm
            PRESSURE_AIR_SEA_LEVEL = "PPY"  # Luftdruck auf Meeresniveau reduziert mbar
            PRESSURE_AIR_SITE = "PPX"  # Luftdruck Stationsniveau mbar
            PRESSURE_VAPOR = "VPX"  # Dampfdruck mbar
            RADIATION_GLOBAL = "GSX"  # Globalstrahlung J/cm²
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "HSX"  # Diffusstrahlung J/cm² pro Stunde
            RADIATION_SKY_SHORT_WAVE_DIRECT = "SST"  # Direkte Sonnenstrahlung (direkt) J/cm² pro Stunde
            SNOW_DEPTH = "SCH"  # Schneehöhe cm
            SUNSHINE_DURATION = "SUX"  # Sonnenscheindauer h
            TEMPERATURE_AIR_MEAN_005 = "LT2"  # LT2 Lufttemperatur in 5 cm °C
            TEMPERATURE_AIR_MEAN_200 = "TTX"  # Lufttemperatur 2 meter °C
            TEMPERATURE_SOIL_MEAN_010 = "TT2"  # Erdbodentemperatur in 10 cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_020 = "TT3"  # Erdbodentemperatur in 20 cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_050 = "TT4"  # Erdbodentemperatur in 50 cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_100 = "TT5"  # Erdbodentemperatur in 100 cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_200 = "TT0"  # Erdbodentemperatur in 200 cm Tiefe °C
            TEMPERATURE_DEW_POINT_MEAN_200 = "TDX"  # Taupunktstemperatur °C
            WIND_DIRECTION = "D6X"  # Windrichtung °
            WIND_DIRECTION_GUST_MAX = "WSD"  # Windrichtung der Windspitze °
            WIND_GUST_MAX = "WSX"  # Windspitzen m/s
            WIND_SPEED = "VVX"  # Windgeschwindigkeit m/s
            # Not (yet) implemented parameters:
            #     D2X	Windrichtung in Sektoren
            #     D2X_qflag	Qualitätsqflag für D2X
            #     D2X_typ	Qualitätstyp für D2X
            #     D6X_qflag	Qualitätsqflag für D6X
            #     D6X_typ	Qualitätstyp für D6X
            #     FFX_qflag	Qualitätsqflag für FFX
            #     FFX_typ	Qualitätstyp für FFX
            #     GSR	Globalstrahlung ungeeicht	mV
            #     GSR_qflag	Qualitätsqflag für GSR
            #     GSR_typ	Qualitätstyp für GSR
            #     GSW	Globalstrahlung	W/m²
            #     GSW_qflag	Qualitätsqflag für GSW
            #     GSW_typ	Qualitätstyp für GSW
            #     GSX_qflag	Qualitätsqflag für GSX
            #     GSX_typ	Qualitätstyp für GSX
            #     HSR	Diffusstrahlung ungeeicht	mV
            #     HSR_qflag	Qualitätsqflag für HSR
            #     HSR_typ	Qualitätstyp für HSR
            #     HSX_qflag	Qualitätsqflag für HSX
            #     HSX_typ	Qualitätstyp für HSX
            #     LT2_qflag	Qualitätsqflag für LT2
            #     LT2_typ	Qualitätstyp für LT2
            #     PPX_qflag	Qualitätsqflag für PPX
            #     PPX_typ	Qualitätstyp für PPX
            #     PPY_qflag	Qualitätsqflag für PPY
            #     PPY_typ	Qualitätstyp für PPY
            #     RS2	Niederschlag 2	mm
            #     RS2_qflag	Qualitätsqflag für RS2
            #     RS2_typ	Qualitätstyp für RS2
            #     RSD_qflag	Qualitätsqflag für RSD
            #     RSD_typ	Qualitätstyp für RSD
            #     RSX_qflag	Qualitätsqflag für RSX
            #     RSX_typ	Qualitätstyp für RSX
            #     SCH_qflag	Qualitätsqflag für SCH
            #     SCH_typ	Qualitätstyp für SCH
            #     SST_qflag	Qualitätsqflag für SST
            #     SST_typ	Qualitätstyp für SST
            #     SUX_qflag	Qualitätsqflag für SUX
            #     SUX_typ	Qualitätstyp für SUX
            #     TDX_qflag	Qualitätsqflag für TDX
            #     TDX_typ	Qualitätstyp für TDX
            #     TT0_qflag	Qualitätsqflag für TT0
            #     TT0_typ	Qualitätstyp für TT0
            #     TT2_qflag	Qualitätsqflag für TT2
            #     TT2_typ	Qualitätstyp für TT2
            #     TT3_qflag	Qualitätsqflag für TT3
            #     TT3_typ	Qualitätstyp für TT3
            #     TT4_qflag	Qualitätsqflag für TT4
            #     TT4_typ	Qualitätstyp für TT4
            #     TT5_qflag	Qualitätsqflag für TT5
            #     TT5_typ	Qualitätstyp für TT5
            #     TTX_qflag	Qualitätsqflag für TTX
            #     TTX_typ	Qualitätstyp für TTX
            #     VKM_qflag	Qualitätsqflag für VKM
            #     VKM_typ	Qualitätstyp für VKM
            #     VPX_qflag	Qualitätsqflag für VPX
            #     VPX_typ	Qualitätstyp für VPX
            #     VKM	Windgeschwindigkeit km/h
            #     VVX_qflag	Qualitätsqflag für VVX
            #     VVX_typ	Qualitätstyp für VVX
            #     WSD_qflag	Qualitätsqflag für WSD
            #     WSD_typ	Qualitätstyp für WSD
            #     WSK	Windspitzen	km/h
            #     WSK_qflag	Qualitätsqflag für WSK
            #     WSK_typ	Qualitätstyp für WSK
            #     WSX_qflag	Qualitätsqflag für WSX
            #     WSX_typ	Qualitätstyp für WSX
            #     WSZ	Zeit der Windspitze
            #     WSZ_qflag	Qualitätsqflag für WSZ
            #     WSZ_typ	Qualitätstyp für WSZ

        HUMIDITY = HOURLY.HUMIDITY
        PRECIPITATION_DURATION = HOURLY.PRECIPITATION_DURATION
        PRECIPITATION_HEIGHT = HOURLY.PRECIPITATION_HEIGHT
        PRESSURE_AIR_SEA_LEVEL = HOURLY.PRESSURE_AIR_SEA_LEVEL
        PRESSURE_AIR_SITE = HOURLY.PRESSURE_AIR_SITE
        PRESSURE_VAPOR = HOURLY.PRESSURE_VAPOR
        RADIATION_GLOBAL = HOURLY.RADIATION_GLOBAL
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = HOURLY.RADIATION_SKY_SHORT_WAVE_DIFFUSE
        RADIATION_SKY_SHORT_WAVE_DIRECT = HOURLY.RADIATION_SKY_SHORT_WAVE_DIRECT
        SNOW_DEPTH = HOURLY.SNOW_DEPTH
        SUNSHINE_DURATION = HOURLY.SUNSHINE_DURATION
        TEMPERATURE_AIR_MEAN_005 = HOURLY.TEMPERATURE_AIR_MEAN_005
        TEMPERATURE_AIR_MEAN_200 = HOURLY.TEMPERATURE_AIR_MEAN_200
        TEMPERATURE_SOIL_MEAN_010 = HOURLY.TEMPERATURE_SOIL_MEAN_010
        TEMPERATURE_SOIL_MEAN_020 = HOURLY.TEMPERATURE_SOIL_MEAN_020
        TEMPERATURE_SOIL_MEAN_050 = HOURLY.TEMPERATURE_SOIL_MEAN_050
        TEMPERATURE_SOIL_MEAN_100 = HOURLY.TEMPERATURE_SOIL_MEAN_100
        TEMPERATURE_SOIL_MEAN_200 = HOURLY.TEMPERATURE_SOIL_MEAN_200
        TEMPERATURE_DEW_POINT_MEAN_200 = HOURLY.TEMPERATURE_DEW_POINT_MEAN_200
        WIND_DIRECTION = HOURLY.WIND_DIRECTION
        WIND_DIRECTION_GUST_MAX = HOURLY.WIND_DIRECTION_GUST_MAX
        WIND_GUST_MAX = HOURLY.WIND_GUST_MAX
        WIND_SPEED = HOURLY.WIND_SPEED

    class DAILY(DatasetTreeCore):
        class DAILY(Enum):
            HUMIDITY = "rel"  # Relative Feuchte Tagesmittel %
            PRECIPITATION_HEIGHT = "nied"  # Niederschlagssumme mm
            PRESSURE_AIR_SITE = "druckmit"  # Luftdruck Tagesmittel hPa
            PRESSURE_VAPOR = "dampfmit"  # Dampfdruck Tagesmittel hPa
            RADIATION_GLOBAL = "strahl"  # Globalstrahlung 24h-Summe J/cm²
            SNOW_DEPTH = "schnee"  # Gesamtschneehöhe zum Beobachtungstermin I cm
            SNOW_DEPTH_NEW = "neuschnee"  # Neuschneehöhe zum Beobachtungstermin I cm
            SUNSHINE_DURATION = "sonne"  # Sonnenscheindauer 24h-Summe h
            TEMPERATURE_AIR_MAX_200 = "tmax"  # Lufttemperatur 2m Maximum °C
            TEMPERATURE_AIR_MEAN_200 = "t"  # Lufttemperaturmittel 2m °C
            TEMPERATURE_AIR_MIN_200 = "tmin"  # Lufttemperatur 2m Minimum °C
            TEMPERATURE_AIR_MIN_005 = "erdmin"  # 5 cm Lufttemperatur Minimum °C
            WIND_GUST_MAX = "vvmax"  # Windgeschwindigkeit Tagesmaximum m/s
            WIND_SPEED = "vv"  # Windgeschwindigkeit Tagesmittel m/s
            # Not (yet) implemented parameters:
            #     bew07_d	Bewölklungsdichte zum Beobachtungstermine I	Code
            #     bew07_m	Bewölkungsmenge zum Beobachtungstermin I	1/10
            #     bew14_d	Bewölklungsdichte zum Beobachtungstermin II	Code
            #     bew14_m	Bewölkungsmenge zum Beobachtungstermin II	1/10
            #     bew19_d	Bewölklungsdichte zum Beobachtungstermin III	Code
            #     bew19_m	Bewölkungsmenge zum Beobachtungstermin III	1/10
            #     bewmit	Bewölkungsmenge Tagesmittel der Beobachtungstermine I,II,III	1/100
            #     code_b	abgesetzter Niederschlag - Code b	Code
            #     code_c	sonstige Wettererscheinungen - Code c	Code
            #     dampf07	Dampfdruck zum Beobachtungstermin I	hPa
            #     dampf14	Dampfdruck zum Beobachtungstermin II	hPa
            #     dampf19	Dampfdruck zum Beobachtungstermin III	hPa
            #     dd07	Windrichtung in 32 Sektoren zum Beobachtungstermin I
            #     dd14	Windrichtung in 32 Sektoren zum Beobachtungstermin II
            #     dd19	Windrichtung in 32 Sektoren zum Beobachtungstermin III
            #     druck07	Luftdruck zum Beobachtungstermin I	hPa
            #     druck14	Luftdruck zum Beobachtungstermin II	hPa
            #     druck19	Luftdruck zum Beobachtungstermin III	hPa
            #     erdb07	Erdbodenzustand zum Beobachtungstermin I	Code
            #     erdb14	Erdbodenzustand zum Beobachtungstermin II	Code
            #     erdb19	Erdbodenzustand zum Beobachtungstermin III	Code
            #     nied07	Niederschlagssumme 19:01 MEZ Vortag - 07:00 MEZ	mm
            #     nied07a	Niederschlagsart 19:01 MEZ Vortag - 07:00 MEZ	Code
            #     nied19	Niederschlagssumme 7:01 MEZ - 19:00 MEZ	mm
            #     nied19a	Niederschlagsart 7:01 MEZ - 19:00 MEZ	Code
            #     nieda	Niederschlagsart 7:01 MEZ - 7:00 MEZ Folgetag	Code
            #     qflag	DCT Information	Code
            #     rel07	Relative Feuchte zum Beobachtungstermin I	%
            #     rel07_b	Relative Feuchte berechnet zum Beobachtungstermin I	%
            #     rel14	Relative Feuchte zum Beobachtungstermin II	%
            #     rel14_b	Relative Feuchte berechnet zum Beobachtungstermin II	%
            #     rel19	Relative Feuchte zum Beobachtungstermin III	%
            #     rel19_b	Relative Feuchte berechnet zum Beobachtungstermin III	%
            #     rel_b	Relative Feuchte berechnet Tagesmittel	%
            #     schnee_a	Schneeart zum Beobachtungstermin I	Code
            #     sicht07	Sichtweite zum Beobachtungstermin I	m
            #     sicht14	Sichtweite zum Beobachtungstermin II	m
            #     sicht19	Sichtweite zum Beobachtungstermin III	m
            #     t14	Lufttemperatur 2m zum Beobachtungstermin II	°C
            #     t19	Lufttemperatur 2m zum Beobachtungstermin III	°C
            #     t7	Lufttemperatur 2m zum Beobachtungstermin I	°C
            #     typ	Qualitätstyp	Code
            #     vv07	Windstärke zum Beobachtungstermin I	Beaufort
            #     vv14	Windstärke zum Beobachtungstermin II	Beaufort
            #     vv19	Windstärke zum Beobachtungstermin III	Beaufort
            #     vvmaxz	Windstärke - Zeit des Tagesmaximums

        HUMIDITY = DAILY.HUMIDITY
        PRECIPITATION_HEIGHT = DAILY.PRECIPITATION_HEIGHT
        PRESSURE_AIR_SITE = DAILY.PRESSURE_AIR_SITE
        PRESSURE_VAPOR = DAILY.PRESSURE_VAPOR
        RADIATION_GLOBAL = DAILY.RADIATION_GLOBAL
        SNOW_DEPTH = DAILY.SNOW_DEPTH
        SNOW_DEPTH_NEW = DAILY.SNOW_DEPTH_NEW
        SUNSHINE_DURATION = DAILY.SUNSHINE_DURATION
        TEMPERATURE_AIR_MAX_200 = DAILY.TEMPERATURE_AIR_MAX_200
        TEMPERATURE_AIR_MEAN_200 = DAILY.TEMPERATURE_AIR_MEAN_200
        TEMPERATURE_AIR_MIN_200 = DAILY.TEMPERATURE_AIR_MIN_200
        TEMPERATURE_AIR_MIN_005 = DAILY.TEMPERATURE_AIR_MIN_005
        WIND_GUST_MAX = DAILY.WIND_GUST_MAX
        WIND_SPEED = DAILY.WIND_SPEED

    class MONTHLY(DatasetTreeCore):
        class MONTHLY(Enum):
            HUMIDITY = "rel"  # Relative Feuchte Monatsmittel %
            PRECIPITATION_HEIGHT = "rsum"  # Monatssumme des Niederschlags mm
            PRECIPITATION_HEIGHT_MAX = "rmax"  # größte Tagesniederschlagssumme eines Monats mm
            PRESSURE_AIR_SITE = "p"  # Luftdruck Monatsmittel hPa
            PRESSURE_AIR_SITE_MAX = "pmax"  # Luftdruck Monatsmaximum hPa
            PRESSURE_AIR_SITE_MIN = "pmin"  # Luftdruck Monatsmainimum hPa
            PRESSURE_VAPOR = "e"  # Dampfdruck Monatsmittel aller Beobachtungstermine I,II,III hPa
            RADIATION_GLOBAL = "global"  # Monatssumme der Globalstrahlung J/cm²
            SNOW_DEPTH_NEW = "nsch"  # Neuschneehöhe Monatssumme cm
            SNOW_DEPTH_NEW_MAX = "nschmax"  # Neuschneehöhe Monatsmaximum der Tageswerte cm
            SNOW_DEPTH_MAX = "schmax"  # Maximale Tagesschneehöhe cm
            SUNSHINE_DURATION = "s"  # Monatssumme der Sonnenscheindauer h
            SUNSHINE_DURATION_RELATIVE = "sp"  # Anteil der Sonnenscheindauer zur effektiv möglichen Sonnenscheindauer %
            TEMPERATURE_AIR_MAX_200 = "tmax"  # Lufttemperatur 2m Monatsmaximum °C
            TEMPERATURE_AIR_MAX_200_MEAN = "mtmax"  # Lufttemperatur 2m Monatsmittel aller Tagesmaxima °C
            TEMPERATURE_AIR_MEAN_005 = "t5m"  # Lufttemperatur +5cm Monatsmittel °C
            TEMPERATURE_AIR_MEAN_200 = "t"  # Lufttemperatur 2m Monatsmittel °C
            TEMPERATURE_AIR_MIN_005 = "t5min"  # Lufttemperatur +5cm Monatsminimum °C
            TEMPERATURE_AIR_MIN_200 = "tmin"  # Lufttemperatur 2m Monatsminimum °C
            TEMPERATURE_AIR_MIN_200_MEAN = "mtmin"  # Lufttemperatur 2m Monatsmittel aller Tagesminima °C
            TEMPERATURE_DEW_POINT_MEAN_200 = "Tautemp"  # Taupunkt Monatsmittel °C
            TEMPERATURE_SOIL_MAX_010 = "maxe10"  # Erdbodentemperatur -10cm Monatsmaximum °C
            TEMPERATURE_SOIL_MAX_020 = "maxe20"  # Erdbodentemperatur -20cm Monatsmaximum °C
            TEMPERATURE_SOIL_MAX_050 = "maxe50"  # Erdbodentemperatur -50cm Monatsmaximum °C
            TEMPERATURE_SOIL_MAX_100 = "maxe100"  # Erdbodentemperatur -100cm Monatsmaximum °C
            TEMPERATURE_SOIL_MAX_200 = "maxe200"  # Erdbodentemperatur -200cm Monatsmaximum °C
            TEMPERATURE_SOIL_MEAN_010 = "e10"  # Erdbodentemperatur -10cm Monatsmittel °C
            TEMPERATURE_SOIL_MEAN_020 = "e20"  # Erdbodentemperatur -20cm Monatsmittel °C
            TEMPERATURE_SOIL_MEAN_050 = "e50"  # Erdbodentemperatur -50cm Monatsmittel °C
            TEMPERATURE_SOIL_MEAN_100 = "e100"  # Erdbodentemperatur -100cm Monatsmittel °C
            TEMPERATURE_SOIL_MEAN_200 = "e200"  # Erdbodentemperatur -200cm Monatsmittel °C
            TEMPERATURE_SOIL_MIN_010 = "mine10"  # Erdbodentemperatur -10cm Monatsminimum °C
            TEMPERATURE_SOIL_MIN_020 = "mine20"  # Erdbodentemperatur -20cm Monatsminimum °C
            TEMPERATURE_SOIL_MIN_050 = "mine50"  # Erdbodentemperatur -50cm Monatsminimum °C
            TEMPERATURE_SOIL_MIN_100 = "mine100"  # Erdbodentemperatur -100cm Monatsminimum °C
            TEMPERATURE_SOIL_MIN_200 = "mine200"  # Erdbodentemperatur -200cm Monatsminimum °C
            WIND_SPEED = "vv"  # Windgeschwindigkeit Monatsmittel m/s
            # Not (yet) implemented parameters:
            #     b	Bewölkungsmenge Monatsmittel aller Beobachtungstermine I,II,III	1/100
            #     b14	Bewölkungsmenge Monatsmittel der Beobachtungstermine II	1/100
            #     b19	Bewölkungsmenge Monatsmittel der Beobachtungstermine III	1/100
            #     b7	Bewölkungsmenge Monatsmittel der Beobachtungstermine I	1/100
            #     ddc	Anzahl der Beobachtungstermine mit Calmen
            #     dde	Anzahl der Beobachtungstermine mit Windrichtung O
            #     ddn	Anzahl der Beobachtungstermine mit Windrichtung N
            #     ddne	Anzahl der Beobachtungstermine mit Windrichtung NO
            #     ddnw	Anzahl der Beobachtungstermine mit Windrichtung NW
            #     dds	Anzahl der Beobachtungstermine mit Windrichtung S
            #     ddse	Anzahl der Beobachtungstermine mit Windrichtung SO
            #     ddsw	Anzahl der Beobachtungstermine mit Windrichtung SW
            #     ddw	Anzahl der Beobachtungstermine mit Windrichtung W
            #     e14	Dampfdruck Monatsmittel der Beobachtungstermine II	hPa
            #     e19	Dampfdruck Monatsmittel der Beobachtungstermine III	hPa
            #     e7	Dampfdruck Monatsmittel der Beobachtungstermine I	hPa
            #     eis	Zahl der Eistage
            #     eschwuel	Zahl der etwas schwülen Tage
            #     festrr	Monatsssumme des festen Niederschlags	mm
            #     festrrp	Anteil des festen Niederschlags am Gesamtniederschlag	%
            #     frost	Zahl der Frosttage
            #     gew	Zahl der Tage mit Gewitter
            #     gradt	Gradtagszahl 20/12	°C
            #     graupel	Zahl der Tage mit Graupel
            #     hagel	Zahl der Tage mit Hagel
            #     heit	Zahl der heiteren Tage
            #     ht	Zahl der Heiztage
            #     n01	Zahl der Tage mit Niederschlag >= 0.1mm
            #     n1	Zahl der Tage mit Niederschlag >= 1mm
            #     n10	Zahl der Tage mit Niederschlag >= 10mm
            #     n5	Zahl der Tage mit Niederschlag >= 5mm
            #     nebel	Zahl der Tage mit Nebel
            #     nschmaxt	Neuschneehöhe Tag des Monatsmaximums
            #     qflag	Qualitätsflag	Code
            #     r15	Niederschlag Zahl der Tage >=15mm
            #     r20	Niederschlag Zahl der Tage >=20mm
            #     r30	Niederschlag Zahl der Tage >=30mm
            #     raureif	Zahl der Tage mit Raureif
            #     reif	Zahl der Tage mit Reif
            #     rel14	Relative Feuchte Monatsmittel der Beobachtungstermine II	%
            #     rel19	Relative Feuchte Monatsmittel der Beobachtungstermine III	%
            #     rel7	Relative Feuchte Monatsmittel der Beobachtungstermine I	%
            #     rk1	Niederschlag Zahl der Tage >=0.1 und <=2.4mm
            #     rk2	Niederschlag Zahl der Tage >=2.5 und <=4.9mm
            #     rk3	Niederschlag Zahl der Tage >=5.0 und <=9.9mm
            #     rk4	Niederschlag Zahl der Tage >=10.0 und <=19.9mm
            #     rk5	Niederschlag Zahl der Tage >=20.0 und <=49.9mm
            #     rk6	Niederschlag Zahl der Tage >=50.0mm
            #     rmaxt	Tag des Niederschlagsmaximums eines Monats
            #     rsum19	12 stündige Monatssumme des Niederschlags 7-19 Uhr	mm
            #     rsum7	12 stündige Monatssumme des Niederschlags 19-7 Uhr	mm
            #     sch1	Zahl der Tage mit Schneehöhen >= 1 cm
            #     sch10	Zahl der Tage mit Schneedecke >= 10 cm
            #     sch100	Zahl der Tage mit Schneehöhen >=100 cm
            #     sch15	Zahl der Tage mit Schneehöhen >= 15 cm
            #     sch20	Zahl der Tage mit Schneehöhen >= 20 cm
            #     sch30	Zahl der Tage mit Schneehöhen >= 30 cm
            #     sch5	Zahl der Tage mit Schneehöhen >= 5 cm
            #     sch50	Zahl der Tage mit Schneehöhen >= 50 cm
            #     schdeck	Zahl der Tage mit Schneedecke
            #     schfall	Zahl der Tage mit Schneefall
            #     schoenw	Zahl der Schönwettertage
            #     schreg	Zahl der Tage mit Schneefall und Regen
            #     schwuel	Zahl der schwülen Tage
            #     sicht0	Zahl der Termine mit Sicht <=200 m
            #     sicht1	Zahl der Termine mit Sicht >200 <=500 m
            #     sicht2	Zahl der Termine mit Sicht >500 <=1000 m
            #     sicht3	Zahl der Termine mit Sicht >1000 <=2000 m
            #     sicht3a	Zahl der Termine mit Sicht >2000 <=10000 m
            #     sicht4	Zahl der Termine mit Sicht >10000 <=20000 m
            #     sicht5	Zahl der Termine mit Sicht >20000 <=50000 m
            #     sicht6	Zahl der Termine mit Sicht >50000 m
            #     sommer	Zahl der Sommertage
            #     sonn0	Zahl der Tage ohne Sonnenschein
            #     sonn1	Zahl der Tage mit Sonnenschein >= 1h
            #     sonn10	Zahl der Tage mit Sonnenschein >= 10h
            #     sonn5	Zahl der Tage mit Sonnenschein >= 5h
            #     stFrost	Zahl der Tage mit strengem Frost
            #     t14	Lufttemperatur 2m Monatsmittel der Beobachtungstermine II	°C
            #     t19	Lufttemperatur 2m Monatsmittel der Beobachtungstermine III	°C
            #     t5mint	Lufttemperatur +5cm Tag des Monatsminimums
            #     t7	Lufttemperatur 2m Monatsmittel der Beobachtungstermine I	°C
            #     tau	Zahl der Tage mit Tau
            #     temp10	Lufttemperatur 2m Zahl der Tage mit 10 °C <= Tagesmittel
            #     temp15	Lufttemperatur 2m Zahl der Tage mit 15 °C <= Tagesmittel
            #     temp20	Lufttemperatur 2m Zahl der Tage mit 20 °C <= Tagesmittel
            #     temp25	Lufttemperatur 2m Zahl der Tage mit 25 °C <= Tagesmittel
            #     temp5	Lufttemperatur 2m Zahl der Tage mit 5 °C <= Tagesmittel
            #     tempn5	Lufttemperatur 2m Zahl der Tage mit -5 °C < Tagesmittel
            #     tk0	Lufttemperatur 2m Zahl der Tage mit Tagesmittel < -25 °C
            #     tk1	Lufttemperatur 2m Zahl der Tage mit -25 °C <= Tagesmittel < -20 °C
            #     tk10	Lufttemperatur 2m Zahl der Tage mit 20 °C <= Tagesmittel < 25 °C
            #     tk2	Lufttemperatur 2m Zahl der Tage mit -20 °C <= Tagesmittel < -15 °C
            #     tk3	Lufttemperatur 2m Zahl der Tage mit -15 °C <= Tagesmittel < -10 °C
            #     tk4	Lufttemperatur 2m Zahl der Tage mit -10 °C <= Tagesmittel < -5 °C
            #     tk5	Lufttemperatur 2m Zahl der Tage mit -5 °C <= Tagesmittel < 0 °C
            #     tk6	Lufttemperatur 2m Zahl der Tage mit 0 °C <= Tagesmittel < 5 °C
            #     tk7	Lufttemperatur 2m Zahl der Tage mit 5 °C <= Tagesmittel < 10 °C
            #     tk8	Lufttemperatur 2m Zahl der Tage mit 10 °C <= Tagesmittel < 15 °C
            #     tk9	Lufttemperatur 2m Zahl der Tage mit 15 °C <= Tagesmittel < 20 °C
            #     tmaxe10	Erdbodentemperatur -10cm Tag des Monatsmaximums
            #     tmaxe100	Erdbodentemperatur -100cm Tag des Monatsmaximums
            #     tmaxe20	Erdbodentemperatur -20cm Tag des Monatsmaximums
            #     tmaxe200	Erdbodentemperatur -200cm Tag des Monatsmaximums
            #     tmaxe50	Erdbodentemperatur -50cm Tag des Monatsmaximums
            #     tmaxt	Lufttemperatur 2m Tag des Monatsmaximums
            #     tmine10	Erdbodentemperatur -10cm Tag des Monatsminimums
            #     tmine100	Erdbodentemperatur -100cm Tag des Monatsminimums
            #     tmine20	Erdbodentemperatur -20cm Tag des Monatsminimums
            #     tmine200	Erdbodentemperatur -200cm Tag des Monatsminimums
            #     tmine50	Erdbodentemperatur -50cm Tag des Monatsminimums
            #     tmint	Lufttemperatur 2m Tag des Monatsminimums
            #     tropen	Zahl der Tropentage
            #     trueb	Zahl der trüben Tage
            #     typ	Qualitätstyp
            #     v100	Windgeschwindigkeit Zahl der Tage mit Böen >= 100 km/h
            #     v60	Windgeschwindigkeit Zahl der Tage mit Böen >= 60 km/h
            #     v70	Windgeschwindigkeit Zahl der Tage mit Böen >= 70 km/h
            #     v80	Windgeschwindigkeit Zahl der Tage mit Böen >= 80 km/h
            #     w6	Windgeschwindigkeit Zahl der Tage mit Windstärke >= 6 Bft
            #     w8	Windgeschwindigkeit Zahl der Tage mit Windstärke >= 8 Bft

        HUMIDITY = MONTHLY.HUMIDITY
        PRECIPITATION_HEIGHT = MONTHLY.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_MAX = MONTHLY.PRECIPITATION_HEIGHT_MAX
        PRESSURE_AIR_SITE = MONTHLY.PRESSURE_AIR_SITE
        PRESSURE_AIR_SITE_MAX = MONTHLY.PRESSURE_AIR_SITE_MAX
        PRESSURE_AIR_SITE_MIN = MONTHLY.PRESSURE_AIR_SITE_MIN
        PRESSURE_VAPOR = MONTHLY.PRESSURE_VAPOR
        RADIATION_GLOBAL = MONTHLY.RADIATION_GLOBAL
        SNOW_DEPTH_NEW = MONTHLY.SNOW_DEPTH_NEW
        SNOW_DEPTH_NEW_MAX = MONTHLY.SNOW_DEPTH_NEW_MAX
        SNOW_DEPTH_MAX = MONTHLY.SNOW_DEPTH_MAX
        SUNSHINE_DURATION = MONTHLY.SUNSHINE_DURATION
        SUNSHINE_DURATION_RELATIVE = MONTHLY.SUNSHINE_DURATION_RELATIVE
        TEMPERATURE_AIR_MAX_200 = MONTHLY.TEMPERATURE_AIR_MAX_200
        TEMPERATURE_AIR_MAX_200_MEAN = MONTHLY.TEMPERATURE_AIR_MAX_200_MEAN
        TEMPERATURE_AIR_MEAN_005 = MONTHLY.TEMPERATURE_AIR_MEAN_005
        TEMPERATURE_AIR_MEAN_200 = MONTHLY.TEMPERATURE_AIR_MEAN_200
        TEMPERATURE_AIR_MIN_005 = MONTHLY.TEMPERATURE_AIR_MIN_005
        TEMPERATURE_AIR_MIN_200 = MONTHLY.TEMPERATURE_AIR_MIN_200
        TEMPERATURE_AIR_MIN_200_MEAN = MONTHLY.TEMPERATURE_AIR_MIN_200_MEAN
        TEMPERATURE_DEW_POINT_MEAN_200 = MONTHLY.TEMPERATURE_DEW_POINT_MEAN_200
        TEMPERATURE_SOIL_MAX_010 = MONTHLY.TEMPERATURE_SOIL_MAX_010
        TEMPERATURE_SOIL_MAX_020 = MONTHLY.TEMPERATURE_SOIL_MAX_020
        TEMPERATURE_SOIL_MAX_050 = MONTHLY.TEMPERATURE_SOIL_MAX_050
        TEMPERATURE_SOIL_MAX_100 = MONTHLY.TEMPERATURE_SOIL_MAX_100
        TEMPERATURE_SOIL_MAX_200 = MONTHLY.TEMPERATURE_SOIL_MAX_200
        TEMPERATURE_SOIL_MEAN_010 = MONTHLY.TEMPERATURE_SOIL_MEAN_010
        TEMPERATURE_SOIL_MEAN_020 = MONTHLY.TEMPERATURE_SOIL_MEAN_020
        TEMPERATURE_SOIL_MEAN_050 = MONTHLY.TEMPERATURE_SOIL_MEAN_050
        TEMPERATURE_SOIL_MEAN_100 = MONTHLY.TEMPERATURE_SOIL_MEAN_100
        TEMPERATURE_SOIL_MEAN_200 = MONTHLY.TEMPERATURE_SOIL_MEAN_200
        TEMPERATURE_SOIL_MIN_010 = MONTHLY.TEMPERATURE_SOIL_MIN_010
        TEMPERATURE_SOIL_MIN_020 = MONTHLY.TEMPERATURE_SOIL_MIN_020
        TEMPERATURE_SOIL_MIN_050 = MONTHLY.TEMPERATURE_SOIL_MIN_050
        TEMPERATURE_SOIL_MIN_100 = MONTHLY.TEMPERATURE_SOIL_MIN_100
        TEMPERATURE_SOIL_MIN_200 = MONTHLY.TEMPERATURE_SOIL_MIN_200
        WIND_SPEED = MONTHLY.WIND_SPEED


class GeosphereObservationUnit(DatasetTreeCore):
    class MINUTE_10(DatasetTreeCore):
        class MINUTE_10(UnitEnum):
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value  # Niederschlag
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_METER.value, SIUnit.JOULE_PER_SQUARE_METER.value
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = (
                OriginUnit.JOULE_PER_SQUARE_METER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SUNSHINE_DURATION = OriginUnit.SECOND.value, SIUnit.SECOND.value
            TEMPERATURE_AIR_MAX_005 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_005 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_005 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_DEW_POINT_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_010 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_020 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_050 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_DIRECTION_GUST_MAX = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

    class HOURLY(DatasetTreeCore):
        class HOURLY(UnitEnum):
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value, SIUnit.JOULE_PER_SQUARE_METER.value
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            RADIATION_SKY_SHORT_WAVE_DIRECT = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            TEMPERATURE_AIR_MEAN_005 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_010 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_020 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_050 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_100 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_DEW_POINT_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_DIRECTION_GUST_MAX = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

    class DAILY(DatasetTreeCore):
        class DAILY(UnitEnum):
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value, SIUnit.JOULE_PER_SQUARE_METER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_005 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

    class MONTHLY(DatasetTreeCore):
        class MONTHLY(UnitEnum):
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SITE_MAX = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SITE_MIN = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value, SIUnit.JOULE_PER_SQUARE_METER.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH_NEW_MAX = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH_MAX = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            SUNSHINE_DURATION_RELATIVE = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MAX_200_MEAN = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_005 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_005 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_200_MEAN = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_DEW_POINT_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_010 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_020 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_050 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_100 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_010 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_020 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_050 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_100 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_010 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_020 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_050 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_100 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value


class GeosphereObservationDataset(Enum):
    MINUTE_10 = "klima-v1-10min"
    HOURLY = "klima-v1-1h"
    DAILY = "klima-v1-1d"
    MONTHLY = "klima-v1-1m"


class GeosphereObservationValues(TimeseriesValues):
    _data_tz = Timezone.UTC
    _endpoint = (
        "https://dataset.api.hub.zamg.ac.at/v1/station/historical/{resolution}?"
        "parameters={parameters}&"
        "start={start_date}&"
        "end={end_date}&"
        "station_ids={station_id}&"
        "output_format=geojson"
    )

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pl.DataFrame:
        if parameter == dataset:
            parameter = [par.value for par in self.sr._parameter_base[self.sr.resolution.name]]
        else:
            parameter = [parameter.value]
        start_date = self.sr.start_date - timedelta(days=1)
        end_date = self.sr.end_date + timedelta(days=1)
        url = self._endpoint.format(
            station_id=station_id,
            parameters=",".join(parameter),
            resolution=GeosphereObservationDataset[dataset.name].value,
            start_date=start_date.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%m"),
            end_date=end_date.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%m"),
        )
        response = download_file(url=url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        data_raw = json.loads(response.read())
        timestamps = data_raw.pop("timestamps")
        data = {Columns.DATE.value: timestamps}
        for par, par_dict in data_raw["features"][0]["properties"]["parameters"].items():
            data[par] = par_dict["data"]
        df = pl.DataFrame(data)
        df = df.melt(
            id_vars=[Columns.DATE.value], variable_name=Columns.PARAMETER.value, value_name=Columns.VALUE.value
        )
        if self.sr.resolution == Resolution.MINUTE_10:
            df = df.with_columns(
                pl.when(pl.col(Columns.PARAMETER.value).is_in(["GSX", "HSX"]))
                .then(pl.col(Columns.VALUE.value) * 600)
                .otherwise(pl.col(Columns.VALUE.value))
                .alias(Columns.VALUE.value)
            )
        return df.with_columns(
            pl.col(Columns.DATE.value).str.to_datetime("%Y-%m-%dT%H:%M+%Z").dt.replace_time_zone("UTC"),
            pl.col(Columns.PARAMETER.value).str.to_lowercase(),
            pl.lit(station_id).alias(Columns.STATION_ID.value),
            pl.lit(None, pl.Float64).alias(Columns.QUALITY.value),
        )


class GeosphereObservationRequest(TimeseriesRequest):
    _provider = Provider.GEOSPHERE
    _kind = Kind.OBSERVATION
    _tz = Timezone.AUSTRIA
    _dataset_base = GeosphereObservationDataset
    _parameter_base = GeosphereObservationParameter
    _unit_base = GeosphereObservationUnit
    _resolution_base = GeosphereObservationResolution
    _resolution_type = ResolutionType.MULTI
    _period_base = GeosphereObservationPeriod
    _period_type = PeriodType.FIXED
    _has_datasets = True
    _unique_dataset = True
    _data_range = DataRange.FIXED
    _values = GeosphereObservationValues

    _endpoint = "https://dataset.api.hub.zamg.ac.at/v1/station/historical/{dataset}/metadata/stations"
    # dates collected from ZAMG website, end date will be set to now if not given
    _default_start_dates = {
        "minute_10": "1992-01-01",
        "hourly": "1880-01-01",
        "daily": "1775-01-01",
        "monthly": "1767-01-01",
    }

    def __init__(
        self,
        parameter: List[Union[str, GeosphereObservationParameter, Parameter]],
        resolution: Union[str, GeosphereObservationResolution, Resolution],
        start_date: Optional[Union[str, dt.datetime]] = None,
        end_date: Optional[Union[str, dt.datetime]] = None,
        settings: Optional[Settings] = None,
    ):
        if not start_date or not end_date:
            res = parse_enumeration_from_template(resolution, self._resolution_base, Resolution)
            start_date = self._default_start_dates[res.name.lower()]
            end_date = datetime.now()
        super(GeosphereObservationRequest, self).__init__(
            parameter=parameter,
            resolution=resolution,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        dataset = self._dataset_base[self.resolution.name].value
        url = self._endpoint.format(dataset=dataset)
        response = download_file(url=url, settings=self.settings, ttl=CacheExpiry.METAINDEX)
        df = pl.read_csv(response).lazy()
        df = df.drop("Sonnenschein", "Globalstrahlung")
        df = df.rename(
            mapping={
                "id": Columns.STATION_ID.value,
                "Stationsname": Columns.NAME.value,
                "Länge [°E]": Columns.LONGITUDE.value,
                "Breite [°N]": Columns.LATITUDE.value,
                "Höhe [m]": Columns.HEIGHT.value,
                "Startdatum": Columns.START_DATE.value,
                "Enddatum": Columns.END_DATE.value,
                "Bundesland": Columns.STATE.value,
            }
        )
        return df.with_columns(
            pl.col(Columns.START_DATE.value).str.to_datetime(),
            pl.col(Columns.END_DATE.value).str.to_datetime(),
        )
