# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.dwd.metadata.column_names import DwdColumns
from wetterdienst.dwd.observations.metadata.parameter import (
    DwdObservationDatasetStructure,
)

DATE_FIELDS_REGULAR = (
    DwdColumns.DATE.value,
    DwdColumns.FROM_DATE.value,
    DwdColumns.TO_DATE.value,
)
DATE_PARAMETERS_IRREGULAR = (
    DwdObservationDatasetStructure.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DwdObservationDatasetStructure.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
)
QUALITY_PARAMETERS = (
    # 1_minute
    # precipitation
    DwdObservationDatasetStructure.MINUTE_1.PRECIPITATION.QUALITY.value,
    # 10_minutes
    # temperature_air
    DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_AIR.QUALITY.value,
    # temperature_extreme
    DwdObservationDatasetStructure.MINUTE_10.TEMPERATURE_EXTREME.QUALITY.value,
    # wind_extreme
    DwdObservationDatasetStructure.MINUTE_10.WIND_EXTREME.QUALITY.value,
    # precipitation
    DwdObservationDatasetStructure.MINUTE_10.PRECIPITATION.QUALITY.value,
    # solar
    DwdObservationDatasetStructure.MINUTE_10.SOLAR.QUALITY.value,
    # wind
    DwdObservationDatasetStructure.MINUTE_10.WIND.QUALITY.value,
    # hourly
    # temperature_air
    DwdObservationDatasetStructure.HOURLY.TEMPERATURE_AIR.QUALITY.value,
    # cloud_type
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.QUALITY.value,
    # cloudiness
    DwdObservationDatasetStructure.HOURLY.CLOUDINESS.QUALITY.value,
    # dew_point
    DwdObservationDatasetStructure.HOURLY.DEW_POINT.QUALITY.value,
    # precipitation
    DwdObservationDatasetStructure.HOURLY.PRECIPITATION.QUALITY.value,
    # pressure
    DwdObservationDatasetStructure.HOURLY.PRESSURE.QUALITY.value,
    # soil_temperature
    DwdObservationDatasetStructure.HOURLY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DwdObservationDatasetStructure.HOURLY.SOLAR.QUALITY.value,
    # sun
    DwdObservationDatasetStructure.HOURLY.SUN.QUALITY.value,
    # visibility
    DwdObservationDatasetStructure.HOURLY.VISIBILITY.QUALITY.value,
    # wind
    DwdObservationDatasetStructure.HOURLY.WIND.QUALITY.value,
    # wind_synop
    DwdObservationDatasetStructure.HOURLY.WIND_SYNOPTIC.QUALITY.value,
    # subdaily
    # air_temperature
    DwdObservationDatasetStructure.SUBDAILY.TEMPERATURE_AIR.QUALITY.value,
    # cloudiness
    DwdObservationDatasetStructure.SUBDAILY.CLOUDINESS.QUALITY.value,
    # moisture
    DwdObservationDatasetStructure.SUBDAILY.MOISTURE.QUALITY.value,
    # pressure
    DwdObservationDatasetStructure.SUBDAILY.PRESSURE.QUALITY.value,
    # soil
    DwdObservationDatasetStructure.SUBDAILY.SOIL.QUALITY.value,
    # visibility
    DwdObservationDatasetStructure.SUBDAILY.VISIBILITY.QUALITY.value,
    # wind
    DwdObservationDatasetStructure.SUBDAILY.WIND.QUALITY.value,
    # daily
    # kl
    DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
    DwdObservationDatasetStructure.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    # more_precip
    DwdObservationDatasetStructure.DAILY.PRECIPITATION_MORE.QUALITY.value,
    # soil_temperature
    DwdObservationDatasetStructure.DAILY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DwdObservationDatasetStructure.DAILY.SOLAR.QUALITY.value,
    # water_equiv
    DwdObservationDatasetStructure.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.QUALITY.value,
    # monthly
    # kl
    DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DwdObservationDatasetStructure.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DwdObservationDatasetStructure.MONTHLY.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.QUALITY.value,
    # annual
    # kl
    DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DwdObservationDatasetStructure.ANNUAL.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DwdObservationDatasetStructure.ANNUAL.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.QUALITY.value,
)
INTEGER_PARAMETERS = (
    # 1_minute
    # precipitation
    DwdObservationDatasetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM.value,
    # 10_minutes
    # wind_extreme
    DwdObservationDatasetStructure.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_MAX_VELOCITY.value,
    # precipitation
    DwdObservationDatasetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR.value,
    # hourly
    # cloud_type
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4.value,
    # cloudiness
    DwdObservationDatasetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    # precipitation
    DwdObservationDatasetStructure.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR.value,
    DwdObservationDatasetStructure.HOURLY.PRECIPITATION.PRECIPITATION_FORM.value,
    # visibility
    DwdObservationDatasetStructure.HOURLY.VISIBILITY.VISIBILITY.value,
    # wind
    DwdObservationDatasetStructure.HOURLY.WIND.WIND_DIRECTION.value,
    # wind_synop
    DwdObservationDatasetStructure.HOURLY.WIND_SYNOPTIC.WIND_DIRECTION.value,
    # subdaily
    # cloudiness
    DwdObservationDatasetStructure.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    DwdObservationDatasetStructure.SUBDAILY.CLOUDINESS.CLOUD_DENSITY.value,
    # soil
    DwdObservationDatasetStructure.SUBDAILY.SOIL.TEMPERATURE_SOIL_005.value,
    # visibility
    DwdObservationDatasetStructure.SUBDAILY.VISIBILITY.VISIBILITY.value,
    # wind
    DwdObservationDatasetStructure.SUBDAILY.WIND.WIND_DIRECTION.value,
    DwdObservationDatasetStructure.SUBDAILY.WIND.WIND_FORCE_BEAUFORT.value,
    # daily
    # more_precip
    DwdObservationDatasetStructure.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM.value,
    DwdObservationDatasetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    DwdObservationDatasetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    # water_equiv
    DwdObservationDatasetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED.value,
    DwdObservationDatasetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.FOG.value,
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.DEW.value,
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.RIPE.value,
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationDatasetStructure.DAILY.WEATHER_PHENOMENA.HAIL.value,
    # monthly
    # more_precip
    DwdObservationDatasetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DwdObservationDatasetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.HAIL.value,
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.FOG.value,
    DwdObservationDatasetStructure.MONTHLY.WEATHER_PHENOMENA.DEW.value,
    # annual
    # more_precip
    DwdObservationDatasetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DwdObservationDatasetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.THUNDER.value,
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.GLAZE.value,
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.SLEET.value,
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.HAIL.value,
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.FOG.value,
    DwdObservationDatasetStructure.ANNUAL.WEATHER_PHENOMENA.DEW.value,
)
STRING_PARAMETERS = (
    # hourly
    # cloud_type
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDICATOR.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DwdObservationDatasetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DwdObservationDatasetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR.value,
    # visibility
    DwdObservationDatasetStructure.HOURLY.VISIBILITY.VISIBILITY_INDICATOR.value,
)
