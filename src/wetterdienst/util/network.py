# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Network utilities for the wetterdienst package."""

from __future__ import annotations

import hashlib
import json
import logging
import ssl
import threading
from collections.abc import Iterator, MutableMapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal
from urllib.parse import urlparse

import stamina
from aiohttp import ClientConnectorError, ClientPayloadError, ClientResponseError
from fsspec.exceptions import FSTimeoutError
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.http import HTTPFileSystem as _HTTPFileSystem

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry

HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


def _create_ssl_context(*, use_certifi: bool) -> ssl.SSLContext | None:
    """Create an SSL context optionally using certifi certificates.

    Args:
        use_certifi: If True, use certifi certificate bundle instead of system certificates.

    Returns:
        An SSL context configured with certifi certificates if requested, None otherwise.

    """
    if not use_certifi:
        return None

    import certifi  # noqa: PLC0415

    return ssl.create_default_context(cafile=certifi.where())


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
        """Raise an exception if the content is not a BytesIO object.

        For NoInternetError, logs at debug level and returns silently instead of raising,
        allowing callers to return empty frames rather than propagating the error.
        """
        if isinstance(self.content, NoInternetError):
            log.debug(f"No internet connection available for {self.url}, returning empty result.")
            return
        if isinstance(self.content, Exception):
            raise self.content

    @property
    def is_no_internet_error(self) -> bool:
        """Check if the content is a NoInternetError."""
        return isinstance(self.content, NoInternetError)

    @property
    def nbytes(self) -> int:
        """Return the number of bytes in the file content."""
        if isinstance(self.content, BytesIO):
            return self.content.getbuffer().nbytes
        return 0

    @property
    def is_empty(self) -> bool:
        """Check if the file content is empty."""
        return self.nbytes == 0


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
        if not self.use_listings_cache:
            raise KeyError(item)
        _missing = object()
        value = self._cache.get(key=item, default=_missing, read=True, retry=True)
        if value is _missing:
            raise KeyError(item)
        return value

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return number of items in cache."""
        return len(self._cache)

    def __contains__(self, item: object) -> bool:
        """Check if item is in cache and not expired."""
        if not self.use_listings_cache:
            return False
        return item in self._cache

    def __setitem__(self, key: str, value: BytesIO) -> None:
        """Store fileobject in cache."""
        if not self.use_listings_cache:
            return
        self._cache.set(key=key, value=value, expire=self.listings_expiry_time, retry=True)

    def __delitem__(self, key: str) -> None:
        """Remove item from cache."""
        del self._cache[key]

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys in cache."""
        if not self.use_listings_cache:
            return iter([])
        return iter(self._cache)

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
        use_certifi: bool = False,
        **kwargs,  # noqa: ANN003
    ) -> None:
        """Initialize the HTTPFileSystem.

        Args:
            use_listings_cache: If False, this cache never returns items, but always reports KeyError,
            listings_expiry_time: Time in seconds that a listing is considered valid. If None,
            listings_cache_location: Directory path at which the listings cache file is stored. If None,
            use_certifi: If True, use certifi certificate bundle instead of system certificates.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.

        """
        # Store use_certifi for later use
        self._use_certifi = use_certifi

        # Create a custom get_client function that will create a session with our SSL context
        if use_certifi:

            async def get_client_with_certifi(**client_kwargs):  # noqa: ANN202, ANN003
                """Create an aiohttp ClientSession with certifi SSL context."""
                import aiohttp  # noqa: PLC0415

                ssl_context = _create_ssl_context(use_certifi=True)
                if ssl_context is None:
                    msg = "Failed to create SSL context with certifi"
                    raise RuntimeError(msg)
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                return aiohttp.ClientSession(connector=connector, **client_kwargs)

            kwargs["get_client"] = get_client_with_certifi

        # aiohttp >= 3.9 rejects bare int timeouts; wrap in ClientTimeout
        if "client_kwargs" in kwargs and isinstance(kwargs["client_kwargs"].get("timeout"), int):
            import aiohttp  # noqa: PLC0415

            client_kw = dict(kwargs["client_kwargs"])
            client_kw["timeout"] = aiohttp.ClientTimeout(total=client_kw["timeout"])
            kwargs["client_kwargs"] = client_kw

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
    """Manage multiple FSSPEC instances keyed by cache expiration time.

    Each thread gets its own set of filesystem instances to avoid thread-safety
    issues with WholeFileCacheFileSystem's in-memory metadata cache.
    """

    _thread_local: ClassVar[threading.local] = threading.local()

    @classmethod
    def _get_filesystems(cls) -> dict[str, HTTPFileSystem | WholeFileCacheFileSystem]:
        """Return the per-thread filesystem registry."""
        if not hasattr(cls._thread_local, "filesystems"):
            cls._thread_local.filesystems = {}
        return cls._thread_local.filesystems

    @staticmethod
    def _client_kwargs_suffix(client_kwargs: dict | None) -> str:
        """Return a short stable hash suffix that distinguishes different client_kwargs (e.g. auth headers)."""
        if not client_kwargs:
            return ""
        try:
            serialized = json.dumps({k: str(v) for k, v in sorted(client_kwargs.items())}, sort_keys=True)
            return "-" + hashlib.sha256(serialized.encode()).hexdigest()[:8]
        except Exception:  # noqa: BLE001
            return ""

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
        use_certifi: bool = False,
    ) -> None:
        """Register a new filesystem instance for a given cache expiration time.

        Args:
            cache_dir: The cache directory to use for the filesystem.
            cache_expiry: The cache expiration time.
            client_kwargs: Additional keyword arguments for the client.
            cache_disable: If True, the cache is disabled.
            use_certifi: If True, use certifi certificate bundle instead of system certificates.

        Returns:
            None

        """
        ttl_name, ttl_value = cls.resolve_ttl(cache_expiry)
        key = f"ttl-{ttl_name}{cls._client_kwargs_suffix(client_kwargs)}"
        fs = HTTPFileSystem(
            use_listings_cache=False,
            client_kwargs=client_kwargs,
            listings_expiry_time=0.0,  # not relevant for the download of files
            listings_cache_location=cache_dir,  # ensure mkdir still occurs in correct location
            use_certifi=use_certifi,
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
        cls._get_filesystems()[key] = filesystem_effective

    @classmethod
    def get(
        cls,
        cache_dir: Path,
        cache_expiry: CacheExpiry = CacheExpiry.NO_CACHE,
        client_kwargs: dict | None = None,
        *,
        cache_disable: bool,
        use_certifi: bool = False,
    ) -> HTTPFileSystem | WholeFileCacheFileSystem:
        """Get a filesystem instance for a given cache expiration time.

        Args:
            cache_dir: The cache directory to use for the filesystem.
            cache_expiry: The cache expiration time.
            client_kwargs: Additional keyword arguments for the client.
            cache_disable: If True, the cache is disabled
            use_certifi: If True, use certifi certificate bundle instead of system certificates.

        Returns:
            The filesystem instance.

        """
        ttl_name, _ = cls.resolve_ttl(cache_expiry)
        key = f"ttl-{ttl_name}{cls._client_kwargs_suffix(client_kwargs)}"
        if key not in cls._get_filesystems():
            cls.register(
                cache_dir=cache_dir,
                cache_expiry=cache_expiry,
                client_kwargs=client_kwargs,
                cache_disable=cache_disable,
                use_certifi=use_certifi,
            )
        return cls._get_filesystems()[key]


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
        use_certifi=settings.use_certifi,
    )
    return fs.find(url)


