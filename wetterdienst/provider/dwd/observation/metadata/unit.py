# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.parameter import DatasetTreeCore


class DwdObservationUnit(DatasetTreeCore):
    # 1_minute
    class MINUTE_1(DatasetTreeCore):  # noqa
        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_HEIGHT_DROPLET = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_HEIGHT_ROCKER = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_FORM = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

    # 10_minutes
    class MINUTE_10(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRESSURE_AIR_STATION_HEIGHT = (
                OriginUnit.HECTOPASCAL.value,
                SIUnit.PASCAL.value,
            )
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_005 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_DEW_POINT_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # extreme_temperature
        class TEMPERATURE_EXTREME(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_MAX_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MAX_005 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_005 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # extreme_wind
        class WIND_EXTREME(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_GUST_MAX = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            WIND_SPEED_MIN = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            WIND_SPEED_ROLLING_MEAN_MAX = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            WIND_DIRECTION_MAX_VELOCITY = (
                OriginUnit.WIND_DIRECTION.value,
                SIUnit.WIND_DIRECTION.value,
            )

        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRECIPITATION_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_INDICATOR_WR = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

        # solar
        class SOLAR(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            RADIATION_SKY_DIFFUSE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            RADIATION_GLOBAL = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            RADIATION_SKY_LONG_WAVE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )

        # wind
        class WIND(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_SPEED = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.WIND_DIRECTION.value

    # hourly
    class HOURLY(DatasetTreeCore):
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value

        # cloud_type
        class CLOUD_TYPE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            CLOUD_COVER_TOTAL_INDICATOR = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_TYPE_LAYER1 = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_TYPE_LAYER1_ABBREVIATION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_HEIGHT_LAYER1 = OriginUnit.METER.value, SIUnit.METER.value
            CLOUD_COVER_LAYER1 = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            CLOUD_TYPE_LAYER2 = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_TYPE_LAYER2_ABBREVIATION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_HEIGHT_LAYER2 = OriginUnit.METER.value, SIUnit.METER.value
            CLOUD_COVER_LAYER2 = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            CLOUD_TYPE_LAYER3 = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_TYPE_LAYER3_ABBREVIATION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_HEIGHT_LAYER3 = OriginUnit.METER.value, SIUnit.METER.value
            CLOUD_COVER_LAYER3 = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            CLOUD_TYPE_LAYER4 = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_TYPE_LAYER4_ABBREVIATION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_HEIGHT_LAYER4 = OriginUnit.METER.value, SIUnit.METER.value
            CLOUD_COVER_LAYER4 = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value

        # cloudiness
        class CLOUDINESS(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL_INDICATOR = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value

        # dew_point
        class DEW_POINT(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_DEW_POINT_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_INDICATOR = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRECIPITATION_FORM = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

        # pressure
        class PRESSURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRESSURE_AIR_SEA_LEVEL = (
                OriginUnit.HECTOPASCAL.value,
                SIUnit.PASCAL.value,
            )
            PRESSURE_AIR_STATION_HEIGHT = (
                OriginUnit.HECTOPASCAL.value,
                SIUnit.PASCAL.value,
            )

        # soil_temperature
        class TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_002 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_005 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_010 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_020 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_050 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_100 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # solar
        class SOLAR(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            END_OF_INTERVAL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            RADIATION_SKY_LONG_WAVE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            RADIATION_GLOBAL = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            SUNSHINE_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value
            SUN_ZENITH = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            TRUE_LOCAL_TIME = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

        # sun
        class SUNSHINE_DURATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SUNSHINE_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value

        # visibility
        class VISIBILITY(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            VISIBILITY_INDICATOR = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            VISIBILITY = OriginUnit.METER.value, SIUnit.METER.value

        # wind
        class WIND(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_SPEED = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            WIND_DIRECTION = (
                OriginUnit.WIND_DIRECTION.value,
                SIUnit.WIND_DIRECTION.value,
            )

        # wind_synop
        class WIND_SYNOPTIC(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_SPEED = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            WIND_DIRECTION = (
                OriginUnit.WIND_DIRECTION.value,
                SIUnit.WIND_DIRECTION.value,
            )

        class MOISTURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            HUMIDITY_ABSOLUTE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_WET = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            PRESSURE_AIR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_DEW_POINT_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

    # subdaily
    class SUBDAILY(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value

        # cloudiness
        class CLOUDINESS(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            CLOUD_DENSITY = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

        # moisture
        class MOISTURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_AIR_005 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value

        # pressure
        class PRESSURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRESSURE_AIR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value

        # soil
        class SOIL(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_005 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # visibility
        class VISIBILITY(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            VISIBILITY = OriginUnit.METER.value, SIUnit.METER.value

        # wind
        class WIND(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.WIND_DIRECTION.value
            WIND_FORCE_BEAUFORT = OriginUnit.BEAUFORT.value, SIUnit.BEAUFORT.value

    # Daily
    class DAILY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            WIND_GUST_MAX = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            WIND_SPEED = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            QUALITY_GENERAL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_FORM = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_AIR_MAX_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_005 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_FORM = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value

        # soil_temperature
        class TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_002 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_005 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_010 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_020 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_050 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # solar
        class SOLAR(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            RADIATION_SKY_LONG_WAVE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            RADIATION_SKY_SHORT_WAVE_DIRECT = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value

        # water_equiv
        class WATER_EQUIVALENT(UnitEnum):  # noqa
            QN_6 = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SNOW_DEPTH_EXCELLED = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            WATER_EQUIVALENT_TOTAL_SNOW_DEPTH = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            WATER_EQUIVALENT_SNOW = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            FOG = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            THUNDER = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            STORM_STORMIER_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            DEW = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            GLAZE = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            RIPE = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SLEET = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            HAIL = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value

    # monthly
    class MONTHLY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_GENERAL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MAX_MEAN_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_MEAN_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            WIND_FORCE_BEAUFORT = OriginUnit.BEAUFORT.value, SIUnit.BEAUFORT.value
            TEMPERATURE_AIR_MAX_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            WIND_GUST_MAX = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            TEMPERATURE_AIR_MIN_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            QUALITY_PRECIPITATION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_HEIGHT_MAX = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            PRECIPITATION_HEIGHT_MAX = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            STORM_STORMIER_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            THUNDER = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            GLAZE = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SLEET = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            HAIL = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            FOG = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            DEW = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value

    # annual
    class ANNUAL(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_GENERAL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            TEMPERATURE_AIR_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MAX_MEAN_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_MEAN_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            WIND_FORCE_BEAUFORT = OriginUnit.BEAUFORT.value, SIUnit.BEAUFORT.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            WIND_GUST_MAX = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            TEMPERATURE_AIR_MAX_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_200 = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            QUALITY_PRECIPITATION = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            PRECIPITATION_HEIGHT_MAX = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            PRECIPITATION_HEIGHT_MAX = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            STORM_STORMIER_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            THUNDER = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            GLAZE = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SLEET = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            HAIL = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            FOG = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            DEW = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
