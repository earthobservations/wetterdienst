""" file index creation for available DWD station data """
import re
import functools
import pandas as pd

from wetterdienst.constants.access_credentials import DWD_CDC_PATH, DWD_CLIM_OBS_GERMANY_PATH
from wetterdienst.constants.metadata import ARCHIVE_FORMAT, STATION_ID_REGEX
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.file_path_handling.path_handling import build_path_to_parameter, \
    list_files_of_climate_observations


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
    parameter_path = build_path_to_parameter(
        parameter, time_resolution, period_type)

    files_server = list_files_of_climate_observations(
        parameter_path, recursive=True)

    files_server = pd.DataFrame(
        files_server, columns=[DWDMetaColumns.FILENAME.value], dtype='str')

    # Filter for .zip files
    files_server = files_server[files_server.FILENAME.str.endswith(
        ARCHIVE_FORMAT)]

    files_server.loc[:, DWDMetaColumns.FILENAME.value] = files_server.loc[:, DWDMetaColumns.FILENAME.value].\
        str.replace(f"{DWD_CDC_PATH}/{DWD_CLIM_OBS_GERMANY_PATH}/", "")

    file_names = files_server.loc[:, DWDMetaColumns.FILENAME.value].str.split("/").apply(
        lambda strings: strings[-1])

    files_server.loc[:, DWDMetaColumns.STATION_ID.value] = file_names.apply(
        lambda x: re.findall(STATION_ID_REGEX, x).pop(0))

    files_server.loc[:, DWDMetaColumns.STATION_ID.value] = files_server.loc[:, DWDMetaColumns.STATION_ID.value].\
        astype(int)

    files_server = files_server.sort_values(
        by=[DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value])

    return files_server.loc[:, [DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]]


def reset_file_index_cache() -> None:
    """ Function to reset the cached file index for all kinds of parameters """
    create_file_index_for_dwd_server.cache_clear()