@stamina.retry(on=Exception, attempts=3)
def list_remote_directory_fsspec(
    url: str, settings: Settings, cache_expiry: CacheExpiry = CacheExpiry.FILEINDEX
) -> list[dict]:
    """List the immediate contents (files and subdirectories) of a given path on the server, non-recursively.

    Unlike ``list_remote_files_fsspec``, this does not descend into subdirectories, which is useful for
    servers exposing a deeply nested directory tree where the folder names themselves carry enough
    information (e.g. a date range) to decide which subdirectories are actually worth descending into.

    Args:
        url: The URL to list the contents of.
        settings: The settings to use for the listing.
        cache_expiry: The cache expiration time.

    Returns:
        A list of fsspec detail dicts (with "name" and "type" keys, among others) for each entry.

    """
    use_cache = not (settings.cache_disable or cache_expiry is CacheExpiry.NO_CACHE)
    fs = HTTPFileSystem(
        use_listings_cache=use_cache,
        listings_expiry_time=not settings.cache_disable and cache_expiry.value,
        listings_cache_location=settings.cache_dir,
        client_kwargs=settings.fsspec_client_kwargs,
        use_certifi=settings.use_certifi,
    )
    return fs.ls(url, detail=True)


def _is_retryable(exc: Exception) -> bool:
    """Decide whether a failed download is worth waiting out and trying again.

    A response the server meant is not: 401, 403 and the like are its final word, and retrying only
    delays the error. 429 and 5xx are the opposite -- they say "not now" rather than "no" -- and are
    the ones worth waiting out, which matters when several jobs hit the same endpoint at once.

    ``FileNotFoundError`` is deliberately absent: a 404 is a legitimate answer here, since providers
    use it to mean "this station has no such file", so it gets the short retry in ``_cat_file``
    instead of a backoff measured in seconds.
    """
    if isinstance(exc, ClientResponseError):
        return exc.status == HTTP_TOO_MANY_REQUESTS or exc.status >= HTTP_SERVER_ERROR
    return isinstance(exc, (FSTimeoutError, ClientConnectorError, ClientPayloadError))


