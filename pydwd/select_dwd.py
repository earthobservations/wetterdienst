import pandas as pd
from pathlib import Path, WindowsPath

from .additionals.helpers import create_fileindex

from .additionals.generic_functions import check_parameters
from .additionals.generic_functions import correct_folder_path

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
    check_parameters(var=var,
                     res=res,
                     per=per)

    if type(statid) == int:
        statid = [statid]

    elif type(statid) != list:
        statid = list(statid)

    folder = correct_folder_path(folder)

    # Create name of fileslistfile
    filelist_local = "{}_{}_{}_{}".format("filelist",
                                          var,
                                          res,
                                          per)

    filelist_local_path = "{}/{}/{}{}".format(folder,
                                              "metadata",
                                              filelist_local,
                                              ".csv")

    exist_old_file = WindowsPath(filelist_local_path) in Path(
        "{}/{}".format(folder, "metadata")).glob('*.csv')

    # Except if a new one should be created
    if create_new_filelist or not exist_old_file:
        # If there was an error with reading in the fileslist get a new
        # fileslist
        create_fileindex(var=var,
                         res=res,
                         per=per,
                         folder=folder)

    # Try to read in file
    try:
        # Try to read in file
        filelist = pd.read_csv(filelist_local_path)

    except Exception:
        # If there was an error with reading in the fileslist get a new
        # fileslist
        create_fileindex(var=var,
                         res=res,
                         per=per,
                         folder=folder)
        # Try to read in file
        filelist = pd.read_csv(filelist_local_path)

    # files_statid_id = [id
    #                    for id, statid_file in enumerate(filelist["STATID"])
    #                    if statid_file == statid]

    filelist = filelist.loc[filelist["STATID"].isin(statid), 'FILENAME']

    # filelist = filelist.iloc[files_statid_id, 2]

    filelist = list(filelist)

    return filelist
