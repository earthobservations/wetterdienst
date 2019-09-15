""" A set of helping functions used by the main functions """
import os
from io import TextIOWrapper
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import pandas as pd
from tqdm import tqdm

from python_dwd.download.ftp_handling import FTP
from python_dwd.file_path_handling.path_handling import remove_old_file, \
    create_folder
from python_dwd.additionals.variables import STRING_STATID_COL
from python_dwd.constants.column_name_mapping import STATION_ID_NAME, FROM_DATE_NAME, TO_DATE_NAME, \
    GERMAN_TO_ENGLISH_COLUMNS_MAPPING, FILENAME_NAME, FILEID_NAME
from python_dwd.constants.ftp_credentials import DWD_SERVER, DWD_PATH, MAIN_FOLDER, SUB_FOLDER_METADATA
from python_dwd.constants.metadata import METADATA_1MIN_COLUMNS, METADATA_MATCHSTRINGS, METADATA_1MIN_GEO_MATCHSTRINGS, \
    METADATA_1MIN_PAR_MATCHSTRINGS, FILELIST_NAME, FTP_METADATA_NAME, ARCHIVE_FORMAT, DATA_FORMAT, METADATA_COLSPECS
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def create_metaindex(parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType) -> pd.DataFrame:
    """

    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    """
    server_path = PurePosixPath(DWD_PATH,
                                time_resolution.value,
                                parameter.value,
                                period_type.value)

    # Type conversion to string is needed as ftplib doesn't work with Path objects
    server_path = str(server_path)

    # Try downloading metadata file under given local link
    try:
        # Open connection with ftp server
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            files_server = ftp.list_files(path=server_path)

    # If there's a problem with the connection throw an error
    except Exception:
        raise NameError("Couldn't retrieve filelist from server")

    metafile_server = [file
                       for file in files_server
                       if all([matchstring in file.lower()
                               for matchstring in METADATA_MATCHSTRINGS])]

    metafile_server = metafile_server.pop(0)

    try:
        # Open connection with ftp server
        with FTP(DWD_SERVER) as ftp:
            ftp.login()

            file = ftp.read_file_to_byte(metafile_server)

    # If not possible raise an error
    except Exception:
        raise NameError(
            "Reading metadata file currently is not possible. Try again!")

    metaindex = pd.read_fwf(filepath_or_buffer=file,
                            colspecs=METADATA_COLSPECS,
                            skiprows=[1],
                            dtype=str)

    # Extract column names from metaindex except from those containing "unnamed"
    # Column names contain the tag "unnamed" if the header space between the corresponding width from colspecs has only
    # empty characters and thus doesn't hold a part of the original column names
    # Example:
    # Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland
    # 00001 19370101 19860630            478     47.8413    8.8493 Aach                                Baden-Württemberg
    metaindex_colnames = [colname for colname in metaindex.columns if "unnamed" not in colname.lower()]
    # Paste together the columnnames (they have empty characters in between)
    metaindex_colnames_string = "".join(metaindex_colnames)
    # Split them by those empty characters
    metaindex_colnames_fixed = metaindex_colnames_string.split(" ")

    # Replace names by english and upper equivalent
    metaindex_colnames_translated = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(name.upper(), name.upper())
                                     for name in metaindex_colnames_fixed]

    metaindex.columns = metaindex_colnames_translated

    # Fix datatypes
    metaindex.iloc[:, 0] = metaindex.iloc[:, 0].apply(int)
    metaindex.iloc[:, 1] = metaindex.iloc[:, 1].apply(pd.to_datetime)
    metaindex.iloc[:, 2] = metaindex.iloc[:, 2].apply(pd.to_datetime)
    metaindex.iloc[:, 3] = metaindex.iloc[:, 3].apply(float)
    metaindex.iloc[:, 4] = metaindex.iloc[:, 4].apply(float)
    metaindex.iloc[:, 5] = metaindex.iloc[:, 5].apply(float)
    metaindex.iloc[:, 6] = metaindex.iloc[:, 6].apply(str)
    metaindex.iloc[:, 7] = metaindex.iloc[:, 7].apply(str)

    return metaindex


