# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Union

from fsspec import AbstractFileSystem
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.http import HTTPFileSystem

from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry


class NetworkFilesystemManager:
    """
    Manage multiple FSSPEC instances keyed by cache expiration time.
    """

    filesystems: Dict[str, AbstractFileSystem] = {}

    @staticmethod
    def resolve_ttl(ttl: Union[int, CacheExpiry]) -> Tuple[str, int]:

        ttl_name = ttl
        ttl_value = ttl

        if isinstance(ttl, CacheExpiry):
            ttl_name = ttl.name
            ttl_value = ttl.value

        return ttl_name, ttl_value

    @classmethod
    def register(cls, ttl=CacheExpiry.NO_CACHE):
        ttl_name, ttl_value = cls.resolve_ttl(ttl)
        key = f"ttl-{ttl_name}"
        real_cache_dir = os.path.join(Settings.cache_dir, "fsspec", key)
        filesystem_real = HTTPFileSystem(use_listings_cache=True, client_kwargs=Settings.fsspec_client_kwargs)
        if Settings.cache_disable or ttl is CacheExpiry.NO_CACHE:
            filesystem_effective = filesystem_real
        else:
            filesystem_effective = WholeFileCacheFileSystem(
                fs=filesystem_real, cache_storage=real_cache_dir, expiry_time=ttl_value
            )
        cls.filesystems[key] = filesystem_effective

    @classmethod
    def get(cls, ttl=CacheExpiry.NO_CACHE) -> AbstractFileSystem:
        ttl_name, _ = cls.resolve_ttl(ttl)
        key = f"ttl-{ttl_name}"
        if key not in cls.filesystems:
            cls.register(ttl=ttl)
        return cls.filesystems[key]


def list_remote_files_fsspec(url: str, ttl: CacheExpiry = CacheExpiry.FILEINDEX) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server.

    The default ttl with ``CacheExpiry.FILEINDEX`` is "5 minutes".

    :param url:         The URL which should be searched for files.
    :param ttl:         The cache expiration time.
    :returns:  A list of strings representing the files from the path.
    """
    fs = HTTPFileSystem(
        use_listings_cache=True,
        listings_expiry_time=not Settings.cache_disable and ttl.value,
        listings_cache_type="filedircache",
        listings_cache_location=Settings.cache_dir,
        client_kwargs=Settings.fsspec_client_kwargs,
    )

    return fs.find(url)


def download_file(url: str, ttl: Optional[int] = CacheExpiry.NO_CACHE) -> BytesIO:
    """
    A function used to download a specified file from the server.

    :param url:     The url to the file on the dwd server
    :param ttl:     How long the resource should be cached.

    :returns:        Bytes of the file.
    """
    filesystem = NetworkFilesystemManager.get(ttl=ttl)
    payload = filesystem.cat(url)
    return BytesIO(payload)
