# Imports
import pandas as pd
from .select_dwd import select_dwd

from .additionals.helpers import create_metaindex
from .additionals.helpers import fix_metaindex
from .additionals.helpers import create_fileindex
# from .additionals.helpers import add_filepresence

from .additionals.generic_functions import correct_folder_path
from .additionals.generic_functions import check_parameters
from .additionals.generic_functions import create_folder
from .additionals.generic_functions import remove_old_file
from .additionals.generic_functions import determine_statid_col

"""
#################################
### Function add_filepresence ###
#################################
"""


def add_filepresence(metainfo,
                     var,
                     res,
                     per,
                     folder,
                     create_new_filelist):

    if create_new_filelist:
        create_fileindex(var=var,
                         res=res,
                         per=per,
                         folder=folder)

    metainfo["HAS_FILE"] = False

    statid_col = determine_statid_col(per)

    has_file_df = pd.DataFrame(select_dwd(
        metainfo.STATIONS_ID, var='kl', res='daily', per='historical'))

    has_file_df.iloc[:, 0] = has_file_df.iloc[:, 0].apply(
        lambda x: x.split('_')[statid_col]).astype(int)

    metainfo.loc[metainfo.loc[:, 'STATIONS_ID'].isin(
        has_file_df.iloc[:, 0]), 'HAS_FILE'] = True

    return metainfo


"""
#############################
### Function metadata_dwd ###
#############################
"""


def metadata_dwd(var,
                 res,
                 per,
                 folder="./dwd_data",
                 write_file=True,
                 create_new_filelist=False):
    # Check for the combination of requested parameters
    check_parameters(var=var,
                     res=res,
                     per=per)

    # Correct folder so that it doesn't end with slash
    folder = correct_folder_path(folder)

    # Get new metadata as unformated file
    metaindex = create_metaindex(var=var,
                                 res=res,
                                 per=per)

    # Format raw metadata
    metainfo = fix_metaindex(metaindex)

    metainfo = add_filepresence(metainfo=metainfo,
                                var=var,
                                res=res,
                                per=per,
                                folder=folder,
                                create_new_filelist=create_new_filelist)

    if write_file:
        # Check for folder and create if necessary
        create_folder(subfolder="metadata",
                      folder=folder)

        # Create filename for metafile
        metafile_local = "metadata_{}_{}_{}".format(var,
                                                    res,
                                                    per)

        # Create filepath with filename and including extension
        metafile_local_path = "{}/{}/{}{}".format(folder,
                                                  "metadata",
                                                  metafile_local,
                                                  ".csv")

        # Check for possible old files and remove them
        remove_old_file(file_type="metadata",
                        var=var,
                        res=res,
                        per=per,
                        folder=folder)

        metainfo.to_csv(path_or_buf=metafile_local_path,
                        header=True,
                        index=False)

    return metainfo
