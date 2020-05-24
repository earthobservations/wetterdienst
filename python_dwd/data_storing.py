""" Data storing/restoring methods"""
from pathlib import Path
from typing import Tuple, Union
import pandas as pd

from python_dwd.additionals.helpers import create_stationdata_dtype_mapping
from python_dwd.constants.metadata import STATIONDATA_NAME, H5_FORMAT
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def store_dwd_data(station_data: pd.DataFrame,
                   station_id: int,
                   parameter: Parameter,
                   time_resolution: TimeResolution,
                   period_type: PeriodType,
                   folder: str) -> None:
    """
    Function to store data in a local file hdf file. The function takes a pandas
    DataFrame plus additionally the request parameters to identify data within the
    hdf file and another folder argument for the place where the file is stored.

    Args:
        station_data: the pandas DataFrame with the obtained data
        station_id: the id of the station of which the data is stored in the DataFrame
        parameter: the parameter enumeration
        time_resolution: the time resolution enumeration
        period_type: the period type as enumeration
        folder: the folder where the hdf is stored
    Returns:
        None, prints information if data was not stored
    """
    # Make sure that there is data that can be stored
    if station_data.empty:
        print("There is no data in 'station_data' that can be stored.")

        return

    request_string = _build_local_store_key(
        station_id, parameter, time_resolution, period_type)

    local_filepath = Path(folder, STATIONDATA_NAME).absolute() / \
        f"{STATIONDATA_NAME}{H5_FORMAT}"
    local_filepath.parent.mkdir(parents=True, exist_ok=True)

    try:
        station_data.to_hdf(
            path_or_buf=local_filepath,
            key=request_string
        )
    except FileNotFoundError:
        print(f"Error: File for station data could not be created at {str(local_filepath)}. "
              f"Data for {request_string} could not be written.")


def restore_dwd_data(station_id: int,
                     parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType,
                     folder: str) -> Tuple[bool, pd.DataFrame]:
    """
    Function to restore data from a local hdf file based on the place (folder) where
    the file is stored and parameters that define the request in particular.

    Args:
        station_id: the station id of which data should be restored
        parameter: parameter as enumeration
        time_resolution: time resolution as enumeration
        period_type: period type as enumeration
        folder: folder where the hdf file should be found as string

    Returns:
        Tuple, first is boolean if data could be restored, second is the DataFrame
        holding the data
    """
    request_string = _build_local_store_key(station_id, parameter, time_resolution, period_type)

    local_filepath = Path(folder, STATIONDATA_NAME).absolute() / \
        f"{STATIONDATA_NAME}{H5_FORMAT}"

    try:
        # typing required as pandas.read_hdf returns an object by typing
        station_data: Union[object, pd.DataFrame] = pd.read_hdf(
            path_or_buf=local_filepath,
            key=request_string
        )
    except FileNotFoundError:
        print(f"Error: There seems to be no file at {str(local_filepath)}. "
              f"Data will be loaded freshly.")
        return False, pd.DataFrame()
    except KeyError:
        print(f"Error: The requested data for {request_string} does not yet "
              f"exist in local store at {str(local_filepath)}. "
              f"Data will be loaded freshly.")
        return False, pd.DataFrame()

    return True, station_data.astype(create_stationdata_dtype_mapping(station_data.columns))


def _build_local_store_key(station_id: Union[str, int],
                           parameter: Parameter,
                           time_resolution: TimeResolution,
                           period_type: PeriodType) -> str:
    """
    Function that builds a request string from defined parameters including a single station id

    Args:
        station_id: station id of data
        parameter: parameter as enumeration
        time_resolution: time resolution as enumeration
        period_type: period type as enumeration

    Returns:
        a string building a key that is used to identify the request
    """
    request_string = f"{parameter.value}/{time_resolution.value}/" \
                     f"{period_type.value}/station_id_{int(station_id)}"

    return request_string
