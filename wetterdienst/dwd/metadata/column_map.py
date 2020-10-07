""" mapping from german column names to english column names"""
from numpy import datetime64

from wetterdienst.dwd.metadata import TimeResolution, Parameter
from wetterdienst.dwd.metadata.column_names import (
    DWDOrigMetaColumns,
    DWDMetaColumns,
    DWDOrigDataColumns,
    DWDDataColumns,
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


def create_humanized_column_names_mapping(
    time_resolution: TimeResolution, parameter: Parameter
) -> dict:
    """
    Function to create a humanized column names mapping. The function
    takes care of the special cases of quality columns. Therefore it requires the
    time resolution and parameter.

    Args:
        time_resolution: time resolution enumeration
        parameter: parameter enumeration

    Returns:
        dictionary with mappings extended by quality columns mappings
    """
    column_name_mapping = {
        orig_column.value: humanized_column.value
        for orig_column, humanized_column in zip(
            DWDOrigDataColumns[time_resolution.name][parameter.name],
            DWDDataColumns[time_resolution.name][parameter.name],
        )
    }

    return column_name_mapping
