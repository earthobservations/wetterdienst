from wetterdienst.dwd.metadata.column_names import (
    DWDMetaColumns,
)
from wetterdienst.dwd.observations.metadata.column_names import (
    DWDObservationsOrigDataColumns,
    DWDObservationsDataColumns,
)

DATE_FIELDS_REGULAR = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)
DATE_FIELDS_IRREGULAR = (
    DWDObservationsDataColumns.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DWDObservationsDataColumns.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
)
QUALITY_FIELDS = (
    # 1_minute
    # precipitation
    DWDObservationsOrigDataColumns.MINUTE_1.PRECIPITATION.QUALITY.value,
    # 10_minutes
    # temperature_air
    DWDObservationsOrigDataColumns.MINUTE_10.TEMPERATURE_AIR.QUALITY.value,
    # temperature_extreme
    DWDObservationsOrigDataColumns.MINUTE_10.TEMPERATURE_EXTREME.QUALITY.value,
    # wind_extreme
    DWDObservationsOrigDataColumns.MINUTE_10.WIND_EXTREME.QUALITY.value,
    # precipitation
    DWDObservationsOrigDataColumns.MINUTE_10.PRECIPITATION.QUALITY.value,
    # solar
    DWDObservationsOrigDataColumns.MINUTE_10.SOLAR.QUALITY.value,
    # wind
    DWDObservationsOrigDataColumns.MINUTE_10.WIND.QUALITY.value,
    # hourly
    # temperature_air
    DWDObservationsOrigDataColumns.HOURLY.TEMPERATURE_AIR.QUALITY.value,
    # cloud_type
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.QUALITY.value,
    # cloudiness
    DWDObservationsOrigDataColumns.HOURLY.CLOUDINESS.QUALITY.value,
    # dew_point
    DWDObservationsOrigDataColumns.HOURLY.DEW_POINT.QUALITY.value,
    # precipitation
    DWDObservationsOrigDataColumns.HOURLY.PRECIPITATION.QUALITY.value,
    # pressure
    DWDObservationsOrigDataColumns.HOURLY.PRESSURE.QUALITY.value,
    # soil_temperature
    DWDObservationsOrigDataColumns.HOURLY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DWDObservationsOrigDataColumns.HOURLY.SOLAR.QUALITY.value,
    # sun
    DWDObservationsOrigDataColumns.HOURLY.SUN.QUALITY.value,
    # visibility
    DWDObservationsOrigDataColumns.HOURLY.VISIBILITY.QUALITY.value,
    # wind
    DWDObservationsOrigDataColumns.HOURLY.WIND.QUALITY.value,
    # wind_synop
    DWDObservationsOrigDataColumns.HOURLY.WIND_SYNOPTIC.QUALITY.value,
    # subdaily
    # air_temperature
    DWDObservationsOrigDataColumns.SUBDAILY.TEMPERATURE_AIR.QUALITY.value,
    # cloudiness
    DWDObservationsOrigDataColumns.SUBDAILY.CLOUDINESS.QUALITY.value,
    # moisture
    DWDObservationsOrigDataColumns.SUBDAILY.MOISTURE.QUALITY.value,
    # pressure
    DWDObservationsOrigDataColumns.SUBDAILY.PRESSURE.QUALITY.value,
    # soil
    DWDObservationsOrigDataColumns.SUBDAILY.SOIL.QUALITY.value,
    # visibility
    DWDObservationsOrigDataColumns.SUBDAILY.VISIBILITY.QUALITY.value,
    # wind
    DWDObservationsOrigDataColumns.SUBDAILY.WIND.QUALITY.value,
    # daily
    # kl
    DWDObservationsOrigDataColumns.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
    DWDObservationsOrigDataColumns.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    # more_precip
    DWDObservationsOrigDataColumns.DAILY.PRECIPITATION_MORE.QUALITY.value,
    # soil_temperature
    DWDObservationsOrigDataColumns.DAILY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DWDObservationsOrigDataColumns.DAILY.SOLAR.QUALITY.value,
    # water_equiv
    DWDObservationsOrigDataColumns.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.QUALITY.value,
    # monthly
    # kl
    DWDObservationsOrigDataColumns.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DWDObservationsOrigDataColumns.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DWDObservationsOrigDataColumns.MONTHLY.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.QUALITY.value,
    # annual
    # kl
    DWDObservationsOrigDataColumns.ANNUAL.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DWDObservationsOrigDataColumns.ANNUAL.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DWDObservationsOrigDataColumns.ANNUAL.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.QUALITY.value,
)
INTEGER_FIELDS = (
    # 1_minute
    # precipitation
    DWDObservationsOrigDataColumns.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM.value,
    # 10_minutes
    # wind_extreme
    DWDObservationsOrigDataColumns.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_MAX_VELOCITY.value,
    # precipitation
    DWDObservationsOrigDataColumns.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR.value,
    # hourly
    # cloud_type
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4.value,
    # cloudiness
    DWDObservationsOrigDataColumns.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    # precipitation
    DWDObservationsOrigDataColumns.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR.value,
    DWDObservationsOrigDataColumns.HOURLY.PRECIPITATION.PRECIPITATION_FORM.value,
    # visibility
    DWDObservationsOrigDataColumns.HOURLY.VISIBILITY.VISIBILITY.value,
    # wind
    DWDObservationsOrigDataColumns.HOURLY.WIND.WIND_DIRECTION.value,
    # wind_synop
    DWDObservationsOrigDataColumns.HOURLY.WIND_SYNOPTIC.WIND_DIRECTION.value,
    # subdaily
    # cloudiness
    DWDObservationsOrigDataColumns.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    DWDObservationsOrigDataColumns.SUBDAILY.CLOUDINESS.CLOUD_DENSITY.value,
    # soil
    DWDObservationsOrigDataColumns.SUBDAILY.SOIL.TEMPERATURE_SOIL_005.value,
    # visibility
    DWDObservationsOrigDataColumns.SUBDAILY.VISIBILITY.VISIBILITY.value,
    # wind
    DWDObservationsOrigDataColumns.SUBDAILY.WIND.WIND_DIRECTION.value,
    DWDObservationsOrigDataColumns.SUBDAILY.WIND.WIND_FORCE_BEAUFORT.value,
    # daily
    # more_precip
    DWDObservationsOrigDataColumns.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM.value,
    DWDObservationsOrigDataColumns.DAILY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    DWDObservationsOrigDataColumns.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    # water_equiv
    DWDObservationsOrigDataColumns.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED.value,
    DWDObservationsOrigDataColumns.DAILY.WATER_EQUIVALENT.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.FOG.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.DEW.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.RIPE.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.HAIL.value,
    # monthly
    # more_precip
    DWDObservationsOrigDataColumns.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DWDObservationsOrigDataColumns.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.HAIL.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.FOG.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.DEW.value,
    # annual
    # more_precip
    DWDObservationsOrigDataColumns.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DWDObservationsOrigDataColumns.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.HAIL.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.FOG.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.DEW.value,
)
STRING_FIELDS = (
    # hourly
    # cloud_type
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDICATOR.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DWDObservationsOrigDataColumns.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR.value,
    # visibility
    DWDObservationsOrigDataColumns.HOURLY.VISIBILITY.VISIBILITY_INDICATOR.value,
)
