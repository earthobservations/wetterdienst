# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Download climate observations data from DWD server."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import BadZipFile

from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.exceptions import ProductFileNotFoundError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    import polars as pl

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


def download_climate_observations_data(
    remote_files: pl.Series,
    settings: Settings,
) -> list[tuple[str, BytesIO]]:
    """Download climate observations data from DWD server."""
    if len(remote_files) > 1:
        with ThreadPoolExecutor() as p:
            files_in_bytes = p.map(
                lambda file: _download_climate_observations_data(remote_file=file, settings=settings),
                remote_files,
            )
    else:
        files_in_bytes = [_download_climate_observations_data(remote_file=remote_files[0], settings=settings)]
    return list(zip(remote_files, files_in_bytes, strict=False))


def _download_climate_observations_data(remote_file: str, settings: Settings) -> BytesIO:
    return BytesIO(__download_climate_observations_data(remote_file=remote_file, settings=settings))


def __download_climate_observations_data(remote_file: str, settings: Settings) -> bytes:
    file = download_file(
        url=remote_file,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.FIVE_MINUTES,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
    )
    try:
        zfs = ZipFileSystem(file)
    except BadZipFile as e:
        msg = f"The archive of {remote_file} seems to be corrupted."
        raise BadZipFile(msg) from e
    product_file = zfs.glob("produkt*")
    if len(product_file) != 1:
        msg = f"The archive of {remote_file} does not hold a 'produkt' file."
        raise ProductFileNotFoundError(msg)
    return zfs.open(product_file[0]).read()
