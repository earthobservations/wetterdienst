# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationParameter,
)

DATE_FIELDS_REGULAR = {
    DwdColumns.DATE.value,
    DwdColumns.FROM_DATE.value,
    DwdColumns.TO_DATE.value,
}
DATE_PARAMETERS_IRREGULAR = {
    DwdObservationParameter.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DwdObservationParameter.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
}
QUALITY_PARAMETERS = {
    # 1_minute
    # precipitation
    DwdObservationParameter.MINUTE_1.PRECIPITATION.QUALITY.value,
    # 10_minutes
    # temperature_air
    DwdObservationParameter.MINUTE_10.TEMPERATURE_AIR.QUALITY.value,
    # temperature_extreme
    DwdObservationParameter.MINUTE_10.TEMPERATURE_EXTREME.QUALITY.value,
    # wind_extreme
    DwdObservationParameter.MINUTE_10.WIND_EXTREME.QUALITY.value,
    # precipitation
    DwdObservationParameter.MINUTE_10.PRECIPITATION.QUALITY.value,
    # solar
    DwdObservationParameter.MINUTE_10.SOLAR.QUALITY.value,
    # wind
    DwdObservationParameter.MINUTE_10.WIND.QUALITY.value,
    # hourly
    # temperature_air
    DwdObservationParameter.HOURLY.TEMPERATURE_AIR.QUALITY.value,
    # cloud_type
    DwdObservationParameter.HOURLY.CLOUD_TYPE.QUALITY.value,
    # cloudiness
    DwdObservationParameter.HOURLY.CLOUDINESS.QUALITY.value,
    # dew_point
    DwdObservationParameter.HOURLY.DEW_POINT.QUALITY.value,
    # precipitation
    DwdObservationParameter.HOURLY.PRECIPITATION.QUALITY.value,
    # pressure
    DwdObservationParameter.HOURLY.PRESSURE.QUALITY.value,
    # soil_temperature
    DwdObservationParameter.HOURLY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DwdObservationParameter.HOURLY.SOLAR.QUALITY.value,
    # sun
    # DwdObservationParameter.HOURLY.SUNSHINE_DURATION.QUALITY.value,
    # visibility
    DwdObservationParameter.HOURLY.VISIBILITY.QUALITY.value,
    # wind
    DwdObservationParameter.HOURLY.WIND.QUALITY.value,
    # wind_synop
    DwdObservationParameter.HOURLY.WIND_SYNOPTIC.QUALITY.value,
    # subdaily
    # air_temperature
    DwdObservationParameter.SUBDAILY.TEMPERATURE_AIR.QUALITY.value,
    # cloudiness
    DwdObservationParameter.SUBDAILY.CLOUDINESS.QUALITY.value,
    # moisture
    DwdObservationParameter.SUBDAILY.MOISTURE.QUALITY.value,
    # pressure
    DwdObservationParameter.SUBDAILY.PRESSURE.QUALITY.value,
    # soil
    DwdObservationParameter.SUBDAILY.SOIL.QUALITY.value,
    # visibility
    DwdObservationParameter.SUBDAILY.VISIBILITY.QUALITY.value,
    # wind
    DwdObservationParameter.SUBDAILY.WIND.QUALITY.value,
    # daily
    # kl
    DwdObservationParameter.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
    DwdObservationParameter.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    # more_precip
    DwdObservationParameter.DAILY.PRECIPITATION_MORE.QUALITY.value,
    # soil_temperature
    DwdObservationParameter.DAILY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DwdObservationParameter.DAILY.SOLAR.QUALITY.value,
    # water_equiv
    DwdObservationParameter.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.QUALITY.value,
    # monthly
    # kl
    DwdObservationParameter.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DwdObservationParameter.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DwdObservationParameter.MONTHLY.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.QUALITY.value,
    # annual
    # kl
    DwdObservationParameter.ANNUAL.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DwdObservationParameter.ANNUAL.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DwdObservationParameter.ANNUAL.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.QUALITY.value,
}
INTEGER_PARAMETERS = {
    # 1_minute
    # precipitation
    DwdObservationParameter.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM.value,
    # 10_minutes
    # wind_extreme
    DwdObservationParameter.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_GUST_MAX.value,
    # precipitation
    DwdObservationParameter.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR.value,
    # hourly
    # cloud_type
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4.value,
    # cloudiness
    DwdObservationParameter.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    # precipitation
    DwdObservationParameter.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR.value,
    DwdObservationParameter.HOURLY.PRECIPITATION.PRECIPITATION_FORM.value,
    # visibility
    DwdObservationParameter.HOURLY.VISIBILITY.VISIBILITY_RANGE.value,
    # wind
    DwdObservationParameter.HOURLY.WIND.WIND_DIRECTION.value,
    # wind_synop
    DwdObservationParameter.HOURLY.WIND_SYNOPTIC.WIND_DIRECTION.value,
    # subdaily
    # cloudiness
    DwdObservationParameter.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    DwdObservationParameter.SUBDAILY.CLOUDINESS.CLOUD_DENSITY.value,
    # soil
    DwdObservationParameter.SUBDAILY.SOIL.TEMPERATURE_SOIL_MEAN_005.value,
    # visibility
    DwdObservationParameter.SUBDAILY.VISIBILITY.VISIBILITY_RANGE.value,
    # wind
    DwdObservationParameter.SUBDAILY.WIND.WIND_DIRECTION.value,
    DwdObservationParameter.SUBDAILY.WIND.WIND_FORCE_BEAUFORT.value,
    # daily
    # kl
    DwdObservationParameter.DAILY.CLIMATE_SUMMARY.SNOW_DEPTH.value,
    # more_precip
    DwdObservationParameter.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM.value,
    DwdObservationParameter.DAILY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    DwdObservationParameter.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    # water_equiv
    DwdObservationParameter.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED.value,
    DwdObservationParameter.DAILY.WATER_EQUIVALENT.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_FOG.value,
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_THUNDER.value,
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STRONG_WIND.value,
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND.value,
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_DEW.value,
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_GLAZE.value,
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_RIPE.value,
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_SLEET.value,
    DwdObservationParameter.DAILY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_HAIL.value,
    # monthly
    # more_precip
    DwdObservationParameter.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DwdObservationParameter.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STRONG_WIND.value,
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND.value,
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_THUNDER.value,
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_GLAZE.value,
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_SLEET.value,
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_HAIL.value,
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_FOG.value,
    DwdObservationParameter.MONTHLY.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_DEW.value,
    # annual
    # more_precip
    DwdObservationParameter.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DwdObservationParameter.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STRONG_WIND.value,
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_STORM_STORMIER_WIND.value,
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_THUNDER.value,
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_GLAZE.value,
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_SLEET.value,
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_HAIL.value,
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_FOG.value,
    DwdObservationParameter.ANNUAL.WEATHER_PHENOMENA.COUNT_WEATHER_TYPE_DEW.value,
}
STRING_PARAMETERS = {
    # hourly
    # cloud_type
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDICATOR.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DwdObservationParameter.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR.value,
    # visibility
    DwdObservationParameter.HOURLY.VISIBILITY.VISIBILITY_RANGE_INDICATOR.value,
}
