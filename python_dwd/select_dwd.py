""" file list creation for requested files """
from pathlib import Path
from typing import List

import pandas as pd

from python_dwd.constants.column_name_mapping import STATION_ID_NAME, FILENAME_NAME
from python_dwd.constants.ftp_credentials import MAIN_FOLDER, SUB_FOLDER_METADATA
from python_dwd.constants.metadata import FILELIST_NAME, DATA_FORMAT
from .additionals.functions import check_parameters
from .additionals.functions import correct_folder_path
from .additionals.helpers import create_fileindex


def create_file_list_for_dwd_server(statid: List[int],
                                    parameter: str,
                                    time_resolution: str,
                                    period_type: str,
                                    folder: str = MAIN_FOLDER,
                                    create_new_filelist=False) -> List[str]:
    """
    Function for selecting datafiles (links to archives) for given
    statid, parameter, time_resolution and period_type under consideration of a created list of files that are
    available online.

    Args:
        statid: id for the weather station to ask for data
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        folder:
        create_new_filelist: boolean for checking existing file list or not

    Returns:
        List of path's to file

    """
    # Check type of function parameters
    assert isinstance(statid, list)
    assert isinstance(parameter, str)
    assert isinstance(time_resolution, str)
    assert isinstance(period_type, str)
    assert isinstance(folder, str)
    assert isinstance(create_new_filelist, bool)

    # Check for the combination of requested parameters
    check_parameters(parameter=parameter,
                     time_resolution=time_resolution,
                     period_type=period_type)

    folder = correct_folder_path(folder)

    # Create name of fileslistfile
    filelist_local = f'{FILELIST_NAME}_{parameter}_{time_resolution}_{period_type}'

    # Create filepath to filelist in folder
    filelist_local_path = Path(folder,
                               SUB_FOLDER_METADATA,
                               filelist_local)

    filelist_local_path = f"{filelist_local_path}{DATA_FORMAT}"

    # Check if there's an old filelist
    exist_old_file = Path(filelist_local_path).is_file()

    # Except if a new one should be created
    if create_new_filelist or not exist_old_file:
        # If there was an error with reading in the fileslist get a new
        # fileslist
        create_fileindex(parameter=parameter,
                         time_resolution=time_resolution,
                         period_type=period_type,
                         folder=folder)

    # Read in filelist
    filelist = pd.read_csv(filelist_local_path)

    # Return filenames for filtered statids
    filelist = filelist.loc[filelist[STATION_ID_NAME].isin(
        statid), FILENAME_NAME]

    return list(filelist)
