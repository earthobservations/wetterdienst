from functools import reduce

from urllib.parse import urljoin
import pandas as pd

from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameterSet,
    DWDObservationResolution,
    DWDObservationPeriod,
)
from wetterdienst.dwd.metadata.constants import DWDCDCBase, DWD_SERVER, DWD_CDC_PATH
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.util.cache import (
    fileindex_cache_five_minutes,
    fileindex_cache_one_hour,
)
from wetterdienst.util.network import list_remote_files


def _create_file_index_for_dwd_server(
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
    cdc_base: DWDCDCBase,
) -> pd.DataFrame:
    """
    Function to create a file index of the DWD station data, which usually is shipped as
    zipped/archived data. The file index is created for an individual set of parameters.
    Args:
        parameter_set: parameter set of Parameter enumeration
        resolution: time resolution of TimeResolution enumeration
        period: period type of PeriodType enumeration
        cdc_base: base path e.g. climate_observations/germany
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    parameter_path = build_path_to_parameter(parameter_set, resolution, period)

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
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
) -> str:
    """
    Function to build a indexing file path
    Args:
        parameter_set: observation measure
        resolution: frequency/granularity of measurement interval
        period: recent or historical files

    Returns:
        indexing file path relative to climate observations path
    """
    if parameter_set == DWDObservationParameterSet.SOLAR and resolution in (
        DWDObservationResolution.HOURLY,
        DWDObservationResolution.DAILY,
    ):
        return f"{resolution.value}/{parameter_set.value}/"

    return f"{resolution.value}/{parameter_set.value}/{period.value}/"
