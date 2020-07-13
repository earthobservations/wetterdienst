""" mapping from german column names to english column names"""
from numpy import datetime64
from wetterdienst.enumerations.column_names_enumeration import DWDOrigMetaColumns, DWDMetaColumns

GERMAN_TO_ENGLISH_COLUMNS_MAPPING = {
    DWDOrigMetaColumns.STATION_ID.value:                DWDMetaColumns.STATION_ID.value,
    DWDOrigMetaColumns.DATE.value:                      DWDMetaColumns.DATE.value,
    DWDOrigMetaColumns.FROM_DATE.value:                 DWDMetaColumns.FROM_DATE.value,
    DWDOrigMetaColumns.TO_DATE.value:                   DWDMetaColumns.TO_DATE.value,
    DWDOrigMetaColumns.FROM_DATE_ALTERNATIVE.value:     DWDMetaColumns.FROM_DATE.value,
    DWDOrigMetaColumns.TO_DATE_ALTERNATIVE.value:       DWDMetaColumns.TO_DATE.value,
    DWDOrigMetaColumns.STATION_HEIGHT.value:            DWDMetaColumns.STATION_HEIGHT.value,
    DWDOrigMetaColumns.LATITUDE.value:                  DWDMetaColumns.LATITUDE.value,
    DWDOrigMetaColumns.LATITUDE_ALTERNATIVE.value:      DWDMetaColumns.LATITUDE.value,
    DWDOrigMetaColumns.LONGITUDE.value:                 DWDMetaColumns.LONGITUDE.value,
    DWDOrigMetaColumns.LONGITUDE_ALTERNATIVE.value:     DWDMetaColumns.LONGITUDE.value,
    DWDOrigMetaColumns.STATION_NAME.value:              DWDMetaColumns.STATION_NAME.value,
    DWDOrigMetaColumns.STATE.value:                     DWDMetaColumns.STATE.value,
}

