# Imports
import pandas as pd

from additionals.metadata_functions import create_metaindex as _create_metaindex
from additionals.metadata_functions import fix_metaindex as _fix_metaindex

from additionals.generic_functions import correct_folder_path as _correct_folder_path
from additionals.generic_functions import check_dwd_structure as _check_dwd_structure
from additionals.functions import create_dwd_folder as _create_dwd_folder
from additionals.functions import remove_dwdfile as _remove_dwdfile


def metadata_dwd(var,
                 res,
                 per,
                 folder="./dwd_data",
                 write_file=True):
    # Check for the combination of requested parameters
    _check_dwd_structure(var=var, res=res, per=per)

    # Correct folder so that it doesn't end with slash
    folder = _correct_folder_path(folder)

    # Get new metadata as unformated file
    metaindex = _create_metaindex(var=var, res=res, per=per)

    # Format raw metadata, remove old file (and replace it with formatted)
    metainfo = _fix_metaindex(metaindex)

    if write_file:
        # Check for folder and create if necessary
        _create_dwd_folder(subfolder="metadata", folder=folder)

        # Create filename for metafile
        metafile_local = "metadata_{}_{}_{}".format(var, res, per)

        # Create filepath with filename and including extension
        metafile_local_path = "{}/{}/{}{}".format(folder,
                                                  "metadata",
                                                  metafile_local,
                                                  ".csv")

        # Check for possible old files and remove them
        _remove_dwdfile(
            file_type="metadata", var=var, res=res, per=per, folder=folder)

        pd.DataFrame.to_csv(metainfo, metafile_local_path, header=True,
                            index=False)

    return metainfo
