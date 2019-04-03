# Imports
import pandas as pd

from .additionals.helpers import (__create_metaindex,
                                  __fix_metaindex,
                                  __add_filepresence)

from .additionals.generic_functions import (__correct_folder_path,
                                            __check_parameters,
                                            __create_folder,
                                            __remove_old_file)


def metadata_dwd(var,
                 res,
                 per,
                 folder="./dwd_data",
                 write_file=True,
                 create_new_filelist=False):
    # Check for the combination of requested parameters
    __check_parameters(var=var, res=res, per=per)

    # Correct folder so that it doesn't end with slash
    folder = __correct_folder_path(folder)

    # Get new metadata as unformated file
    metaindex = __create_metaindex(var=var, res=res, per=per)

    # Format raw metadata
    metainfo = __fix_metaindex(metaindex)

    metainfo = __add_filepresence(metainfo=metainfo,
                                  var=var,
                                  res=res,
                                  per=per,
                                  folder=folder,
                                  create_new_filelist=create_new_filelist)

    if write_file:
        # Check for folder and create if necessary
        __create_folder(subfolder="metadata", folder=folder)

        # Create filename for metafile
        metafile_local = "metadata_{}_{}_{}".format(var, res, per)

        # Create filepath with filename and including extension
        metafile_local_path = "{}/{}/{}{}".format(folder,
                                                  "metadata",
                                                  metafile_local,
                                                  ".csv")

        # Check for possible old files and remove them
        __remove_old_file(
            file_type="metadata", var=var, res=res, per=per, folder=folder)

        pd.DataFrame.to_csv(metainfo, metafile_local_path, header=True,
                            index=False)

    return metainfo
