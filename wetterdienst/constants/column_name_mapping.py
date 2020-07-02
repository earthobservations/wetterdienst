""" mapping from german column names to english column names"""
from numpy import datetime64
from wetterdienst.enumerations.column_names_enumeration import DWDOrigColumns, DWDMetaColumns, DWDDataColumns

GERMAN_TO_ENGLISH_COLUMNS_MAPPING = {
    DWDOrigColumns.STATION_ID.value:                DWDMetaColumns.STATION_ID.value,
    DWDOrigColumns.DATE.value:                      DWDMetaColumns.DATE.value,
    DWDOrigColumns.FROM_DATE.value:                 DWDMetaColumns.FROM_DATE.value,
    DWDOrigColumns.TO_DATE.value:                   DWDMetaColumns.TO_DATE.value,
    DWDOrigColumns.FROM_DATE_ALTERNATIVE.value:     DWDMetaColumns.FROM_DATE.value,
    DWDOrigColumns.TO_DATE_ALTERNATIVE.value:       DWDMetaColumns.TO_DATE.value,
    DWDOrigColumns.STATIONHEIGHT.value:             DWDMetaColumns.STATIONHEIGHT.value,
    DWDOrigColumns.LATITUDE.value:                  DWDMetaColumns.LATITUDE.value,
    DWDOrigColumns.LATITUDE_ALTERNATIVE.value:      DWDMetaColumns.LATITUDE.value,
    DWDOrigColumns.LONGITUDE.value:                 DWDMetaColumns.LONGITUDE.value,
    DWDOrigColumns.LONGITUDE_ALTERNATIVE.value:     DWDMetaColumns.LONGITUDE.value,
    DWDOrigColumns.STATIONNAME.value:               DWDMetaColumns.STATIONNAME.value,
    DWDOrigColumns.STATE.value:                     DWDMetaColumns.STATE.value,
    DWDOrigColumns.END_OF_INTERVAL.value:           DWDDataColumns.END_OF_INTERVAL.value,
    DWDOrigColumns.TRUE_LOCAL_TIME.value:           DWDDataColumns.TRUE_LOCAL_TIME.value,
}

GERMAN_TO_ENGLISH_COLUMNS_MAPPING_HUMANIZED = {
    # Daily climate summary
    DWDOrigColumns.FX.value: DWDDataColumns.FX.value,
    DWDOrigColumns.FM.value: DWDDataColumns.FM.value,
    DWDOrigColumns.RSK.value: DWDDataColumns.RSK.value,
    DWDOrigColumns.RSKF.value: DWDDataColumns.RSKF.value,
    DWDOrigColumns.SDK.value: DWDDataColumns.SDK.value,
    DWDOrigColumns.SHK_TAG.value: DWDDataColumns.SHK_TAG.value,
    DWDOrigColumns.NM.value: DWDDataColumns.NM.value,
    DWDOrigColumns.VPM.value: DWDDataColumns.VPM.value,
    DWDOrigColumns.PM.value: DWDDataColumns.PM.value,
    DWDOrigColumns.TMK.value: DWDDataColumns.TMK.value,
    DWDOrigColumns.UPM.value: DWDDataColumns.UPM.value,
    DWDOrigColumns.TXK.value: DWDDataColumns.TXK.value,
    DWDOrigColumns.TNK.value: DWDDataColumns.TNK.value,
    DWDOrigColumns.TGK.value: DWDDataColumns.TGK.value,
}

METADATA_DTYPE_MAPPING = {
    DWDMetaColumns.STATION_ID.value:        int,
    DWDMetaColumns.FROM_DATE.value:         datetime64,
    DWDMetaColumns.TO_DATE.value:           datetime64,
    DWDMetaColumns.STATIONHEIGHT.value:     float,
    DWDMetaColumns.LATITUDE.value:          float,
    DWDMetaColumns.LONGITUDE.value:         float,
    DWDMetaColumns.STATIONNAME.value:       str,
    DWDMetaColumns.STATE.value:             str
}
