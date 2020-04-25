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
    DWDOrigColumns.STATE.value:                     DWDColumns.STATE.value
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
