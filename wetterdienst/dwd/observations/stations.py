import logging
from datetime import datetime
from typing import Union, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.spatial.ckdtree import cKDTree

from wetterdienst import Parameter, TimeResolution, PeriodType
from wetterdienst.dwd.observations.fileindex import (
    create_file_index_for_climate_observations,
)
from wetterdienst.dwd.observations.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.exceptions import InvalidParameterCombination
from wetterdienst.dwd.util import (
    check_parameters,
    parse_enumeration_from_template,
    parse_datetime,
)
from wetterdienst.util.geo import Coordinates

logger = logging.getLogger(__name__)


def metadata_for_climate_observations(
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
) -> pd.DataFrame:
    """
    A main function to retrieve metadata for a set of parameters that creates a
    corresponding csv.
    STATE information is added to metadata for cases where there's no such named
    column (e.g. STATE) in the pandas.DataFrame.
    For this purpose we use daily precipitation data. That has two reasons:

    - daily precipitation data has a STATE information combined with a city
    - daily precipitation data is the most common data served by the DWD

    :param parameter:               Observation measure
    :param time_resolution:         Frequency/granularity of measurement interval
    :param period_type:             Recent or historical files

    :return: List of stations for selected parameters
    """

    parameter = parse_enumeration_from_template(parameter, Parameter)
    time_resolution = parse_enumeration_from_template(time_resolution, TimeResolution)
    period_type = parse_enumeration_from_template(period_type, PeriodType)

    meta_index = create_meta_index_for_climate_observations(
        parameter, time_resolution, period_type
    )

    meta_index[DWDMetaColumns.HAS_FILE.value] = False

    file_index = create_file_index_for_climate_observations(
        parameter, time_resolution, period_type
    )

    meta_index.loc[
        meta_index.loc[:, DWDMetaColumns.STATION_ID.value].isin(
            file_index[DWDMetaColumns.STATION_ID.value]
        ),
        DWDMetaColumns.HAS_FILE.value,
    ] = True

    return meta_index
