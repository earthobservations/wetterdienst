import pandas as pd

from additionals.select_functions import create_fileindex as _create_fileindex

from additionals.generic_functions import check_dwd_structure as _check_dwd_structure
from additionals.generic_functions import correct_folder_path as _correct_folder_path

"""
Function for selecting datafile for given statid, var, res, per
"""


def select_dwd(statid,
               var,
               res,
               per,
               folder="./dwd_data",
               create_new_filelist=False):
    # Check for the combination of requested parameters
    _check_dwd_structure(var=var, res=res, per=per)

    folder = _correct_folder_path(folder)

    # Create name of fileslistfile
    filelist_local = "{}_{}_{}_{}".format("filelist", var, res, per)

    filelist_local_path = "{}/{}/{}{}".format(
        folder, "metadata", filelist_local, ".csv")

    # Try to read in file
    try:
        # Except if a new one should be created
        if create_new_filelist:
            raise Exception

        # Try to read in file
        filelist = pd.read_csv(
            filelist_local_path)
    except Exception:
        # If there was an error with reading in the fileslist get a new
        # fileslist
        _create_fileindex(var=var, res=res, per=per,
                          folder=folder)

        # Try to read in file
        filelist = pd.read_csv(
            filelist_local_path)

    files_statid_id = [id for id, statid_file in enumerate(
        filelist["STATID"]) if statid_file == statid]

    filelist = filelist.iloc[files_statid_id, 2]

    filelist = list(filelist)

    return filelist
