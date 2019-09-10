""" Meta data handling """
from pathlib import Path

import pandas as pd

from python_dwd.constants.column_name_mapping import STATIONNAME_NAME, STATE_NAME, HAS_FILE_NAME
from python_dwd.constants.ftp_credentials import MAIN_FOLDER, SUB_FOLDER_METADATA
from python_dwd.constants.metadata import METADATA_NAME, DATA_FORMAT
from .additionals.functions import check_parameters
from .additionals.functions import correct_folder_path
from .additionals.functions import create_folder
from .additionals.functions import remove_old_file
from .additionals.helpers import create_fileindex
from .additionals.helpers import create_metaindex, create_metaindex2
from .additionals.helpers import fix_metaindex
from .additionals.variables import STRING_STATID_COL
from .select_dwd import create_file_list_for_dwd_server


def add_filepresence(metainfo: str,
                     parameter: str,
                     time_resolution: str,
                     period_type: str,
                     folder: str,
                     create_new_filelist: bool):
    """

    Args:
        metainfo:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        folder:
        create_new_filelist:

    Returns:
        meta info
    """
    # Check for the combination of requested parameters
    check_parameters(parameter, time_resolution, period_type)

    # Correct folder so that it doesn't end with slash
    folder = correct_folder_path(folder)

    if create_new_filelist:
        create_fileindex(parameter=parameter,
                         time_resolution=time_resolution,
                         period_type=period_type,
                         folder=folder)

    metainfo[HAS_FILE_NAME] = False

    file_existence = create_file_list_for_dwd_server(statid=list(metainfo.iloc[:, 0]),
                                                     parameter=parameter,
                                                     time_resolution=time_resolution,
                                                     period_type=period_type,
                                                     folder=folder)

    file_existence = pd.DataFrame(file_existence)

    file_existence.iloc[:, 0] = file_existence.iloc[:, 0].apply(
        lambda x: x.split('_')[STRING_STATID_COL.get(period_type, None)]).astype(int)

    metainfo.loc[metainfo.iloc[:, 0].isin(
        file_existence.iloc[:, 0]), HAS_FILE_NAME] = True

    return metainfo


def metadata_for_dwd_data(parameter: str,
                          time_resolution: str,
                          period_type: str,
                          folder: str = MAIN_FOLDER,
                          write_file: bool = True,
                          create_new_filelist: bool = False):
    """
    A main function to retrieve metadata for a set of parameters that creates a
        corresponding csv.
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        folder: local file system folder where files should be stored
        write_file:
        create_new_filelist:

    Returns:

    """
    # Check types of function parameters
    assert isinstance(parameter, str)
    assert isinstance(time_resolution, str)
    assert isinstance(period_type, str)
    assert isinstance(folder, str)
    assert isinstance(write_file, bool)
    assert isinstance(create_new_filelist, bool)

    # Check for the combination of requested parameters
    check_parameters(parameter=parameter,
                     time_resolution=time_resolution,
                     period_type=period_type)

    # Correct folder so that it doesn't end with slash
    folder = correct_folder_path(folder)

    # Check for folder and create if necessary
    create_folder(subfolder=SUB_FOLDER_METADATA,
                  folder=folder)

    old_file = f"{METADATA_NAME}_{parameter}_{time_resolution}_{period_type}{DATA_FORMAT}"

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

    if time_resolution != "1_minute":
        # Get new metadata as unformated file
        metaindex = create_metaindex(parameter=parameter,
                                     time_resolution=time_resolution,
                                     period_type=period_type)

        # Format raw metadata
        metainfo = fix_metaindex(metaindex)
    else:
        metainfo = create_metaindex2(var=parameter,
                                     res=time_resolution,
                                     per=period_type,
                                     folder=folder)

    # We want to add the STATE information for our metadata for cases where
    # we don't request daily precipitation data. That has two reasons:
    # - daily precipitation data has a STATE information combined with a city
    # - daily precipitation data is the most common data served by the DWD
    # First we check if the data has a column with name STATE
    if STATE_NAME not in metainfo.columns:
        # If the column is not available we need this information to be added
        # (recursive call)
        mdp = metadata_for_dwd_data("more_precip",
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
                                parameter=parameter,
                                time_resolution=time_resolution,
                                period_type=period_type,
                                folder=folder,
                                create_new_filelist=create_new_filelist)

    # If a file should be written
    if write_file and not old_file_exists and not create_new_filelist:
        # Create filename for metafile
        metafile_local = f"{METADATA_NAME}_{parameter}_{time_resolution}_{period_type}"

        # Create filepath with filename and including extension
        metafile_local_path = Path(folder,
                                   SUB_FOLDER_METADATA,
                                   metafile_local)

        metafile_local_path = f'{metafile_local_path}{DATA_FORMAT}'

        # Check for possible old files and remove them
        remove_old_file(file_type=METADATA_NAME,
                        fileformat=DATA_FORMAT,
                        parameter=parameter,
                        time_resolution=time_resolution,
                        period_type=period_type,
                        folder=folder,
                        subfolder=SUB_FOLDER_METADATA)

        # Write file to csv
        metainfo.to_csv(path_or_buf=metafile_local_path,
                        header=True,
                        index=False)

    return metainfo