def create_metaindex2(parameter: Parameter,
                      time_resolution: TimeResolution,
                      folder):
    """
    A helping function to create a raw index of metadata for stations of the set of
    parameters as given. This raw metadata is then used by other functions. This
    second/alternative function must be used for high resolution data, where the
    metadata is not available as file but instead saved in external files per each
    station.
    - especially for precipitation/1_minute/historical!

    """
    metadata_path = PurePosixPath(DWD_PATH,
                                  time_resolution.value,
                                  parameter.value,
                                  FTP_METADATA_NAME)

    metadata_path = str(metadata_path)

    with FTP(DWD_SERVER) as ftp:
        ftp.login()

        metadata_server = ftp.nlst(metadata_path)

    metadata_local = [str(Path(folder,
                               SUB_FOLDER_METADATA,
                               metadata_file.split("/")[-1]))
                      for metadata_file in metadata_server]

    metadata_df = pd.DataFrame(None,
                               columns=METADATA_1MIN_COLUMNS)

    for metafile_server, metafile_local in tqdm(zip(metadata_server, metadata_local), total=len(metadata_server)):
        with FTP(DWD_SERVER) as ftp:
            ftp.login()

            ftp.download(metafile_server,
                         metafile_local)

        with ZipFile(metafile_local) as zip_file:
            # List of fileitems in zipfile
            zip_file_files = zip_file.infolist()

            # List of filenames of fileitems
            zip_file_files = [zip_file_file.filename
                              for zip_file_file in zip_file_files]

            # Filter file with 'produkt' in filename
            file_geo = [zip_file_file
                        for zip_file_file in zip_file_files
                        if all([matchstring in zip_file_file.lower()
                                for matchstring in METADATA_1MIN_GEO_MATCHSTRINGS])]

            # List to filename
            file_geo = file_geo.pop(0)

            file_par = [zip_file_file
                        for zip_file_file in zip_file_files
                        if all([matchstring in zip_file_file.lower()
                                for matchstring in METADATA_1MIN_PAR_MATCHSTRINGS])]

            # List to filename
            file_par = file_par.pop(0)

            # Read data into a dataframe
            with zip_file.open(file_geo) as file_opened:
                try:
                    geo_file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                                           sep=";",
                                           na_values="-999",
                                           dtype=str)
                except UnicodeDecodeError:
                    geo_file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                                           sep=";",
                                           na_values="-999",
                                           engine="python",
                                           dtype=str)

            with zip_file.open(file_par) as file_opened:
                try:
                    par_file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                                           sep=";",
                                           na_values="-999",
                                           dtype=str)

                except UnicodeDecodeError:
                    par_file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                                           sep=";",
                                           na_values="-999",
                                           engine="python",
                                           dtype=str)

        # Remove file
        Path(metafile_local).unlink()

        # Clean names
        geo_file.columns = [name.strip().upper()
                            for name in geo_file.columns]

        # Replace them
        geo_file.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(name, name)
                            for name in geo_file.columns]

        # Clean names
        par_file.columns = [name.strip().upper()
                            for name in par_file.columns]

        # Replace them
        par_file.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(name, name)
                            for name in par_file.columns]

        # List for DataFrame return
        geo_file = geo_file.iloc[[-1], :]

        par_file = par_file.loc[:, [FROM_DATE_NAME, TO_DATE_NAME]].dropna()

        geo_file[FROM_DATE_NAME] = par_file[FROM_DATE_NAME].min()
        geo_file[TO_DATE_NAME] = par_file[TO_DATE_NAME].max()

        geo_file = geo_file.loc[:, METADATA_1MIN_COLUMNS]

        metadata_df = metadata_df.append(geo_file,
                                         ignore_index=True)

    metadata_df = metadata_df.reset_index(drop=True)

    # Fix datatypes
    metadata_df.iloc[:, 0] = metadata_df.iloc[:, 0].apply(int)
    metadata_df.iloc[:, 1] = metadata_df.iloc[:, 1].apply(pd.to_datetime)
    metadata_df.iloc[:, 2] = metadata_df.iloc[:, 2].apply(pd.to_datetime)
    metadata_df.iloc[:, 3] = metadata_df.iloc[:, 3].apply(float)
    metadata_df.iloc[:, 4] = metadata_df.iloc[:, 4].apply(float)
    metadata_df.iloc[:, 5] = metadata_df.iloc[:, 5].apply(float)
    metadata_df.iloc[:, 6] = metadata_df.iloc[:, 6].apply(str)

    metadata_df = metadata_df.sort_values(
        STATION_ID_NAME).reset_index(drop=True)

    return metadata_df


