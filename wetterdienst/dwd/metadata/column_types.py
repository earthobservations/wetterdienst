from wetterdienst.dwd.metadata.column_names import (
    DWDMetaColumns,
)
from wetterdienst.dwd.observations.metadata import DWDObservationsOrigDataColumns, \
    DWDObservationsDataColumns

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
    DWDObservationsOrigDataColumns.MINUTE_1.PRECIPITATION.QN.value,
    # 10_minutes
    # temperature_air
    DWDObservationsOrigDataColumns.MINUTE_10.TEMPERATURE_AIR.QN.value,
    # temperature_extreme
    DWDObservationsOrigDataColumns.MINUTE_10.TEMPERATURE_EXTREME.QN.value,
    # wind_extreme
    DWDObservationsOrigDataColumns.MINUTE_10.WIND_EXTREME.QN.value,
    # precipitation
    DWDObservationsOrigDataColumns.MINUTE_10.PRECIPITATION.QN.value,
    # solar
    DWDObservationsOrigDataColumns.MINUTE_10.SOLAR.QN.value,
    # wind
    DWDObservationsOrigDataColumns.MINUTE_10.WIND.QN.value,
    # hourly
    # temperature_air
    DWDObservationsOrigDataColumns.HOURLY.TEMPERATURE_AIR.QN_9.value,
    # cloud_type
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.QN_8.value,
    # cloudiness
    DWDObservationsOrigDataColumns.HOURLY.CLOUDINESS.QN_8.value,
    # dew_point
    DWDObservationsOrigDataColumns.HOURLY.DEW_POINT.QN_8.value,
    # precipitation
    DWDObservationsOrigDataColumns.HOURLY.PRECIPITATION.QN_8.value,
    # pressure
    DWDObservationsOrigDataColumns.HOURLY.PRESSURE.QN_8.value,
    # soil_temperature
    DWDObservationsOrigDataColumns.HOURLY.TEMPERATURE_SOIL.QN_2.value,
    # solar
    DWDObservationsOrigDataColumns.HOURLY.SOLAR.QN_592.value,
    # sun
    DWDObservationsOrigDataColumns.HOURLY.SUN.QN_7.value,
    # visibility
    DWDObservationsOrigDataColumns.HOURLY.VISIBILITY.QN_8.value,
    # wind
    DWDObservationsOrigDataColumns.HOURLY.WIND.QN_3.value,
    # wind_synop
    DWDObservationsOrigDataColumns.HOURLY.WIND_SYNOPTIC.QN_8.value,
    # subdaily
    # air_temperature
    DWDObservationsOrigDataColumns.SUBDAILY.TEMPERATURE_AIR.QN_4.value,
    # cloudiness
    DWDObservationsOrigDataColumns.SUBDAILY.CLOUDINESS.QN_4.value,
    # moisture
    DWDObservationsOrigDataColumns.SUBDAILY.MOISTURE.QN_4.value,
    # pressure
    DWDObservationsOrigDataColumns.SUBDAILY.PRESSURE.QN_4.value,
    # soil
    DWDObservationsOrigDataColumns.SUBDAILY.SOIL.QN_4.value,
    # visibility
    DWDObservationsOrigDataColumns.SUBDAILY.VISIBILITY.QN_4.value,
    # wind
    DWDObservationsOrigDataColumns.SUBDAILY.WIND.QN_4.value,
    # daily
    # kl
    DWDObservationsOrigDataColumns.DAILY.CLIMATE_SUMMARY.QN_3.value,
    DWDObservationsOrigDataColumns.DAILY.CLIMATE_SUMMARY.QN_4.value,
    # more_precip
    DWDObservationsOrigDataColumns.DAILY.PRECIPITATION_MORE.QN_6.value,
    # soil_temperature
    DWDObservationsOrigDataColumns.DAILY.TEMPERATURE_SOIL.QN_2.value,
    # solar
    DWDObservationsOrigDataColumns.DAILY.SOLAR.QN_592.value,
    # water_equiv
    DWDObservationsOrigDataColumns.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.QN_4.value,
    # monthly
    # kl
    DWDObservationsOrigDataColumns.MONTHLY.CLIMATE_SUMMARY.QN_4.value,
    DWDObservationsOrigDataColumns.MONTHLY.CLIMATE_SUMMARY.QN_6.value,
    # more_precip
    DWDObservationsOrigDataColumns.MONTHLY.PRECIPITATION_MORE.QN_6.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.QN_4.value,
    # annual
    # kl
    DWDObservationsOrigDataColumns.ANNUAL.CLIMATE_SUMMARY.QN_4.value,
    # more_precip
    DWDObservationsOrigDataColumns.ANNUAL.PRECIPITATION_MORE.QN_6.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.QN_4.value,
)
INTEGER_FIELDS = (
    # 1_minute
    # precipitation
    DWDObservationsOrigDataColumns.MINUTE_1.PRECIPITATION.RS_IND_01.value,
    # 10_minutes
    # wind_extreme
    DWDObservationsOrigDataColumns.MINUTE_10.WIND_EXTREME.DX_10.value,
    # precipitation
    DWDObservationsOrigDataColumns.MINUTE_10.PRECIPITATION.RWS_IND_10.value,
    # hourly
    # cloud_type
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_N.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_CS.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_NS.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_CS.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_NS.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_CS.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_NS.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_CS.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_NS.value,
    # cloudiness
    DWDObservationsOrigDataColumns.HOURLY.CLOUDINESS.V_N.value,
    # precipitation
    DWDObservationsOrigDataColumns.HOURLY.PRECIPITATION.RS_IND.value,
    DWDObservationsOrigDataColumns.HOURLY.PRECIPITATION.WRTR.value,
    # visibility
    DWDObservationsOrigDataColumns.HOURLY.VISIBILITY.V_VV.value,
    # wind
    DWDObservationsOrigDataColumns.HOURLY.WIND.D.value,
    # wind_synop
    DWDObservationsOrigDataColumns.HOURLY.WIND_SYNOPTIC.DD.value,
    # subdaily
    # cloudiness
    DWDObservationsOrigDataColumns.SUBDAILY.CLOUDINESS.N_TER.value,
    DWDObservationsOrigDataColumns.SUBDAILY.CLOUDINESS.CD_TER.value,
    # soil
    DWDObservationsOrigDataColumns.SUBDAILY.SOIL.EK_TER.value,
    # visibility
    DWDObservationsOrigDataColumns.SUBDAILY.VISIBILITY.VK_TER.value,
    # wind
    DWDObservationsOrigDataColumns.SUBDAILY.WIND.DK_TER.value,
    DWDObservationsOrigDataColumns.SUBDAILY.WIND.FK_TER.value,
    # daily
    # more_precip
    DWDObservationsOrigDataColumns.DAILY.PRECIPITATION_MORE.RSF.value,
    DWDObservationsOrigDataColumns.DAILY.PRECIPITATION_MORE.SH_TAG.value,
    DWDObservationsOrigDataColumns.DAILY.PRECIPITATION_MORE.NSH_TAG.value,
    # water_equiv
    DWDObservationsOrigDataColumns.DAILY.WATER_EQUIVALENT.ASH_6.value,
    DWDObservationsOrigDataColumns.DAILY.WATER_EQUIVALENT.SH_TAG.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.NEBEL.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.GEWITTER.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.STURM_6.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.STURM_8.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.TAU.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.GLATTEIS.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.REIF.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.GRAUPEL.value,
    DWDObservationsOrigDataColumns.DAILY.WEATHER_PHENOMENA.HAGEL.value,
    # monthly
    # more_precip
    DWDObservationsOrigDataColumns.MONTHLY.PRECIPITATION_MORE.MO_NSH.value,
    DWDObservationsOrigDataColumns.MONTHLY.PRECIPITATION_MORE.MO_SH_S.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_STURM_6.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_STURM_8.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GEWITTER.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GLATTEIS.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GRAUPEL.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_HAGEL.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_NEBEL.value,
    DWDObservationsOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_TAU.value,
    # annual
    # more_precip
    DWDObservationsOrigDataColumns.ANNUAL.PRECIPITATION_MORE.JA_NSH.value,
    DWDObservationsOrigDataColumns.ANNUAL.PRECIPITATION_MORE.JA_SH_S.value,
    # weather_phenomena
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_STURM_6.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_STURM_8.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GEWITTER.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GLATTEIS.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GRAUPEL.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_HAGEL.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_NEBEL.value,
    DWDObservationsOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_TAU.value,
)
STRING_FIELDS = (
    # hourly
    # cloud_type
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_N_I.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_CSA.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_CSA.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_CSA.value,
    DWDObservationsOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_CSA.value,
    # cloudiness
    DWDObservationsOrigDataColumns.HOURLY.CLOUDINESS.V_N_I.value,
    # visibility
    DWDObservationsOrigDataColumns.HOURLY.VISIBILITY.V_VV_I.value,
)
