# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO
from typing import List, Tuple
from zipfile import BadZipFile

import polars as pl
from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.exceptions import ProductFileNotFoundError
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file


def download_climate_observations_data_parallel(
    remote_files: pl.Series, settings: Settings
) -> List[Tuple[str, BytesIO]]:
    """
    Wrapper for ``_download_dwd_data`` to provide a multiprocessing feature.

    :param remote_files:    List of requested files
    :return:                List of downloaded files
    """
    with ThreadPoolExecutor() as p:
        files_in_bytes = p.map(partial(_download_climate_observations_data, settings=settings), remote_files)

    return list(zip(remote_files, files_in_bytes))


def _download_climate_observations_data(remote_file: str, settings: Settings) -> BytesIO:
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
    return BytesIO(__download_climate_observations_data(remote_file=remote_file, settings=settings))


def __download_climate_observations_data(remote_file: str, settings: Settings) -> bytes:
    file = download_file(remote_file, settings=settings, ttl=CacheExpiry.FIVE_MINUTES)

    try:
        zfs = ZipFileSystem(file)
    except BadZipFile as e:
        raise BadZipFile(f"The archive of {remote_file} seems to be corrupted.") from e

    product_file = zfs.glob("produkt*")

    if len(product_file) != 1:
        raise ProductFileNotFoundError(f"The archive of {remote_file} does not hold a 'produkt' file.")

    return zfs.open(product_file[0]).read()