def create_fileindex(parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType,
                     folder: str = MAIN_FOLDER):
    """
        A function to receive current files on server as list excluding description
        files and only containing those files that have measuring data.

    """
    # Check for folder and create if necessary
    create_folder(subfolder=SUB_FOLDER_METADATA,
                  folder=folder)

    # Create filename for local metadata file containing information of date
    filelist_local = f"{FILELIST_NAME}_{parameter.value}_" \
                     f"{time_resolution.value}_{period_type.value}"

    # Create filename with dataformat
    filelist_local_with_format = f"{filelist_local}{DATA_FORMAT}"

    # Create filename
    filelist_local_path = Path(folder,
                               SUB_FOLDER_METADATA,
                               filelist_local_with_format)

    filelist_local_path = str(filelist_local_path).replace('\\', '/')

    server_path = Path(DWD_PATH,
                       time_resolution.value,
                       parameter.value,
                       period_type.value)

    server_path = f"{server_path}{os.sep}"

    server_path = server_path.replace('\\', '/')

    # Try listing files under given path
    try:
        # Open connection with ftp server
        with FTP(DWD_SERVER) as ftp:
            # Login
            ftp.login()

            # Get files for set of paramters
            files_server = ftp.list_files(path=server_path)

    # If not possible raise an error
    except Exception:
        raise NameError(
            "Download of fileslist file currently not possible. Try again!")

    files_server = pd.DataFrame(files_server)

    files_server.columns = [FILENAME_NAME]

    files_server.loc[:, FILENAME_NAME] = files_server.loc[:, FILENAME_NAME] \
        .apply(str)

    files_server.loc[:, FILENAME_NAME] = files_server.loc[:, FILENAME_NAME].apply(
        lambda filename: filename.lstrip(DWD_PATH + '/'))

    files_server = files_server[files_server.FILENAME.str.contains(
        ARCHIVE_FORMAT)]

    files_server \
        .insert(loc=1,
                column=FILEID_NAME,
                value=files_server.index)

    files_server \
        .insert(loc=2,
                column=STATION_ID_NAME,
                value=files_server.iloc[:, 0].str.split('_')
                .apply(lambda string: string[STRING_STATID_COL.get(period_type, None)]))

    files_server = files_server.iloc[:, [1, 2, 0]]

    files_server.iloc[:, 1] = files_server.iloc[:, 1].apply(int)

    files_server = files_server.sort_values(by=[STATION_ID_NAME])

    # Remove old file
    remove_old_file(file_type=FILELIST_NAME,
                    parameter=parameter,
                    time_resolution=time_resolution,
                    period_type=period_type,
                    file_postfix=DATA_FORMAT,
                    folder=folder,
                    subfolder=SUB_FOLDER_METADATA)

    # Write new file
    files_server.to_csv(path_or_buf=filelist_local_path,
                        header=True,
                        index=False)

    return None


def check_file_exist(file_path: Path) -> bool:
    """ checks if the file behind the path exists """
    return Path(file_path).is_file()