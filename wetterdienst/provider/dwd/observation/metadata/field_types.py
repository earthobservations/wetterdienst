# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationDatasetTree,
)

DATE_FIELDS_REGULAR = {
    DwdColumns.DATE.value,
    DwdColumns.FROM_DATE.value,
    DwdColumns.TO_DATE.value,
}
DATE_PARAMETERS_IRREGULAR = {
    DwdObservationDatasetTree.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DwdObservationDatasetTree.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
}
QUALITY_PARAMETERS = {
    # 1_minute
    # precipitation
    DwdObservationDatasetTree.MINUTE_1.PRECIPITATION.QUALITY.value,
    # 10_minutes
    # temperature_air
    DwdObservationDatasetTree.MINUTE_10.TEMPERATURE_AIR.QUALITY.value,
    # temperature_extreme
    DwdObservationDatasetTree.MINUTE_10.TEMPERATURE_EXTREME.QUALITY.value,
    # wind_extreme
    DwdObservationDatasetTree.MINUTE_10.WIND_EXTREME.QUALITY.value,
    # precipitation
    DwdObservationDatasetTree.MINUTE_10.PRECIPITATION.QUALITY.value,
    # solar
    DwdObservationDatasetTree.MINUTE_10.SOLAR.QUALITY.value,
    # wind
    DwdObservationDatasetTree.MINUTE_10.WIND.QUALITY.value,
    # hourly
    # temperature_air
    DwdObservationDatasetTree.HOURLY.TEMPERATURE_AIR.QUALITY.value,
    # cloud_type
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.QUALITY.value,
    # cloudiness
    DwdObservationDatasetTree.HOURLY.CLOUDINESS.QUALITY.value,
    # dew_point
    DwdObservationDatasetTree.HOURLY.DEW_POINT.QUALITY.value,
    # precipitation
    DwdObservationDatasetTree.HOURLY.PRECIPITATION.QUALITY.value,
    # pressure
    DwdObservationDatasetTree.HOURLY.PRESSURE.QUALITY.value,
    # soil_temperature
    DwdObservationDatasetTree.HOURLY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DwdObservationDatasetTree.HOURLY.SOLAR.QUALITY.value,
    # sun
    DwdObservationDatasetTree.HOURLY.SUNSHINE_DURATION.QUALITY.value,
    # visibility
    DwdObservationDatasetTree.HOURLY.VISIBILITY.QUALITY.value,
    # wind
    DwdObservationDatasetTree.HOURLY.WIND.QUALITY.value,
    # wind_synop
    DwdObservationDatasetTree.HOURLY.WIND_SYNOPTIC.QUALITY.value,
    # subdaily
    # air_temperature
    DwdObservationDatasetTree.SUBDAILY.TEMPERATURE_AIR.QUALITY.value,
    # cloudiness
    DwdObservationDatasetTree.SUBDAILY.CLOUDINESS.QUALITY.value,
    # moisture
    DwdObservationDatasetTree.SUBDAILY.MOISTURE.QUALITY.value,
    # pressure
    DwdObservationDatasetTree.SUBDAILY.PRESSURE.QUALITY.value,
    # soil
    DwdObservationDatasetTree.SUBDAILY.SOIL.QUALITY.value,
    # visibility
    DwdObservationDatasetTree.SUBDAILY.VISIBILITY.QUALITY.value,
    # wind
    DwdObservationDatasetTree.SUBDAILY.WIND.QUALITY.value,
    # daily
    # kl
    DwdObservationDatasetTree.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
    DwdObservationDatasetTree.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    # more_precip
    DwdObservationDatasetTree.DAILY.PRECIPITATION_MORE.QUALITY.value,
    # soil_temperature
    DwdObservationDatasetTree.DAILY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DwdObservationDatasetTree.DAILY.SOLAR.QUALITY.value,
    # water_equiv
    DwdObservationDatasetTree.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.QUALITY.value,
    # monthly
    # kl
    DwdObservationDatasetTree.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DwdObservationDatasetTree.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DwdObservationDatasetTree.MONTHLY.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.QUALITY.value,
    # annual
    # kl
    DwdObservationDatasetTree.ANNUAL.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DwdObservationDatasetTree.ANNUAL.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DwdObservationDatasetTree.ANNUAL.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.QUALITY.value,
}
INTEGER_PARAMETERS = {
    # 1_minute
    # precipitation
    DwdObservationDatasetTree.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM.value,
    # 10_minutes
    # wind_extreme
    DwdObservationDatasetTree.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_MAX_VELOCITY.value,
    # precipitation
    DwdObservationDatasetTree.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR.value,
    # hourly
    # cloud_type
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4.value,
    # cloudiness
    DwdObservationDatasetTree.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    # precipitation
    DwdObservationDatasetTree.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR.value,
    DwdObservationDatasetTree.HOURLY.PRECIPITATION.PRECIPITATION_FORM.value,
    # visibility
    DwdObservationDatasetTree.HOURLY.VISIBILITY.VISIBILITY.value,
    # wind
    DwdObservationDatasetTree.HOURLY.WIND.WIND_DIRECTION.value,
    # wind_synop
    DwdObservationDatasetTree.HOURLY.WIND_SYNOPTIC.WIND_DIRECTION.value,
    # subdaily
    # cloudiness
    DwdObservationDatasetTree.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    DwdObservationDatasetTree.SUBDAILY.CLOUDINESS.CLOUD_DENSITY.value,
    # soil
    DwdObservationDatasetTree.SUBDAILY.SOIL.TEMPERATURE_SOIL_005.value,
    # visibility
    DwdObservationDatasetTree.SUBDAILY.VISIBILITY.VISIBILITY.value,
    # wind
    DwdObservationDatasetTree.SUBDAILY.WIND.WIND_DIRECTION.value,
    DwdObservationDatasetTree.SUBDAILY.WIND.WIND_FORCE_BEAUFORT.value,
    # daily
    # kl
    DwdObservationDatasetTree.DAILY.CLIMATE_SUMMARY.SNOW_DEPTH.value,
    # more_precip
    DwdObservationDatasetTree.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM.value,
    DwdObservationDatasetTree.DAILY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    DwdObservationDatasetTree.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    # water_equiv
    DwdObservationDatasetTree.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED.value,
    DwdObservationDatasetTree.DAILY.WATER_EQUIVALENT.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.FOG.value,
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.DEW.value,
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.RIPE.value,
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationDatasetTree.DAILY.WEATHER_PHENOMENA.HAIL.value,
    # monthly
    # more_precip
    DwdObservationDatasetTree.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DwdObservationDatasetTree.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.HAIL.value,
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.FOG.value,
    DwdObservationDatasetTree.MONTHLY.WEATHER_PHENOMENA.DEW.value,
    # annual
    # more_precip
    DwdObservationDatasetTree.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DwdObservationDatasetTree.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.HAIL.value,
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.FOG.value,
    DwdObservationDatasetTree.ANNUAL.WEATHER_PHENOMENA.DEW.value,
}
STRING_PARAMETERS = {
    # hourly
    # cloud_type
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDICATOR.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DwdObservationDatasetTree.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DwdObservationDatasetTree.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR.value,
    # visibility
    DwdObservationDatasetTree.HOURLY.VISIBILITY.VISIBILITY_INDICATOR.value,
}
