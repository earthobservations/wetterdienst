# Copyright (C) 2018-2021, earthobservations developers.
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
            PRECIPITATION_INDEX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

    # 5_minutes
    class MINUTE_5(DatasetTreeCore):  # noqa
        # precipitation
        class PRECIPITATION(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRECIPITATION_INDEX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
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

    # 10_minutes
    class MINUTE_10(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRESSURE_AIR_SITE = (
                OriginUnit.HECTOPASCAL.value,
                SIUnit.PASCAL.value,
            )
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MEAN_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_DEW_POINT_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # extreme_temperature
        class TEMPERATURE_EXTREME(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MAX_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_0_05M = (
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
            WIND_DIRECTION_GUST_MAX = (
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
            PRECIPITATION_INDEX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

        # solar
        class SOLAR(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            RADIATION_SKY_SHORT_WAVE_DIFFUSE = (
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
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value

        # cloud_type
        class CLOUD_TYPE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            CLOUD_COVER_TOTAL_INDEX = (
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
            CLOUD_COVER_TOTAL_INDEX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value

        # dew_point
        class DEW_POINT(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_DEW_POINT_MEAN_2M = (
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

        # moisture
        class MOISTURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            HUMIDITY_ABSOLUTE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_WET_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_DEW_POINT_MEAN_2M = (
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
            PRECIPITATION_INDEX = (
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
            PRESSURE_AIR_SITE = (
                OriginUnit.HECTOPASCAL.value,
                SIUnit.PASCAL.value,
            )

        # soil_temperature
        class TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_MEAN_0_02M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_1M = (
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
            SUN_ZENITH_ANGLE = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            TRUE_LOCAL_TIME = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

        # sun
        class SUN(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SUNSHINE_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value

        # visibility
        class VISIBILITY(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            VISIBILITY_RANGE_INDEX = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            VISIBILITY_RANGE = OriginUnit.METER.value, SIUnit.METER.value

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WEATHER = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WEATHER_TEXT = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value

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

        class URBAN_TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value

        class URBAN_PRECIPITATION(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )

        class URBAN_PRESSURE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRESSURE_AIR_SEA_LEVEL = (
                OriginUnit.HECTOPASCAL.value,
                SIUnit.PASCAL.value,
            )
            PRESSURE_AIR_SITE = (
                OriginUnit.HECTOPASCAL.value,
                SIUnit.PASCAL.value,
            )

        class URBAN_TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_MEAN_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        class URBAN_SUN(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SUNSHINE_DURATION = OriginUnit.MINUTE.value, SIUnit.SECOND.value

        class URBAN_WIND(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_SPEED = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            WIND_DIRECTION = (
                OriginUnit.WIND_DIRECTION.value,
                SIUnit.WIND_DIRECTION.value,
            )

    # subdaily
    class SUBDAILY(DatasetTreeCore):  # noqa
        # air_temperature
        class TEMPERATURE_AIR(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_MEAN_2M = (
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

        # extreme_wind
        class WIND_EXTREME(UnitEnum):
            QUALITY_3 = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_GUST_MAX_LAST_3H = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            QUALITY_6 = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            WIND_GUST_MAX_LAST_6H = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )

        # moisture
        class MOISTURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRESSURE_VAPOR = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_AIR_MEAN_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value

        # pressure
        class PRESSURE(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value

        # soil
        class SOIL(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_MEAN_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )

        # visibility
        class VISIBILITY(UnitEnum):
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            VISIBILITY_RANGE = OriginUnit.METER.value, SIUnit.METER.value

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
            PRESSURE_AIR_SITE = OriginUnit.HECTOPASCAL.value, SIUnit.PASCAL.value
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_0_05M = (
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

        # more_weather_phenomena
        class WEATHER_PHENOMENA_MORE(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            COUNT_WEATHER_TYPE_SLEET = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            COUNT_WEATHER_TYPE_HAIL = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            COUNT_WEATHER_TYPE_FOG = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            COUNT_WEATHER_TYPE_THUNDER = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value

        # soil_temperature
        class TEMPERATURE_SOIL(UnitEnum):  # noqa
            QUALITY = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DIMENSIONLESS.value
            TEMPERATURE_SOIL_MEAN_0_02M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_05M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_1M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_0_5M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_SOIL_MEAN_1M = (
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
            RADIATION_GLOBAL = (
                OriginUnit.JOULE_PER_SQUARE_CENTIMETER.value,
                SIUnit.JOULE_PER_SQUARE_METER.value,
            )
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value

        # water_equiv
        class WATER_EQUIVALENT(UnitEnum):  # noqa
            QN_6 = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            SNOW_DEPTH_EXCELLED = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            SNOW_DEPTH = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            WATER_EQUIVALENT_SNOW_DEPTH = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )
            WATER_EQUIVALENT_SNOW_DEPTH_EXCELLED = (
                OriginUnit.MILLIMETER.value,
                SIUnit.KILOGRAM_PER_SQUARE_METER.value,
            )

        # weather_phenomena
        class WEATHER_PHENOMENA(UnitEnum):  # noqa
            QUALITY = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
            COUNT_WEATHER_TYPE_FOG = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_THUNDER = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_STORM_STRONG_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_DEW = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_GLAZE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_RIPE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_SLEET = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_HAIL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

    # monthly
    class MONTHLY(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_GENERAL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MAX_2M_MEAN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_2M_MEAN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            WIND_FORCE_BEAUFORT = OriginUnit.BEAUFORT.value, SIUnit.BEAUFORT.value
            TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            WIND_GUST_MAX = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            TEMPERATURE_AIR_MIN_2M = (
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
            COUNT_WEATHER_TYPE_STORM_STRONG_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_THUNDER = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_GLAZE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_SLEET = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_HAIL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_FOG = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_DEW = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )

    # annual
    class ANNUAL(DatasetTreeCore):
        # kl
        class CLIMATE_SUMMARY(UnitEnum):  # noqa
            QUALITY_GENERAL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            CLOUD_COVER_TOTAL = OriginUnit.ONE_EIGHTH.value, SIUnit.PERCENT.value
            TEMPERATURE_AIR_MEAN_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MAX_2M_MEAN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_2M_MEAN = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            WIND_FORCE_BEAUFORT = OriginUnit.BEAUFORT.value, SIUnit.BEAUFORT.value
            SUNSHINE_DURATION = OriginUnit.HOUR.value, SIUnit.SECOND.value
            WIND_GUST_MAX = (
                OriginUnit.METER_PER_SECOND.value,
                SIUnit.METER_PER_SECOND.value,
            )
            TEMPERATURE_AIR_MAX_2M = (
                OriginUnit.DEGREE_CELSIUS.value,
                SIUnit.DEGREE_KELVIN.value,
            )
            TEMPERATURE_AIR_MIN_2M = (
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
            COUNT_WEATHER_TYPE_STORM_STRONG_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_STORM_STORMIER_WIND = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_THUNDER = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_GLAZE = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_SLEET = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_HAIL = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_FOG = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
            COUNT_WEATHER_TYPE_DEW = (
                OriginUnit.DIMENSIONLESS.value,
                SIUnit.DIMENSIONLESS.value,
            )
