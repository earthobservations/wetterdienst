from functools import reduce
from urllib.parse import urljoin

import pandas as pd

from wetterdienst import Parameter, TimeResolution, PeriodType
from wetterdienst.dwd.metadata.constants import DWDCDCBase, DWD_SERVER, DWD_CDC_PATH
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.util.cache import (
    fileindex_cache_five_minutes,
    fileindex_cache_one_hour,
)
from wetterdienst.util.network import list_remote_files


def _create_file_index_for_dwd_server(
    parameter: Parameter,
    time_resolution: TimeResolution,
    period_type: PeriodType,
    cdc_base: DWDCDCBase,
) -> pd.DataFrame:
    """
    Function to create a file index of the DWD station data, which usually is shipped as
    zipped/archived data. The file index is created for an individual set of parameters.
    Args:
        parameter: parameter of Parameter enumeration
        time_resolution: time resolution of TimeResolution enumeration
        period_type: period type of PeriodType enumeration
        cdc_base: base path e.g. climate_observations/germany
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    parameter_path = build_path_to_parameter(parameter, time_resolution, period_type)

    url = reduce(urljoin, [DWD_SERVER, DWD_CDC_PATH, cdc_base.value, parameter_path])

    files_server = list_remote_files(url, recursive=True)

    files_server = pd.DataFrame(
        files_server, columns=[DWDMetaColumns.FILENAME.value], dtype="str"
    )

    return files_server


def reset_file_index_cache() -> None:
    """ Function to reset the cached file index for all kinds of parameters """
    fileindex_cache_five_minutes.invalidate()
    fileindex_cache_one_hour.invalidate()


def build_path_to_parameter(
    parameter: Parameter, time_resolution: TimeResolution, period_type: PeriodType
) -> str:
    """
    Function to build a indexing file path
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    Returns:
        indexing file path relative to climate observations path
    """
    if parameter == Parameter.SOLAR and time_resolution in (
        TimeResolution.HOURLY,
        TimeResolution.DAILY,
    ):
        return f"{time_resolution.value}/{parameter.value}/"

    return f"{time_resolution.value}/{parameter.value}/{period_type.value}/"
