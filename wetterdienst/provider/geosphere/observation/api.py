# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

import polars as pl

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

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wetterdienst import Parameter, Settings

log = logging.getLogger(__name__)


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
            HUMIDITY = "rf"  # Relative Feuchte %
            PRECIPITATION_HEIGHT = "rr"  # Niederschlag mm
            PRECIPITATION_DURATION = "rrm"  # Niederschlagsdauer min
            PRESSURE_AIR_SITE = "P"  # Luftdruck hPa
            PRESSURE_AIR_SEA_LEVEL = "pred"  # Reduzierter Luftdruck hPa
            RADIATION_GLOBAL = "cglo"  # Globalstrahlung Mittelwert W/m²
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = "chim"  # Himmelsstrahlung/Diffusstrahlung Mittelwert in W/m²
            SNOW_DEPTH = "sh"  # Gesamtschneehöhe aus Schneepegelmessung cm
            SUNSHINE_DURATION = "so"  # Sonnenscheindauer s
            TEMPERATURE_AIR_MAX_0_05M = "tsmax"  # Lufttemperaturmaximum in 5cm °C
            TEMPERATURE_AIR_MAX_2M = "tlmax"  # Lufttemperaturmaximum in 2m °C
            TEMPERATURE_AIR_MEAN_0_05M = "ts"  # Lufttemperatur in 5cm °C
            TEMPERATURE_AIR_MEAN_2M = "tl"  # Lufttemperatur in 2m °C
            TEMPERATURE_AIR_MIN_0_05M = "tsmin"  # Lufttemperaturminimum in 5cm °C
            TEMPERATURE_AIR_MIN_2M = "tsmax"  # Lufttemperaturminimum in 2m °C
            TEMPERATURE_SOIL_MEAN_0_1M = "tb10"  # Erdbodentemperatur in 10cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_0_2M = "tb20"  # Erdbodentemperatur in 20cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_0_5M = "tb50"  # Erdbodentemperatur in 50cm Tiefe °C
            WIND_DIRECTION = "dd"  # Windrichtung °
            WIND_DIRECTION_GUST_MAX = "ddx"  # Windrichtung zum Böenspitzenwert °
            WIND_GUST_MAX = "ffx"  # maximale Windgeschwindigkeit m/s
            WIND_SPEED = "ff"  # vektorielle Windgeschwindigkeit m/s
            WIND_SPEED_ARITHMETIC = "ffam"  # vektorielle Windgeschwindigkeit in 10m Höhe m/s
            # Not (yet) implemented parameters:
            # Check dataset description and metadeta for more details (https://data.hub.geosphere.at/dataset/klima-v2-10min)

        HUMIDITY = MINUTE_10.HUMIDITY
        PRECIPITATION_HEIGHT = MINUTE_10.PRECIPITATION_HEIGHT
        PRECIPITATION_DURATION = MINUTE_10.PRECIPITATION_DURATION
        PRESSURE_AIR_SITE = MINUTE_10.PRESSURE_AIR_SITE
        PRESSURE_AIR_SEA_LEVEL = MINUTE_10.PRESSURE_AIR_SEA_LEVEL
        RADIATION_GLOBAL = MINUTE_10.RADIATION_GLOBAL
        RADIATION_SKY_SHORT_WAVE_DIFFUSE = MINUTE_10.RADIATION_SKY_SHORT_WAVE_DIFFUSE
        SNOW_DEPTH = MINUTE_10.SNOW_DEPTH
        SUNSHINE_DURATION = MINUTE_10.SUNSHINE_DURATION
        TEMPERATURE_AIR_MAX_0_05M = MINUTE_10.TEMPERATURE_AIR_MAX_0_05M
        TEMPERATURE_AIR_MAX_2M = MINUTE_10.TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_AIR_MEAN_0_05M = MINUTE_10.TEMPERATURE_AIR_MEAN_0_05M
        TEMPERATURE_AIR_MEAN_2M = MINUTE_10.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_AIR_MIN_0_05M = MINUTE_10.TEMPERATURE_AIR_MIN_0_05M
        TEMPERATURE_AIR_MIN_2M = MINUTE_10.TEMPERATURE_AIR_MIN_2M
        TEMPERATURE_SOIL_MEAN_0_1M = MINUTE_10.TEMPERATURE_SOIL_MEAN_0_1M
        TEMPERATURE_SOIL_MEAN_0_2M = MINUTE_10.TEMPERATURE_SOIL_MEAN_0_2M
        TEMPERATURE_SOIL_MEAN_0_5M = MINUTE_10.TEMPERATURE_SOIL_MEAN_0_5M
        WIND_DIRECTION = MINUTE_10.WIND_DIRECTION
        WIND_DIRECTION_GUST_MAX = MINUTE_10.WIND_DIRECTION_GUST_MAX
        WIND_GUST_MAX = MINUTE_10.WIND_GUST_MAX
        WIND_SPEED = MINUTE_10.WIND_SPEED
        WIND_SPEED_ARITHMETIC = MINUTE_10.WIND_SPEED_ARITHMETIC

    class HOURLY(DatasetTreeCore):
        class HOURLY(Enum):
            HUMIDITY = "rf"  # Relative Feuchte %
            PRECIPITATION_DURATION = "rrm"  # Niederschlagsdauer min
            PRECIPITATION_HEIGHT = "rr"  # Niederschlag mm
            PRESSURE_AIR_SEA_LEVEL = "pred"  # Luftdruck auf Meeresniveau reduziert hPa
            PRESSURE_AIR_SITE = "p"  # Luftdruck Stationsniveau hPa
            RADIATION_GLOBAL = "cglo"  # Globalstrahlung Mittelwert W/m²
            SNOW_DEPTH = "sh"  # Schneehöhe cm
            SUNSHINE_DURATION = "so_h"  # Sonnenscheindauer h
            TEMPERATURE_AIR_MEAN_2M = "tl"  # Lufttemperatur 2 meter °C
            TEMPERATURE_AIR_MIN_0_05M = "tsmin"  # Lufttemperatur 5cm Minimalwert °C
            TEMPERATURE_SOIL_MEAN_0_1M = "tb10"  # Erdbodentemperatur in 10 cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_0_2M = "tb20"  # Erdbodentemperatur in 20 cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_0_5M = "tb50"  # Erdbodentemperatur in 50 cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_1M = "tb100"  # Erdbodentemperatur in 100 cm Tiefe °C
            TEMPERATURE_SOIL_MEAN_2M = "tb200"  # Erdbodentemperatur in 200 cm Tiefe °C
            WIND_DIRECTION = "dd"  # Windrichtung 360° Mittelwert °
            WIND_DIRECTION_GUST_MAX = "ddx"  # Windrichtung zur Spitzenböe °
            WIND_GUST_MAX = "ffx"  # Maximale Windgeschwindigkeit (Spitzenböe) m/s
            WIND_SPEED = "ff"  # vektorielle Windgeschwindigkeit m/s
            # Not (yet) implemented parameters:
            # Check dataset description and metadeta for more details (https://data.hub.geosphere.at/dataset/klima-v2-1h)

        HUMIDITY = HOURLY.HUMIDITY
        PRECIPITATION_DURATION = HOURLY.PRECIPITATION_DURATION
        PRECIPITATION_HEIGHT = HOURLY.PRECIPITATION_HEIGHT
        PRESSURE_AIR_SEA_LEVEL = HOURLY.PRESSURE_AIR_SEA_LEVEL
        PRESSURE_AIR_SITE = HOURLY.PRESSURE_AIR_SITE
        RADIATION_GLOBAL = HOURLY.RADIATION_GLOBAL
        SNOW_DEPTH = HOURLY.SNOW_DEPTH
        SUNSHINE_DURATION = HOURLY.SUNSHINE_DURATION
        TEMPERATURE_AIR_MEAN_2M = HOURLY.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_AIR_MIN_0_05M = HOURLY.TEMPERATURE_AIR_MIN_0_05M
        TEMPERATURE_SOIL_MEAN_0_1M = HOURLY.TEMPERATURE_SOIL_MEAN_0_1M
        TEMPERATURE_SOIL_MEAN_0_2M = HOURLY.TEMPERATURE_SOIL_MEAN_0_2M
        TEMPERATURE_SOIL_MEAN_0_5M = HOURLY.TEMPERATURE_SOIL_MEAN_0_5M
        TEMPERATURE_SOIL_MEAN_1M = HOURLY.TEMPERATURE_SOIL_MEAN_1M
        TEMPERATURE_SOIL_MEAN_2M = HOURLY.TEMPERATURE_SOIL_MEAN_2M
        WIND_DIRECTION = HOURLY.WIND_DIRECTION
        WIND_DIRECTION_GUST_MAX = HOURLY.WIND_DIRECTION_GUST_MAX
        WIND_GUST_MAX = HOURLY.WIND_GUST_MAX
        WIND_SPEED = HOURLY.WIND_SPEED

    class DAILY(DatasetTreeCore):
        class DAILY(Enum):
            CLOUD_COVER_TOTAL = (
                "bewm_mittel"  # Bewölkungsmenge, Tagesmittelwert berechnet aus den Beobachtungsterminen I,II,III 1/100
            )
            HUMIDITY = "rf_mittel"  # Relative Feuchte Tagesmittel aus den Beobachtungsterminen I,II,III %
            PRECIPITATION_HEIGHT = "rr"  # Niederschlagssumme 24h mm
            PRESSURE_AIR_SITE = "p_mittel"  # Luftdruck Tagesmittel aus den Beobachtungsterminen I,II,III hPa
            PRESSURE_VAPOR = "dampf_mittel"  # Dampfdruck Tagesmittel aus den Beobachtungsterminen I,II,III hPa
            RADIATION_GLOBAL = "cglo_j"  # Globalstrahlung 24h-Summe J/cm²
            SNOW_DEPTH = "sh"  # Gesamtschneehöhe zum Beobachtungstermin I cm
            SNOW_DEPTH_MANUAL = "sh_manu"  # Gesamtschneehhöhe, Handmessung cm
            SNOW_DEPTH_NEW = "shneu_manu"  # Neuschneehöhe, Handmessung zum Beobachtungstermin I cm
            SUNSHINE_DURATION = "so_h"  # Sonnenscheindauer 24h-Summe h
            TEMPERATURE_AIR_MAX_2M = "tlmax"  # Lufttemperatur 2m Maximum °C
            TEMPERATURE_AIR_MEAN_2M = "tl_mittel"  # Lufttemperaturmittel 2m °C
            TEMPERATURE_AIR_MIN_2M = "tlmin"  # Lufttemperatur 2m Minimum °C
            TEMPERATURE_AIR_MIN_0_05M = "tsmin"  # 5 cm Lufttemperatur Minimum °C
            WIND_GUST_MAX = "ffx"  # Maximale Windgeschwindigkeit (Spitzenböe) m/s
            WIND_SPEED = "vv_mittel"  # Windgeschwindigkeit Tagesmittel m/s
            # Not (yet) implemented parameters:
            # Check dataset description and metadeta for more details (https://data.hub.geosphere.at/dataset/klima-v2-1d)

        CLOUD_COVER_TOTAL = DAILY.CLOUD_COVER_TOTAL
        HUMIDITY = DAILY.HUMIDITY
        PRECIPITATION_HEIGHT = DAILY.PRECIPITATION_HEIGHT
        PRESSURE_AIR_SITE = DAILY.PRESSURE_AIR_SITE
        PRESSURE_VAPOR = DAILY.PRESSURE_VAPOR
        RADIATION_GLOBAL = DAILY.RADIATION_GLOBAL
        SNOW_DEPTH = DAILY.SNOW_DEPTH
        SNOW_DEPTH_MANUAL = DAILY.SNOW_DEPTH_MANUAL
        SNOW_DEPTH_NEW = DAILY.SNOW_DEPTH_NEW
        SUNSHINE_DURATION = DAILY.SUNSHINE_DURATION
        TEMPERATURE_AIR_MAX_2M = DAILY.TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_AIR_MEAN_2M = DAILY.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_AIR_MIN_2M = DAILY.TEMPERATURE_AIR_MIN_2M
        TEMPERATURE_AIR_MIN_0_05M = DAILY.TEMPERATURE_AIR_MIN_0_05M
        WIND_GUST_MAX = DAILY.WIND_GUST_MAX
        WIND_SPEED = DAILY.WIND_SPEED

    class MONTHLY(DatasetTreeCore):
        class MONTHLY(Enum):
            CLOUD_COVER_TOTAL = "bewm_mittel"  # Bewölkungsmittel aller Beobachtungstermine
            HUMIDITY = "rf_mittel"  # Relative Feuchte Monatsmittel %
            PRECIPITATION_HEIGHT = "rr"  # Monatssumme des Niederschlags mm
            PRECIPITATION_HEIGHT_MAX = "rr_max"  # größte Tagesniederschlagssumme eines Monats mm
            PRESSURE_AIR_SITE = "p"  # Luftdruck Monatsmittel hPa
            PRESSURE_AIR_SITE_MAX = "pmax"  # Luftdruck Monatsmaximum hPa
            PRESSURE_AIR_SITE_MIN = "pmin"  # Luftdruck Monatsmainimum hPa
            PRESSURE_VAPOR = "dampf_mittel"  # Dampfdruck, Monats-Mittelwert aus Tageswerten hPa
            RADIATION_GLOBAL = "cglo_j"  # Monatssumme der Globalstrahlung J/cm²
            SNOW_DEPTH_NEW = "shneu_manu"  # Neuschneehöhe Monatssumme cm
            SNOW_DEPTH_NEW_MAX = "shneu_manu_max"  # Neuschneehöhe Monatsmaximum der Tageswerte cm
            SNOW_DEPTH_MAX = "sh_manu_max"  # Gesamtschneehöhe, Monats-Maximum der Tageswerte cm
            SUNSHINE_DURATION = "so_h"  # Monatssumme der Sonnenscheindauer h
            SUNSHINE_DURATION_RELATIVE = (
                "so_r"  # Anteil der Sonnenscheindauer zur effektiv möglichen Sonnenscheindauer %
            )
            TEMPERATURE_AIR_MAX_2M = "tlmax"  # Lufttemperatur 2m Monatsmaximum °C
            TEMPERATURE_CONCRETE_MAX_0M = "bet0_max"  # Lufttemperatur Beton 0cm Monatsmaximal °C
            TEMPERATURE_AIR_MEAN_2M = "tl_mittel"  # Lufttemperatur 2m Monatsmittel °C
            TEMPERATURE_CONCRETE_MEAN_0M = "bet0"  # Lufttemperatur Beton 0cm Monatsmittel °C
            TEMPERATURE_AIR_MIN_2M = "tlmin"  # Lufttemperatur 2m Monatsminimum °C
            TEMPERATURE_CONCRETE_MIN_0M = "bet0_min"  # Lufttemperatur Beton 0cm Monatsminimum °C
            TEMPERATURE_SOIL_MAX_0_1M = "tb10_max"  # Erdbodentemperatur -10cm Monatsmaximum °C
            TEMPERATURE_SOIL_MAX_0_2M = "tb20_max"  # Erdbodentemperatur -20cm Monatsmaximum °C
            TEMPERATURE_SOIL_MAX_0_5M = "tb50_max"  # Erdbodentemperatur -50cm Monatsmaximum °C
            TEMPERATURE_SOIL_MAX_1M = "tb100_max"  # Erdbodentemperatur -100cm Monatsmaximum °C
            TEMPERATURE_SOIL_MAX_2M = "tb200_max"  # Erdbodentemperatur -200cm Monatsmaximum °C
            TEMPERATURE_SOIL_MEAN_0_1M = "tb10_mittel"  # Erdbodentemperatur -10cm Monatsmittel °C
            TEMPERATURE_SOIL_MEAN_0_2M = "tb20_mittel"  # Erdbodentemperatur -20cm Monatsmittel °C
            TEMPERATURE_SOIL_MEAN_0_5M = "tb50_mittel"  # Erdbodentemperatur -50cm Monatsmittel °C
            TEMPERATURE_SOIL_MEAN_1M = "tb100_mittel"  # Erdbodentemperatur -100cm Monatsmittel °C
            TEMPERATURE_SOIL_MEAN_2M = "tb200_mittel"  # Erdbodentemperatur -200cm Monatsmittel °C
            TEMPERATURE_SOIL_MIN_0_1M = "tb10_min"  # Erdbodentemperatur -10cm Monatsminimum °C
            TEMPERATURE_SOIL_MIN_0_2M = "tb20_min"  # Erdbodentemperatur -20cm Monatsminimum °C
            TEMPERATURE_SOIL_MIN_0_5M = "tb50_min"  # Erdbodentemperatur -50cm Monatsminimum °C
            TEMPERATURE_SOIL_MIN_1M = "tb100_min"  # Erdbodentemperatur -100cm Monatsminimum °C
            TEMPERATURE_SOIL_MIN_2M = "tb200_min"  # Erdbodentemperatur -200cm Monatsminimum °C
            WIND_SPEED = "vv_mittel"  # Windgeschwindigkeit Monatsmittel m/s
            # Not (yet) implemented parameters:
            # Check the dataset description and metadeta for more details (https://data.hub.geosphere.at/dataset/klima-v2-1m)

        CLOUD_COVER_TOTAL = MONTHLY.CLOUD_COVER_TOTAL
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
        TEMPERATURE_AIR_MAX_2M = MONTHLY.TEMPERATURE_AIR_MAX_2M
        TEMPERATURE_CONCRETE_MAX_0M = MONTHLY.TEMPERATURE_CONCRETE_MAX_0M
        TEMPERATURE_AIR_MEAN_2M = MONTHLY.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_CONCRETE_MEAN_0M = MONTHLY.TEMPERATURE_CONCRETE_MEAN_0M
        TEMPERATURE_AIR_MIN_2M = MONTHLY.TEMPERATURE_AIR_MIN_2M
        TEMPERATURE_CONCRETE_MIN_0M = MONTHLY.TEMPERATURE_CONCRETE_MIN_0M
        TEMPERATURE_SOIL_MAX_0_1M = MONTHLY.TEMPERATURE_SOIL_MAX_0_1M
        TEMPERATURE_SOIL_MAX_0_2M = MONTHLY.TEMPERATURE_SOIL_MAX_0_2M
        TEMPERATURE_SOIL_MAX_0_5M = MONTHLY.TEMPERATURE_SOIL_MAX_0_5M
        TEMPERATURE_SOIL_MAX_1M = MONTHLY.TEMPERATURE_SOIL_MAX_1M
        TEMPERATURE_SOIL_MAX_2M = MONTHLY.TEMPERATURE_SOIL_MAX_2M
        TEMPERATURE_SOIL_MEAN_0_1M = MONTHLY.TEMPERATURE_SOIL_MEAN_0_1M
        TEMPERATURE_SOIL_MEAN_0_2M = MONTHLY.TEMPERATURE_SOIL_MEAN_0_2M
        TEMPERATURE_SOIL_MEAN_0_5M = MONTHLY.TEMPERATURE_SOIL_MEAN_0_5M
        TEMPERATURE_SOIL_MEAN_1M = MONTHLY.TEMPERATURE_SOIL_MEAN_1M
        TEMPERATURE_SOIL_MEAN_2M = MONTHLY.TEMPERATURE_SOIL_MEAN_2M
        TEMPERATURE_SOIL_MIN_0_1M = MONTHLY.TEMPERATURE_SOIL_MIN_0_1M
        TEMPERATURE_SOIL_MIN_0_2M = MONTHLY.TEMPERATURE_SOIL_MIN_0_2M
        TEMPERATURE_SOIL_MIN_0_5M = MONTHLY.TEMPERATURE_SOIL_MIN_0_5M
        TEMPERATURE_SOIL_MIN_1M = MONTHLY.TEMPERATURE_SOIL_MIN_1M
        TEMPERATURE_SOIL_MIN_2M = MONTHLY.TEMPERATURE_SOIL_MIN_2M
        WIND_SPEED = MONTHLY.WIND_SPEED


