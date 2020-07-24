""" mapping from german column names to english column names"""
from numpy import datetime64
from wetterdienst.enumerations.column_names_enumeration import (
    DWDOrigMetaColumns,
    DWDMetaColumns,
)

GERMAN_TO_ENGLISH_COLUMNS_MAPPING = {
    DWDOrigMetaColumns.STATION_ID.value: DWDMetaColumns.STATION_ID.value,
    DWDOrigMetaColumns.DATE.value: DWDMetaColumns.DATE.value,
    DWDOrigMetaColumns.FROM_DATE.value: DWDMetaColumns.FROM_DATE.value,
    DWDOrigMetaColumns.TO_DATE.value: DWDMetaColumns.TO_DATE.value,
    DWDOrigMetaColumns.FROM_DATE_ALTERNATIVE.value: DWDMetaColumns.FROM_DATE.value,
    DWDOrigMetaColumns.TO_DATE_ALTERNATIVE.value: DWDMetaColumns.TO_DATE.value,
    DWDOrigMetaColumns.STATION_HEIGHT.value: DWDMetaColumns.STATION_HEIGHT.value,
    DWDOrigMetaColumns.LATITUDE.value: DWDMetaColumns.LATITUDE.value,
    DWDOrigMetaColumns.LATITUDE_ALTERNATIVE.value: DWDMetaColumns.LATITUDE.value,
    DWDOrigMetaColumns.LONGITUDE.value: DWDMetaColumns.LONGITUDE.value,
    DWDOrigMetaColumns.LONGITUDE_ALTERNATIVE.value: DWDMetaColumns.LONGITUDE.value,
    DWDOrigMetaColumns.STATION_NAME.value: DWDMetaColumns.STATION_NAME.value,
    DWDOrigMetaColumns.STATE.value: DWDMetaColumns.STATE.value,
}

METADATA_DTYPE_MAPPING = {
    DWDMetaColumns.STATION_ID.value: int,
    DWDMetaColumns.FROM_DATE.value: datetime64,
    DWDMetaColumns.TO_DATE.value: datetime64,
    DWDMetaColumns.STATION_HEIGHT.value: float,
    DWDMetaColumns.LATITUDE.value: float,
    DWDMetaColumns.LONGITUDE.value: float,
    DWDMetaColumns.STATION_NAME.value: str,
    DWDMetaColumns.STATE.value: str,
}
