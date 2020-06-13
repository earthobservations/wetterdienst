""" file list creation for requested files """
from pathlib import Path
from typing import Union
import pandas as pd

from python_dwd.additionals.functions import check_parameters
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
    parameter = Parameter(parameter)
    time_resolution = TimeResolution(time_resolution)
    period_type = PeriodType(period_type)

    # Check for the combination of requested parameters
    check_parameters(parameter=parameter,
                     time_resolution=time_resolution,
                     period_type=period_type)

    file_index_local_path = _create_file_index_path(folder)

    if not file_index_local_path.is_file():
        create_file_index_for_dwd_server(folder)

    file_list = pd.read_csv(
        filepath_or_buffer=file_index_local_path,
        sep=",",
        dtype={
            DWDColumns.FILEID.value: int,
            DWDColumns.STATION_ID.value: int,
            DWDColumns.FILENAME.value: str
        }
    )

    return file_list.loc[file_list[DWDColumns.STATION_ID.value] == station_id, :]