class GeosphereObservationUnit(DatasetTreeCore):
    class MINUTE_10(DatasetTreeCore):
        class MINUTE_10(UnitEnum):
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value  # Niederschlag
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value, SIUnit.JOULE_PER_SQUARE_METER.value
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SUNSHINE_DURATION = OriginUnit.SECOND.value, SIUnit.SECOND.value
            TEMPERATURE_AIR_MAX_0_05M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MAX_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_0_05M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_0_05M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_5M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_DIRECTION_GUST_MAX = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED_ARITHMETIC = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

    class HOURLY(DatasetTreeCore):
        class HOURLY(UnitEnum):
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value, SIUnit.JOULE_PER_SQUARE_METER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_0_05M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_5M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_DIRECTION_GUST_MAX = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

    class DAILY(DatasetTreeCore):
        class DAILY(UnitEnum):
            CLOUD_COVER_TOTAL = OriginUnit.ONE_HUNDREDTH.value, SIUnit.ONE_HUNDREDTH.value
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value, SIUnit.JOULE_PER_SQUARE_METER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH_MANUAL = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            TEMPERATURE_AIR_MAX_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_0_05M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value

    class MONTHLY(DatasetTreeCore):
        class MONTHLY(UnitEnum):
            CLOUD_COVER_TOTAL = OriginUnit.ONE_HUNDREDTH.value, SIUnit.ONE_HUNDREDTH.value
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
            TEMPERATURE_AIR_MAX_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_CONCRETE_MAX_0M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_CONCRETE_MEAN_0M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_CONCRETE_MIN_0M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_0_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_0_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_0_5M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MAX_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_0_5M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_0_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_0_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_0_5M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_1M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_MIN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value


