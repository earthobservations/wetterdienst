# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.unit import MetricUnit, OriginUnit, UnitEnum
from wetterdienst.util.parameter import DatasetTreeCore


class DwdObservationUnitOrigin(DatasetTreeCore):
    # 1_minute
    class MINUTE_1(DatasetTreeCore):  # noqa
        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            PRECIPITATION_HEIGHT_DROPLET = OriginUnit.MILLIMETER.value
            PRECIPITATION_HEIGHT_ROCKER = OriginUnit.MILLIMETER.value
            PRECIPITATION_FORM = OriginUnit.DIMENSIONLESS.value

    # 10_minutes
    class MINUTE_10(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            PRESSURE_AIR_STATION_HEIGHT = OriginUnit.HECTOPASCAL.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_005 = OriginUnit.DEGREE_CELSIUS.value
            HUMIDITY = OriginUnit.PERCENT.value
            TEMPERATURE_DEW_POINT_200 = OriginUnit.DEGREE_CELSIUS.value

        # extreme_temperature
        class TEMPERATURE_EXTREME(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MAX_005 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MIN_005 = OriginUnit.DEGREE_CELSIUS.value

        # extreme_wind
        class WIND_EXTREME(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value
            WIND_SPEED_MIN = OriginUnit.METER_PER_SECOND.value
            WIND_SPEED_ROLLING_MEAN_MAX = OriginUnit.METER_PER_SECOND.value
            WIND_DIRECTION_MAX_VELOCITY = OriginUnit.WIND_DIRECTION.value

        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_DURATION = OriginUnit.MINUTE.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            PRECIPITATION_INDICATOR_WR = OriginUnit.DIMENSIONLESS.value

        # solar
        class SOLAR(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            RADIATION_SKY_DIFFUSE = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value
            RADIATION_SKY_LONG_WAVE = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value

        # wind
        class WIND(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value
            WIND_DIRECTION = OriginUnit.DEGREE.value

    # hourly
    class HOURLY(DatasetTreeCore):
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            HUMIDITY = OriginUnit.PERCENT.value

        # cloud_type
        class CLOUD_TYPE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value
            CLOUD_COVER_TOTAL_INDICATOR = OriginUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER1 = OriginUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER1_ABBREVIATION = OriginUnit.DIMENSIONLESS.value
            CLOUD_HEIGHT_LAYER1 = OriginUnit.METER.value
            CLOUD_COVER_LAYER1 = OriginUnit.ONE_EIGHTH.value
            CLOUD_TYPE_LAYER2 = OriginUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER2_ABBREVIATION = OriginUnit.DIMENSIONLESS.value
            CLOUD_HEIGHT_LAYER2 = OriginUnit.METER.value
            CLOUD_COVER_LAYER2 = OriginUnit.ONE_EIGHTH.value
            CLOUD_TYPE_LAYER3 = OriginUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER3_ABBREVIATION = OriginUnit.DIMENSIONLESS.value
            CLOUD_HEIGHT_LAYER3 = OriginUnit.METER.value
            CLOUD_COVER_LAYER3 = OriginUnit.ONE_EIGHTH.value
            CLOUD_TYPE_LAYER4 = OriginUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER4_ABBREVIATION = OriginUnit.DIMENSIONLESS.value
            CLOUD_HEIGHT_LAYER4 = OriginUnit.METER.value
            CLOUD_COVER_LAYER4 = OriginUnit.ONE_EIGHTH.value

        # cloudiness
        class CLOUDINESS(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL_INDICATOR = OriginUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value

        # dew_point
        class DEW_POINT(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_DEW_POINT_200 = OriginUnit.DEGREE_CELSIUS.value

        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            PRECIPITATION_INDICATOR = OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_FORM = OriginUnit.DIMENSIONLESS.value

        # pressure
        class PRESSURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.HECTOPASCAL.value
            PRESSURE_AIR_STATION_HEIGHT = OriginUnit.HECTOPASCAL.value

        # soil_temperature
        class TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_002 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_005 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_010 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_020 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_050 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_100 = OriginUnit.DEGREE_CELSIUS.value

        # solar
        class SOLAR(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            END_OF_INTERVAL = OriginUnit.DIMENSIONLESS.value
            RADIATION_SKY_LONG_WAVE = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value
            )
            RADIATION_GLOBAL = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value
            SUNSHINE_DURATION = OriginUnit.MINUTE.value
            SUN_ZENITH = OriginUnit.DEGREE.value
            TRUE_LOCAL_TIME = OriginUnit.DIMENSIONLESS.value

        # sun
        class SUNSHINE_DURATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            SUNSHINE_DURATION = OriginUnit.MINUTE.value

        # visibility
        class VISIBILITY(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            VISIBILITY_INDICATOR = OriginUnit.DIMENSIONLESS.value
            VISIBILITY = OriginUnit.METER.value

        # wind
        class WIND(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value
            WIND_DIRECTION = OriginUnit.WIND_DIRECTION.value

        # wind_synop
        class WIND_SYNOPTIC(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value
            WIND_DIRECTION = OriginUnit.WIND_DIRECTION.value

        class MOISTURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            HUMIDITY_ABSOLUTE = OriginUnit.DIMENSIONLESS.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value
            TEMPERATURE_WET = OriginUnit.DEGREE_CELSIUS.value
            PRESSURE_AIR = OriginUnit.HECTOPASCAL.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            HUMIDITY = OriginUnit.PERCENT.value
            TEMPERATURE_DEW_POINT_200 = OriginUnit.DEGREE_CELSIUS.value

    # subdaily
    class SUBDAILY(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            HUMIDITY = OriginUnit.PERCENT.value

        # cloudiness
        class CLOUDINESS(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value
            CLOUD_DENSITY = OriginUnit.DIMENSIONLESS.value

        # moisture
        class MOISTURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value
            TEMPERATURE_AIR_005 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            HUMIDITY = OriginUnit.PERCENT.value

        # pressure
        class PRESSURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            PRESSURE_AIR = OriginUnit.HECTOPASCAL.value

        # soil
        class SOIL(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_005 = OriginUnit.DEGREE_CELSIUS.value

        # visibility
        class VISIBILITY(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            VISIBILITY = OriginUnit.METER.value

        # wind
        class WIND(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            WIND_DIRECTION = OriginUnit.DEGREE.value
            WIND_FORCE_BEAUFORT = OriginUnit.BEAUFORT.value

    # Daily
    class DAILY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_WIND = OriginUnit.DIMENSIONLESS.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value
            QUALITY_GENERAL = OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            PRECIPITATION_FORM = OriginUnit.DIMENSIONLESS.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value
            PRESSURE_AIR = OriginUnit.HECTOPASCAL.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            HUMIDITY = OriginUnit.PERCENT.value
            TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MIN_005 = OriginUnit.DEGREE_CELSIUS.value

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            PRECIPITATION_FORM = OriginUnit.DIMENSIONLESS.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value

        # soil_temperature
        class TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_002 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_005 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_010 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_020 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_SOIL_050 = OriginUnit.DEGREE_CELSIUS.value

        # solar
        class SOLAR(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value
            RADIATION_SKY_LONG_WAVE = OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value
            )
            RADIATION_SKY_SHORT_WAVE_DIRECT = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value
            )
            SUNSHINE_DURATION = OriginUnit.HOUR.value

        # water_equiv
        class WATER_EQUIVALENT(UnitEnum):  # noqa
            QN_6 = OriginUnit.DIMENSIONLESS.value
            SNOW_DEPTH_EXCELLED = OriginUnit.CENTIMETER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value
            WATER_EQUIVALENT_TOTAL_SNOW_DEPTH = OriginUnit.MILLIMETER.value
            WATER_EQUIVALENT_SNOW = OriginUnit.MILLIMETER.value

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            FOG = OriginUnit.DIMENSIONLESS.value
            THUNDER = OriginUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = OriginUnit.DIMENSIONLESS.value
            STORM_STORMIER_WIND = OriginUnit.DIMENSIONLESS.value
            DEW = OriginUnit.DIMENSIONLESS.value
            GLAZE = OriginUnit.DIMENSIONLESS.value
            RIPE = OriginUnit.DIMENSIONLESS.value
            SLEET = OriginUnit.DIMENSIONLESS.value
            HAIL = OriginUnit.DIMENSIONLESS.value

    # monthly
    class MONTHLY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_GENERAL = OriginUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MAX_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MIN_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value
            WIND_FORCE_BEAUFORT = OriginUnit.BEAUFORT.value
            TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value
            TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value
            QUALITY_PRECIPITATION = OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value
            PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = OriginUnit.DIMENSIONLESS.value
            STORM_STORMIER_WIND = OriginUnit.DIMENSIONLESS.value
            THUNDER = OriginUnit.DIMENSIONLESS.value
            GLAZE = OriginUnit.DIMENSIONLESS.value
            SLEET = OriginUnit.DIMENSIONLESS.value
            HAIL = OriginUnit.DIMENSIONLESS.value
            FOG = OriginUnit.DIMENSIONLESS.value
            DEW = OriginUnit.DIMENSIONLESS.value

    # annual
    class ANNUAL(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_GENERAL = OriginUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value
            TEMPERATURE_AIR_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MAX_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MIN_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value
            WIND_FORCE_BEAUFORT = OriginUnit.BEAUFORT.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value
            TEMPERATURE_AIR_MAX_200 = OriginUnit.DEGREE_CELSIUS.value
            TEMPERATURE_AIR_MIN_200 = OriginUnit.DEGREE_CELSIUS.value
            QUALITY_PRECIPITATION = OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            SNOW_DEPTH_NEW = OriginUnit.CENTIMETER.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value
            PRECIPITATION_HEIGHT_MAX = OriginUnit.MILLIMETER.value

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = OriginUnit.DIMENSIONLESS.value
            STORM_STORMIER_WIND = OriginUnit.DIMENSIONLESS.value
            THUNDER = OriginUnit.DIMENSIONLESS.value
            GLAZE = OriginUnit.DIMENSIONLESS.value
            SLEET = OriginUnit.DIMENSIONLESS.value
            HAIL = OriginUnit.DIMENSIONLESS.value
            FOG = OriginUnit.DIMENSIONLESS.value
            DEW = OriginUnit.DIMENSIONLESS.value


class DwdObservationUnitSI(DatasetTreeCore):
    # 1_minute
    class MINUTE_1(DatasetTreeCore):  # noqa
        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_DROPLET = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_ROCKER = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_FORM = MetricUnit.DIMENSIONLESS.value

    # 10_minutes
    class MINUTE_10(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            PRESSURE_AIR_STATION_HEIGHT = MetricUnit.PASCAL.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_005 = MetricUnit.DEGREE_KELVIN.value
            HUMIDITY = MetricUnit.PERCENT.value
            TEMPERATURE_DEW_POINT_200 = MetricUnit.DEGREE_KELVIN.value

        # extreme_temperature
        class TEMPERATURE_EXTREME(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_MAX_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MAX_005 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_005 = MetricUnit.DEGREE_KELVIN.value

        # extreme_wind
        class WIND_EXTREME(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            WIND_GUST_MAX = MetricUnit.METER_PER_SECOND.value
            WIND_SPEED_MIN = MetricUnit.METER_PER_SECOND.value
            WIND_SPEED_ROLLING_MEAN_MAX = MetricUnit.METER_PER_SECOND.value
            WIND_DIRECTION_MAX_VELOCITY = MetricUnit.WIND_DIRECTION.value

        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            PRECIPITATION_DURATION = MetricUnit.SECOND.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_INDICATOR_WR = MetricUnit.DIMENSIONLESS.value

        # solar
        class SOLAR(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            RADIATION_SKY_DIFFUSE = MetricUnit.JOULE_PER_SQUARE_METER.value
            RADIATION_GLOBAL = MetricUnit.JOULE_PER_SQUARE_METER.value
            SUNSHINE_DURATION = MetricUnit.SECOND.value
            RADIATION_SKY_LONG_WAVE = MetricUnit.JOULE_PER_SQUARE_METER.value

        # wind
        class WIND(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            WIND_SPEED = MetricUnit.METER_PER_SECOND.value
            WIND_DIRECTION = MetricUnit.WIND_DIRECTION.value

    # hourly
    class HOURLY(DatasetTreeCore):
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            HUMIDITY = MetricUnit.PERCENT.value

        # cloud_type
        class CLOUD_TYPE(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = MetricUnit.PERCENT.value
            CLOUD_COVER_TOTAL_INDICATOR = MetricUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER1 = MetricUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER1_ABBREVIATION = MetricUnit.DIMENSIONLESS.value
            CLOUD_HEIGHT_LAYER1 = MetricUnit.METER.value
            CLOUD_COVER_LAYER1 = MetricUnit.PERCENT.value
            CLOUD_TYPE_LAYER2 = MetricUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER2_ABBREVIATION = MetricUnit.DIMENSIONLESS.value
            CLOUD_HEIGHT_LAYER2 = MetricUnit.METER.value
            CLOUD_COVER_LAYER2 = MetricUnit.PERCENT.value
            CLOUD_TYPE_LAYER3 = MetricUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER3_ABBREVIATION = MetricUnit.DIMENSIONLESS.value
            CLOUD_HEIGHT_LAYER3 = MetricUnit.METER.value
            CLOUD_COVER_LAYER3 = MetricUnit.PERCENT.value
            CLOUD_TYPE_LAYER4 = MetricUnit.DIMENSIONLESS.value
            CLOUD_TYPE_LAYER4_ABBREVIATION = MetricUnit.DIMENSIONLESS.value
            CLOUD_HEIGHT_LAYER4 = MetricUnit.METER.value
            CLOUD_COVER_LAYER4 = MetricUnit.PERCENT.value

        # cloudiness
        class CLOUDINESS(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL_INDICATOR = MetricUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = MetricUnit.PERCENT.value

        # dew_point
        class DEW_POINT(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_DEW_POINT_200 = MetricUnit.DEGREE_KELVIN.value

        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_INDICATOR = MetricUnit.DIMENSIONLESS.value
            PRECIPITATION_FORM = MetricUnit.DIMENSIONLESS.value

        # pressure
        class PRESSURE(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            PRESSURE_AIR_SEA_LEVEL = MetricUnit.PASCAL.value
            PRESSURE_AIR_STATION_HEIGHT = MetricUnit.PASCAL.value

        # soil_temperature
        class TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_002 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_005 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_010 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_020 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_050 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_100 = MetricUnit.DEGREE_KELVIN.value

        # solar
        class SOLAR(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            END_OF_INTERVAL = MetricUnit.DIMENSIONLESS.value
            RADIATION_SKY_LONG_WAVE = MetricUnit.JOULE_PER_SQUARE_METER.value
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = MetricUnit.JOULE_PER_SQUARE_METER.value
            RADIATION_GLOBAL = MetricUnit.JOULE_PER_SQUARE_METER.value
            SUNSHINE_DURATION = MetricUnit.SECOND.value
            SUN_ZENITH = MetricUnit.DEGREE.value
            TRUE_LOCAL_TIME = MetricUnit.DIMENSIONLESS.value

        # sun
        class SUNSHINE_DURATION(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            SUNSHINE_DURATION = MetricUnit.SECOND.value

        # visibility
        class VISIBILITY(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            VISIBILITY_INDICATOR = MetricUnit.DIMENSIONLESS.value
            VISIBILITY = MetricUnit.METER.value

        # wind
        class WIND(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            WIND_SPEED = MetricUnit.METER_PER_SECOND.value
            WIND_DIRECTION = MetricUnit.WIND_DIRECTION.value

        # wind_synop
        class WIND_SYNOPTIC(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            WIND_SPEED = MetricUnit.METER_PER_SECOND.value
            WIND_DIRECTION = MetricUnit.WIND_DIRECTION.value

        # moisture
        class MOISTURE(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            HUMIDITY_ABSOLUTE = MetricUnit.DIMENSIONLESS.value
            PRESSURE_VAPOR = MetricUnit.PASCAL.value
            TEMPERATURE_WET = MetricUnit.DEGREE_KELVIN.value
            PRESSURE_AIR = MetricUnit.PASCAL.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            HUMIDITY = MetricUnit.PERCENT.value
            TEMPERATURE_DEW_POINT_200 = MetricUnit.DEGREE_KELVIN.value

    # subdaily
    class SUBDAILY(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            HUMIDITY = MetricUnit.PERCENT.value

        # cloudiness
        class CLOUDINESS(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = MetricUnit.PERCENT.value
            CLOUD_DENSITY = MetricUnit.DIMENSIONLESS.value

        # moisture
        class MOISTURE(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            PRESSURE_VAPOR = MetricUnit.PASCAL.value
            TEMPERATURE_AIR_005 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            HUMIDITY = MetricUnit.PERCENT.value

        # pressure
        class PRESSURE(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            PRESSURE_AIR = MetricUnit.PASCAL.value

        # soil
        class SOIL(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_005 = MetricUnit.DEGREE_KELVIN.value

        # visibility
        class VISIBILITY(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            VISIBILITY = MetricUnit.METER.value

        # wind
        class WIND(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            WIND_DIRECTION = MetricUnit.WIND_DIRECTION.value
            WIND_FORCE_BEAUFORT = MetricUnit.BEAUFORT.value

    # Daily
    class DAILY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_WIND = MetricUnit.DIMENSIONLESS.value
            WIND_GUST_MAX = MetricUnit.METER_PER_SECOND.value
            WIND_SPEED = MetricUnit.METER_PER_SECOND.value
            QUALITY_GENERAL = MetricUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_FORM = MetricUnit.DIMENSIONLESS.value
            SUNSHINE_DURATION = MetricUnit.SECOND.value
            SNOW_DEPTH = MetricUnit.METER.value
            CLOUD_COVER_TOTAL = MetricUnit.PERCENT.value
            PRESSURE_VAPOR = MetricUnit.PASCAL.value
            PRESSURE_AIR = MetricUnit.PASCAL.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            HUMIDITY = MetricUnit.PERCENT.value
            TEMPERATURE_AIR_MAX_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_005 = MetricUnit.DEGREE_KELVIN.value

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_FORM = MetricUnit.DIMENSIONLESS.value
            SNOW_DEPTH = MetricUnit.METER.value
            SNOW_DEPTH_NEW = MetricUnit.METER.value

        # soil_temperature
        class TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_002 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_005 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_010 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_020 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_SOIL_050 = MetricUnit.DEGREE_KELVIN.value

        # solar
        class SOLAR(UnitEnum):
            QUALITY = MetricUnit.DIMENSIONLESS.value
            RADIATION_SKY_LONG_WAVE = MetricUnit.JOULE_PER_SQUARE_METER.value
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = MetricUnit.JOULE_PER_SQUARE_METER.value
            RADIATION_SKY_SHORT_WAVE_DIRECT = MetricUnit.JOULE_PER_SQUARE_METER.value
            SUNSHINE_DURATION = MetricUnit.SECOND.value

        # water_equiv
        class WATER_EQUIVALENT(UnitEnum):  # noqa
            QN_6 = MetricUnit.DIMENSIONLESS.value
            SNOW_DEPTH_EXCELLED = MetricUnit.METER.value
            SNOW_DEPTH = MetricUnit.METER.value
            WATER_EQUIVALENT_TOTAL_SNOW_DEPTH = (
                MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            )
            WATER_EQUIVALENT_SNOW = MetricUnit.KILOGRAM_PER_SQUARE_METER.value

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            FOG = MetricUnit.DIMENSIONLESS.value
            THUNDER = MetricUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = MetricUnit.DIMENSIONLESS.value
            STORM_STORMIER_WIND = MetricUnit.DIMENSIONLESS.value
            DEW = MetricUnit.DIMENSIONLESS.value
            GLAZE = MetricUnit.DIMENSIONLESS.value
            RIPE = MetricUnit.DIMENSIONLESS.value
            SLEET = MetricUnit.DIMENSIONLESS.value
            HAIL = MetricUnit.DIMENSIONLESS.value

    # monthly
    class MONTHLY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_GENERAL = MetricUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = MetricUnit.PERCENT.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MAX_MEAN_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_MEAN_200 = MetricUnit.DEGREE_KELVIN.value
            WIND_FORCE_BEAUFORT = MetricUnit.BEAUFORT.value
            TEMPERATURE_AIR_MAX_200 = MetricUnit.DEGREE_KELVIN.value
            WIND_GUST_MAX = MetricUnit.METER_PER_SECOND.value
            TEMPERATURE_AIR_MIN_200 = MetricUnit.DEGREE_KELVIN.value
            SUNSHINE_DURATION = MetricUnit.SECOND.value
            QUALITY_PRECIPITATION = MetricUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_MAX = MetricUnit.KILOGRAM_PER_SQUARE_METER.value

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            SNOW_DEPTH_NEW = MetricUnit.METER.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            SNOW_DEPTH = MetricUnit.METER.value
            PRECIPITATION_HEIGHT_MAX = MetricUnit.KILOGRAM_PER_SQUARE_METER.value

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = MetricUnit.DIMENSIONLESS.value
            STORM_STORMIER_WIND = MetricUnit.DIMENSIONLESS.value
            THUNDER = MetricUnit.DIMENSIONLESS.value
            GLAZE = MetricUnit.DIMENSIONLESS.value
            SLEET = MetricUnit.DIMENSIONLESS.value
            HAIL = MetricUnit.DIMENSIONLESS.value
            FOG = MetricUnit.DIMENSIONLESS.value
            DEW = MetricUnit.DIMENSIONLESS.value

    # annual
    class ANNUAL(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_GENERAL = MetricUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = MetricUnit.PERCENT.value
            TEMPERATURE_AIR_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MAX_MEAN_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_MEAN_200 = MetricUnit.DEGREE_KELVIN.value
            WIND_FORCE_BEAUFORT = MetricUnit.BEAUFORT.value
            SUNSHINE_DURATION = MetricUnit.SECOND.value
            WIND_GUST_MAX = MetricUnit.METER_PER_SECOND.value
            TEMPERATURE_AIR_MAX_200 = MetricUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_200 = MetricUnit.DEGREE_KELVIN.value
            QUALITY_PRECIPITATION = MetricUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_MAX = MetricUnit.KILOGRAM_PER_SQUARE_METER.value

        # more_precip
        class PRECIPITATION_MORE(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            SNOW_DEPTH_NEW = MetricUnit.METER.value
            PRECIPITATION_HEIGHT = MetricUnit.KILOGRAM_PER_SQUARE_METER.value
            SNOW_DEPTH = MetricUnit.METER.value
            PRECIPITATION_HEIGHT_MAX = MetricUnit.KILOGRAM_PER_SQUARE_METER.value

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = MetricUnit.DIMENSIONLESS.value
            STORM_STRONG_WIND = MetricUnit.DIMENSIONLESS.value
            STORM_STORMIER_WIND = MetricUnit.DIMENSIONLESS.value
            THUNDER = MetricUnit.DIMENSIONLESS.value
            GLAZE = MetricUnit.DIMENSIONLESS.value
            SLEET = MetricUnit.DIMENSIONLESS.value
            HAIL = MetricUnit.DIMENSIONLESS.value
            FOG = MetricUnit.DIMENSIONLESS.value
            DEW = MetricUnit.DIMENSIONLESS.value
