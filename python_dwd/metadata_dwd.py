# Imports
import pandas as pd
from pathlib import Path
from .select_dwd import select_dwd

from .additionals.helpers import create_metaindex, create_metaindex2
from .additionals.helpers import fix_metaindex
from .additionals.helpers import create_fileindex

from .additionals.functions import correct_folder_path
from .additionals.functions import check_parameters
from .additionals.functions import create_folder
from .additionals.functions import remove_old_file

from python_dwd.constants.ftp_credentials import MAIN_FOLDER, SUB_FOLDER_METADATA
from python_dwd.constants.metadata import METADATA_NAME, DATA_FORMAT
from .additionals.variables import STRING_STATID_COL
from python_dwd.constants.column_name_mapping import STATIONNAME_NAME, STATE_NAME, HAS_FILE_NAME

"""
###################################
### Function 'add_filepresence' ###
###################################
"""


def add_filepresence(metainfo,
                     var,
                     res,
                     per,
                     folder,
                     create_new_filelist):

    # Check for the combination of requested parameters
    check_parameters(parameter=var,
                     time_resolution=res,
                     period_type=per)

    # Correct folder so that it doesn't end with slash
    folder = correct_folder_path(folder)

    if create_new_filelist:
        create_fileindex(var=var,
                         res=res,
                         per=per,
                         folder=folder)

    metainfo[HAS_FILE_NAME] = False

    file_existence = select_dwd(statid=list(metainfo.iloc[:, 0]),
                                var=var,
                                res=res,
                                per=per,
                                folder=folder)

    file_existence = pd.DataFrame(file_existence)

    file_existence.iloc[:, 0] = file_existence.iloc[:, 0].apply(
        lambda x: x.split('_')[STRING_STATID_COL.get(per, None)]).astype(int)

    metainfo.loc[metainfo.iloc[:, 0].isin(
        file_existence.iloc[:, 0]), HAS_FILE_NAME] = True

    return metainfo


"""
###############################
### Function 'metadata_dwd' ###
###############################
A main function to retrieve metadata for a set of parameters that creates a
corresponding csv.
"""


def metadata_dwd(var,
                 res,
                 per,
                 folder=MAIN_FOLDER,
                 write_file=True,
                 create_new_filelist=False):
    # Check types of function parameters
    assert isinstance(var, str)
    assert isinstance(res, str)
    assert isinstance(per, str)
    assert isinstance(folder, str)
    assert isinstance(write_file, bool)
    assert isinstance(create_new_filelist, bool)

    # Check for the combination of requested parameters
    check_parameters(parameter=var,
                     time_resolution=res,
                     period_type=per)

    # Correct folder so that it doesn't end with slash
    folder = correct_folder_path(folder)

    # Check for folder and create if necessary
    create_folder(subfolder=SUB_FOLDER_METADATA,
                  folder=folder)

    old_file = f"{METADATA_NAME}_{var}_{res}_{per}{DATA_FORMAT}"

    # Create old file path
    old_file_path = Path(folder,
                         SUB_FOLDER_METADATA,
                         old_file)

    # Check for old file existance
    old_file_exists = Path(old_file_path).is_file()

    # If there's an old file and no new one should be created read in old
    if old_file_exists and not create_new_filelist:
        metainfo = pd.read_csv(filepath_or_buffer=old_file_path)

        # Here we can return, as we don't want to remove the file without further knowledge
        # Also we don't need to write a file that's already on the drive
        return metainfo

    if res != "1_minute":
        # Get new metadata as unformated file
        metaindex = create_metaindex(var=var,
                                     res=res,
                                     per=per)

        # Format raw metadata
        metainfo = fix_metaindex(metaindex)
    else:
        metainfo = create_metaindex2(var=var,
                                     res=res,
                                     per=per,
                                     folder=folder)

    # We want to add the STATE information for our metadata for cases where
    # we don't request daily precipitation data. That has two reasons:
    # - daily precipitation data has a STATE information combined with a city
    # - daily precipitation data is the most common data served by the DWD
    # First we check if the data has a column with name STATE
    if STATE_NAME not in metainfo.columns:
        # If the column is not available we need this information to be added
        # (recursive call)
        mdp = metadata_dwd("more_precip",
                           "daily",
                           "historical",
                           folder=folder,
                           write_file=False,
                           create_new_filelist=False)

        # Join state of daily precipitation data on this dataframe
        metainfo = metainfo.merge(
            mdp.loc[:, [STATIONNAME_NAME, STATE_NAME]], on=STATIONNAME_NAME).reset_index(drop=True)

    # Add info if file is available on ftp server
    metainfo = add_filepresence(metainfo=metainfo,
                                var=var,
                                res=res,
                                per=per,
                                folder=folder,
                                create_new_filelist=create_new_filelist)

    # If a file should be written
    if write_file and not old_file_exists and not create_new_filelist:
        # Create filename for metafile
        metafile_local = f"{METADATA_NAME}_{var}_{res}_{per}"

        # Create filepath with filename and including extension
        metafile_local_path = Path(folder,
                                   SUB_FOLDER_METADATA,
                                   metafile_local)

        metafile_local_path = f'{metafile_local_path}{DATA_FORMAT}'

        # Check for possible old files and remove them
        remove_old_file(file_type=METADATA_NAME,
                        fileformat=DATA_FORMAT,
                        var=var,
                        res=res,
                        per=per,
                        folder=folder,
                        subfolder=SUB_FOLDER_METADATA)

        # Write file to csv
        metainfo.to_csv(path_or_buf=metafile_local_path,
                        header=True,
                        index=False)

    return metainfo