class GeosphereObservationDataset(Enum):
    MINUTE_10 = "klima-v2-10min"
    HOURLY = "klima-v2-1h"
    DAILY = "klima-v2-1d"
    MONTHLY = "klima-v2-1m"


class GeosphereObservationValues(TimeseriesValues):
    _data_tz = Timezone.UTC
    _endpoint = (
        "https://dataset.api.hub.geosphere.at/v1/station/historical/{resolution}?"
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
        log.info(f"Downloading file {url}.")
        response = download_file(url=url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        data_raw = json.loads(response.read())
        timestamps = data_raw.pop("timestamps")
        data = {Columns.DATE.value: timestamps}
        for par, par_dict in data_raw["features"][0]["properties"]["parameters"].items():
            data[par] = par_dict["data"]
        df = pl.DataFrame(data)
        df = df.unpivot(
            index=[Columns.DATE.value],
            variable_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
        )
        # adjust units for radiation parameters of 10 minute/hourly resolution from W / m² to J / cm²
        if self.sr.resolution == Resolution.MINUTE_10:
            df = df.with_columns(
                pl.when(pl.col(Columns.PARAMETER.value).is_in(["cglo", "chim"]))
                .then(pl.col(Columns.VALUE.value) * 600 / 10000)
                .otherwise(pl.col(Columns.VALUE.value))
                .alias(Columns.VALUE.value),
            )
        elif self.sr.resolution == Resolution.HOURLY:
            df = df.with_columns(
                pl.when(pl.col(Columns.PARAMETER.value).eq("cglo"))
                .then(pl.col(Columns.VALUE.value) * 3600 / 10000)
                .otherwise(pl.col(Columns.VALUE.value))
                .alias(Columns.VALUE.value),
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
        "minute_10": "1992-05-20",
        "hourly": "1880-03-31",
        "daily": "1774-12-31",
        "monthly": "1767-11-30",
    }

    def __init__(
        self,
        parameter: str
        | GeosphereObservationParameter
        | Parameter
        | Sequence[str | GeosphereObservationParameter | Parameter],
        resolution: str | GeosphereObservationResolution | Resolution,
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
        settings: Settings | None = None,
    ):
        if not start_date or not end_date:
            res = parse_enumeration_from_template(resolution, self._resolution_base, Resolution)
            if not start_date:
                # update start date only when it is not given
                start_date = self._default_start_dates[res.name.lower()]
            end_date = datetime.now()
        super().__init__(
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
        log.info(f"Downloading file {url}.")
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
            },
        )
        return df.with_columns(
            pl.col(Columns.START_DATE.value).str.to_datetime(),
            pl.col(Columns.END_DATE.value).str.to_datetime(),
        )
