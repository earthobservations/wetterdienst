import logging

import pandas as pd

from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameterSet,
    DWDObservationResolution,
    DWDObservationPeriod,
)
from wetterdienst.dwd.observations.fileindex import (
    create_file_index_for_climate_observations,
)
from wetterdienst.dwd.observations.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns

logger = logging.getLogger(__name__)


def metadata_for_climate_observations(
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
) -> pd.DataFrame:
    """
    A main function to retrieve metadata for a set of parameters that creates a
    corresponding csv.
    STATE information is added to metadata for cases where there's no such named
    column (e.g. STATE) in the pandas.DataFrame.
    For this purpose we use daily precipitation data. That has two reasons:

    - daily precipitation data has a STATE information combined with a city
    - daily precipitation data is the most common data served by the DWD

    :param parameter_set:               Observation measure
    :param resolution:         Frequency/granularity of measurement interval
    :param period:             Recent or historical files

    :return: List of stations for selected parameters
    """

    meta_index = create_meta_index_for_climate_observations(
        parameter_set, resolution, period
    )

    meta_index[DWDMetaColumns.HAS_FILE.value] = False

    file_index = create_file_index_for_climate_observations(
        parameter_set, resolution, period
    )

    meta_index.loc[
        meta_index.loc[:, DWDMetaColumns.STATION_ID.value].isin(
            file_index[DWDMetaColumns.STATION_ID.value]
        ),
        DWDMetaColumns.HAS_FILE.value,
    ] = True

    return meta_index
