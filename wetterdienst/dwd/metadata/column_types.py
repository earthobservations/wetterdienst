from wetterdienst.dwd.metadata.column_names import (
    DWDMetaColumns,
    DWDDataColumns,
    DWDOrigDataColumns,
)

DATE_FIELDS_REGULAR = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)
DATE_FIELDS_IRREGULAR = (
    DWDDataColumns.HOURLY.SOLAR.END_OF_INTERVAL.value,
    DWDDataColumns.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
)
QUALITY_FIELDS = (
    # 1_minute
    # precipitation
    DWDOrigDataColumns.MINUTE_1.PRECIPITATION.QN.value,
    # 10_minutes
    # temperature_air
    DWDOrigDataColumns.MINUTE_10.TEMPERATURE_AIR.QN.value,
    # temperature_extreme
    DWDOrigDataColumns.MINUTE_10.TEMPERATURE_EXTREME.QN.value,
    # wind_extreme
    DWDOrigDataColumns.MINUTE_10.WIND_EXTREME.QN.value,
    # precipitation
    DWDOrigDataColumns.MINUTE_10.PRECIPITATION.QN.value,
    # solar
    DWDOrigDataColumns.MINUTE_10.SOLAR.QN.value,
    # wind
    DWDOrigDataColumns.MINUTE_10.WIND.QN.value,
    # hourly
    # temperature_air
    DWDOrigDataColumns.HOURLY.TEMPERATURE_AIR.QN_9.value,
    # cloud_type
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.QN_8.value,
    # cloudiness
    DWDOrigDataColumns.HOURLY.CLOUDINESS.QN_8.value,
    # dew_point
    DWDOrigDataColumns.HOURLY.DEW_POINT.QN_8.value,
    # precipitation
    DWDOrigDataColumns.HOURLY.PRECIPITATION.QN_8.value,
    # pressure
    DWDOrigDataColumns.HOURLY.PRESSURE.QN_8.value,
    # soil_temperature
    DWDOrigDataColumns.HOURLY.TEMPERATURE_SOIL.QN_2.value,
    # solar
    DWDOrigDataColumns.HOURLY.SOLAR.QN_592.value,
    # sun
    DWDOrigDataColumns.HOURLY.SUN.QN_7.value,
    # visibility
    DWDOrigDataColumns.HOURLY.VISIBILITY.QN_8.value,
    # wind
    DWDOrigDataColumns.HOURLY.WIND.QN_3.value,
    # wind_synop
    DWDOrigDataColumns.HOURLY.WIND_SYNOPTIC.QN_8.value,
    # subdaily
    # air_temperature
    DWDOrigDataColumns.SUBDAILY.TEMPERATURE_AIR.QN_4.value,
    # cloudiness
    DWDOrigDataColumns.SUBDAILY.CLOUDINESS.QN_4.value,
    # moisture
    DWDOrigDataColumns.SUBDAILY.MOISTURE.QN_4.value,
    # pressure
    DWDOrigDataColumns.SUBDAILY.PRESSURE.QN_4.value,
    # soil
    DWDOrigDataColumns.SUBDAILY.SOIL.QN_4.value,
    # visibility
    DWDOrigDataColumns.SUBDAILY.VISIBILITY.QN_4.value,
    # wind
    DWDOrigDataColumns.SUBDAILY.WIND.QN_4.value,
    # daily
    # kl
    DWDOrigDataColumns.DAILY.CLIMATE_SUMMARY.QN_3.value,
    DWDOrigDataColumns.DAILY.CLIMATE_SUMMARY.QN_4.value,
    # more_precip
    DWDOrigDataColumns.DAILY.PRECIPITATION_MORE.QN_6.value,
    # soil_temperature
    DWDOrigDataColumns.DAILY.TEMPERATURE_SOIL.QN_2.value,
    # solar
    DWDOrigDataColumns.DAILY.SOLAR.QN_592.value,
    # water_equiv
    DWDOrigDataColumns.DAILY.WATER_EQUIVALENT.QN_6.value,
    # weather_phenomena
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.QN_4.value,
    # monthly
    # kl
    DWDOrigDataColumns.MONTHLY.CLIMATE_SUMMARY.QN_4.value,
    DWDOrigDataColumns.MONTHLY.CLIMATE_SUMMARY.QN_6.value,
    # more_precip
    DWDOrigDataColumns.MONTHLY.PRECIPITATION_MORE.QN_6.value,
    # weather_phenomena
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.QN_4.value,
    # annual
    # kl
    DWDOrigDataColumns.ANNUAL.CLIMATE_SUMMARY.QN_4.value,
    # more_precip
    DWDOrigDataColumns.ANNUAL.PRECIPITATION_MORE.QN_6.value,
    # weather_phenomena
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.QN_4.value,
)
INTEGER_FIELDS = (
    # 1_minute
    # precipitation
    DWDOrigDataColumns.MINUTE_1.PRECIPITATION.RS_IND_01.value,
    # 10_minutes
    # wind_extreme
    DWDOrigDataColumns.MINUTE_10.WIND_EXTREME.DX_10.value,
    # precipitation
    DWDOrigDataColumns.MINUTE_10.PRECIPITATION.RWS_IND_10.value,
    # hourly
    # cloud_type
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_N.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_CS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_NS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_CS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_NS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_CS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_NS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_CS.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_NS.value,
    # cloudiness
    DWDOrigDataColumns.HOURLY.CLOUDINESS.V_N.value,
    # precipitation
    DWDOrigDataColumns.HOURLY.PRECIPITATION.RS_IND.value,
    DWDOrigDataColumns.HOURLY.PRECIPITATION.WRTR.value,
    # visibility
    DWDOrigDataColumns.HOURLY.VISIBILITY.V_VV.value,
    # wind
    DWDOrigDataColumns.HOURLY.WIND.D.value,
    # wind_synop
    DWDOrigDataColumns.HOURLY.WIND_SYNOPTIC.DD.value,
    # subdaily
    # cloudiness
    DWDOrigDataColumns.SUBDAILY.CLOUDINESS.N_TER.value,
    DWDOrigDataColumns.SUBDAILY.CLOUDINESS.CD_TER.value,
    # soil
    DWDOrigDataColumns.SUBDAILY.SOIL.EK_TER.value,
    # visibility
    DWDOrigDataColumns.SUBDAILY.VISIBILITY.VK_TER.value,
    # wind
    DWDOrigDataColumns.SUBDAILY.WIND.DK_TER.value,
    DWDOrigDataColumns.SUBDAILY.WIND.FK_TER.value,
    # daily
    # more_precip
    DWDOrigDataColumns.DAILY.PRECIPITATION_MORE.RSF.value,
    DWDOrigDataColumns.DAILY.PRECIPITATION_MORE.SH_TAG.value,
    DWDOrigDataColumns.DAILY.PRECIPITATION_MORE.NSH_TAG.value,
    # water_equiv
    DWDOrigDataColumns.DAILY.WATER_EQUIVALENT.ASH_6.value,
    DWDOrigDataColumns.DAILY.WATER_EQUIVALENT.SH_TAG.value,
    # weather_phenomena
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.NEBEL.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.GEWITTER.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.STURM_6.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.STURM_8.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.TAU.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.GLATTEIS.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.REIF.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.GRAUPEL.value,
    DWDOrigDataColumns.DAILY.WEATHER_PHENOMENA.HAGEL.value,
    # monthly
    # more_precip
    DWDOrigDataColumns.MONTHLY.PRECIPITATION_MORE.MO_NSH.value,
    DWDOrigDataColumns.MONTHLY.PRECIPITATION_MORE.MO_SH_S.value,
    # weather_phenomena
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_STURM_6.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_STURM_8.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GEWITTER.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GLATTEIS.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_GRAUPEL.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_HAGEL.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_NEBEL.value,
    DWDOrigDataColumns.MONTHLY.WEATHER_PHENOMENA.MO_TAU.value,
    # annual
    # more_precip
    DWDOrigDataColumns.ANNUAL.PRECIPITATION_MORE.JA_NSH.value,
    DWDOrigDataColumns.ANNUAL.PRECIPITATION_MORE.JA_SH_S.value,
    # weather_phenomena
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_STURM_6.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_STURM_8.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GEWITTER.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GLATTEIS.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_GRAUPEL.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_HAGEL.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_NEBEL.value,
    DWDOrigDataColumns.ANNUAL.WEATHER_PHENOMENA.JA_TAU.value,
)
STRING_FIELDS = (
    # hourly
    # cloud_type
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_N_I.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S1_CSA.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S2_CSA.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S3_CSA.value,
    DWDOrigDataColumns.HOURLY.CLOUD_TYPE.V_S4_CSA.value,
    # cloudiness
    DWDOrigDataColumns.HOURLY.CLOUDINESS.V_N_I.value,
    # visibility
    DWDOrigDataColumns.HOURLY.VISIBILITY.V_VV_I.value,
)
