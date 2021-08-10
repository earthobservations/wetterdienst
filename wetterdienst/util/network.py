# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from io import BytesIO
from typing import List, Optional, Union
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.http import HTTPFileSystem

from wetterdienst.util.cache import WD_CACHE_DISABLE, CacheExpiry, cache_dir

# v1: Global HTTP session object for custom implementation based on "requests".
session = requests.Session()


# v2: Remote filesystem access through FSSPEC.
class NetworkFilesystemManager:
    """
    Manage multiple FSSPEC instances keyed by cache expiration time.
    """

    filesystems = {}

    @staticmethod
    def resolve_ttl(ttl: Union[int, CacheExpiry]):

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
        real_cache_dir = os.path.join(cache_dir, "fsspec", key)
        filesystem_real = HTTPFileSystem(use_listings_cache=True)
        if WD_CACHE_DISABLE or ttl is CacheExpiry.NO_CACHE:
            filesystem_effective = filesystem_real
        else:
            filesystem_effective = WholeFileCacheFileSystem(
                fs=filesystem_real,
                cache_storage=real_cache_dir,
                expiry_time=ttl_value,
            )
        cls.filesystems[key] = filesystem_effective

    @classmethod
    def get(cls, ttl=CacheExpiry.NO_CACHE):
        ttl_name, ttl_value = cls.resolve_ttl(ttl)
        key = f"ttl-{ttl_name}"
        if key not in cls.filesystems:
            cls.register(ttl=ttl)
        return cls.filesystems[key]


# v1: Custom "remote directory index" implementation.
def list_remote_files_legacy(url: str, recursive: bool) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server

    Args:
        url: the url which should be searched for files
        recursive: definition if the function should iteratively list files
        from sub folders

    Returns:
        a list of strings representing the files from the path
    """

    if not url.endswith("/"):
        url += "/"

    r = session.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    files_and_folders = [
        link.get("href") for link in soup.find_all("a") if link.get("href") != "../"
    ]

    files = []
    folders = []

    for f in files_and_folders:
        if not f.endswith("/"):
            files.append(urljoin(url, f))
        else:
            folders.append(urljoin(url, f))

    if recursive:
        files_in_folders = [
            list_remote_files_legacy(folder, recursive) for folder in folders
        ]

        for files_in_folder in files_in_folders:
            files.extend(files_in_folder)

    return files


# v2: "Remote directory index" implementation based on FSSPEC.
def list_remote_files_fsspec(
    url: str, recursive: bool = False, ttl: CacheExpiry = CacheExpiry.FILEINDEX
) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server.

    The default ttl with ``CacheExpiry.FILEINDEX`` is "5 minutes".

    Args:
        :param url:         The URL which should be searched for files.
        :param recursive:   Definition if the function should iteratively list files
                            from sub folders.
        :param ttl:         The cache expiration time.

    Returns:
        A list of strings representing the files from the path.
    """

    # Acquire filesystem instance.
    filesystem = NetworkFilesystemManager.get(ttl=ttl)

    # Recursively list remote directory.
    if not recursive:
        remote_urls = filesystem.find(url)
    else:
        remote_urls = filesystem.expand_path(url, recursive=recursive)

    # Only list files, so remove all directories.
    try:
        remote_urls.remove(url)
    except ValueError:
        pass
    remote_urls = [i for i in remote_urls if not i.endswith("/")]

    return remote_urls


def download_file(url: str, ttl: Optional[int] = CacheExpiry.NO_CACHE) -> BytesIO:
    """
    A function used to download a specified file from the server.

    :param url:     The url to the file on the dwd server
    :param ttl:     How long the resource should be cached.

    :return:        Bytes of the file.
    """
    filesystem = NetworkFilesystemManager.get(ttl=ttl)
    payload = filesystem.cat(url)
    return BytesIO(payload)
