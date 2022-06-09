# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.parameter import DatasetTreeCore


class DwdMosmixUnit(DatasetTreeCore):
    class SMALL(UnitEnum):
        TEMPERATURE_AIR_MEAN_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        TEMPERATURE_DEW_POINT_MEAN_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        TEMPERATURE_AIR_MAX_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        TEMPERATURE_AIR_MIN_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        WIND_DIRECTION = (
            OriginUnit.WIND_DIRECTION.value,
            SIUnit.WIND_DIRECTION.value,
        )
        WIND_SPEED = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        WIND_GUST_MAX_LAST_1H = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        WIND_GUST_MAX_LAST_3H = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        WIND_GUST_MAX_LAST_12H = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        PRECIPITATION_HEIGHT_SIGNIFICANT_WEATHER_LAST_1H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PRECIPITATION_HEIGHT_SIGNIFICANT_WEATHER_LAST_3H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        WATER_EQUIVALENT_SNOW_DEPTH_NEW_LAST_1H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        WATER_EQUIVALENT_SNOW_DEPTH_NEW_LAST_3H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        WEATHER_SIGNIFICANT = (
            OriginUnit.SIGNIFICANT_WEATHER.value,
            SIUnit.SIGNIFICANT_WEATHER.value,
        )
        WEATHER_LAST_6H = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
        CLOUD_COVER_TOTAL = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        CLOUD_COVER_EFFECTIVE = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        CLOUD_COVER_BELOW_500_FT = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        CLOUD_COVER_BELOW_1000_FT = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        CLOUD_COVER_BETWEEN_2_TO_7_KM = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        CLOUD_COVER_ABOVE_7_KM = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PRESSURE_AIR_SITE_REDUCED = OriginUnit.PASCAL.value, SIUnit.PASCAL.value
        TEMPERATURE_AIR_MEAN_005 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        RADIATION_GLOBAL = (
            OriginUnit.GLOBAL_IRRADIANCE.value,
            SIUnit.GLOBAL_IRRADIANCE.value,
        )
        VISIBILITY_RANGE = OriginUnit.METER.value, SIUnit.METER.value
        SUNSHINE_DURATION = OriginUnit.SECOND.value, SIUnit.SECOND.value
        PROBABILITY_WIND_GUST_GE_25_KN_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_WIND_GUST_GE_40_KN_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_WIND_GUST_GE_55_KN_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_FOG_LAST_1H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_FOG_LAST_6H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_FOG_LAST_12H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0_MM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_2_MM_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_2_MM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_2_MM_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_1_0_MM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_5_0_MM_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_5_0_MM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_5_0_MM_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )

    class LARGE(UnitEnum):
        # https://opendata.dwd.de/weather/lib/MetElementDefinition.xml
        TEMPERATURE_AIR_MEAN_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        TEMPERATURE_DEW_POINT_MEAN_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        TEMPERATURE_AIR_MAX_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        TEMPERATURE_AIR_MIN_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        WIND_DIRECTION = (
            OriginUnit.WIND_DIRECTION.value,
            SIUnit.WIND_DIRECTION.value,
        )
        WIND_SPEED = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        WIND_GUST_MAX_LAST_1H = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        WIND_GUST_MAX_LAST_3H = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        WIND_GUST_MAX_LAST_12H = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        PRECIPITATION_HEIGHT_SIGNIFICANT_WEATHER_LAST_1H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PRECIPITATION_HEIGHT_LAST_1H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PRECIPITATION_HEIGHT_SIGNIFICANT_WEATHER_LAST_3H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PRECIPITATION_HEIGHT_LAST_3H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        WATER_EQUIVALENT_SNOW_DEPTH_NEW_LAST_1H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        WATER_EQUIVALENT_SNOW_DEPTH_NEW_LAST_3H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        WEATHER_SIGNIFICANT = (
            OriginUnit.SIGNIFICANT_WEATHER.value,
            SIUnit.SIGNIFICANT_WEATHER.value,
        )
        WEATHER_LAST_6H = OriginUnit.DIMENSIONLESS.value, SIUnit.DIMENSIONLESS.value
        CLOUD_COVER_TOTAL = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        CLOUD_COVER_EFFECTIVE = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        CLOUD_COVER_BELOW_500_FT = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        CLOUD_COVER_BELOW_1000_FT = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        CLOUD_COVER_BETWEEN_2_TO_7_KM = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        CLOUD_COVER_ABOVE_7_KM = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PRESSURE_AIR_SITE_REDUCED = OriginUnit.PASCAL.value, SIUnit.PASCAL.value
        TEMPERATURE_AIR_MEAN_005 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        RADIATION_GLOBAL_LAST_3H = (
            OriginUnit.KILOJOULE_PER_SQUARE_METER.value,
            SIUnit.JOULE_PER_SQUARE_METER.value,
        )
        RADIATION_GLOBAL = (
            OriginUnit.GLOBAL_IRRADIANCE.value,
            SIUnit.GLOBAL_IRRADIANCE.value,
        )
        RADIATION_SKY_LONG_WAVE_LAST_3H = (
            OriginUnit.KILOJOULE_PER_SQUARE_METER.value,
            SIUnit.JOULE_PER_SQUARE_METER.value,
        )
        VISIBILITY_RANGE = OriginUnit.METER.value, SIUnit.METER.value
        SUNSHINE_DURATION = OriginUnit.SECOND.value, SIUnit.SECOND.value
        PROBABILITY_WIND_GUST_GE_25_KN_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_WIND_GUST_GE_40_KN_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_WIND_GUST_GE_55_KN_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_FOG_LAST_1H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_FOG_LAST_6H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_FOG_LAST_12H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0_MM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_2_MM_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_2_MM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_2_MM_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_1_0_MM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_5_0_MM_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_5_0_MM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_5_0_MM_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        TEMPERATURE_AIR_MIN_005_LAST_12H = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        TEMPERATURE_AIR_MEAN_200_LAST_24H = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        PRECIPITATION_DURATION = OriginUnit.SECOND.value, SIUnit.SECOND.value
        PROBABILITY_DRIZZLE_LAST_1H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_PRECIPITATION_STRATIFORM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_CONVECTIVE_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_THUNDER_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_LIQUID_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_SOLID_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_FREEZING_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_VISIBILITY_BELOW_1000_M = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        ERROR_ABSOLUTE_TEMPERATURE_AIR_MEAN_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        ERROR_ABSOLUTE_WIND_SPEED = (
            OriginUnit.METER_PER_SECOND.value,
            SIUnit.METER_PER_SECOND.value,
        )
        ERROR_ABSOLUTE_WIND_DIRECTION = (
            OriginUnit.WIND_DIRECTION.value,
            SIUnit.WIND_DIRECTION.value,
        )
        ERROR_ABSOLUTE_TEMPERATURE_DEW_POINT_MEAN_200 = (
            OriginUnit.DEGREE_KELVIN.value,
            SIUnit.DEGREE_KELVIN.value,
        )
        PRECIPITATION_HEIGHT_LAST_6H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PRECIPITATION_HEIGHT_SIGNIFICANT_WEATHER_LAST_6H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0_MM_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_1_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_2_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_3_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_5_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_7_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_1_0_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_2_0_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        SUNSHINE_DURATION_YESTERDAY = OriginUnit.SECOND.value, SIUnit.SECOND.value
        SUNSHINE_DURATION_RELATIVE_LAST_24H = (
            OriginUnit.DIMENSIONLESS.value,
            SIUnit.DIMENSIONLESS.value,
        )
        PROBABILITY_SUNSHINE_DURATION_RELATIVE_GT_0_PCT_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_SUNSHINE_DURATION_RELATIVE_GT_30_PCT_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_SUNSHINE_DURATION_RELATIVE_GT_60_PCT_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_RADIATION_GLOBAL_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        EVAPOTRANSPIRATION_POTENTIAL_LAST_24H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_3_0_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_5_0_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_10_0_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_15_0_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_25_0_MM_LAST_1H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_STRATIFORM_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_CONVECTIVE_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_THUNDER_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_LIQUID_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_FREEZING_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_SOLID_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_DRIZZLE_LAST_6H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_FOG_LAST_24H = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_WIND_GUST_GE_25_KN_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_WIND_GUST_GE_40_KN_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_WIND_GUST_GE_55_KN_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_STRATIFORM_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_CONVECTIVE_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_THUNDER_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_LIQUID_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_FREEZING_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_SOLID_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_DRIZZLE_LAST_12H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_1_0_MM_LAST_6H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PRECIPITATION_HEIGHT_LAST_12H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PRECIPITATION_HEIGHT_SIGNIFICANT_WEATHER_LAST_12H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        WEATHER_SIGNIFICANT_LAST_3H = (
            OriginUnit.SIGNIFICANT_WEATHER.value,
            SIUnit.SIGNIFICANT_WEATHER.value,
        )
        PRECIPITATION_HEIGHT_LIQUID_SIGNIFICANT_WEATHER_LAST_1H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_0_0_MM_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PROBABILITY_PRECIPITATION_HEIGHT_GT_1_0_MM_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        PRECIPITATION_HEIGHT_LAST_24H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        PRECIPITATION_HEIGHT_SIGNIFICANT_WEATHER_LAST_24H = (
            OriginUnit.KILOGRAM_PER_SQUARE_METER.value,
            SIUnit.KILOGRAM_PER_SQUARE_METER.value,
        )
        CLOUD_COVER_BELOW_7_KM = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        PROBABILITY_PRECIPITATION_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        CLOUD_BASE_CONVECTIVE = OriginUnit.METER.value, SIUnit.METER.value
        PROBABILITY_THUNDER_LAST_24H = (
            OriginUnit.PERCENT.value,
            SIUnit.PERCENT.value,
        )
        ERROR_ABSOLUTE_PRESSURE_AIR_SITE = (
            OriginUnit.PASCAL.value,
            SIUnit.PASCAL.value,
        )
        SUNSHINE_DURATION_LAST_3H = OriginUnit.SECOND.value, SIUnit.SECOND.value
        WEATHER_SIGNIFICANT_OPTIONAL_LAST_1H = (
            OriginUnit.SIGNIFICANT_WEATHER.value,
            SIUnit.SIGNIFICANT_WEATHER.value,
        )
        WEATHER_SIGNIFICANT_OPTIONAL_LAST_3H = (
            OriginUnit.SIGNIFICANT_WEATHER.value,
            SIUnit.SIGNIFICANT_WEATHER.value,
        )
        WEATHER_SIGNIFICANT_OPTIONAL_LAST_6H = (
            OriginUnit.SIGNIFICANT_WEATHER.value,
            SIUnit.SIGNIFICANT_WEATHER.value,
        )
        WEATHER_SIGNIFICANT_OPTIONAL_LAST_12H = (
            OriginUnit.SIGNIFICANT_WEATHER.value,
            SIUnit.SIGNIFICANT_WEATHER.value,
        )
        WEATHER_SIGNIFICANT_OPTIONAL_LAST_24H = (
            OriginUnit.SIGNIFICANT_WEATHER.value,
            SIUnit.SIGNIFICANT_WEATHER.value,
        )