# """
# Humanized columns mapping will not include quality columns, as they have some anomalies
# and will be added manually
# """
# GERMAN_TO_ENGLISH_COLUMNS_MAPPING_HUMANIZED = {
#     # 1_minute
#     # precipitation
#     DWDOrigDataColumns.RS_01.value: DWDDataColumns.RS_01.value,
#     DWDOrigDataColumns.RS_IND_01.value: DWDDataColumns.RS_IND_01.value,
#
#     # 10_minutes
#     # air_temperature
#     DWDOrigDataColumns.PP_10.value: DWDDataColumns.PP_10.value,
#     DWDOrigDataColumns.TT_10.value: DWDDataColumns.TT_10.value,
#     DWDOrigDataColumns.TM5_10.value: DWDDataColumns.TM5_10.value,
#     DWDOrigDataColumns.RF_10.value: DWDDataColumns.RF_10.value,
#     DWDOrigDataColumns.TD_10.value: DWDDataColumns.TD_10.value,
#
#     # extreme_temperature
#     DWDOrigDataColumns.TX_10.value: DWDDataColumns.TX_10.value,
#     DWDOrigDataColumns.TX5_10.value: DWDDataColumns.TX5_10.value,
#     DWDOrigDataColumns.TN_10.value: DWDDataColumns.TN_10.value,
#     DWDOrigDataColumns.TN5_10.value: DWDDataColumns.TN5_10.value,
#
#     # extreme_wind
#     DWDOrigDataColumns.FX_10.value: DWDDataColumns.FX_10.value,
#     DWDOrigDataColumns.FNX_10.value: DWDDataColumns.FNX_10.value,
#     DWDOrigDataColumns.FMX_10.value: DWDDataColumns.FMX_10.value,
#     DWDOrigDataColumns.DX_10.value: DWDDataColumns.DX_10.value,
#
#     # precipitation
#     DWDOrigDataColumns.RWS_DAU_10.value: DWDDataColumns.RWS_DAU_10.value,
#     DWDOrigDataColumns.RWS_10.value: DWDDataColumns.RWS_10.value,
#     DWDOrigDataColumns.RWS_IND_10.value: DWDDataColumns.RWS_IND_10.value,
#
#     # solar
#     DWDOrigDataColumns.DS_10.value: DWDDataColumns.DS_10.value,
#     DWDOrigDataColumns.GS_10.value: DWDDataColumns.GS_10.value,
#     DWDOrigDataColumns.SD_10.value: DWDDataColumns.SD_10.value,
#     DWDOrigDataColumns.LS_10.value: DWDDataColumns.LS_10.value,
#
#     # wind
#     DWDOrigDataColumns.FF_10.value: DWDDataColumns.FF_10.value,
#     DWDOrigDataColumns.DD_10.value: DWDDataColumns.DD_10.value,
#
#     # hourly
#     # air_temperature
#     DWDOrigDataColumns.TT_TU.value: DWDDataColumns.TT_TU.value,
#     DWDOrigDataColumns.RF_TU.value: DWDDataColumns.RF_TU.value,
#
#     # cloud_type
#     DWDOrigDataColumns.V_N.value: DWDDataColumns.V_N.value,
#     DWDOrigDataColumns.V_N_I.value: DWDDataColumns.V_N_I.value,
#     DWDOrigDataColumns.V_S1_CS.value: DWDDataColumns.V_S1_CS.value,
#     DWDOrigDataColumns.V_S1_CSA.value: DWDDataColumns.V_S1_CSA.value,
#     DWDOrigDataColumns.V_S1_HHS.value: DWDDataColumns.V_S1_HHS.value,
#     DWDOrigDataColumns.V_S1_NS.value: DWDDataColumns.V_S1_NS.value,
#     DWDOrigDataColumns.V_S2_CS.value: DWDDataColumns.V_S2_CS.value,
#     DWDOrigDataColumns.V_S2_CSA.value: DWDDataColumns.V_S2_CSA.value,
#     DWDOrigDataColumns.V_S2_HHS.value: DWDDataColumns.V_S2_HHS.value,
#     DWDOrigDataColumns.V_S2_NS.value: DWDDataColumns.V_S2_NS.value,
#     DWDOrigDataColumns.V_S3_CS.value: DWDDataColumns.V_S3_CS.value,
#     DWDOrigDataColumns.V_S3_CSA.value: DWDDataColumns.V_S3_CSA.value,
#     DWDOrigDataColumns.V_S3_HHS.value: DWDDataColumns.V_S3_HHS.value,
#     DWDOrigDataColumns.V_S3_NS.value: DWDDataColumns.V_S3_NS.value,
#     DWDOrigDataColumns.V_S4_CS.value: DWDDataColumns.V_S4_CS.value,
#     DWDOrigDataColumns.V_S4_CSA.value: DWDDataColumns.V_S4_CSA.value,
#     DWDOrigDataColumns.V_S4_HHS.value: DWDDataColumns.V_S4_HHS.value,
#     DWDOrigDataColumns.V_S4_NS.value: DWDDataColumns.V_S4_NS.value,
#
#     # cloudiness
#     DWDOrigDataColumns.V_N_I.value: DWDDataColumns.V_N_I.value,
#     DWDOrigDataColumns.V_N.value: DWDDataColumns.V_N.value,
#
#     # dew_point
#     DWDOrigDataColumns.TT.value: DWDDataColumns.TT.value,
#     DWDOrigDataColumns.TD.value: DWDDataColumns.TD.value,
#
#     # precipitation
#     DWDOrigDataColumns.R1.value: DWDDataColumns.R1.value,
#     DWDOrigDataColumns.RS_IND.value: DWDDataColumns.RS_IND.value,
#     DWDOrigDataColumns.WRTR.value: DWDDataColumns.WRTR.value,
#
#     # pressure
#     DWDOrigDataColumns.P.value: DWDDataColumns.P.value,
#     DWDOrigDataColumns.P0.value: DWDDataColumns.P0.value,
#
#     # soil_temperature
#     DWDOrigDataColumns.V_TE002.value: DWDDataColumns.V_TE002.value,
#     DWDOrigDataColumns.V_TE005.value: DWDDataColumns.V_TE005.value,
#     DWDOrigDataColumns.V_TE010.value: DWDDataColumns.V_TE010.value,
#     DWDOrigDataColumns.V_TE020.value: DWDDataColumns.V_TE020.value,
#     DWDOrigDataColumns.V_TE050.value: DWDDataColumns.V_TE050.value,
#     DWDOrigDataColumns.V_TE100.value: DWDDataColumns.V_TE100.value,
#
#     # solar
#     DWDOrigDataColumns.END_OF_INTERVAL.value: DWDDataColumns.END_OF_INTERVAL.value,
#     DWDOrigDataColumns.ATMO_LBERG.value: DWDDataColumns.ATMO_LBERG.value,
#     DWDOrigDataColumns.FD_LBERG.value: DWDDataColumns.FD_LBERG.value,
#     DWDOrigDataColumns.FG_LBERG.value: DWDDataColumns.FG_LBERG.value,
#     DWDOrigDataColumns.SD_LBERG.value: DWDDataColumns.SD_LBERG.value,
#     DWDOrigDataColumns.ZENIT.value: DWDDataColumns.ZENIT.value,
#     DWDOrigDataColumns.TRUE_LOCAL_TIME.value: DWDDataColumns.TRUE_LOCAL_TIME.value,
#
#     # sun
#     DWDOrigDataColumns.SD_SO.value: DWDDataColumns.SD_SO.value,
#
#     # visibility
#     DWDOrigDataColumns.V_VV_I.value: DWDDataColumns.V_VV_I.value,
#     DWDOrigDataColumns.V_VV.value: DWDDataColumns.V_VV.value,
#
#     # wind
#     DWDOrigDataColumns.F.value: DWDDataColumns.F.value,
#     DWDOrigDataColumns.D.value: DWDDataColumns.D.value,
#
#     # wind_synop
#     DWDOrigDataColumns.FF.value: DWDDataColumns.FF.value,
#     DWDOrigDataColumns.DD.value: DWDDataColumns.DD.value,
#
#     # subdaily
#     # air_temperature
#     DWDOrigDataColumns.TT_TER.value: DWDDataColumns.TT_TER.value,
#     DWDOrigDataColumns.RF_TER.value: DWDDataColumns.RF_TER.value,
#
#     # cloudiness
#     DWDOrigDataColumns.N_TER.value: DWDDataColumns.N_TER.value,
#     DWDOrigDataColumns.CD_TER.value: DWDDataColumns.CD_TER.value,
#
#     # moisture
#     DWDOrigDataColumns.VP_TER.value: DWDDataColumns.VP_TER.value,
#     DWDOrigDataColumns.E_TF_TER.value: DWDDataColumns.E_TF_TER.value,
#     DWDOrigDataColumns.TF_TER.value: DWDDataColumns.TF_TER.value,
#     DWDOrigDataColumns.RF_TER.value: DWDDataColumns.RF_TER.value,
#
#     # pressure
#     DWDOrigDataColumns.PP_TER.value: DWDDataColumns.PP_TER.value,
#
#     # soil
#     DWDOrigDataColumns.EK_TER.value: DWDDataColumns.EK_TER.value,
#
#     # visibility
#     DWDOrigDataColumns.VK_TER.value: DWDDataColumns.VK_TER.value,
#
#     # wind
#     DWDOrigDataColumns.DK_TER.value: DWDDataColumns.DK_TER.value,
#     DWDOrigDataColumns.FK_TER.value: DWDDataColumns.FK_TER.value,
#
#     # Daily
#     # kl
#     DWDOrigDataColumns.FX.value: DWDDataColumns.FX.value,
#     DWDOrigDataColumns.FM.value: DWDDataColumns.FM.value,
#     DWDOrigDataColumns.RSK.value: DWDDataColumns.RSK.value,
#     DWDOrigDataColumns.RSKF.value: DWDDataColumns.RSKF.value,
#     DWDOrigDataColumns.SDK.value: DWDDataColumns.SDK.value,
#     DWDOrigDataColumns.SHK_TAG.value: DWDDataColumns.SHK_TAG.value,
#     DWDOrigDataColumns.NM.value: DWDDataColumns.NM.value,
#     DWDOrigDataColumns.VPM.value: DWDDataColumns.VPM.value,
#     DWDOrigDataColumns.PM.value: DWDDataColumns.PM.value,
#     DWDOrigDataColumns.TMK.value: DWDDataColumns.TMK.value,
#     DWDOrigDataColumns.UPM.value: DWDDataColumns.UPM.value,
#     DWDOrigDataColumns.TXK.value: DWDDataColumns.TXK.value,
#     DWDOrigDataColumns.TNK.value: DWDDataColumns.TNK.value,
#     DWDOrigDataColumns.TGK.value: DWDDataColumns.TGK.value,
#
#     # more_precip
#     DWDOrigDataColumns.RS.value: DWDDataColumns.RS.value,
#     DWDOrigDataColumns.RSF.value: DWDDataColumns.RSF.value,
#     DWDOrigDataColumns.SH_TAG.value: DWDDataColumns.SH_TAG.value,
#     DWDOrigDataColumns.NSH_TAG.value: DWDDataColumns.NSH_TAG.value,
#
#     # soil_temperature
#     DWDOrigDataColumns.V_TE002M.value: DWDDataColumns.V_TE002M.value,
#     DWDOrigDataColumns.V_TE005M.value: DWDDataColumns.V_TE005M.value,
#     DWDOrigDataColumns.V_TE010M.value: DWDDataColumns.V_TE010M.value,
#     DWDOrigDataColumns.V_TE020M.value: DWDDataColumns.V_TE020M.value,
#     DWDOrigDataColumns.V_TE050M.value: DWDDataColumns.V_TE050M.value,
#
#     # solar
#     DWDOrigDataColumns.ATMO_STRAHL.value: DWDDataColumns.ATMO_STRAHL.value,
#     DWDOrigDataColumns.FD_STRAHL.value: DWDDataColumns.FD_STRAHL.value,
#     DWDOrigDataColumns.FG_STRAHL.value: DWDDataColumns.FG_STRAHL.value,
#     DWDOrigDataColumns.SD_STRAHL.value: DWDDataColumns.SD_STRAHL.value,
#
#     # water_equiv
#     DWDOrigDataColumns.ASH_6.value: DWDDataColumns.ASH_6.value,
#     DWDOrigDataColumns.SH_TAG.value: DWDDataColumns.SH_TAG.value,
#     DWDOrigDataColumns.WASH_6.value: DWDDataColumns.WASH_6.value,
#     DWDOrigDataColumns.WAAS_6.value: DWDDataColumns.WAAS_6.value,
#
#     # weather_phenomena
#     DWDOrigDataColumns.NEBEL.value: DWDDataColumns.NEBEL.value,
#     DWDOrigDataColumns.GEWITTER.value: DWDDataColumns.GEWITTER.value,
#     DWDOrigDataColumns.STURM_6.value: DWDDataColumns.STURM_6.value,
#     DWDOrigDataColumns.STURM_8.value: DWDDataColumns.STURM_8.value,
#     DWDOrigDataColumns.TAU.value: DWDDataColumns.TAU.value,
#     DWDOrigDataColumns.GLATTEIS.value: DWDDataColumns.GLATTEIS.value,
#     DWDOrigDataColumns.REIF.value: DWDDataColumns.REIF.value,
#     DWDOrigDataColumns.GRAUPEL.value: DWDDataColumns.GRAUPEL.value,
#     DWDOrigDataColumns.HAGEL.value: DWDDataColumns.HAGEL.value,
#
#     # monthly
#     # kl
#     DWDOrigDataColumns.MO_N.value: DWDDataColumns.MO_N.value,
#     DWDOrigDataColumns.MO_TT.value: DWDDataColumns.MO_TT.value,
#     DWDOrigDataColumns.MO_TX.value: DWDDataColumns.MO_TX.value,
#     DWDOrigDataColumns.MO_TN.value: DWDDataColumns.MO_TN.value,
#     DWDOrigDataColumns.MO_FK.value: DWDDataColumns.MO_FK.value,
#     DWDOrigDataColumns.MX_TX.value: DWDDataColumns.MX_TX.value,
#     DWDOrigDataColumns.MX_FX.value: DWDDataColumns.MX_FX.value,
#     DWDOrigDataColumns.MX_TN.value: DWDDataColumns.MX_TN.value,
#     DWDOrigDataColumns.MO_SD_S.value: DWDDataColumns.MO_SD_S.value,
#     DWDOrigDataColumns.MO_RR.value: DWDDataColumns.MO_RR.value,
#     DWDOrigDataColumns.MX_RS.value: DWDDataColumns.MX_RS.value,
#
#     # more_precip
#     DWDOrigDataColumns.MO_NSH.value: DWDDataColumns.MO_NSH.value,
#     DWDOrigDataColumns.MO_RR.value: DWDDataColumns.MO_RR.value,
#     DWDOrigDataColumns.MO_SH_S.value: DWDDataColumns.MO_SH_S.value,
#     DWDOrigDataColumns.MX_RS.value: DWDDataColumns.MX_RS.value,
#
#     # weather_phenomena
#     DWDOrigDataColumns.MO_STURM_6.value: DWDDataColumns.MO_STURM_6.value,
#     DWDOrigDataColumns.MO_STURM_8.value: DWDDataColumns.MO_STURM_8.value,
#     DWDOrigDataColumns.MO_GEWITTER.value: DWDDataColumns.MO_GEWITTER.value,
#     DWDOrigDataColumns.MO_GLATTEIS.value: DWDDataColumns.MO_GLATTEIS.value,
#     DWDOrigDataColumns.MO_GRAUPEL.value: DWDDataColumns.MO_GRAUPEL.value,
#     DWDOrigDataColumns.MO_HAGEL.value: DWDDataColumns.MO_HAGEL.value,
#     DWDOrigDataColumns.MO_NEBEL.value: DWDDataColumns.MO_NEBEL.value,
#     DWDOrigDataColumns.MO_TAU.value: DWDDataColumns.MO_TAU.value,
#
#     # annual
#     # kl
#     DWDOrigDataColumns.JA_N.value: DWDDataColumns.JA_N.value,
#     DWDOrigDataColumns.JA_TT.value: DWDDataColumns.JA_TT.value,
#     DWDOrigDataColumns.JA_TX.value: DWDDataColumns.JA_TX.value,
#     DWDOrigDataColumns.JA_TN.value: DWDDataColumns.JA_TN.value,
#     DWDOrigDataColumns.JA_FK.value: DWDDataColumns.JA_FK.value,
#     DWDOrigDataColumns.JA_SD_S.value: DWDDataColumns.JA_SD_S.value,
#     DWDOrigDataColumns.JA_MX_FX.value: DWDDataColumns.JA_MX_FX.value,
#     DWDOrigDataColumns.JA_MX_TX.value: DWDDataColumns.JA_MX_TX.value,
#     DWDOrigDataColumns.JA_MX_TN.value: DWDDataColumns.JA_MX_TN.value,
#     DWDOrigDataColumns.JA_RR.value: DWDDataColumns.JA_RR.value,
#     DWDOrigDataColumns.JA_MX_RS.value: DWDDataColumns.JA_MX_RS.value,
#
#     # more_precip
#     DWDOrigDataColumns.JA_NSH.value: DWDDataColumns.JA_NSH.value,
#     DWDOrigDataColumns.JA_RR.value: DWDDataColumns.JA_RR.value,
#     DWDOrigDataColumns.JA_SH_S.value: DWDDataColumns.JA_SH_S.value,
#     DWDOrigDataColumns.JA_MX_RS.value: DWDDataColumns.JA_MX_RS.value,
#
#     # weather_phenomena
#     DWDOrigDataColumns.JA_STURM_6.value: DWDDataColumns.JA_STURM_6.value,
#     DWDOrigDataColumns.JA_STURM_8.value: DWDDataColumns.JA_STURM_8.value,
#     DWDOrigDataColumns.JA_GEWITTER.value: DWDDataColumns.JA_GEWITTER.value,
#     DWDOrigDataColumns.JA_GLATTEIS.value: DWDDataColumns.JA_GLATTEIS.value,
#     DWDOrigDataColumns.JA_GRAUPEL.value: DWDDataColumns.JA_GRAUPEL.value,
#     DWDOrigDataColumns.JA_HAGEL.value: DWDDataColumns.JA_HAGEL.value,
#     DWDOrigDataColumns.JA_NEBEL.value: DWDDataColumns.JA_NEBEL.value,
#     DWDOrigDataColumns.JA_TAU.value: DWDDataColumns.JA_TAU.value,
# }

METADATA_DTYPE_MAPPING = {
    DWDMetaColumns.STATION_ID.value:        int,
    DWDMetaColumns.FROM_DATE.value:         datetime64,
    DWDMetaColumns.TO_DATE.value:           datetime64,
    DWDMetaColumns.STATION_HEIGHT.value:     float,
    DWDMetaColumns.LATITUDE.value:          float,
    DWDMetaColumns.LONGITUDE.value:         float,
    DWDMetaColumns.STATION_NAME.value:       str,
    DWDMetaColumns.STATE.value:             str
}
