""" mapping from german column names to english column names"""
from numpy import datetime64
from python_dwd.enumerations.column_names_enumeration import DWDOrigColumns, DWDColumns

GERMAN_TO_ENGLISH_COLUMNS_MAPPING = {
    DWDOrigColumns.STATION_ID.value:                DWDColumns.STATION_ID.value,
    DWDOrigColumns.DATE.value:                      DWDColumns.DATE.value,
    DWDOrigColumns.FROM_DATE.value:                 DWDColumns.FROM_DATE.value,
    DWDOrigColumns.TO_DATE.value:                   DWDColumns.TO_DATE.value,
    DWDOrigColumns.STATIONHEIGHT.value:             DWDColumns.STATIONHEIGHT.value,
    DWDOrigColumns.LATITUDE.value:                  DWDColumns.LATITUDE.value,
    DWDOrigColumns.LATITUDE_ALTERNATIVE.value:      DWDColumns.LATITUDE.value,
    DWDOrigColumns.LONGITUDE.value:                 DWDColumns.LONGITUDE.value,
    DWDOrigColumns.LONGITUDE_ALTERNATIVE.value:     DWDColumns.LONGITUDE.value,
    DWDOrigColumns.STATIONNAME.value:               DWDColumns.STATIONNAME.value,
    DWDOrigColumns.STATE.value:                     DWDColumns.STATE.value,

    # Daily climate summary
    DWDOrigColumns.FX.value:                        DWDColumns.FX.value,
    DWDOrigColumns.FM.value:                        DWDColumns.FM.value,
    DWDOrigColumns.RSK.value:                       DWDColumns.RSK.value,
    DWDOrigColumns.RSKF.value:                      DWDColumns.RSKF.value,
    DWDOrigColumns.SDK.value:                       DWDColumns.SDK.value,
    DWDOrigColumns.SHK_TAG.value:                   DWDColumns.SHK_TAG.value,
    DWDOrigColumns.NM.value:                        DWDColumns.NM.value,
    DWDOrigColumns.VPM.value:                       DWDColumns.VPM.value,
    DWDOrigColumns.PM.value:                        DWDColumns.PM.value,
    DWDOrigColumns.TMK.value:                       DWDColumns.TMK.value,
    DWDOrigColumns.UPM.value:                       DWDColumns.UPM.value,
    DWDOrigColumns.TXK.value:                       DWDColumns.TXK.value,
    DWDOrigColumns.TNK.value:                       DWDColumns.TNK.value,
    DWDOrigColumns.TGK.value:                       DWDColumns.TGK.value,
}

METADATA_DTYPE_MAPPING = {
    DWDColumns.STATION_ID.value:        int,
    DWDColumns.FROM_DATE.value:         datetime64,
    DWDColumns.TO_DATE.value:           datetime64,
    DWDColumns.STATIONHEIGHT.value:     float,
    DWDColumns.LATITUDE.value:          float,
    DWDColumns.LONGITUDE.value:         float,
    DWDColumns.STATIONNAME.value:       str,
    DWDColumns.STATE.value:             str
}
