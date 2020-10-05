""" Data collection pipeline """
import logging
from concurrent.futures.thread import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import List, Union, Optional, Tuple
from zipfile import ZipFile, BadZipFile

import pandas as pd
from requests.exceptions import InvalidURL

from wetterdienst.dwd.observations.fileindex import (
    create_file_list_for_climate_observations,
)
from wetterdienst.util.cache import payload_cache_five_minutes

from wetterdienst.dwd.util import (
    check_parameters,
    parse_enumeration_from_template,
    create_humanized_column_names_mapping,
    coerce_field_types,
)
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst import TimeResolution
from wetterdienst.dwd.metadata.constants import DWD_FOLDER_MAIN
from wetterdienst.exceptions import (
    InvalidParameterCombination,
    FailedDownload,
    ProductFileNotFound,
)
from wetterdienst.dwd.observations.parser import (
    parse_climate_observations_data,
)
from wetterdienst.dwd.network import download_file_from_dwd
from wetterdienst.dwd.observations.store import (
    store_climate_observations,
    restore_climate_observations,
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

PRODUCT_FILE_IDENTIFIER = "produkt"


def collect_climate_observations_data(
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
) -> Optional[pd.DataFrame]:
    """
    Function that organizes the complete pipeline of data collection, either
    from the internet or from a local file. It therefor goes through every given
    station id and, given by the parameters, either tries to get data from local
    store and/or if fails tries to get data from the internet. Finally if wanted
    it will try to store the data in a hdf file.

    :param station_ids:             station ids that are trying to be loaded
    :param parameter:               Parameter as enumeration
    :param time_resolution:         Time resolution as enumeration
    :param period_type:             Period type as enumeration
    :param folder:                  Folder for local file interaction
    :param prefer_local:            Local data should be preferred
    :param write_file:              Write data to local storage
    :param tidy_data:               Tidy up data so that there's only one set of values
                                    for a datetime in a row, e.g. station_id, parameter,
                                    element, datetime, value, quality.
    :param humanize_column_names:   Yield column names for human consumption
    :param run_download_only:       Run only the download and storing process

    :return:                        All the data given by the station ids.
    """
    parameter = parse_enumeration_from_template(parameter, Parameter)
    time_resolution = parse_enumeration_from_template(time_resolution, TimeResolution)
    period_type = parse_enumeration_from_template(period_type, PeriodType)

    if not check_parameters(parameter, time_resolution, period_type):
        raise InvalidParameterCombination(
            f"The combination of {parameter.value}, {time_resolution.value}, "
            f"{period_type.value} is invalid."
        )

    # List for collected pandas DataFrames per each station id
    data = []
    for station_id in set(station_ids):

        # Just for logging.
        request_string = _build_local_store_key(
            station_id, parameter, time_resolution, period_type
        )

        if prefer_local:
            # Try restoring data
            station_data = restore_climate_observations(
                station_id, parameter, time_resolution, period_type, folder
            )

            # When successful append data and continue with next iteration
            if not station_data.empty:
                log.info(f"Data for {request_string} restored from local.")

                data.append(station_data)

                continue

        log.info(f"Acquiring observations data for {request_string}")

        remote_files = create_file_list_for_climate_observations(
            [station_id], parameter, time_resolution, period_type
        )

        if len(remote_files) == 0:
            log.info(f"No files found for {request_string}. Station will be skipped.")
            continue

        filenames_and_files = download_climate_observations_data_parallel(remote_files)

        station_data = parse_climate_observations_data(
            filenames_and_files, parameter, time_resolution
        )

        if write_file:
            store_climate_observations(
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

    data = coerce_field_types(data, time_resolution)

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

    :param df:          DataFrame to be tidied
    :param parameter:   the parameter that is written in a column to identify a set of
                        different parameters amongst each other

    :return:            The tidied DataFrame
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
    quality = pd.Series(dtype=int)
    column_quality = pd.Series(dtype=int)

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


def download_climate_observations_data_parallel(
    remote_files: List[str],
) -> List[Tuple[str, BytesIO]]:
    """
    Wrapper for ``_download_dwd_data`` to provide a multiprocessing feature.

    :param remote_files:    List of requested files
    :return:                List of downloaded files
    """

    with ThreadPoolExecutor() as executor:
        files_in_bytes = executor.map(_download_climate_observations_data, remote_files)

    return list(zip(remote_files, files_in_bytes))


def _download_climate_observations_data(remote_file: Union[str, Path]) -> BytesIO:
    """
    This function downloads the station data for which the link is
    provided by the 'select_dwd' function. It checks the shortened filepath (just
    the zipfile) for its parameters, creates the full filepath and downloads the
    file(s) according to the set up folder.

    Args:
        remote_file: contains path to file that should be downloaded
            and the path to the folder to store the files

    Returns:
        stores data on local file system

    """
    return BytesIO(__download_climate_observations_data(remote_file=remote_file))


@payload_cache_five_minutes.cache_on_arguments()
def __download_climate_observations_data(remote_file: str) -> bytes:

    try:
        zip_file = download_file_from_dwd(remote_file)
    except InvalidURL as e:
        raise InvalidURL(
            f"Error: the station data {remote_file} couldn't be reached."
        ) from e
    except Exception:
        raise FailedDownload(f"Download failed for {remote_file}")

    try:
        zip_file_opened = ZipFile(zip_file)

        # Files of archive
        archive_files = zip_file_opened.namelist()

        for file in archive_files:
            # If found file load file in bytes, close zipfile and return bytes
            if file.startswith(PRODUCT_FILE_IDENTIFIER):
                file_in_bytes = zip_file_opened.open(file).read()

                zip_file_opened.close()

                return file_in_bytes

        # If whatsoever no file was found and returned already throw exception
        raise ProductFileNotFound(
            f"The archive of {remote_file} does not hold a 'produkt' file."
        )

    except BadZipFile as e:
        raise BadZipFile(f"The archive of {remote_file} seems to be corrupted.") from e
