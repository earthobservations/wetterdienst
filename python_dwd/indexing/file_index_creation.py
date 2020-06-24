""" file index creation for available DWD station data """
from pathlib import PurePosixPath
import re
import functools
import ftplib
import pandas as pd

from python_dwd.constants.access_credentials import DWD_PATH, DWD_SERVER
from python_dwd.constants.metadata import ARCHIVE_FORMAT, STATID_REGEX
from python_dwd.download.ftp_handling import FTP
from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.path_handling import build_index_path


@functools.lru_cache(maxsize=None)
def create_file_index_for_dwd_server(parameter: Parameter,
                                     time_resolution: TimeResolution,
                                     period_type: PeriodType) -> pd.DataFrame:
    """
    Function (cached) to create a file index of the DWD station data. The file index
    is created for an individual set of parameters.
    Args:
        parameter: parameter of Parameter enumeration
        time_resolution: time resolution of TimeResolution enumeration
        period_type: period type of PeriodType enumeration
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    server_path = build_index_path(parameter, time_resolution, period_type)

    # todo: replace with global requests.Session creating the index
    try:
        with FTP(DWD_SERVER) as ftp:
            ftp.login()
            files_server = ftp.list_files(
                remote_path=str(server_path), also_subfolders=True)

    except ftplib.all_errors as e:
        raise e("Creating file index currently not possible.")

    files_server = pd.DataFrame(
        files_server, columns=[DWDMetaColumns.FILENAME.value], dtype='str')

    # Filter for .zip files
    files_server = files_server[files_server.FILENAME.str.endswith(
        ARCHIVE_FORMAT)]

    files_server.loc[:, DWDMetaColumns.FILENAME.value] = files_server.loc[:, DWDMetaColumns.FILENAME.value].\
        str.replace(DWD_PATH + '/', '')

    file_names = files_server.loc[:, DWDMetaColumns.FILENAME.value].str.split("/").apply(
        lambda strings: strings[-1])

    files_server.loc[:, DWDMetaColumns.STATION_ID.value] = file_names.apply(
        lambda x: re.findall(STATID_REGEX, x).pop(0))

    files_server.loc[:, DWDMetaColumns.STATION_ID.value] = files_server.loc[:, DWDMetaColumns.STATION_ID.value].\
        astype(int)

    files_server = files_server.sort_values(
        by=[DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value])

    return files_server.loc[:, [DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]]


def reset_file_index_cache() -> None:
    """ Function to reset the cached file index for all kinds of parameters """
    create_file_index_for_dwd_server.cache_clear()
