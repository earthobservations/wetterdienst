from pathlib import Path

import pandas as pd

from python_dwd.constants.column_name_mapping import STATION_ID_NAME, FILENAME_NAME
from python_dwd.constants.ftp_credentials import MAIN_FOLDER, SUB_FOLDER_METADATA
from python_dwd.constants.metadata import FILELIST_NAME, DATA_FORMAT
from .additionals.functions import check_parameters
from .additionals.functions import correct_folder_path
from .additionals.helpers import create_fileindex


def select_dwd(statid,
               var,
               res,
               per,
               folder=MAIN_FOLDER,
               create_new_filelist=False):
    """
    Function for selecting datafiles (links to archives) for given
    statid, var, res, per under consideration of a created list of files that are
    available online.

    Args:
        statid:
        var:
        res:
        per:
        folder:
        create_new_filelist:

    Returns:

    """
    # Check type of function parameters
    assert isinstance(statid, list)
    assert isinstance(var, str)
    assert isinstance(res, str)
    assert isinstance(per, str)
    assert isinstance(folder, str)
    assert isinstance(create_new_filelist, bool)

    # Check for the combination of requested parameters
    check_parameters(parameter=var,
                     time_resolution=res,
                     period_type=per)

    folder = correct_folder_path(folder)

    # Create name of fileslistfile
    filelist_local = f'{FILELIST_NAME}_{var}_{res}_{per}'

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
        create_fileindex(var=var,
                         res=res,
                         per=per,
                         folder=folder)

    # Read in filelist
    filelist = pd.read_csv(filelist_local_path)

    # Return filenames for filtered statids
    filelist = filelist.loc[filelist[STATION_ID_NAME].isin(
        statid), FILENAME_NAME]

    # Convert to simple list
    filelist = list(filelist)

    return filelist
