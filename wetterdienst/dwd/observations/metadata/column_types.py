from wetterdienst.dwd.metadata.column_names import (
    DWDMetaColumns,
)
from wetterdienst.dwd.observations.metadata.parameter import (
    DWDObservationParameterSetStructure,
)

DATE_FIELDS_REGULAR = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)
DATE_FIELDS_IRREGULAR = (
    DWDObservationParameterSetStructure.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DWDObservationParameterSetStructure.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
)
QUALITY_FIELDS = (
    # 1_minute
    # precipitation
    DWDObservationParameterSetStructure.MINUTE_1.PRECIPITATION.QUALITY.value,
    # 10_minutes
    # temperature_air
    DWDObservationParameterSetStructure.MINUTE_10.TEMPERATURE_AIR.QUALITY.value,
    # temperature_extreme
    DWDObservationParameterSetStructure.MINUTE_10.TEMPERATURE_EXTREME.QUALITY.value,
    # wind_extreme
    DWDObservationParameterSetStructure.MINUTE_10.WIND_EXTREME.QUALITY.value,
    # precipitation
    DWDObservationParameterSetStructure.MINUTE_10.PRECIPITATION.QUALITY.value,
    # solar
    DWDObservationParameterSetStructure.MINUTE_10.SOLAR.QUALITY.value,
    # wind
    DWDObservationParameterSetStructure.MINUTE_10.WIND.QUALITY.value,
    # hourly
    # temperature_air
    DWDObservationParameterSetStructure.HOURLY.TEMPERATURE_AIR.QUALITY.value,
    # cloud_type
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.QUALITY.value,
    # cloudiness
    DWDObservationParameterSetStructure.HOURLY.CLOUDINESS.QUALITY.value,
    # dew_point
    DWDObservationParameterSetStructure.HOURLY.DEW_POINT.QUALITY.value,
    # precipitation
    DWDObservationParameterSetStructure.HOURLY.PRECIPITATION.QUALITY.value,
    # pressure
    DWDObservationParameterSetStructure.HOURLY.PRESSURE.QUALITY.value,
    # soil_temperature
    DWDObservationParameterSetStructure.HOURLY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DWDObservationParameterSetStructure.HOURLY.SOLAR.QUALITY.value,
    # sun
    DWDObservationParameterSetStructure.HOURLY.SUN.QUALITY.value,
    # visibility
    DWDObservationParameterSetStructure.HOURLY.VISIBILITY.QUALITY.value,
    # wind
    DWDObservationParameterSetStructure.HOURLY.WIND.QUALITY.value,
    # wind_synop
    DWDObservationParameterSetStructure.HOURLY.WIND_SYNOPTIC.QUALITY.value,
    # subdaily
    # air_temperature
    DWDObservationParameterSetStructure.SUBDAILY.TEMPERATURE_AIR.QUALITY.value,
    # cloudiness
    DWDObservationParameterSetStructure.SUBDAILY.CLOUDINESS.QUALITY.value,
    # moisture
    DWDObservationParameterSetStructure.SUBDAILY.MOISTURE.QUALITY.value,
    # pressure
    DWDObservationParameterSetStructure.SUBDAILY.PRESSURE.QUALITY.value,
    # soil
    DWDObservationParameterSetStructure.SUBDAILY.SOIL.QUALITY.value,
    # visibility
    DWDObservationParameterSetStructure.SUBDAILY.VISIBILITY.QUALITY.value,
    # wind
    DWDObservationParameterSetStructure.SUBDAILY.WIND.QUALITY.value,
    # daily
    # kl
    DWDObservationParameterSetStructure.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
    DWDObservationParameterSetStructure.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    # more_precip
    DWDObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.QUALITY.value,
    # soil_temperature
    DWDObservationParameterSetStructure.DAILY.TEMPERATURE_SOIL.QUALITY.value,
    # solar
    DWDObservationParameterSetStructure.DAILY.SOLAR.QUALITY.value,
    # water_equiv
    DWDObservationParameterSetStructure.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.QUALITY.value,
    # monthly
    # kl
    DWDObservationParameterSetStructure.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DWDObservationParameterSetStructure.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DWDObservationParameterSetStructure.MONTHLY.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.QUALITY.value,
    # annual
    # kl
    DWDObservationParameterSetStructure.ANNUAL.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
    DWDObservationParameterSetStructure.ANNUAL.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
    # more_precip
    DWDObservationParameterSetStructure.ANNUAL.PRECIPITATION_MORE.QUALITY.value,
    # weather_phenomena
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.QUALITY.value,
)
INTEGER_FIELDS = (
    # 1_minute
    # precipitation
    DWDObservationParameterSetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_FORM.value,
    # 10_minutes
    # wind_extreme
    DWDObservationParameterSetStructure.MINUTE_10.WIND_EXTREME.WIND_DIRECTION_MAX_VELOCITY.value,
    # precipitation
    DWDObservationParameterSetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_INDICATOR_WR.value,
    # hourly
    # cloud_type
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER1.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER2.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER3.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_LAYER4.value,
    # cloudiness
    DWDObservationParameterSetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    # precipitation
    DWDObservationParameterSetStructure.HOURLY.PRECIPITATION.PRECIPITATION_INDICATOR.value,
    DWDObservationParameterSetStructure.HOURLY.PRECIPITATION.PRECIPITATION_FORM.value,
    # visibility
    DWDObservationParameterSetStructure.HOURLY.VISIBILITY.VISIBILITY.value,
    # wind
    DWDObservationParameterSetStructure.HOURLY.WIND.WIND_DIRECTION.value,
    # wind_synop
    DWDObservationParameterSetStructure.HOURLY.WIND_SYNOPTIC.WIND_DIRECTION.value,
    # subdaily
    # cloudiness
    DWDObservationParameterSetStructure.SUBDAILY.CLOUDINESS.CLOUD_COVER_TOTAL.value,
    DWDObservationParameterSetStructure.SUBDAILY.CLOUDINESS.CLOUD_DENSITY.value,
    # soil
    DWDObservationParameterSetStructure.SUBDAILY.SOIL.TEMPERATURE_SOIL_005.value,
    # visibility
    DWDObservationParameterSetStructure.SUBDAILY.VISIBILITY.VISIBILITY.value,
    # wind
    DWDObservationParameterSetStructure.SUBDAILY.WIND.WIND_DIRECTION.value,
    DWDObservationParameterSetStructure.SUBDAILY.WIND.WIND_FORCE_BEAUFORT.value,
    # daily
    # more_precip
    DWDObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.PRECIPITATION_FORM.value,
    DWDObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    DWDObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    # water_equiv
    DWDObservationParameterSetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH_EXCELLED.value,
    DWDObservationParameterSetStructure.DAILY.WATER_EQUIVALENT.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.FOG.value,
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.DEW.value,
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.RIPE.value,
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationParameterSetStructure.DAILY.WEATHER_PHENOMENA.HAIL.value,
    # monthly
    # more_precip
    DWDObservationParameterSetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DWDObservationParameterSetStructure.MONTHLY.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.HAIL.value,
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.FOG.value,
    DWDObservationParameterSetStructure.MONTHLY.WEATHER_PHENOMENA.DEW.value,
    # annual
    # more_precip
    DWDObservationParameterSetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH_NEW.value,
    DWDObservationParameterSetStructure.ANNUAL.PRECIPITATION_MORE.SNOW_DEPTH.value,
    # weather_phenomena
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STRONG_WIND.value,
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.STORM_STORMIER_WIND.value,
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.THUNDER.value,
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.GLAZE.value,
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.SLEET.value,
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.HAIL.value,
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.FOG.value,
    DWDObservationParameterSetStructure.ANNUAL.WEATHER_PHENOMENA.DEW.value,
)
STRING_FIELDS = (
    # hourly
    # cloud_type
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDICATOR.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DWDObservationParameterSetStructure.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DWDObservationParameterSetStructure.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDICATOR.value,
    # visibility
    DWDObservationParameterSetStructure.HOURLY.VISIBILITY.VISIBILITY_INDICATOR.value,
)
