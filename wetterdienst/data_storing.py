""" Data storing/restoring methods"""
from io import BytesIO
from pathlib import Path
from typing import Union, Tuple
from datetime import datetime

import pandas as pd

from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.file_path_handling.path_handling import (
    build_local_filepath_for_station_data,
    build_local_filepath_for_radolan,
)


def store_climate_observations(
    station_data: pd.DataFrame,
    station_id: int,
    parameter: Parameter,
    time_resolution: TimeResolution,
    period_type: PeriodType,
    folder: Union[str, Path],
) -> None:
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
        return

    request_string = _build_local_store_key(
        station_id, parameter, time_resolution, period_type
    )

    local_filepath = build_local_filepath_for_station_data(folder)

    local_filepath.parent.mkdir(parents=True, exist_ok=True)

    station_data.to_hdf(path_or_buf=local_filepath, key=request_string)


def restore_climate_observations(
    station_id: int,
    parameter: Parameter,
    time_resolution: TimeResolution,
    period_type: PeriodType,
    folder: Union[str, Path],
) -> pd.DataFrame:
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
        a DataFrame holding the data or an empty DataFrame depending on if data
        could be restored
    """
    request_string = _build_local_store_key(
        station_id, parameter, time_resolution, period_type
    )

    local_filepath = build_local_filepath_for_station_data(folder)

    try:
        # typing required as pandas.read_hdf returns an object by typing
        station_data = pd.read_hdf(path_or_buf=local_filepath, key=request_string)
    except (FileNotFoundError, KeyError):
        return pd.DataFrame()

    # Cast to pandas DataFrame
    station_data = pd.DataFrame(station_data)

    return station_data


def _build_local_store_key(
    station_id: Union[str, int],
    parameter: Parameter,
    time_resolution: TimeResolution,
    period_type: PeriodType,
) -> str:
    """
    Function that builds a request string from defined parameters including a single
    station id

    Args:
        station_id: station id of data
        parameter: parameter as enumeration
        time_resolution: time resolution as enumeration
        period_type: period type as enumeration

    Returns:
        a string building a key that is used to identify the request
    """
    request_string = (
        f"{parameter.value}/{time_resolution.value}/"
        f"{period_type.value}/station_id_{int(station_id)}"
    )

    return request_string


def store_radolan_data(
    date_time_and_file: Tuple[datetime, BytesIO],
    time_resolution: TimeResolution,
    folder: Union[str, Path],
) -> None:

    date_time, file = date_time_and_file

    filepath = build_local_filepath_for_radolan(date_time, folder, time_resolution)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("wb") as f:
        f.write(file.read())


def restore_radolan_data(
    date_time: datetime, time_resolution: TimeResolution, folder: Union[str, Path]
) -> BytesIO:
    filepath = build_local_filepath_for_radolan(date_time, folder, time_resolution)

    with filepath.open("rb") as f:
        file_in_bytes = BytesIO(f.read())

    return file_in_bytes
