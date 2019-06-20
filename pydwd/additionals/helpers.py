'''
A set of helping functions used by the main functions
'''
import pandas as pd
from numpy import datetime64

from .generic_classes import FTP

from .generic_functions import create_folder
from .generic_functions import remove_old_file

from .generic_variables import DWD_SERVER, DWD_PATH
from .generic_variables import MAIN_FOLDER, SUB_FOLDER_METADATA
from .generic_variables import METADATA_MATCHSTRINGS
from .generic_variables import FILELIST_NAME
from .generic_variables import ARCHIVE_FORMAT, DATA_FORMAT
from .generic_variables import METADATA_COLS_REPL
from .generic_variables import STRING_STATID_COL


"""
###################################
### Function 'create_metaindex' ###
###################################
A helping function to create a raw index of metadata for stations of the set of
parameters as given. This raw metadata is then used by other functions.
"""


def create_metaindex(var,
                     res,
                     per,
                     server=DWD_SERVER,
                     path=DWD_PATH):

    # Try downloading metadata file under given local link
    try:
        # Open connection with ftp server
        with FTP(server) as ftp:
            # Login
            ftp.login()

            # Establish connection with server
            files_server = ftp.walk(path="{}/{}/{}/{}".format(path,
                                                              res,
                                                              var,
                                                              per))

    # If there's a problem with the connection throw an error
    except Exception:
        raise NameError("Couldn't retrieve filelist from server")

    files_server = [file
                    for file in files_server
                    if file[0] == '.']

    files_server = files_server[0][1]

    metafile_server = [file
                       for file in files_server
                       if all([matchstring in file.lower()
                               for matchstring in METADATA_MATCHSTRINGS])]

    metafile_server = metafile_server[0]

    # Create full path of server file
    metafile_server_path = "{}/{}/{}/{}/{}".format(path,
                                                   res,
                                                   var,
                                                   per,
                                                   metafile_server)

    try:
        # Open connection with ftp server
        with FTP(server) as ftp:
            # Login
            ftp.login()

            # Download file into folder path
            metaindex = ftp.readlines(metafile_server_path)

    # If not possible raise an error
    except Exception:
        raise NameError(
            "Reading metadata file currently is not possible. Try again!")

    return metaindex


"""
################################
### Function 'fix_metaindex' ###
################################
A helping function to fix the raw index of metadata by some string operations
so that every information is in the right column.
"""


def fix_metaindex(metaindex):
    # Convert data to pandas dataframe
    metaindex = pd.DataFrame(metaindex)
    # Split the data into columns by any spaces
    metaindex = metaindex.iloc[:, 0].str.split(expand=True)

    # Get the column names
    column_names = metaindex.iloc[0, :]
    # Remove Nones
    column_names = [name
                    for name in column_names
                    if name is not None]
    # Make them upper ones
    column_names = [name.upper()
                    for name in column_names]
    # Replace names by english aquivalent
    column_names = [METADATA_COLS_REPL.get(name, name)
                    for name in column_names]

    # Skip first two lines (header and seperating line)
    metaindex = metaindex.iloc[2:-1, :]
    # Create dataframe with strings to fix
    metaindex_to_fix = metaindex.iloc[:, 6:]
    # Reduce the original dataframe by those columns
    metaindex = metaindex.iloc[:, :6]

    # Index is fixed by string operations (put together all except the last
    # string which refers to state)
    metaindex_to_fix = metaindex_to_fix \
        .agg(lambda data: [string
                           for string in data
                           if string is not None], 1) \
        .to_frame() \
        .agg(lambda data: [' '.join(data[:-1]), data[-1]], 1) \
        .apply(pd.Series)

    # Finally put together again the original frame and the fixed data
    metaindex = pd.concat([metaindex, metaindex_to_fix], axis=1)
    # Overwrite the columns
    metaindex.columns = column_names

    # Fix datatypes
    metaindex.iloc[:, 0] = metaindex.iloc[:, 0].astype(int)
    metaindex.iloc[:, 1] = metaindex.iloc[:, 1].astype(datetime64)
    metaindex.iloc[:, 2] = metaindex.iloc[:, 2].astype(datetime64)
    metaindex.iloc[:, 3] = metaindex.iloc[:, 3].astype(int)
    metaindex.iloc[:, 4] = metaindex.iloc[:, 4].astype(float)
    metaindex.iloc[:, 5] = metaindex.iloc[:, 5].astype(float)
    metaindex.iloc[:, 6] = metaindex.iloc[:, 6].astype(str)
    metaindex.iloc[:, 7] = metaindex.iloc[:, 7].astype(str)

    return metaindex


