""" file list creation for requested files """
from typing import Union, List
from datetime import datetime

from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.indexing.file_index_creation import (
    create_file_index_for_climate_observations,
    reset_file_index_cache,
    create_file_index_for_radolan,
)


def create_file_list_for_climate_observations(
    station_ids: List[int],
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
    create_new_file_index: bool = False,
) -> List[str]:
    """
    Function for selecting datafiles (links to archives) for given
    station_ids, parameter, time_resolution and period_type under consideration of a
    created list of files that are
    available online.
    Args:
        station_ids: ids for the weather station to ask for data
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        create_new_file_index: set if new file index is created
    Returns:
        List of path's to file
    """
    if create_new_file_index:
        reset_file_index_cache()

    parameter = Parameter(parameter)
    time_resolution = TimeResolution(time_resolution)
    period_type = PeriodType(period_type)

    file_index = create_file_index_for_climate_observations(
        parameter, time_resolution, period_type
    )

    file_index = file_index[
        file_index[DWDMetaColumns.STATION_ID.value].isin(station_ids)
    ]

    return file_index[DWDMetaColumns.FILENAME.value].values.tolist()


def create_filepath_for_radolan(
    date_time: datetime, time_resolution: TimeResolution
) -> str:
    """
    Function used to create a relative filepath for a requested datetime depending on
    the file index for the relevant time resolution.

    Args:
        date_time: datetime for requested RADOLAN file
        time_resolution: time resolution enumeration of the request

    Returns:
        a string, either empty if non found or with the relative path to the file
    """
    file_index = create_file_index_for_radolan(time_resolution)

    if date_time in file_index[DWDMetaColumns.DATETIME.value].tolist():
        file_index = file_index[file_index[DWDMetaColumns.DATETIME.value] == date_time]
    else:
        file_index = file_index[
            (file_index[DWDMetaColumns.DATETIME.value].dt.year == date_time.year)
            & (file_index[DWDMetaColumns.DATETIME.value].dt.month == date_time.month)
        ]

    if file_index.empty:
        return ""

    return f"{file_index[DWDMetaColumns.FILENAME.value].item()}"
