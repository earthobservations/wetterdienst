""" file list creation for requested files """
from pathlib import Path
from typing import Union
import pandas as pd

from python_dwd.constants.access_credentials import DWD_FOLDER_MAIN
from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.file_index_creation import _create_file_index_path, \
    create_file_index_for_dwd_server


def create_file_list_for_dwd_server(station_id: Union[str, int],
                                    parameter: Union[Parameter, str],
                                    time_resolution: Union[TimeResolution, str],
                                    period_type: Union[PeriodType, str],
                                    folder: Union[str, Path] = DWD_FOLDER_MAIN) -> pd.DataFrame:
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
        folder:

    Returns:
        List of path's to file

    """
    create_file_index_for_dwd_server(folder)

    parameter = Parameter(parameter)
    time_resolution = TimeResolution(time_resolution)
    period_type = PeriodType(period_type)

    file_list = pd.read_csv(
        filepath_or_buffer=_create_file_index_path(folder),
        sep=",",
        dtype={
            DWDColumns.FILEID.value: int,
            DWDColumns.STATION_ID.value: int,
            DWDColumns.FILENAME.value: str
        }
    )

    file_list_for_station_id = file_list[
        (file_list[DWDColumns.PARAMETER.value] == parameter.value) &
        (file_list[DWDColumns.TIME_RESOLUTION.value] == time_resolution.value) &
        (file_list[DWDColumns.PERIOD_TYPE.value] == period_type.value) &
        (file_list[DWDColumns.STATION_ID.value] == int(station_id))
    ]

    return file_list_for_station_id.loc[:, [DWDColumns.FILENAME.value]]
