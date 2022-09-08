# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
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
STRING_PARAMETERS = {
    # hourly
    # cloud_type
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDEX.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DwdObservationParameter.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDEX.value,
    # visibility
    DwdObservationParameter.HOURLY.VISIBILITY.VISIBILITY_RANGE_INDEX.value,
}
