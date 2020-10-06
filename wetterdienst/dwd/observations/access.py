""" Data collection pipeline """
import logging
from concurrent.futures.thread import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import List, Union, Tuple
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
    coerce_field_types,
    build_parameter_identifier,
)
from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst import TimeResolution
from wetterdienst.exceptions import (
    InvalidParameterCombination,
    FailedDownload,
    ProductFileNotFound,
)
from wetterdienst.dwd.observations.parser import (
    parse_climate_observations_data,
)
from wetterdienst.dwd.network import download_file_from_dwd

log = logging.getLogger(__name__)

PRODUCT_FILE_IDENTIFIER = "produkt"


def collect_climate_observations_data(
    station_id: int,
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
) -> pd.DataFrame:
    """
    Function that organizes the complete pipeline of data collection, either
    from the internet or from a local file. It therefore goes through every given
    station id and, given by the parameters, either tries to get data from local
    store and/or if fails tries to get data from the internet. Finally if wanted
    it will try to store the data in a hdf file.

    :param station_id:              station id that is being loaded
    :param parameter:               Parameter as enumeration
    :param time_resolution:         Time resolution as enumeration
    :param period_type:             Period type as enumeration

    :return:                        All the data given by the station ids.
    """
    parameter = parse_enumeration_from_template(parameter, Parameter)
    time_resolution = parse_enumeration_from_template(time_resolution, TimeResolution)
    period_type = parse_enumeration_from_template(period_type, PeriodType)

    if not check_parameters(parameter, time_resolution, period_type):
        raise InvalidParameterCombination(
            f"Invalid combination: {parameter.value} / {time_resolution.value} / "
            f"{period_type.value}"
        )

    remote_files = create_file_list_for_climate_observations(
        station_id, parameter, time_resolution, period_type
    )

    if len(remote_files) == 0:
        parameter_identifier = build_parameter_identifier(
            parameter, time_resolution, period_type, station_id
        )
        log.info(f"No files found for {parameter_identifier}. Station will be skipped.")
        return pd.DataFrame()

    filenames_and_files = download_climate_observations_data_parallel(remote_files)

    obs_df = parse_climate_observations_data(
        filenames_and_files, parameter, time_resolution
    )

    obs_df = coerce_field_types(obs_df, time_resolution)

    return obs_df


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
            f"Error: the station data {remote_file} could not be reached."
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
