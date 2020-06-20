""" Data collection pipeline """
from pathlib import Path
from typing import List, Union
import pandas as pd

from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.constants.access_credentials import DWD_FOLDER_MAIN
from python_dwd.file_path_handling.file_index_creation import reset_file_index_cache
from python_dwd.file_path_handling.file_list_creation import create_file_list_for_dwd_server
from python_dwd.download.download import download_dwd_data
from python_dwd.parsing_data.parse_data_from_files import parse_dwd_data
from python_dwd.data_storing import restore_dwd_data, store_dwd_data, _build_local_store_key


def collect_dwd_data(station_ids: List[int],
                     parameter: Union[Parameter, str],
                     time_resolution: Union[TimeResolution, str],
                     period_type: Union[PeriodType, str],
                     folder: Union[str, Path] = DWD_FOLDER_MAIN,
                     prefer_local: bool = False,
                     parallel_download: bool = False,
                     write_file: bool = False,
                     create_new_file_index: bool = False) -> pd.DataFrame:
    """
    Function that organizes the complete pipeline of data collection, either
    from the internet or from a local file. It therefor goes through every given
    station id and, given by the parameters, either tries to get data from local
    store and/or if fails tries to get data from the internet. Finally if wanted
    it will try to store the data in a hdf file.

    Args:
        station_ids: station ids that are trying to be loaded
        parameter: parameter as enumeration
        time_resolution: time resolution as enumeration
        period_type: period type as enumeration
        folder: folder for local file interaction
        prefer_local: boolean for if local data should be preferred
        parallel_download: boolean if to use parallel download when downloading files
        write_file: boolean if to write data to local storage
        create_new_file_index: boolean if to create a new file index for the data selection

    Returns:
        a pandas DataFrame with all the data given by the station ids
    """
    if create_new_file_index:
        reset_file_index_cache()

    parameter = Parameter(parameter)
    time_resolution = TimeResolution(time_resolution)
    period_type = PeriodType(period_type)

    # todo check parameters and if combination not existing, print something and return empty DataFrame

    # List for collected pandas DataFrames per each station id
    data = []
    for station_id in set(station_ids):
        request_string = _build_local_store_key(
            station_id, parameter, time_resolution, period_type)

        if prefer_local:
            # Try restoring data
            station_data = restore_dwd_data(
                station_id, parameter, time_resolution, period_type, folder)

            # When successful append data and continue with next iteration
            if not station_data.empty:
                print(f"Data for {request_string} restored from local.")

                data.append(station_data)

                continue

        print(f"Data for {request_string} will be collected from internet.")

        remote_files = create_file_list_for_dwd_server(
            station_id, parameter, time_resolution, period_type, folder)

        filenames_and_files = download_dwd_data(remote_files, parallel_download)

        station_data = parse_dwd_data(filenames_and_files)

        if write_file:
            store_dwd_data(
                station_data, station_id, parameter, time_resolution, period_type, folder)

        data.append(station_data)

    return pd.concat(data, axis=1, ignore_index=True)
