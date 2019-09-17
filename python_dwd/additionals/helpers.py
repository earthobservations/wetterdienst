""" A set of helping functions used by the main functions """
import os
from io import TextIOWrapper
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import pandas as pd
from numpy import datetime64
from tqdm import tqdm

from python_dwd.constants.column_name_mapping import STATION_ID_NAME, \
    FROM_DATE_NAME, TO_DATE_NAME, \
    GERMAN_TO_ENGLISH_COLUMNS_MAPPING, FILENAME_NAME, FILEID_NAME
from python_dwd.constants.ftp_credentials import DWD_SERVER, DWD_PATH, \
    MAIN_FOLDER, SUB_FOLDER_METADATA
from python_dwd.constants.metadata import METADATA_1MIN_COLUMNS, \
    METADATA_MATCHSTRINGS, METADATA_1MIN_GEO_MATCHSTRINGS, \
    METADATA_1MIN_PAR_MATCHSTRINGS, FILELIST_NAME, FTP_METADATA_NAME, \
    ARCHIVE_FORMAT, DATA_FORMAT, METADATA_FIXED_COLUMN_WIDTH, STRING_STATID_COL
from python_dwd.download.ftp_handling import FTP
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.path_handling import remove_old_file, \
    create_folder


def create_metaindex(parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType) -> pd.DataFrame:
    """
    @todo: please specify what this function does
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
    Return:


    """
    server_path = PurePosixPath(DWD_PATH,
                                time_resolution.value,
                                parameter.value,
                                period_type.value)

    try:
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            files_server = ftp.list_files(path=str(server_path))

    except Exception:
        raise NameError("Couldn't retrieve filelist from server")

    metafile_server = [file
                       for file in files_server
                       if all([matchstring in file.lower()
                               for matchstring in METADATA_MATCHSTRINGS])].pop(0)

    try:
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            file = ftp.read_file_to_bytes(metafile_server)

    except Exception:
        raise NameError(
            "Reading metadata file currently is not possible. Try again!")

    metaindex = pd.read_fwf(filepath_or_buffer=file,
                            colspecs=METADATA_FIXED_COLUMN_WIDTH,
                            skiprows=[1],
                            dtype=str)

    metaindex_colnames = [colname for colname in metaindex.columns if "unnamed" not in colname.lower()]
    metaindex_colnames_fixed = "".join(metaindex_colnames).split(" ")
    metaindex.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(name.upper(), name.upper())
                         for name in metaindex_colnames_fixed]

    columns = metaindex.columns
    META_INDEX_DTYPES = {columns[0]: int,
                         columns[1]: datetime64,
                         columns[2]: datetime64,
                         columns[3]: float,
                         columns[4]: float,
                         columns[5]: float,
                         columns[6]: str,
                         columns[7]: str}
    metaindex = metaindex.astype(META_INDEX_DTYPES)

    return metaindex


def metaindex_for_1minute_data(parameter: Parameter,
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

    assert time_resolution == TimeResolution.MINUTE_1, \
        "Wrong TimeResolution, only 1 minute is valid "

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
            zip_file_files = zip_file.infolist()

            zip_file_files = [zip_file_file.filename
                              for zip_file_file in zip_file_files]

            file_geo = [zip_file_file
                        for zip_file_file in zip_file_files
                        if all([matchstring in zip_file_file.lower()
                                for matchstring in METADATA_1MIN_GEO_MATCHSTRINGS])].pop(0)

            file_par = [zip_file_file
                        for zip_file_file in zip_file_files
                        if all([matchstring in zip_file_file.lower()
                                for matchstring in METADATA_1MIN_PAR_MATCHSTRINGS])].pop(0)

            with zip_file.open(file_geo) as file_opened:
                try:
                    geo_file = parse_zipped_data_into_df(file_opened)
                except UnicodeDecodeError:
                    geo_file = parse_zipped_data_into_df(file_opened,
                                                         engine='python')

            with zip_file.open(file_par) as file_opened:
                try:
                    par_file = parse_zipped_data_into_df(file_opened)
                except UnicodeDecodeError:
                    par_file = parse_zipped_data_into_df(file_opened,
                                                         engine='python')

        Path(metafile_local).unlink()

        geo_file.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(
            name.strip().upper(), name.strip().upper())
            for name in geo_file.columns]

        par_file.columns = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(
            name.strip().upper(), name.strip().upper())
            for name in par_file.columns]

        geo_file = geo_file.iloc[[-1], :]
        par_file = par_file.loc[:, [FROM_DATE_NAME, TO_DATE_NAME]].dropna()

        geo_file[FROM_DATE_NAME] = par_file[FROM_DATE_NAME].min()
        geo_file[TO_DATE_NAME] = par_file[TO_DATE_NAME].max()

        geo_file = geo_file.loc[:, METADATA_1MIN_COLUMNS]

        metadata_df = metadata_df.append(geo_file,
                                         ignore_index=True)

    columns = metadata_df.columns
    META_INDEX_DTYPES = {columns[0]: int,
                         columns[1]: datetime64,
                         columns[2]: datetime64,
                         columns[3]: float,
                         columns[4]: float,
                         columns[5]: float,
                         columns[6]: str}
    metadata_df = metadata_df.astype(META_INDEX_DTYPES)

    metadata_df = metadata_df.sort_values(
        STATION_ID_NAME).reset_index(drop=True)

    return metadata_df


def parse_zipped_data_into_df(file_opened, engine: str = 'c'):
    """ uses opened zip data to parse into df"""
    file = pd.read_csv(filepath_or_buffer=TextIOWrapper(file_opened),
                       sep=";",
                       na_values="-999",
                       enginbe=engine,
                       dtype=str)
    return file


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

    filelist_local_path = Path(folder,
                               SUB_FOLDER_METADATA,
                               f"{FILELIST_NAME}_{parameter.value}_"
                               f"{time_resolution.value}_"
                               f"{period_type.value}{DATA_FORMAT}")

    filelist_local_path = str(filelist_local_path).replace('\\', '/')

    server_path = Path(DWD_PATH,
                       time_resolution.value,
                       parameter.value,
                       period_type.value)

    server_path = f"{server_path}{os.sep}".replace('\\', '/')

    try:
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            files_server = ftp.list_files(path=server_path)

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
                .apply(lambda string: string[STRING_STATID_COL]))

    files_server = files_server.iloc[:, [1, 2, 0]]

    files_server.iloc[:, 1] = files_server.iloc[:, 1].apply(int)

    files_server = files_server.sort_values(by=[STATION_ID_NAME])

    remove_old_file(file_type=FILELIST_NAME,
                    parameter=parameter,
                    time_resolution=time_resolution,
                    period_type=period_type,
                    file_postfix=DATA_FORMAT,
                    folder=folder,
                    subfolder=SUB_FOLDER_METADATA)

    files_server.to_csv(path_or_buf=filelist_local_path,
                        header=True,
                        index=False)

    return None


def check_file_exist(file_path: Path) -> bool:
    """ checks if the file behind the path exists """
    return Path(file_path).is_file()
