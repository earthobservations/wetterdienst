# Imports
import pandas as pd
from pathlib import Path
from .select_dwd import select_dwd

from .additionals.helpers import create_metaindex
from .additionals.helpers import fix_metaindex
from .additionals.helpers import create_fileindex

from .additionals.generic_functions import correct_folder_path
from .additionals.generic_functions import check_parameters
from .additionals.generic_functions import create_folder
from .additionals.generic_functions import remove_old_file

from .additionals.generic_variables import MAIN_FOLDER, SUB_FOLDER_METADATA
from .additionals.generic_variables import METADATA_NAME, DATA_FORMAT
from .additionals.generic_variables import STRING_STATID_COL
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
    check_parameters(var=var,
                     res=res,
                     per=per)

    # Correct folder so that it doesn't end with slash
    folder = correct_folder_path(folder)

    if create_new_filelist:
        create_fileindex(var=var,
                         res=res,
                         per=per,
                         folder=folder)

    metainfo["HAS_FILE"] = False

    file_existence = select_dwd(statid=list(metainfo.iloc[:, 0]),
                                var=var,
                                res=res,
                                per=per,
                                folder=folder)

    file_existence = pd.DataFrame(file_existence)

    file_existence.iloc[:, 0] = file_existence.iloc[:, 0].apply(
        lambda x: x.split('_')[STRING_STATID_COL.get(per, None)]).astype(int)

    metainfo.loc[metainfo.iloc[:, 0].isin(
        file_existence.iloc[:, 0]), 'HAS_FILE'] = True

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
    check_parameters(var=var,
                     res=res,
                     per=per)

    # Correct folder so that it doesn't end with slash
    folder = correct_folder_path(folder)

    # Create old file path
    old_file_path = '{}/{}/{}_{}_{}_{}{}'.format(folder,
                                                 SUB_FOLDER_METADATA,
                                                 METADATA_NAME,
                                                 var,
                                                 res,
                                                 per,
                                                 DATA_FORMAT)

    # Check for old file existance
    old_file_exists = Path(old_file_path).is_file()

    # If there's an old filelist and no new one should be created read in old
    if old_file_exists and not create_new_filelist:
        metainfo = pd.read_csv(filepath_or_buffer=old_file_path)
    else:
        # Get new metadata as unformated file
        metaindex = create_metaindex(var=var,
                                     res=res,
                                     per=per)

        # Format raw metadata
        metainfo = fix_metaindex(metaindex)

        # Add info if file is available on ftp server
        metainfo = add_filepresence(metainfo=metainfo,
                                    var=var,
                                    res=res,
                                    per=per,
                                    folder=folder,
                                    create_new_filelist=create_new_filelist)

    # If a file should be written
    if write_file:
        # Check for folder and create if necessary
        create_folder(subfolder=SUB_FOLDER_METADATA,
                      folder=folder)

        # Create filename for metafile
        metafile_local = "{}_{}_{}_{}".format(METADATA_NAME,
                                              var,
                                              res,
                                              per)

        # Create filepath with filename and including extension
        metafile_local_path = "{}/{}/{}{}".format(folder,
                                                  SUB_FOLDER_METADATA,
                                                  metafile_local,
                                                  DATA_FORMAT)

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
