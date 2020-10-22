import re
from typing import List

import pandas as pd

from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameterSet,
    DWDObservationResolution,
    DWDObservationPeriod,
)
from wetterdienst.dwd.metadata.constants import (
    DWDCDCBase,
    STATION_ID_REGEX,
    ArchiveFormat,
)
from wetterdienst.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.util.cache import fileindex_cache_twelve_hours


def create_file_list_for_climate_observations(
    station_id: int,
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
) -> List[str]:
    """
    Function for selecting datafiles (links to archives) for given
    station_ids, parameter, time_resolution and period_type under consideration of a
    created list of files that are
    available online.
    Args:
        station_id: station id for the weather station to ask for data
        parameter_set: observation measure
        resolution: frequency/granularity of measurement interval
        period: recent or historical files
    Returns:
        List of path's to file
    """
    file_index = create_file_index_for_climate_observations(
        parameter_set, resolution, period
    )

    file_index = file_index[file_index[DWDMetaColumns.STATION_ID.value] == station_id]

    return file_index[DWDMetaColumns.FILENAME.value].values.tolist()


@fileindex_cache_twelve_hours.cache_on_arguments()
def create_file_index_for_climate_observations(
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
) -> pd.DataFrame:
    """
    Function (cached) to create a file index of the DWD station data. The file index
    is created for an individual set of parameters.
    Args:
        parameter_set: parameter of Parameter enumeration
        resolution: time resolution of TimeResolution enumeration
        period: period type of PeriodType enumeration
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    file_index = _create_file_index_for_dwd_server(
        parameter_set, resolution, period, DWDCDCBase.CLIMATE_OBSERVATIONS
    )

    file_index = file_index[
        file_index[DWDMetaColumns.FILENAME.value].str.endswith(ArchiveFormat.ZIP.value)
    ]

    r = re.compile(STATION_ID_REGEX)

    file_index[DWDMetaColumns.STATION_ID.value] = (
        file_index[DWDMetaColumns.FILENAME.value]
        .apply(lambda filename: r.findall(filename.split("/")[-1]))
        .apply(lambda station_id: station_id[0] if station_id else pd.NA)
    )

    file_index = file_index.dropna().reset_index(drop=True)

    file_index[DWDMetaColumns.STATION_ID.value] = file_index[
        DWDMetaColumns.STATION_ID.value
    ].astype(int)

    file_index = file_index.sort_values(
        by=[DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]
    )

    return file_index.loc[
        :, [DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]
    ]
