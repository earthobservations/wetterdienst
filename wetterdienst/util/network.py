# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import logging
from collections.abc import Iterator, MutableMapping
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import stamina
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.http import HTTPFileSystem as _HTTPFileSystem

from wetterdienst.metadata.cache import CacheExpiry

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


class FileDirCache(MutableMapping):
    def __init__(
        self,
        use_listings_cache: bool,
        listings_expiry_time: int | float,
        listings_cache_location: str | None = None,
    ) -> None:
        """

        Parameters
        ----------
        use_listings_cache: bool
            If False, this cache never returns items, but always reports KeyError,
            and setting items has no effect
        listings_expiry_time: int or float
            Time in seconds that a listing is considered valid. If None,
            listings do not expire.
        listings_cache_location: str (optional)
            Directory path at which the listings cache file is stored. If None,
            an autogenerated path at the user folder is created.

        """
        import platformdirs
        from diskcache import Cache

        listings_expiry_time = listings_expiry_time and float(listings_expiry_time)

        if listings_cache_location:
            listings_cache_location = Path(listings_cache_location) / str(listings_expiry_time)
            listings_cache_location.mkdir(exist_ok=True, parents=True)
        else:
            listings_cache_location = Path(platformdirs.user_cache_dir(appname="wetterdienst-fsspec")) / str(
                listings_expiry_time
            )

        try:
            log.info(f"Creating dircache folder at {listings_cache_location}")
            listings_cache_location.mkdir(exist_ok=True, parents=True)
        except OSError:
            log.error(f"Failed creating dircache folder at {listings_cache_location}")

        self.cache_location = listings_cache_location

        self._cache = Cache(directory=listings_cache_location)
        self.use_listings_cache = use_listings_cache
        self.listings_expiry_time = listings_expiry_time

    def __getitem__(self, item: str) -> BytesIO:
        """Draw item as fileobject from cache, retry if timeout occurs"""
        return self._cache.get(key=item, read=True, retry=True)

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(list(self._cache.iterkeys()))

    def __contains__(self, item: str) -> bool:
        value = self._cache.get(item, retry=True)  # None, if expired
        if value:
            return True
        return False

    def __setitem__(self, key: str, value: BytesIO) -> None:
        if not self.use_listings_cache:
            return
        self._cache.set(key=key, value=value, expire=self.listings_expiry_time, retry=True)

    def __delitem__(self, key: str) -> None:
        del self._cache[key]

    def __iter__(self) -> Iterator[str]:
        return (k for k in self._cache.iterkeys() if k in self)

    def __reduce__(self) -> tuple:
        return (
            FileDirCache,
            (self.use_listings_cache, self.listings_expiry_time, self.cache_location),
        )


class HTTPFileSystem(_HTTPFileSystem):
    def __init__(
        self,
        use_listings_cache: bool | None = None,
        listings_expiry_time: int | float | None = None,
        listings_cache_location: str | None = None,
        *args: tuple,
        **kwargs: dict,
    ) -> None:
        kwargs.update(
            {
                "use_listings_cache": use_listings_cache,
                "listings_expiry_time": listings_expiry_time,
            }
        )
        super().__init__(*args, **kwargs)
        # Overwrite the dircache with our own file-based cache
        # we have to use kwargs here, because the parent class
        # requires them to actually activate the cache
        self.dircache = FileDirCache(
            use_listings_cache=use_listings_cache,
            listings_expiry_time=listings_expiry_time,
            listings_cache_location=listings_cache_location,
        )


class NetworkFilesystemManager:
    """
    Manage multiple FSSPEC instances keyed by cache expiration time.
    """

    filesystems: dict[str, AbstractFileSystem] = {}

    @staticmethod
    def resolve_ttl(ttl: int | CacheExpiry) -> tuple[str, int]:
        ttl_name = ttl
        ttl_value = ttl

        if isinstance(ttl, CacheExpiry):
            ttl_name = ttl.name
            ttl_value = ttl.value

        return ttl_name, ttl_value

    @classmethod
    def register(cls, settings: Settings, ttl: int | CacheExpiry = CacheExpiry.NO_CACHE) -> None:
        ttl_name, ttl_value = cls.resolve_ttl(ttl)
        key = f"ttl-{ttl_name}"
        real_cache_dir = str(Path(settings.cache_dir) / "fsspec" / key)

        use_cache = not (settings.cache_disable or ttl is CacheExpiry.NO_CACHE)
        fs = HTTPFileSystem(use_listings_cache=use_cache, client_kwargs=settings.fsspec_client_kwargs)

        if settings.cache_disable or ttl is CacheExpiry.NO_CACHE:
            filesystem_effective = fs
        else:
            filesystem_effective = WholeFileCacheFileSystem(fs=fs, cache_storage=real_cache_dir, expiry_time=ttl_value)
        cls.filesystems[key] = filesystem_effective

    @classmethod
    def get(cls, settings: Settings, ttl: int | CacheExpiry = CacheExpiry.NO_CACHE) -> AbstractFileSystem:
        ttl_name, _ = cls.resolve_ttl(ttl)
        key = f"ttl-{ttl_name}"
        if key not in cls.filesystems:
            cls.register(settings=settings, ttl=ttl)
        return cls.filesystems[key]


@stamina.retry(on=Exception, attempts=3)
def list_remote_files_fsspec(url: str, settings: Settings, ttl: CacheExpiry = CacheExpiry.FILEINDEX) -> list[str]:
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
        listings_cache_location=settings.cache_dir,
        client_kwargs=settings.fsspec_client_kwargs,
    )
    return fs.find(url)


@stamina.retry(on=Exception, attempts=3)
def download_file(
    url: str,
    settings: Settings,
    ttl: int | CacheExpiry = CacheExpiry.NO_CACHE,
) -> BytesIO:
    """
    A function used to download a specified file from the server.

    :param url:     The url to the file on the dwd server
    :param settings: The settings object.
    :param ttl:     How long the resource should be cached.

    :returns:        Bytes of the file.
    """
    filesystem = NetworkFilesystemManager.get(settings=settings, ttl=ttl)
    payload = filesystem.cat(url)
    return BytesIO(payload)