def _cat_file(filesystem: HTTPFileSystem | WholeFileCacheFileSystem, url: str) -> bytes:
    """Fetch the file, retrying a 404 once and cheaply.

    Kept separate from the backoff in ``download_file`` because a 404 is normal control flow rather
    than a fault -- every request for a parameter a station does not carry ends here -- so it must
    stay fast. It is still worth one retry, since opendata servers occasionally 404 a file that does
    exist.
    """
    for attempt in stamina.retry_context(
        on=FileNotFoundError,
        attempts=2,
        wait_initial=0.1,
        wait_max=0.5,
        wait_jitter=0.1,
    ):
        with attempt:
            return filesystem.cat_file(url)
    msg = "unreachable"
    raise AssertionError(msg)


def download_file(
    url: str,
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
    use_certifi: bool = False,
) -> File:
    """Download a specified file from the server.

    Args:
        url: The URL of the file to download.
        cache_dir: The cache directory to use for the filesystem.
        ttl: The cache expiration time.
        client_kwargs: Additional keyword arguments for the client.
        cache_disable: If True, the cache is disabled.
        use_certifi: If True, use certifi certificate bundle instead of system certificates.

    Returns:
        A BytesIO object containing the downloaded file.

    """
    filesystem = NetworkFilesystemManager.get(
        cache_dir=cache_dir,
        cache_expiry=ttl,
        client_kwargs=client_kwargs,
        cache_disable=cache_disable,
        use_certifi=use_certifi,
    )
    log.info(f"Downloading file {url}")
    try:
        for attempt in stamina.retry_context(
            on=_is_retryable,
            attempts=4,
            # a rate limit or an overloaded server needs real time to clear, and the default 0.1 s
            # first wait is short enough that the retries land inside the same window that caused
            # the failure. The other retryable errors are cheap to sit out for a second.
            wait_initial=1.0,
            wait_max=30.0,
            wait_jitter=1.0,
        ):
            with attempt:
                payload = _cat_file(filesystem, url)
                log.info(f"Downloaded file {url}")
                return File(url=url, content=BytesIO(payload), status=200)
        msg = "unreachable"
        raise AssertionError(msg)
    except FileNotFoundError as e:
        log.info(f"Failed to download file {url}.")
        return File(url=url, content=e, status=404)
    except FSTimeoutError as e:
        log.info(f"Failed to download file {url}.")
        return File(url=url, content=e, status=408)
    except ClientConnectorError as e:
        log.info(f"No internet connection while downloading file {url}.")
        return File(url=url, content=NoInternetError(str(e)), status=503)
    except ClientResponseError as e:
        log.info(f"Failed to download file {url}.")
        return File(url=url, content=e, status=e.status or 500)
    except ClientPayloadError as e:
        log.info(f"Failed to download file {url}.")
        return File(url=url, content=e, status=500)


def download_files(
    urls: list[str],
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
    use_certifi: bool = False,
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
                    use_certifi=use_certifi,
                ),
                urls,
            ),
        )