"""
###################################
### Function 'create_fileindex' ###
###################################
A function to receive current files on server as list excluding description
files and only containing those files that have measuring data.
"""


def create_fileindex(var,
                     res,
                     per,
                     folder=MAIN_FOLDER,
                     server=DWD_SERVER,
                     path=DWD_PATH):

    # Check for folder and create if necessary
    create_folder(subfolder=SUB_FOLDER_METADATA,
                  folder=folder)

    # Create filename for local metadata file containing information of date
    filelist_local = "{}_{}_{}_{}".format(FILELIST_NAME,
                                          var,
                                          res,
                                          per)

    # Create filename
    filelist_local_path = "{}/{}/{}{}".format(folder,
                                              SUB_FOLDER_METADATA,
                                              filelist_local,
                                              DATA_FORMAT)

    # Try listing files under given path
    try:
        # Open connection with ftp server
        with FTP(server) as ftp:
            # Login
            ftp.login()

            # Get files for set of paramters
            files_server = ftp.walk(
                "/{}/{}/{}/{}/".format(path,
                                       res,
                                       var,
                                       per))

    # If not possible raise an error
    except Exception:
        raise NameError(
            "Download of fileslist file currently not possible. Try again!")

    files_server = pd.DataFrame(files_server)

    files_server.columns = ['ROOT', 'FILENAMES']

    files_server = files_server.FILENAMES.apply(pd.Series) \
        .merge(files_server, left_index=True, right_index=True) \
        .drop(['FILENAMES'], axis=1) \
        .melt(id_vars=['ROOT'], value_name="FILENAME") \
        .drop('variable', axis=1)

    files_server.loc[:, 'FILENAME'] = files_server.loc[:, 'FILENAME'] \
        .astype(str)

    files_server.loc[:, 'FILENAME'] = files_server.loc[:, 'FILENAME'].apply(
        lambda filename: filename.lstrip('./'))

    files_server = files_server[files_server.FILENAME.str.contains(
        ARCHIVE_FORMAT)]

    files_server.loc[:, 'FILENAME'] = files_server.loc[:, 'ROOT'] \
        + '/' + files_server.loc[:, 'FILENAME']

    files_server = files_server.drop(['ROOT'], axis=1)

    files_server \
        .insert(loc=1,
                column='FILEID',
                value=files_server.index)

    files_server \
        .insert(loc=2,
                column='STATID',
                value=files_server.iloc[:, 0].str.split('_')
                .apply(lambda string: string[STRING_STATID_COL.get(per, None)]))

    files_server = files_server.iloc[:, [1, 2, 0]]

    files_server.iloc[:, 1] = files_server.iloc[:, 1].astype(int)

    files_server = files_server.sort_values(by=["STATID"])

    # Remove old file
    remove_old_file(file_type=FILELIST_NAME,
                    var=var,
                    res=res,
                    per=per,
                    fileformat=DATA_FORMAT,
                    folder=folder,
                    subfolder=SUB_FOLDER_METADATA)

    # Write new file
    files_server.to_csv(path_or_buf=filelist_local_path,
                        header=True,
                        index=False)

    return None
