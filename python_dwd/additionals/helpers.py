""" A set of helping functions used by the main functions """
from typing import List
import pandas as pd

from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns


def create_station_data_dtype_mapping(columns: List[str]) -> dict:
    """
    A function used to create a unique dtype mapping for a given list of column names. This function is needed as we
    want to ensure the expected dtypes of the returned DataFrame as well as for mapping data after reading it from a
    stored .h5 file. This is required as we want to store the data in this file with the same format which is a string,
    thus after reading data back in the dtypes have to be matched.
    
    Args:
        columns: the column names of the DataFrame whose data should be converted
    Return:
         a dictionary with column names and dtypes for each of them
    """
    station_data_dtype_mapping = dict()

    """ Possible columns: STATION_ID, DATETIME, EOR, QN_ and other, measured values like rainfall """

    for column in columns:
        if column == DWDMetaColumns.STATION_ID.value:
            station_data_dtype_mapping[column] = int
        elif column in (DWDMetaColumns.DATE.value, DWDMetaColumns.FROM_DATE.value, DWDMetaColumns.TO_DATE.value):
            station_data_dtype_mapping[column] = "datetime64"
        elif column == DWDMetaColumns.EOR.value:
            station_data_dtype_mapping[column] = str
        else:
            station_data_dtype_mapping[column] = float

    return station_data_dtype_mapping


def convert_datetime_hourly(value):
    return pd.to_datetime(value, format='%Y%m%d%H')
