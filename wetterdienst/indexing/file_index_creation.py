""" file index creation for available DWD station data """
import re
from functools import lru_cache
import pandas as pd

from wetterdienst.constants.access_credentials import (
    DWD_CDC_PATH,
    DWDCDCDataPath,
)
from wetterdienst.constants.metadata import ArchiveFormat, STATION_ID_REGEX, RADOLAN_HISTORICAL_DT_REGEX, \
    RADOLAN_RECENT_DT_REGEX
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.file_path_handling.path_handling import (
    build_path_to_parameter,
    list_files_of_dwd,
)


@lru_cache
def create_file_index_for_climate_observations(
        parameter: Parameter,
        time_resolution: TimeResolution,
        period_type: PeriodType
) -> pd.DataFrame:

    file_index = _create_file_index_for_dwd_server(
        parameter,
        time_resolution,
        period_type,
        DWDCDCDataPath.CLIMATE_OBSERVATIONS
    )

    file_index = file_index[file_index[DWDMetaColumns.FILENAME.value].str.startswith(ArchiveFormat.ZIP.value)]

    file_index[DWDMetaColumns.STATION_ID.value] = file_index[
        DWDMetaColumns.FILENAME.value
    ].apply(lambda x: re.findall(STATION_ID_REGEX, x)[0])

    file_index.loc[:, DWDMetaColumns.STATION_ID.value] = file_index.loc[
        :, DWDMetaColumns.STATION_ID.value
    ].astype(int)

    file_index = file_index.sort_values(
        by=[DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]
    )

    return file_index.loc[
        :, [DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]
    ]


@lru_cache
def create_file_index_for_radolan(
        time_resolution: TimeResolution
) -> pd.DataFrame:
    file_index = pd.DataFrame()

    for period_type, radolan_dt_regex, radolan_dt_format in zip((PeriodType.HISTORICAL, PeriodType.RECENT), (RADOLAN_HISTORICAL_DT_REGEX, RADOLAN_RECENT_DT_REGEX), (DatetimeFormat.YM.value, DatetimeFormat.ymdhm.value)):
        file_index_period = _create_file_index_for_dwd_server(
            Parameter.RADOLAN,
            time_resolution,
            period_type,
            DWDCDCDataPath.GRIDS_GERMANY
        )

        file_index_period = file_index_period[file_index_period[DWDMetaColumns.FILENAME.value].str.endswith(
            (ArchiveFormat.GZ.value, ArchiveFormat.TAR_GZ.value))]

        # Store period type to easily define how to work with data
        # as historical and recent data is stored differently
        file_index_period[DWDMetaColumns.PERIOD_TYPE.value] = period_type

        # Require datetime of file for filtering
        file_index_period[DWDMetaColumns.DATETIME.value] = file_index_period[DWDMetaColumns.FILENAME.value].\
            apply(lambda x: re.findall(radolan_dt_regex, x)[0]).\
            apply(lambda x: pd.to_datetime(x, format=radolan_dt_format))

        file_index = file_index.append(file_index_period)

    return file_index


def _create_file_index_for_dwd_server(
    parameter: Parameter,
    time_resolution: TimeResolution,
    period_type: PeriodType,
    base: DWDCDCDataPath
) -> pd.DataFrame:
    """
    Function to create a file index of the DWD station data, which usually is shipped as
    zipped/archived data. The file index is created for an individual set of parameters.
    Args:
        parameter: parameter of Parameter enumeration
        time_resolution: time resolution of TimeResolution enumeration
        period_type: period type of PeriodType enumeration
        base: base path e.g. climate_observations/germany
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    parameter_path = build_path_to_parameter(parameter, time_resolution, period_type)

    files_server = list_files_of_dwd(parameter_path, base, recursive=True)

    files_server = pd.DataFrame(files_server, columns=[DWDMetaColumns.FILENAME.value], dtype="str")

    files_server[DWDMetaColumns.FILENAME.value] = files_server[
        DWDMetaColumns.FILENAME.value
    ].str.replace(f"{DWD_CDC_PATH}/{base.value}/", "")

    return files_server


def reset_file_index_cache() -> None:
    """ Function to reset the cached file index for all kinds of parameters """
    create_file_index_for_climate_observations.cache_clear()
    create_file_index_for_radolan.cache_clear()
