""" Meta data handling """
from typing import Union
import pandas as pd

from python_dwd.additionals.helpers import metaindex_for_1minute_data, create_metaindex
from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.file_index_creation import create_file_index_for_dwd_server, \
    reset_file_index_cache


def add_filepresence(metainfo: pd.DataFrame,
                     parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType) -> pd.DataFrame:
    """
    updates the metainfo

    Args:
        metainfo: meta info about the weather data
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    Returns:
        updated meta info
    """
    metainfo[DWDMetaColumns.HAS_FILE.value] = False

    file_index = create_file_index_for_dwd_server(
        parameter, time_resolution, period_type)

    metainfo.loc[metainfo.iloc[:, 0].isin(
        file_index[DWDMetaColumns.STATION_ID.value]), DWDMetaColumns.HAS_FILE.value] = True

    return metainfo


def metadata_for_dwd_data(parameter: Union[Parameter, str],
                          time_resolution: Union[TimeResolution, str],
                          period_type: Union[PeriodType, str],
                          create_new_file_index: bool = False) -> pd.DataFrame:
    """
    A main function to retrieve metadata for a set of parameters that creates a
        corresponding csv.

    STATE information is added to metadata for cases where there's no such named
    column (e.g. STATE) in the dataframe.
    For this purpose we use daily precipitation data. That has two reasons:
     - daily precipitation data has a STATE information combined with a city
     - daily precipitation data is the most common data served by the DWD


    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        create_new_file_index: if true: a new file_list for metadata will
         be created

    Returns:

    """
    if create_new_file_index:
        reset_file_index_cache()

    parameter = Parameter(parameter)
    time_resolution = TimeResolution(time_resolution)
    period_type = PeriodType(period_type)

    if time_resolution == TimeResolution.MINUTE_1:
        metainfo = metaindex_for_1minute_data(parameter=parameter,
                                              time_resolution=time_resolution)
    else:
        metainfo = create_metaindex(parameter=parameter,
                                    time_resolution=time_resolution,
                                    period_type=period_type)

    if all(pd.isnull(metainfo[DWDMetaColumns.STATE.value])):
        # @todo avoid calling function in function -> we have to build a function around to manage missing data
        mdp = metadata_for_dwd_data(Parameter.PRECIPITATION_MORE,
                                    TimeResolution.DAILY,
                                    PeriodType.HISTORICAL,
                                    create_new_file_index=False)

        stateinfo = pd.merge(metainfo[DWDMetaColumns.STATION_ID],
                             mdp.loc[:, [DWDMetaColumns.STATION_ID.value, DWDMetaColumns.STATE.value]],
                             how="left")

        metainfo[DWDMetaColumns.STATE.value] = stateinfo[DWDMetaColumns.STATE.value]

    metainfo = add_filepresence(metainfo=metainfo,
                                parameter=parameter,
                                time_resolution=time_resolution,
                                period_type=period_type)

    return metainfo
