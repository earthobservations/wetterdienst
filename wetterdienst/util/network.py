# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Union

import stamina
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

    # TODO: Apply dependency injection for `wetterdienst_settings` here.
    @classmethod
    def register(cls, settings, ttl: Union[int, CacheExpiry] = CacheExpiry.NO_CACHE):
        ttl_name, ttl_value = cls.resolve_ttl(ttl)
        key = f"ttl-{ttl_name}"
        real_cache_dir = os.path.join(settings.cache_dir, "fsspec", key)

        use_cache = not (settings.cache_disable or ttl is CacheExpiry.NO_CACHE)
        fs = HTTPFileSystem(use_listings_cache=use_cache, client_kwargs=settings.fsspec_client_kwargs)

        if settings.cache_disable or ttl is CacheExpiry.NO_CACHE:
            filesystem_effective = fs
        else:
            filesystem_effective = WholeFileCacheFileSystem(fs=fs, cache_storage=real_cache_dir, expiry_time=ttl_value)
        cls.filesystems[key] = filesystem_effective

    @classmethod
    def get(cls, settings, ttl: Optional[Union[int, CacheExpiry]] = CacheExpiry.NO_CACHE) -> AbstractFileSystem:
        ttl_name, _ = cls.resolve_ttl(ttl)
        key = f"ttl-{ttl_name}"
        if key not in cls.filesystems:
            cls.register(settings=settings, ttl=ttl)
        return cls.filesystems[key]


@stamina.retry(on=Exception, attempts=3)
def list_remote_files_fsspec(url: str, settings: Settings, ttl: CacheExpiry = CacheExpiry.FILEINDEX) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server.

    The default ttl with ``CacheExpiry.FILEINDEX`` is "5 minutes".

    :param url:         The URL which should be searched for files.
    :param ttl:         The cache expiration time.
    :returns:  A list of strings representing the files from the path.
    """
    use_cache = not (settings.cache_disable or ttl is CacheExpiry.NO_CACHE)
    fs = HTTPFileSystem(
        use_listings_cache=use_cache,
        listings_expiry_time=not settings.cache_disable and ttl.value,
        listings_cache_type="filedircache",
        listings_cache_location=settings.cache_dir,
        client_kwargs=settings.fsspec_client_kwargs,
    )

    return fs.find(url)


@stamina.retry(on=Exception, attempts=3)
def download_file(
    url: str, settings: Settings, ttl: Optional[Union[int, CacheExpiry]] = CacheExpiry.NO_CACHE
) -> BytesIO:
    """
    A function used to download a specified file from the server.

    :param url:     The url to the file on the dwd server
    :param ttl:     How long the resource should be cached.

    :returns:        Bytes of the file.
    """
    filesystem = NetworkFilesystemManager.get(settings=settings, ttl=ttl)
    payload = filesystem.cat(url)
    return BytesIO(payload)
