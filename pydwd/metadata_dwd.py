# Imports
import pandas as pd

from .additionals.helpers import (create_metaindex as _create_metaindex,
                                  fix_metaindex as _fix_metaindex)

from .additionals.generic_functions import (correct_folder_path as _correct_folder_path,
                                            check_parameters as _check_parameters,
                                            create_folder as _create_folder,
                                            remove_old_file as _remove_old_file)


def metadata_dwd(var,
                 res,
                 per,
                 folder="./dwd_data",
                 write_file=True):
    # Check for the combination of requested parameters
    _check_parameters(var=var, res=res, per=per)

    # Correct folder so that it doesn't end with slash
    folder = _correct_folder_path(folder)

    # Get new metadata as unformated file
    metaindex = _create_metaindex(var=var, res=res, per=per)

    # Format raw metadata
    metainfo = _fix_metaindex(metaindex)

    if write_file:
        # Check for folder and create if necessary
        _create_folder(subfolder="metadata", folder=folder)

        # Create filename for metafile
        metafile_local = "metadata_{}_{}_{}".format(var, res, per)

        # Create filepath with filename and including extension
        metafile_local_path = "{}/{}/{}{}".format(folder,
                                                  "metadata",
                                                  metafile_local,
                                                  ".csv")

        # Check for possible old files and remove them
        _remove_old_file(
            file_type="metadata", var=var, res=res, per=per, folder=folder)

        pd.DataFrame.to_csv(metainfo, metafile_local_path, header=True,
                            index=False)

    return metainfo
