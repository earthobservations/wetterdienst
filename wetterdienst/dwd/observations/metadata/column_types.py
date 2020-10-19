from wetterdienst.dwd.metadata.column_names import (
    DWDMetaColumns,
)
from wetterdienst.dwd.observations.metadata.parameter import DWDObsParameterSetStructure

DATE_FIELDS_REGULAR = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)
DATE_FIELDS_IRREGULAR = (
    DWDObsParameterSetStructure.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DWDObsParameterSetStructure.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
)
QUALITY_FIELDS = (
    # 1_minute
    # precipitation
    DWDObsParameterSetStructure.MINUTE_1.PRECIPITATION.QUALITY.value,
    # 10_minutes
    # temperature_air
    DWDObsParameterSetStructure.MINUTE_10.TEMPERATURE_AIR.QUALITY.value,
    # temperature_extreme
    DWDObsParameterSetStructure.MINUTE_10.TEMPERATURE_EXTREME.QUALITY.value,
    # wind_extreme
    DWDObsParameterSetStructure.MINUTE_10.WIND_EXTREME.QUALITY.value,
    # precipitation
    DWDObsParameterSetStructure.MINUTE_10.PRECIPITATION.QUALITY.value,
    # solar
    DWDObsParameterSetStructure.MINUTE_10.SOLAR.QUALITY.value,
    # wind
    DWDObsParameterSetStructure.MINUTE_10.WIND.QUALITY.value,
    # hourly
    # temperature_air
    DWDObsParameterSetStructure.HOURLY.TEMPERATURE_AIR.QUALITY.value,
    # cloud_type
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.QUALITY.value,
    # cloudiness
    DWDObsParameterSetStructure.HOURLY.CLOUDINESS.QUALITY.value,
    # dew_point
    DWDObsParameterSetStructure.HOURLY.DEW_POINT.QUALITY.value,
    # precipitation
    DWDObsParameterSetStructure.HOURLY.PRECIPITATION.QUALITY.value,
    # pressure
    DWDObsParameterSetStructure.HOURLY.PRESSURE.QUALITY.value,
    # soil_temperature
    DWDObsParameterSetStructure.HOURLY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DWDObsParameterSetStructure.HOURLY.SOLAR.QUALITY.value,
    # sun
    DWDObsParameterSetStructure.HOURLY.SUN.QUALITY.value,
    # visibility
    DWDObsParameterSetStructure.HOURLY.VISIBILITY.QUALITY.value,
    # wind
    DWDObsParameterSetStructure.HOURLY.WIND.QUALITY.value,
    # wind_synop
    DWDObsParameterSetStructure.HOURLY.WIND_SYNOPTIC.QUALITY.value,
    # subdaily
    # air_temperature
    DWDObsParameterSetStructure.SUBDAILY.TEMPERATURE_AIR.QUALITY.value,
    # cloudiness
    DWDObsParameterSetStructure.SUBDAILY.CLOUDINESS.QUALITY.value,
    # moisture
    DWDObsParameterSetStructure.SUBDAILY.MOISTURE.QUALITY.value,
    # pressure
    DWDObsParameterSetStructure.SUBDAILY.PRESSURE.QUALITY.value,
    # soil
    DWDObsParameterSetStructure.SUBDAILY.SOIL.QUALITY.value,
    # visibility
    DWDObsParameterSetStructure.SUBDAILY.VISIBILITY.QUALITY.value,
    # wind
    DWDObsParameterSetStructure.SUBDAILY.WIND.QUALITY.value,
    # daily
    # kl
    DWDObsParameterSetStructure.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
    DWDObsParameterSetStructure.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    # more_precip
    DWDObsParameterSetStructure.DAILY.PRECIPITATION_MORE.QUALITY.value,
    # soil_temperature
    DWDObsParameterSetStructure.DAILY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DWDObsParameterSetStructure.DAILY.SOLAR.QUALITY.value,
    # water_equiv
    DWDObsParameterSetStructure.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.QUALITY.value,
    # monthly
    # kl
    DWDObsParameterSetStructure.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DWDObsParameterSetStructure.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DWDObsParameterSetStructure.MONTHLY.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.QUALITY.value,
    # annual
    # kl
    DWDObsParameterSetStructure.ANNUAL.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DWDObsParameterSetStructure.ANNUAL.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DWDObsParameterSetStructure.ANNUAL.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.QUALITY.value,
)
INTEGER_FIELDS = (
    # 1_minute
    # precipitation
    DWDObsParameterSetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM.value,
    # 10_minutes
    # wind_extreme
    DWDObsParameterSetStructure.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_MAX_VELOCITY.value,
    # precipitation
    DWDObsParameterSetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR.value,
    # hourly
    # cloud_type
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4.value,
    # cloudiness
    DWDObsParameterSetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    # precipitation
    DWDObsParameterSetStructure.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR.value,
    DWDObsParameterSetStructure.HOURLY.PRECIPITATION.PRECIPITATION_FORM.value,
    # visibility
    DWDObsParameterSetStructure.HOURLY.VISIBILITY.VISIBILITY.value,
    # wind
    DWDObsParameterSetStructure.HOURLY.WIND.WIND_DIRECTION.value,
    # wind_synop
    DWDObsParameterSetStructure.HOURLY.WIND_SYNOPTIC.WIND_DIRECTION.value,
    # subdaily
    # cloudiness
    DWDObsParameterSetStructure.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    DWDObsParameterSetStructure.SUBDAILY.CLOUDINESS.CLOUD_DENSITY.value,
    # soil
    DWDObsParameterSetStructure.SUBDAILY.SOIL.TEMPERATURE_SOIL_005.value,
    # visibility
    DWDObsParameterSetStructure.SUBDAILY.VISIBILITY.VISIBILITY.value,
    # wind
    DWDObsParameterSetStructure.SUBDAILY.WIND.WIND_DIRECTION.value,
    DWDObsParameterSetStructure.SUBDAILY.WIND.WIND_FORCE_BEAUFORT.value,
    # daily
    # more_precip
    DWDObsParameterSetStructure.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM.value,
    DWDObsParameterSetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    DWDObsParameterSetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    # water_equiv
    DWDObsParameterSetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED.value,
    DWDObsParameterSetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.FOG.value,
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.THUNDER.value,
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.DEW.value,
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.GLAZE.value,
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.RIPE.value,
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.SLEET.value,
    DWDObsParameterSetStructure.DAILY.WEATHER_PHENOMENA.HAIL.value,
    # monthly
    # more_precip
    DWDObsParameterSetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DWDObsParameterSetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.THUNDER.value,
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.GLAZE.value,
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.SLEET.value,
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.HAIL.value,
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.FOG.value,
    DWDObsParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.DEW.value,
    # annual
    # more_precip
    DWDObsParameterSetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DWDObsParameterSetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.THUNDER.value,
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.GLAZE.value,
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.SLEET.value,
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.HAIL.value,
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.FOG.value,
    DWDObsParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.DEW.value,
)
STRING_FIELDS = (
    # hourly
    # cloud_type
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDICATOR.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DWDObsParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DWDObsParameterSetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR.value,
    # visibility
    DWDObsParameterSetStructure.HOURLY.VISIBILITY.VISIBILITY_INDICATOR.value,
)
