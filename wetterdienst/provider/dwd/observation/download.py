# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import List, Tuple
from zipfile import BadZipFile

from fsspec.implementations.zip import ZipFileSystem
from requests.exceptions import InvalidURL

from wetterdienst.exceptions import (
    FailedDownload,
    MultipleProductFilesFound,
    ProductFileNotFound,
)
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file

PRODUCT_FILE_IDENTIFIER = "produkt"


def download_climate_observations_data_parallel(
    remote_files: List[str],
) -> List[Tuple[str, BytesIO]]:
    """
    Wrapper for ``_download_dwd_data`` to provide a multiprocessing feature.

    :param remote_files:    List of requested files
    :return:                List of downloaded files
    """
    with ThreadPoolExecutor() as p:
        files_in_bytes = p.map(_download_climate_observations_data, remote_files)

    return list(zip(remote_files, files_in_bytes))


def _download_climate_observations_data(remote_file: str) -> BytesIO:
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


def __download_climate_observations_data(remote_file: str) -> bytes:

    try:
        file = download_file(remote_file, ttl=CacheExpiry.FIVE_MINUTES)
    except InvalidURL as e:
        raise InvalidURL(
            f"Error: the station data {remote_file} could not be reached."
        ) from e
    except Exception:
        raise FailedDownload(f"Download failed for {remote_file}")

    try:
        zf = ZipFileSystem(file)

        # Find product files in archive.
        product_files = zf.glob(PRODUCT_FILE_IDENTIFIER + "*")

        # Raise exceptions if no corresponding file was found or if there are multiple product files.
        if not product_files:
            raise ProductFileNotFound(
                f"The archive {remote_file} does not contain a '{PRODUCT_FILE_IDENTIFIER}*' file."
            )
        elif len(product_files) > 1:
            raise MultipleProductFilesFound(
                f"The archive {remote_file} contains multiple product files, which is ambiguous."
            )

        file_in_bytes = zf.open(product_files[0]).read()
        return file_in_bytes

    except BadZipFile as e:
        raise BadZipFile(f"The archive of {remote_file} seems to be corrupted.") from e
