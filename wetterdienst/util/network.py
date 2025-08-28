# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Network utilities for the wetterdienst package."""

from __future__ import annotations

import logging
from collections.abc import Generator, MutableMapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal
from urllib.parse import urlparse

import stamina
from aiohttp import ClientResponse, ClientResponseError
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.http import HTTPFileSystem as _HTTPFileSystem

from wetterdienst.metadata.cache import CacheExpiry

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


@dataclass
class File:
    """File object for the network utilities."""

    url: str
    """The URL of the file."""

    @property
    def filename(self) -> str:
        """The filename of the file."""
        return Path(urlparse(self.url).path).name

    """The filename of the file, if available."""
    content: BytesIO | Exception
    """The content of the file as a BytesIO object."""
    status: int
    """The status code of the file download, if available."""

    def raise_if_exception(self) -> None:
        """Raise an exception if the content is not a BytesIO object."""
        if isinstance(self.content, Exception):
            raise self.content


class FileDirCache(MutableMapping):
    """File-based cache for FSSPEC."""

    def __init__(
        self,
        listings_expiry_time: float,
        *,
        use_listings_cache: bool,
        listings_cache_location: Path | None = None,
    ) -> None:
        """Initialize the FileDirCache.

        Args:
            listings_expiry_time: Time in seconds that a listing is considered valid.
            use_listings_cache: If False, this cache never returns items, but always reports KeyError.
            listings_cache_location: Directory path at which the listings cache file is stored.

        """
        import platformdirs  # noqa: PLC0415
        from diskcache import Cache  # noqa: PLC0415

        listings_expiry_time = listings_expiry_time and float(listings_expiry_time)

        if listings_cache_location:
            cache_location = Path(listings_cache_location) / str(listings_expiry_time)
            cache_location.mkdir(exist_ok=True, parents=True)
        else:
            cache_location = Path(platformdirs.user_cache_dir(appname="wetterdienst-fsspec")) / str(
                listings_expiry_time,
            )

        try:
            log.info(f"Creating dircache folder at {cache_location}")
            cache_location.mkdir(exist_ok=True, parents=True)
        except OSError:
            log.exception(f"Failed creating dircache folder at {cache_location}")

        self.cache_location = cache_location

        self._cache = Cache(directory=str(cache_location))
        self.use_listings_cache = use_listings_cache
        self.listings_expiry_time = listings_expiry_time

    def __getitem__(self, item: str) -> BytesIO:
        """Draw item as fileobject from cache, retry if timeout occurs."""
        return self._cache.get(key=item, read=True, retry=True)

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return number of items in cache."""
        return len(list(self._cache.iterkeys()))

    def __contains__(self, item: object) -> bool:
        """Check if item is in cache and not expired."""
        value = self._cache.get(item, retry=True)  # None, if expired
        return bool(value)

    def __setitem__(self, key: str, value: BytesIO) -> None:
        """Store fileobject in cache."""
        if not self.use_listings_cache:
            return
        self._cache.set(key=key, value=value, expire=self.listings_expiry_time, retry=True)

    def __delitem__(self, key: str) -> None:
        """Remove item from cache."""
        del self._cache[key]

    def __iter__(self) -> Generator[bytes]:
        """Iterate over keys in cache."""
        return (k for k in self._cache.iterkeys() if k in self)

    def __reduce__(self) -> tuple:
        """Return state information for pickling."""
        return (
            FileDirCache,
            (self.use_listings_cache, self.listings_expiry_time, self.cache_location),
        )


class HTTPFileSystem(_HTTPFileSystem):
    """HTTPFileSystem with cache support."""

    def __init__(
        self,
        /,
        *,
        use_listings_cache: bool,
        listings_expiry_time: float,
        listings_cache_location: Path | None = None,
        **kwargs,  # noqa: ANN003
    ) -> None:
        """Initialize the HTTPFileSystem.

        Args:
            use_listings_cache: If False, this cache never returns items, but always reports KeyError,
            listings_expiry_time: Time in seconds that a listing is considered valid. If None,
            listings_cache_location: Directory path at which the listings cache file is stored. If None,
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.

        """
        kwargs.update(
            {
                "use_listings_cache": use_listings_cache,
                "listings_expiry_time": listings_expiry_time,
            },
        )
        super().__init__(**kwargs)
        # Overwrite the dircache with our own file-based cache
        # we have to use kwargs here, because the parent class
        # requires them to actually activate the cache
        self.dircache = FileDirCache(
            use_listings_cache=use_listings_cache,
            listings_expiry_time=listings_expiry_time,
            listings_cache_location=listings_cache_location,
        )


class NetworkFilesystemManager:
    """Manage multiple FSSPEC instances keyed by cache expiration time."""

    filesystems: ClassVar[dict[str, HTTPFileSystem | WholeFileCacheFileSystem]] = {}

    @staticmethod
    def resolve_ttl(cache_expiry: CacheExpiry) -> tuple[str, float | int | Literal[False]]:
        """Resolve the cache expiration time.

        Args:
            cache_expiry: The cache expiration time.

        Returns:
            The cache expiration time as name and value.

        """
        return cache_expiry.name, cache_expiry.value

    @classmethod
    def register(
        cls,
        cache_dir: Path,
        cache_expiry: CacheExpiry = CacheExpiry.NO_CACHE,
        client_kwargs: dict | None = None,
        *,
        cache_disable: bool,
    ) -> None:
        """Register a new filesystem instance for a given cache expiration time.

        Args:
            cache_dir: The cache directory to use for the filesystem.
            cache_expiry: The cache expiration time.
            client_kwargs: Additional keyword arguments for the client.
            cache_disable: If True, the cache is disabled.

        Returns:
            None

        """
        ttl_name, ttl_value = cls.resolve_ttl(cache_expiry)
        key = f"ttl-{ttl_name}"
        fs = HTTPFileSystem(
            use_listings_cache=False,
            client_kwargs=client_kwargs,
            listings_expiry_time=0.0,  # not relevant for the download of files
        )

        if cache_disable or cache_expiry == CacheExpiry.NO_CACHE:
            filesystem_effective = fs
        else:
            real_cache_dir = Path(cache_dir) / "fsspec" / key
            filesystem_effective = WholeFileCacheFileSystem(
                fs=fs,
                cache_storage=str(real_cache_dir),
                expiry_time=int(ttl_value),
            )
        cls.filesystems[key] = filesystem_effective

    @classmethod
    def get(
        cls,
        cache_dir: Path,
        cache_expiry: CacheExpiry = CacheExpiry.NO_CACHE,
        client_kwargs: dict | None = None,
        *,
        cache_disable: bool,
    ) -> HTTPFileSystem | WholeFileCacheFileSystem:
        """Get a filesystem instance for a given cache expiration time.

        Args:
            cache_dir: The cache directory to use for the filesystem.
            cache_expiry: The cache expiration time.
            client_kwargs: Additional keyword arguments for the client.
            cache_disable: If True, the cache is disabled

        Returns:
            The filesystem instance.

        """
        ttl_name, _ = cls.resolve_ttl(cache_expiry)
        key = f"ttl-{ttl_name}"
        if key not in cls.filesystems:
            cls.register(
                cache_dir=cache_dir,
                cache_expiry=cache_expiry,
                client_kwargs=client_kwargs,
                cache_disable=cache_disable,
            )
        return cls.filesystems[key]


@stamina.retry(on=Exception, attempts=3)
def list_remote_files_fsspec(
    url: str, settings: Settings, cache_expiry: CacheExpiry = CacheExpiry.FILEINDEX
) -> list[str]:
    """Create a listing of all files of a given path on the server.

    The default ttl with ``CacheExpiry.FILEINDEX`` is "5 minutes".

    Args:
        url: The URL to list files from.
        settings: The settings to use for the listing.
        cache_expiry: The cache expiration time.

    Returns:
        A list of all files on the server

    """
    use_cache = not (settings.cache_disable or cache_expiry is CacheExpiry.NO_CACHE)
    fs = HTTPFileSystem(
        use_listings_cache=use_cache,
        listings_expiry_time=not settings.cache_disable and cache_expiry.value,
        listings_cache_location=settings.cache_dir,
        client_kwargs=settings.fsspec_client_kwargs,
    )
    return fs.find(url)


@stamina.retry(
    on=lambda response: isinstance(response, ClientResponse)
    and (response.status == 429 or 500 <= response.status < 600),
    attempts=2,
)
def download_file(
    url: str,
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
) -> File:
    """Download a specified file from the server.

    Args:
        url: The URL of the file to download.
        cache_dir: The cache directory to use for the filesystem.
        ttl: The cache expiration time.
        client_kwargs: Additional keyword arguments for the client.
        cache_disable: If True, the cache is disabled.

    Returns:
        A BytesIO object containing the downloaded file.

    """
    filesystem = NetworkFilesystemManager.get(
        cache_dir=cache_dir,
        cache_expiry=ttl,
        client_kwargs=client_kwargs,
        cache_disable=cache_disable,
    )
    log.info(f"Downloading file {url}")
    try:
        payload = filesystem.cat_file(url)
        log.info(f"Downloaded file {url}")
        return File(
            url=url,
            content=BytesIO(payload),
            status=200,
        )
    except (ClientResponseError, FileNotFoundError) as e:
        # retrieve the status code from the exception if available
        status = e.status if isinstance(e, ClientResponseError) else 404
        log.info(f"Failed to download file {url} with status {status}.")
        return File(
            url=url,
            content=e,
            status=status,
        )


def download_files(
    urls: list[str],
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
) -> list[File]:
    """Download multiple files from the server concurrently."""
    log.info(f"Downloading {len(urls)} files.")
    with ThreadPoolExecutor() as p:
        return list(
            p.map(
                lambda file: download_file(
                    url=file,
                    cache_dir=cache_dir,
                    ttl=ttl,
                    client_kwargs=client_kwargs,
                    cache_disable=cache_disable,
                ),
                urls,
            ),
        )
