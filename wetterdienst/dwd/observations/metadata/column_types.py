# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations.metadata.parameter import (
    DwdObservationParameterSetStructure,
)

DATE_FIELDS_REGULAR = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)
DATE_PARAMETERS_IRREGULAR = (
    DwdObservationParameterSetStructure.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DwdObservationParameterSetStructure.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
)
QUALITY_PARAMETERS = (
    # 1_minute
    # precipitation
    DwdObservationParameterSetStructure.MINUTE_1.PRECIPITATION.QUALITY.value,
    # 10_minutes
    # temperature_air
    DwdObservationParameterSetStructure.MINUTE_10.TEMPERATURE_AIR.QUALITY.value,
    # temperature_extreme
    DwdObservationParameterSetStructure.MINUTE_10.TEMPERATURE_EXTREME.QUALITY.value,
    # wind_extreme
    DwdObservationParameterSetStructure.MINUTE_10.WIND_EXTREME.QUALITY.value,
    # precipitation
    DwdObservationParameterSetStructure.MINUTE_10.PRECIPITATION.QUALITY.value,
    # solar
    DwdObservationParameterSetStructure.MINUTE_10.SOLAR.QUALITY.value,
    # wind
    DwdObservationParameterSetStructure.MINUTE_10.WIND.QUALITY.value,
    # hourly
    # temperature_air
    DwdObservationParameterSetStructure.HOURLY.TEMPERATURE_AIR.QUALITY.value,
    # cloud_type
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.QUALITY.value,
    # cloudiness
    DwdObservationParameterSetStructure.HOURLY.CLOUDINESS.QUALITY.value,
    # dew_point
    DwdObservationParameterSetStructure.HOURLY.DEW_POINT.QUALITY.value,
    # precipitation
    DwdObservationParameterSetStructure.HOURLY.PRECIPITATION.QUALITY.value,
    # pressure
    DwdObservationParameterSetStructure.HOURLY.PRESSURE.QUALITY.value,
    # soil_temperature
    DwdObservationParameterSetStructure.HOURLY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DwdObservationParameterSetStructure.HOURLY.SOLAR.QUALITY.value,
    # sun
    DwdObservationParameterSetStructure.HOURLY.SUN.QUALITY.value,
    # visibility
    DwdObservationParameterSetStructure.HOURLY.VISIBILITY.QUALITY.value,
    # wind
    DwdObservationParameterSetStructure.HOURLY.WIND.QUALITY.value,
    # wind_synop
    DwdObservationParameterSetStructure.HOURLY.WIND_SYNOPTIC.QUALITY.value,
    # subdaily
    # air_temperature
    DwdObservationParameterSetStructure.SUBDAILY.TEMPERATURE_AIR.QUALITY.value,
    # cloudiness
    DwdObservationParameterSetStructure.SUBDAILY.CLOUDINESS.QUALITY.value,
    # moisture
    DwdObservationParameterSetStructure.SUBDAILY.MOISTURE.QUALITY.value,
    # pressure
    DwdObservationParameterSetStructure.SUBDAILY.PRESSURE.QUALITY.value,
    # soil
    DwdObservationParameterSetStructure.SUBDAILY.SOIL.QUALITY.value,
    # visibility
    DwdObservationParameterSetStructure.SUBDAILY.VISIBILITY.QUALITY.value,
    # wind
    DwdObservationParameterSetStructure.SUBDAILY.WIND.QUALITY.value,
    # daily
    # kl
    DwdObservationParameterSetStructure.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
    DwdObservationParameterSetStructure.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    # more_precip
    DwdObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.QUALITY.value,
    # soil_temperature
    DwdObservationParameterSetStructure.DAILY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DwdObservationParameterSetStructure.DAILY.SOLAR.QUALITY.value,
    # water_equiv
    DwdObservationParameterSetStructure.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.QUALITY.value,
    # monthly
    # kl
    DwdObservationParameterSetStructure.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DwdObservationParameterSetStructure.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DwdObservationParameterSetStructure.MONTHLY.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.QUALITY.value,
    # annual
    # kl
    DwdObservationParameterSetStructure.ANNUAL.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DwdObservationParameterSetStructure.ANNUAL.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DwdObservationParameterSetStructure.ANNUAL.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.QUALITY.value,
)
INTEGER_PARAMETERS = (
    # 1_minute
    # precipitation
    DwdObservationParameterSetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM.value,
    # 10_minutes
    # wind_extreme
    DwdObservationParameterSetStructure.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_MAX_VELOCITY.value,
    # precipitation
    DwdObservationParameterSetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR.value,
    # hourly
    # cloud_type
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4.value,
    # cloudiness
    DwdObservationParameterSetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    # precipitation
    DwdObservationParameterSetStructure.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR.value,
    DwdObservationParameterSetStructure.HOURLY.PRECIPITATION.PRECIPITATION_FORM.value,
    # visibility
    DwdObservationParameterSetStructure.HOURLY.VISIBILITY.VISIBILITY.value,
    # wind
    DwdObservationParameterSetStructure.HOURLY.WIND.WIND_DIRECTION.value,
    # wind_synop
    DwdObservationParameterSetStructure.HOURLY.WIND_SYNOPTIC.WIND_DIRECTION.value,
    # subdaily
    # cloudiness
    DwdObservationParameterSetStructure.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    DwdObservationParameterSetStructure.SUBDAILY.CLOUDINESS.CLOUD_DENSITY.value,
    # soil
    DwdObservationParameterSetStructure.SUBDAILY.SOIL.TEMPERATURE_SOIL_005.value,
    # visibility
    DwdObservationParameterSetStructure.SUBDAILY.VISIBILITY.VISIBILITY.value,
    # wind
    DwdObservationParameterSetStructure.SUBDAILY.WIND.WIND_DIRECTION.value,
    DwdObservationParameterSetStructure.SUBDAILY.WIND.WIND_FORCE_BEAUFORT.value,
    # daily
    # more_precip
    DwdObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM.value,
    DwdObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    DwdObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    # water_equiv
    DwdObservationParameterSetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED.value,
    DwdObservationParameterSetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.FOG.value,
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.DEW.value,
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.RIPE.value,
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.HAIL.value,
    # monthly
    # more_precip
    DwdObservationParameterSetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DwdObservationParameterSetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.HAIL.value,
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.FOG.value,
    DwdObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.DEW.value,
    # annual
    # more_precip
    DwdObservationParameterSetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DwdObservationParameterSetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.HAIL.value,
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.FOG.value,
    DwdObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.DEW.value,
)
STRING_PARAMETERS = (
    # hourly
    # cloud_type
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDICATOR.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DwdObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DwdObservationParameterSetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR.value,
    # visibility
    DwdObservationParameterSetStructure.HOURLY.VISIBILITY.VISIBILITY_INDICATOR.value,
)
