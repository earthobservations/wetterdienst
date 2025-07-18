# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Download climate observations data from DWD server."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import BadZipFile

from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.exceptions import ProductFileNotFoundError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import File, download_files

if TYPE_CHECKING:
    import polars as pl

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


def download_climate_observations_data(
    remote_files: pl.Series,
    settings: Settings,
) -> list[File]:
    """Download climate observations data from DWD server."""
    files = download_files(
        urls=remote_files.to_list(),
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.FIVE_MINUTES,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
    )
    # filter out exceptions
    files = [file for file in files if isinstance(file.content, BytesIO)]
    # unpack the files
    return [_unpack_climate_observations_data(file) for file in files]


def _unpack_climate_observations_data(file: File) -> File:
    try:
        zfs = ZipFileSystem(file.content)
    except BadZipFile as e:
        msg = f"The archive of {file.filename} seems to be corrupted."
        raise BadZipFile(msg) from e
    product_file = zfs.glob("produkt*")
    if len(product_file) != 1:
        msg = f"The archive of {file.filename} does not hold a 'produkt' file."
        raise ProductFileNotFoundError(msg)
    product_bytes = zfs.open(product_file[0]).read()
    # let's put this again in another file object
    return File(
        url=file.url,
        content=BytesIO(product_bytes),
        status=file.status,
    )
