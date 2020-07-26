""" Data collection pipeline """
import logging
from pathlib import Path
from typing import List, Union, Optional
import pandas as pd

from wetterdienst.additionals.functions import (
    check_parameters,
    parse_enumeration_from_template,
    create_humanized_column_names_mapping,
)
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.constants.metadata import DWD_FOLDER_MAIN
from wetterdienst.exceptions.invalid_parameter_exception import (
    InvalidParameterCombination,
)
from wetterdienst.indexing.file_index_creation import reset_file_index_cache
from wetterdienst.file_path_handling.file_list_creation import (
    create_file_list_for_dwd_server,
)
from wetterdienst.download.download import download_dwd_data_parallel
from wetterdienst.parsing_data.parse_data_from_files import parse_dwd_data
from wetterdienst.data_storing import (
    restore_dwd_data,
    store_dwd_data,
    _build_local_store_key,
)

log = logging.getLogger(__name__)


POSSIBLE_ID_VARS = (
    DWDMetaColumns.STATION_ID.value,
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)

POSSIBLE_DATE_VARS = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)


def collect_dwd_data(
    station_ids: List[int],
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
    folder: Union[str, Path] = DWD_FOLDER_MAIN,
    prefer_local: bool = False,
    write_file: bool = False,
    tidy_data: bool = True,
    humanize_column_names: bool = False,
    run_download_only: bool = False,
    create_new_file_index: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Function that organizes the complete pipeline of data collection, either
    from the internet or from a local file. It therefor goes through every given
    station id and, given by the parameters, either tries to get data from local
    store and/or if fails tries to get data from the internet. Finally if wanted
    it will try to store the data in a hdf file.
    Args:
        station_ids: station ids that are trying to be loaded
        parameter: parameter as enumeration
        time_resolution: time resolution as enumeration
        period_type: period type as enumeration
        folder: folder for local file interaction
        prefer_local: boolean for if local data should be preferred
        write_file: boolean to write data to local storage
        tidy_data: boolean to tidy up data so that there's only one set of values for
        a datetime in a row
        e.g. station_id, parameter, element, datetime, value, quality
        humanize_column_names: boolean to yield column names better for
        human consumption
        run_download_only: boolean to run only the download and storing process
        create_new_file_index: boolean if to create a new file index for the
        data selection

    Returns:
        a pandas DataFrame with all the data given by the station ids
    """
    parameter = parse_enumeration_from_template(parameter, Parameter)
    time_resolution = parse_enumeration_from_template(time_resolution, TimeResolution)
    period_type = parse_enumeration_from_template(period_type, PeriodType)

    if not check_parameters(parameter, time_resolution, period_type):
        raise InvalidParameterCombination(
            f"The combination of {parameter.value}, {time_resolution.value}, "
            f"{period_type.value} is invalid."
        )

    if create_new_file_index:
        reset_file_index_cache()

    # List for collected pandas DataFrames per each station id
    data = []
    for station_id in set(station_ids):
        request_string = _build_local_store_key(
            station_id, parameter, time_resolution, period_type
        )

        if prefer_local:
            # Try restoring data
            station_data = restore_dwd_data(
                station_id, parameter, time_resolution, period_type, folder
            )

            # When successful append data and continue with next iteration
            if not station_data.empty:
                log.info(f"Data for {request_string} restored from local.")

                data.append(station_data)

                continue

        log.info(f"Data for {request_string} will be collected from internet.")

        remote_files = create_file_list_for_dwd_server(
            [station_id], parameter, time_resolution, period_type
        )

        if len(remote_files) == 0:
            log.info(f"No files found for {request_string}. Station will be skipped.")
            continue

        filenames_and_files = download_dwd_data_parallel(remote_files)

        station_data = parse_dwd_data(filenames_and_files, parameter, time_resolution)

        if write_file:
            store_dwd_data(
                station_data,
                station_id,
                parameter,
                time_resolution,
                period_type,
                folder,
            )

        data.append(station_data)

    if run_download_only:
        return None

    try:
        data = pd.concat(data)
    except ValueError:
        return pd.DataFrame()

    if tidy_data:
        data = _tidy_up_data(data, parameter)

    # Assign meaningful column names (humanized).
    if humanize_column_names:
        hcnm = create_humanized_column_names_mapping(time_resolution, parameter)
        if tidy_data:
            data[DWDMetaColumns.ELEMENT.value] = data[
                DWDMetaColumns.ELEMENT.value
            ].apply(lambda x: hcnm[x])
        else:
            data = data.rename(columns=hcnm)

    return data


def _tidy_up_data(df: pd.DataFrame, parameter: Parameter) -> pd.DataFrame:
    """
    Function to create a tidy DataFrame by reshaping it, putting quality in a
    separate column and setting an extra column with the parameter.

    Args:
        df: DataFrame to be tidied
        parameter: the parameter that is written in a column to identify a set of
        different parameters amongst each other

    Returns:
        the tidied DataFrame
    """
    id_vars = []
    date_vars = []

    # Add id columns based on metadata columns
    for column in POSSIBLE_ID_VARS:
        if column in df:
            id_vars.append(column)
            if column in POSSIBLE_DATE_VARS:
                date_vars.append(column)

    # Extract quality
    # Set empty quality for first columns until first QN column
    quality = pd.Series()
    column_quality = pd.Series()

    for column in df:
        # If is quality column, overwrite current "column quality"
        if column.startswith("QN"):
            column_quality = df.pop(column)
        else:
            quality = quality.append(column_quality)

    df_tidy = df.melt(
        id_vars=id_vars,
        var_name=DWDMetaColumns.ELEMENT.value,
        value_name=DWDMetaColumns.VALUE.value,
    )

    df_tidy[DWDMetaColumns.PARAMETER.value] = parameter.name

    df_tidy[DWDMetaColumns.QUALITY.value] = quality.values

    # Reorder properly
    df_tidy = df_tidy.reindex(
        columns=[
            DWDMetaColumns.STATION_ID.value,
            DWDMetaColumns.PARAMETER.value,
            DWDMetaColumns.ELEMENT.value,
            *date_vars,
            DWDMetaColumns.VALUE.value,
            DWDMetaColumns.QUALITY.value,
        ]
    )

    return df_tidy
