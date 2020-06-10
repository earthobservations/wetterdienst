""" file list creation for requested files """
from pathlib import Path
from typing import List
import pandas as pd

from python_dwd.additionals.functions import check_parameters
from python_dwd.additionals.helpers import create_fileindex
from python_dwd.constants.access_credentials import DWD_FOLDER_MAIN, DWD_FOLDER_METADATA
from python_dwd.constants.metadata import FILELIST_NAME, DATA_FORMAT
from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def create_file_list_for_dwd_server(station_ids: List[int],
                                    parameter: Parameter,
                                    time_resolution: TimeResolution,
                                    period_type: PeriodType,
                                    folder: str = DWD_FOLDER_MAIN,
                                    create_new_filelist=False) -> pd.DataFrame:
    """
    Function for selecting datafiles (links to archives) for given
    station_ids, parameter, time_resolution and period_type under consideration of a
    created list of files that are
    available online.

    Args:
        station_ids: id(s) for the weather station to ask for data
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        folder:
        create_new_filelist: boolean for checking existing file list or not

    Returns:
        List of path's to file

    """
    # Check type of function parameters
    station_ids = [int(statid) for statid in station_ids]

    # Check for the combination of requested parameters
    check_parameters(parameter=parameter,
                     time_resolution=time_resolution,
                     period_type=period_type)

    # Create name of fileslistfile
    filelist_local = f'{FILELIST_NAME}_{parameter.value}_' \
                     f'{time_resolution.value}_{period_type.value}'

    # Create filepath to filelist in folder
    filelist_local_path = Path(folder,
                               DWD_FOLDER_METADATA,
                               filelist_local)

    filelist_local_path = f"{filelist_local_path}{DATA_FORMAT}"

    if create_new_filelist or not Path(filelist_local_path).is_file():
        create_fileindex(parameter=parameter,
                         time_resolution=time_resolution,
                         period_type=period_type,
                         folder=folder)

    filelist = pd.read_csv(filepath_or_buffer=filelist_local_path,
                           sep=",",
                           dtype={DWDColumns.FILEID.value: int,
                                  DWDColumns.STATION_ID.value: int,
                                  DWDColumns.FILENAME.value: str})

    return filelist.loc[filelist[DWDColumns.STATION_ID.value].isin(station_ids), :]
