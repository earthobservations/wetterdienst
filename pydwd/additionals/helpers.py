import pandas as pd
from tqdm import tqdm

# from pydwd.select_dwd import select_dwd

from .generic_classes import FTP
from .generic_functions import check_parameters
from .generic_functions import correct_folder_path
from .generic_functions import create_folder
from .generic_functions import remove_old_file

from .dwd_credentials import SERVER, PATH


"""
################################
### Function 'get_metaindex' ###
################################
"""


def create_metaindex(var,
                     res,
                     per,
                     server=SERVER,
                     path=PATH):
    # Check for combination of parameters
    check_parameters(var=var,
                     res=res,
                     per=per)

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

    files_server = list(filter(lambda x: x[0] == '.', files_server))

    files_server = files_server[0][1]

    metafile_server = list(filter(
        (lambda x: ".txt" in x and "beschreibung" in x.lower()), files_server))

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


def fix_metaindex(metaindex):
    # Convert data to pandas dataframe
    metaindex = pd.DataFrame(metaindex)
    # Split the data into columns by any spaces
    metaindex = metaindex.iloc[:, 0].str.split(expand=True)
    # Get the column names
    column_names = list(filter(None, metaindex.iloc[0, :]))
    # Make them upper ones
    column_names = [name.upper() for name in column_names]
    # Skip first two lines (header and seperating line)
    metaindex = metaindex[2:]
    # Remove last empty row
    metaindex = metaindex[:-1]
    # Create dataframe with strings to fix
    metaindex_to_fix = metaindex.iloc[:, 6:]
    # Reduce the original dataframe by those columns
    metaindex = metaindex.iloc[:, :6]
    # Index is fixed by string operations (put together all except the last
    # string which refers to state)
    metaindex_to_fix = metaindex_to_fix \
        .agg((lambda x: [' '.join(list(filter(None, x))[:-1]),
                         list(filter(None, x))[-1]]), 1).apply(pd.Series)
    # Finally put together again the original frame and the fixed data
    metaindex = pd.concat([metaindex, metaindex_to_fix], axis=1)
    # Overwrite the columns
    metaindex.columns = column_names

    # Fix datatypes
    metaindex.iloc[:, 0] = metaindex.iloc[:, 0].astype(int)
    metaindex.iloc[:, 1] = metaindex.iloc[:, 1].astype('datetime64')
    metaindex.iloc[:, 2] = metaindex.iloc[:, 2].astype('datetime64')
    metaindex.iloc[:, 3] = metaindex.iloc[:, 3].astype(int)
    metaindex.iloc[:, 4] = metaindex.iloc[:, 4].astype(float)
    metaindex.iloc[:, 5] = metaindex.iloc[:, 5].astype(float)
    metaindex.iloc[:, 6] = metaindex.iloc[:, 6].astype(str)
    metaindex.iloc[:, 7] = metaindex.iloc[:, 7].astype(str)

    return metaindex


"""
Function to receive current files on server as list excluding description files
"""


def create_fileindex(var,
                     res,
                     per,
                     folder="./dwd_data",
                     server=SERVER,
                     path=PATH):
    # Check for the combination of requested parameters
    check_parameters(var=var,
                     res=res,
                     per=per)

    folder = correct_folder_path(folder)

    # Check for folder and create if necessary
    create_folder(subfolder="metadata",
                  folder=folder)

    # Create filename for local metadata file containing information of date
    filelist_local = "{}_{}_{}_{}".format("filelist", var, res, per)

    # Create filename
    filelist_local_path = "{}/{}/{}{}".format(folder,
                                              "metadata",
                                              filelist_local,
                                              ".csv")

    # Try listing files under given path
    try:
        # Open connection with ftp server
        with FTP(server) as ftp:
            # Login
            ftp.login()

            # Get files for set of paramters
            files_server = ftp.walk(
                "/{}/{}/{}/{}/".format(path, res, var, per))

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

    files_server.loc[:, 'FILENAME'] = files_server.loc[:, 'FILENAME'].apply(
        lambda x: x if x[:2] != "./" else x[2:])

    files_server = files_server[files_server.FILENAME.str.contains('.zip')]

    files_server.loc[:, 'FILELINK'] = files_server.loc[:, 'ROOT'] \
        + '/' + files_server.loc[:, 'FILENAME']

    if per == "historical":
        statid_col = -4
    elif per == "recent":
        statid_col = -2
    elif per == "now":
        statid_col = -2
    else:
        statid_col = None

    files_server \
        .insert(1, 1, files_server.index)

    files_server \
        .insert(2,
                2,
                files_server.iloc[:, 0].str.split('_')
                .apply(lambda x: x[statid_col]))

    files_server = files_server.iloc[:, [1, 2, 0]]

    files_server.columns = ['FILEID', 'STATID', 'FILENAME']

    files_server.iloc[:, 1] = files_server.iloc[:, 1].astype(int)

    files_server = files_server.sort_values(by=["STATID"])

    # Remove old file
    remove_old_file(file_type="filelist",
                    var=var,
                    res=res,
                    per=per,
                    folder=folder)

    # Write new file
    files_server.to_csv(path_or_buf=filelist_local_path,
                        header=True,
                        index=False)

    return None


def reduce_to_values(data):
    pass
