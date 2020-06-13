""" file index creation for available DWD station data """
from pathlib import Path, PurePosixPath
import re
from typing import Union
from tqdm import tqdm
import ftplib
import pandas as pd

from python_dwd.additionals.functions import check_parameters
from python_dwd.constants.access_credentials import DWD_FOLDER_MAIN, DWD_FOLDER_METADATA, DWD_PATH, DWD_SERVER
from python_dwd.constants.metadata import DWD_FILE_INDEX_NAME, CSV_FORMAT, ARCHIVE_FORMAT, STATION_ID_REGEX
from python_dwd.download.ftp_handling import FTP
from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def create_file_index_for_dwd_server(folder: Union[str, Path] = DWD_FOLDER_MAIN,
                                     force: bool = False) -> None:
    """
    Function to create file index of the DWD station data. The file index is created
    by checking all different kinds of parameter combinations, creating an index for
    existing combinations and putting all together, saving the index as a file.

    Args:
        folder: folder where the file index is created
        force: bool if file index should anyway be created even if one is existing

    Returns:
        None, the file index is written on the hard drive
    """
    file_index_local_path = _create_file_index_path(folder)

    if file_index_local_path.is_file() and not force:
        return

    # Check for folder and create if necessary
    file_index_local_path.parent.mkdir(parents=True, exist_ok=True)

    file_index = pd.DataFrame()

    for parameter in tqdm(Parameter):
        for time_resolution in TimeResolution:
            for period_type in PeriodType:
                if not check_parameters(parameter, time_resolution, period_type):
                    continue

                file_index = file_index.append(
                    _create_file_index_for_dwd_server(parameter, time_resolution, period_type))

    file_index.to_csv(path_or_buf=file_index_local_path, header=True, index=False)

    return


def _create_file_index_for_dwd_server(parameter: Parameter,
                                      time_resolution: TimeResolution,
                                      period_type: PeriodType) -> pd.DataFrame:
    """
    Function to create file index for a set of parameters. Creates a listing, extracts station ids,
    writes parameters.
    Args:
        parameter: parameter of Parameter enumeration
        time_resolution: time_resolution of TimeResolution enumeration
        period_type: period_type of PeriodType enumeration

    Returns:
        file index for parameters as pandas DataFrame
    """
    server_path = PurePosixPath(DWD_PATH) / time_resolution.value / \
        parameter.value / period_type.value

    try:
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            files_server = ftp.list_files(
                remote_path=str(server_path), also_subfolders=True)

    except ftplib.all_errors as e:
        raise ftplib.all_errors("Creating file index currently not possible.")

    files_server = pd.DataFrame(
        files_server, columns=[DWDColumns.FILENAME.value], dtype='str')

    # Add parameters
    files_server[DWDColumns.PARAMETER.value] = parameter.value
    files_server[DWDColumns.TIME_RESOLUTION.value] = time_resolution.value
    files_server[DWDColumns.PERIOD_TYPE.value] = period_type.value

    files_server.loc[:, DWDColumns.FILENAME.value] = files_server.loc[:, DWDColumns.FILENAME.value].apply(
        lambda filename: filename.replace(DWD_PATH + '/', ''))

    files_server = files_server[files_server.FILENAME.str.contains(
        ARCHIVE_FORMAT)]

    file_names = files_server.iloc[:, 0].str.split("/").apply(
        lambda string: string[-1])

    files_server.loc[:, DWDColumns.STATION_ID.value] = file_names.apply(
        lambda x: re.findall(STATION_ID_REGEX, x).pop(0))

    files_server.loc[:, DWDColumns.STATION_ID.value] = files_server.loc[:, DWDColumns.STATION_ID.value].astype(int)

    files_server = files_server.sort_values(
        by=[DWDColumns.STATION_ID.value, DWDColumns.FILENAME.value])

    files_server = files_server.reset_index(drop=True)

    files_server.loc[:, DWDColumns.FILEID.value] = files_server.index

    return files_server.loc[:, [DWDColumns.PARAMETER.value, DWDColumns.TIME_RESOLUTION.value,
                                DWDColumns.PERIOD_TYPE.value, DWDColumns.FILEID.value,
                                DWDColumns.STATION_ID.value, DWDColumns.FILENAME.value]]


def _create_file_index_path(folder) -> Path:
    """ Function to create filepath for file index """
    return Path(folder) / DWD_FOLDER_METADATA / f"{DWD_FILE_INDEX_NAME}{CSV_FORMAT}"
