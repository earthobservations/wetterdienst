from typing import List, Optional

import pandas as pd

from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameterSet,
    DWDObservationResolution,
    DWDObservationPeriod,
)
from wetterdienst.dwd.metadata.constants import (
    DWDCDCBase,
    STATION_ID_REGEX,
    ArchiveFormat,
    DATE_RANGE_REGEX,
)
from wetterdienst.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations.metadata.resolution import HIGH_RESOLUTIONS
from wetterdienst.util.cache import fileindex_cache_twelve_hours


def create_file_list_for_climate_observations(
    station_id: str,
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
    date_range: Optional[str] = None,
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
        date_range:
    Returns:
        List of path's to file
    """
    file_index = create_file_index_for_climate_observations(
        parameter_set, resolution, period
    )

    file_index = file_index[file_index[DWDMetaColumns.STATION_ID.value] == station_id]

    if date_range:
        file_index = file_index[
            file_index[DWDMetaColumns.DATE_RANGE.value] == date_range
        ]

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

    file_index[DWDMetaColumns.STATION_ID.value] = (
        file_index[DWDMetaColumns.FILENAME.value].str.findall(STATION_ID_REGEX).str[0]
    )

    file_index = file_index.dropna().reset_index(drop=True)

    file_index[DWDMetaColumns.STATION_ID.value] = file_index[
        DWDMetaColumns.STATION_ID.value
    ].astype(str)

    if resolution in HIGH_RESOLUTIONS and period == DWDObservationPeriod.HISTORICAL:
        # Date range string for additional filtering of historical files
        file_index[DWDMetaColumns.DATE_RANGE.value] = (
            file_index[DWDMetaColumns.FILENAME.value]
            .str.findall(DATE_RANGE_REGEX)
            .str[0]
        )

        file_index[
            [DWDMetaColumns.FROM_DATE.value, DWDMetaColumns.TO_DATE.value]
        ] = file_index[DWDMetaColumns.DATE_RANGE.value].str.split("_", expand=True)

        file_index[DWDMetaColumns.FROM_DATE.value] = pd.to_datetime(
            file_index[DWDMetaColumns.FROM_DATE.value], format=DatetimeFormat.YMD.value
        )

        file_index[DWDMetaColumns.TO_DATE.value] = pd.to_datetime(
            file_index[DWDMetaColumns.TO_DATE.value], format=DatetimeFormat.YMD.value
        )

        # Temporary fix for filenames with wrong ordered/faulty dates
        # Fill those cases with minimum/maximum date to ensure that they are loaded as
        # we don't know what exact date range the included data has
        wrong_date_order_index = (
            file_index[DWDMetaColumns.FROM_DATE.value]
            > file_index[DWDMetaColumns.TO_DATE.value]
        )

        file_index.loc[
            wrong_date_order_index, DWDMetaColumns.FROM_DATE.value
        ] = file_index[DWDMetaColumns.FROM_DATE.value].min()
        file_index.loc[
            wrong_date_order_index, DWDMetaColumns.TO_DATE.value
        ] = file_index[DWDMetaColumns.TO_DATE.value].max()

        file_index[DWDMetaColumns.INTERVAL.value] = file_index.apply(
            lambda x: pd.Interval(
                left=x[DWDMetaColumns.FROM_DATE.value],
                right=x[DWDMetaColumns.TO_DATE.value],
                closed="both",
            ),
            axis=1,
        )

    file_index = file_index.sort_values(
        by=[DWDMetaColumns.STATION_ID.value, DWDMetaColumns.FILENAME.value]
    )

    return file_index
