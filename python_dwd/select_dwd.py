import pandas as pd
from pathlib import Path

from .additionals.helpers import create_fileindex

from .additionals.functions import check_parameters
from .additionals.functions import correct_folder_path

from .additionals.variables import MAIN_FOLDER, SUB_FOLDER_METADATA
from .additionals.variables import FILELIST_NAME, DATA_FORMAT
from .additionals.variables import STATION_ID_NAME, FILENAME_NAME

"""
#############################
### Function 'select_dwd' ###
#############################
Function for selecting datafiles (links to archives) for given
statid, var, res, per under consideration of a created list of files that are
available online.
"""


def select_dwd(statid,
               var,
               res,
               per,
               folder=MAIN_FOLDER,
               create_new_filelist=False):
    # Check type of function parameters
    assert isinstance(statid, list)
    assert isinstance(var, str)
    assert isinstance(res, str)
    assert isinstance(per, str)
    assert isinstance(folder, str)
    assert isinstance(create_new_filelist, bool)

    # Check for the combination of requested parameters
    check_parameters(var=var,
                     res=res,
                     per=per)

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
