from wetterdienst.dwd.metadata.column_names import (
    DWDMetaColumns,
)
from wetterdienst.dwd.observations.metadata.parameter import DWDObservationParameter

DATE_FIELDS_REGULAR = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)
DATE_FIELDS_IRREGULAR = (
    DWDObservationParameter.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DWDObservationParameter.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
)
QUALITY_FIELDS = (
    # 1_minute
    # precipitation
    DWDObservationParameter.MINUTE_1.PRECIPITATION.QUALITY.value,
    # 10_minutes
    # temperature_air
    DWDObservationParameter.MINUTE_10.TEMPERATURE_AIR.QUALITY.value,
    # temperature_extreme
    DWDObservationParameter.MINUTE_10.TEMPERATURE_EXTREME.QUALITY.value,
    # wind_extreme
    DWDObservationParameter.MINUTE_10.WIND_EXTREME.QUALITY.value,
    # precipitation
    DWDObservationParameter.MINUTE_10.PRECIPITATION.QUALITY.value,
    # solar
    DWDObservationParameter.MINUTE_10.SOLAR.QUALITY.value,
    # wind
    DWDObservationParameter.MINUTE_10.WIND.QUALITY.value,
    # hourly
    # temperature_air
    DWDObservationParameter.HOURLY.TEMPERATURE_AIR.QUALITY.value,
    # cloud_type
    DWDObservationParameter.HOURLY.CLOUD_TYPE.QUALITY.value,
    # cloudiness
    DWDObservationParameter.HOURLY.CLOUDINESS.QUALITY.value,
    # dew_point
    DWDObservationParameter.HOURLY.DEW_POINT.QUALITY.value,
    # precipitation
    DWDObservationParameter.HOURLY.PRECIPITATION.QUALITY.value,
    # pressure
    DWDObservationParameter.HOURLY.PRESSURE.QUALITY.value,
    # soil_temperature
    DWDObservationParameter.HOURLY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DWDObservationParameter.HOURLY.SOLAR.QUALITY.value,
    # sun
    DWDObservationParameter.HOURLY.SUN.QUALITY.value,
    # visibility
    DWDObservationParameter.HOURLY.VISIBILITY.QUALITY.value,
    # wind
    DWDObservationParameter.HOURLY.WIND.QUALITY.value,
    # wind_synop
    DWDObservationParameter.HOURLY.WIND_SYNOPTIC.QUALITY.value,
    # subdaily
    # air_temperature
    DWDObservationParameter.SUBDAILY.TEMPERATURE_AIR.QUALITY.value,
    # cloudiness
    DWDObservationParameter.SUBDAILY.CLOUDINESS.QUALITY.value,
    # moisture
    DWDObservationParameter.SUBDAILY.MOISTURE.QUALITY.value,
    # pressure
    DWDObservationParameter.SUBDAILY.PRESSURE.QUALITY.value,
    # soil
    DWDObservationParameter.SUBDAILY.SOIL.QUALITY.value,
    # visibility
    DWDObservationParameter.SUBDAILY.VISIBILITY.QUALITY.value,
    # wind
    DWDObservationParameter.SUBDAILY.WIND.QUALITY.value,
    # daily
    # kl
    DWDObservationParameter.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
    DWDObservationParameter.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    # more_precip
    DWDObservationParameter.DAILY.PRECIPITATION_MORE.QUALITY.value,
    # soil_temperature
    DWDObservationParameter.DAILY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DWDObservationParameter.DAILY.SOLAR.QUALITY.value,
    # water_equiv
    DWDObservationParameter.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.QUALITY.value,
    # monthly
    # kl
    DWDObservationParameter.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DWDObservationParameter.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DWDObservationParameter.MONTHLY.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.QUALITY.value,
    # annual
    # kl
    DWDObservationParameter.ANNUAL.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DWDObservationParameter.ANNUAL.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DWDObservationParameter.ANNUAL.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.QUALITY.value,
)
INTEGER_FIELDS = (
    # 1_minute
    # precipitation
    DWDObservationParameter.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM.value,
    # 10_minutes
    # wind_extreme
    DWDObservationParameter.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_MAX_VELOCITY.value,
    # precipitation
    DWDObservationParameter.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR.value,
    # hourly
    # cloud_type
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4.value,
    # cloudiness
    DWDObservationParameter.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    # precipitation
    DWDObservationParameter.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR.value,
    DWDObservationParameter.HOURLY.PRECIPITATION.PRECIPITATION_FORM.value,
    # visibility
    DWDObservationParameter.HOURLY.VISIBILITY.VISIBILITY.value,
    # wind
    DWDObservationParameter.HOURLY.WIND.WIND_DIRECTION.value,
    # wind_synop
    DWDObservationParameter.HOURLY.WIND_SYNOPTIC.WIND_DIRECTION.value,
    # subdaily
    # cloudiness
    DWDObservationParameter.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    DWDObservationParameter.SUBDAILY.CLOUDINESS.CLOUD_DENSITY.value,
    # soil
    DWDObservationParameter.SUBDAILY.SOIL.TEMPERATURE_SOIL_005.value,
    # visibility
    DWDObservationParameter.SUBDAILY.VISIBILITY.VISIBILITY.value,
    # wind
    DWDObservationParameter.SUBDAILY.WIND.WIND_DIRECTION.value,
    DWDObservationParameter.SUBDAILY.WIND.WIND_FORCE_BEAUFORT.value,
    # daily
    # more_precip
    DWDObservationParameter.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM.value,
    DWDObservationParameter.DAILY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    DWDObservationParameter.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    # water_equiv
    DWDObservationParameter.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED.value,
    DWDObservationParameter.DAILY.WATER_EQUIVALENT.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.FOG.value,
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.DEW.value,
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.RIPE.value,
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationParameter.DAILY.WEATHER_PHENOMENA.HAIL.value,
    # monthly
    # more_precip
    DWDObservationParameter.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DWDObservationParameter.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.HAIL.value,
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.FOG.value,
    DWDObservationParameter.MONTHLY.WEATHER_PHENOMENA.DEW.value,
    # annual
    # more_precip
    DWDObservationParameter.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DWDObservationParameter.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.HAIL.value,
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.FOG.value,
    DWDObservationParameter.ANNUAL.WEATHER_PHENOMENA.DEW.value,
)
STRING_FIELDS = (
    # hourly
    # cloud_type
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDICATOR.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DWDObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DWDObservationParameter.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR.value,
    # visibility
    DWDObservationParameter.HOURLY.VISIBILITY.VISIBILITY_INDICATOR.value,
)
