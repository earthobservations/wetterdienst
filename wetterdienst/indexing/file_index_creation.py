""" file index creation for available DWD station data """
import re
from functools import lru_cache
from typing import Union, Optional

import pandas as pd
from dateparser import parse

from wetterdienst.constants.access_credentials import (
    DWD_CDC_PATH,
    DWDCDCBase,
    DWDWeatherBase
)
from wetterdienst.constants.metadata import (
    ArchiveFormat,
    STATION_ID_REGEX,
    RADOLAN_HISTORICAL_DT_REGEX,
    RADOLAN_RECENT_DT_REGEX,
)
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.file_path_handling.path_handling import (
    build_path_to_parameter,
    list_files_of_dwd_server,
)
from wetterdienst.enumerations.radar_sites import RadarSites
from wetterdienst.enumerations.radar_data_types import RadarDataTypes


@lru_cache(maxsize=None)
def create_file_index_for_climate_observations(
    parameter: Parameter, time_resolution: TimeResolution, period_type: PeriodType
) -> pd.DataFrame:
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
    file_index = _create_file_index_for_dwd_server(
        parameter, time_resolution, DWDCDCBase.CLIMATE_OBSERVATIONS, period_type
    )

    file_index = file_index[
        file_index[DWDMetaColumns.FILENAME.value].str.endswith(ArchiveFormat.ZIP.value)
    ]

    file_index[DWDMetaColumns.STATION_ID.value] = (
        file_index[DWDMetaColumns.FILENAME.value]
        .apply(lambda x: re.findall(STATION_ID_REGEX, x)[0])
        .astype(int)
    )

    file_index = file_index.sort_values(
        by=[DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]
    )

    return file_index.loc[
        :, [DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]
    ]


@lru_cache(maxsize=None)
def create_file_index_for_radolan(time_resolution: TimeResolution) -> pd.DataFrame:
    """
    Function used to create a file index for the RADOLAN product. The file index will
    include both recent as well as historical files. A datetime column is created from
    the filenames which contain some datetime formats. This datetime column is required
    for later filtering for the requested file.

    Args:
        time_resolution: time resolution enumeration for the requesed RADOLAN product,
        where two are possible: hourly and daily

    Returns:
        file index as DataFrame
    """
    file_index = pd.concat(
        [
            _create_file_index_for_dwd_server(
                Parameter.RADOLAN,
                time_resolution,
                DWDCDCBase.GRIDS_GERMANY,
                period_type,

            )
            for period_type in (PeriodType.HISTORICAL, PeriodType.RECENT)
        ]
    )

    file_index = file_index[
        file_index[DWDMetaColumns.FILENAME.value].str.contains("/bin/")
        & file_index[DWDMetaColumns.FILENAME.value].str.endswith(
            (ArchiveFormat.GZ.value, ArchiveFormat.TAR_GZ.value)
        )
    ]

    r = re.compile(f"{RADOLAN_HISTORICAL_DT_REGEX}|{RADOLAN_RECENT_DT_REGEX}")

    # Require datetime of file for filtering
    file_index[DWDMetaColumns.DATETIME.value] = file_index[
        DWDMetaColumns.FILENAME.value
    ].apply(
        lambda filename: parse(
            r.findall(filename)[0],
            date_formats=[DatetimeFormat.YM.value, DatetimeFormat.ymdhm.value],
        )
    )

    return file_index


def _create_file_index_for_dwd_server(
    parameter: Parameter,
    time_resolution: TimeResolution,
    dwd_base: Union[DWDCDCBase, DWDWeatherBase],
    period_type: Optional[PeriodType] = None,
    radar_site: Optional[RadarSites] = None,
    radar_data_type: Optional[RadarDataTypes] = None
) -> pd.DataFrame:
    """
    Function to create a file index of the DWD station data, which usually is shipped as
    zipped/archived data. The file index is created for an individual set of parameters.
    Args:
        parameter: parameter of Parameter enumeration
        time_resolution: time resolution of TimeResolution enumeration
        dwd_base: base path e.g. climate_observations/germany or weather
        period_type: period type of PeriodType enumeration
        radar_site: Site of the radar if parameter is one of RADAR_PARAMETERS_SITES
        radar_data_type: Some radar data are available in different data types
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    parameter_path = build_path_to_parameter(parameter,
                                             time_resolution,
                                             period_type,
                                             radar_site,
                                             radar_data_type)

    files_server = list_files_of_dwd_server(parameter_path, dwd_base, recursive=True)

    files_server = pd.DataFrame(
        files_server, columns=[DWDMetaColumns.FILENAME.value], dtype="str"
    )

    data_directory = DWDCDCBase.PATH.value \
        if isinstance(dwd_base, DWDCDCBase) else DWDWeatherBase.PATH.value

    files_server[DWDMetaColumns.FILENAME.value] = files_server[
        DWDMetaColumns.FILENAME.value
    ].str.replace(f"{data_directory}/{dwd_base.value}/", "")

    return files_server


def reset_file_index_cache() -> None:
    """ Function to reset the cached file index for all kinds of parameters """
    create_file_index_for_climate_observations.cache_clear()
    create_file_index_for_radolan.cache_clear()
