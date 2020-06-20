""" file list creation for requested files """
from pathlib import Path
from typing import Union
import pandas as pd

from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.file_index_creation import create_file_index_for_dwd_server, \
    reset_file_index_cache


def create_file_list_for_dwd_server(station_id: Union[str, int],
                                    parameter: Union[Parameter, str],
                                    time_resolution: Union[TimeResolution, str],
                                    period_type: Union[PeriodType, str],
                                    create_new_file_index: bool = False) -> pd.DataFrame:
    """
    Function for selecting datafiles (links to archives) for given
    station_ids, parameter, time_resolution and period_type under consideration of a
    created list of files that are
    available online.

    Args:
        station_id: id for the weather station to ask for data
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        create_new_file_index: set if new file index is created

    Returns:
        List of path's to file

    """
    if create_new_file_index:
        reset_file_index_cache()

    parameter = Parameter(parameter)
    time_resolution = TimeResolution(time_resolution)
    period_type = PeriodType(period_type)

    file_index = create_file_index_for_dwd_server(
        parameter, time_resolution, period_type)

    file_index = file_index[
        file_index[DWDColumns.STATION_ID.value] == int(station_id)
    ]

    return file_index.loc[:, [DWDColumns.FILENAME.value]]
