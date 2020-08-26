""" Meta data handling """
from typing import Union
import pandas as pd

from wetterdienst.additionals.functions import parse_enumeration_from_template
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.indexing.file_index_creation import (
    create_file_index_for_climate_observations,
    reset_file_index_cache,
)
from wetterdienst.indexing.meta_index_creation import (
    create_meta_index_for_climate_observations,
    reset_meta_index_cache,
)


def metadata_for_climate_observations(
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
    create_new_meta_index: bool = False,
    create_new_file_index: bool = False,
) -> pd.DataFrame:
    """
    A main function to retrieve metadata for a set of parameters that creates a
        corresponding csv.
    STATE information is added to metadata for cases where there's no such named
    column (e.g. STATE) in the pandas.DataFrame.
    For this purpose we use daily precipitation data. That has two reasons:
     - daily precipitation data has a STATE information combined with a city
     - daily precipitation data is the most common data served by the DWD
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        create_new_meta_index: if true: a new meta index for metadata will
         be created
        create_new_file_index: if true: a new file index for metadata will
         be created
    Returns:
        pandas.DataFrame with metadata for selected parameters
    """
    if create_new_meta_index:
        reset_meta_index_cache()

    if create_new_file_index:
        reset_file_index_cache()

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
