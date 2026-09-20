# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Network utilities for the wetterdienst package."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import shutil
import ssl
import threading
from collections.abc import Iterator, MutableMapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal, TypeVar
from urllib.parse import urlparse

import stamina
from aiohttp import (
    ClientConnectionError,
    ClientConnectorError,
    ClientError,
    ClientPayloadError,
    ClientResponseError,
)
from fsspec.asyn import sync, sync_wrapper
from fsspec.exceptions import FSTimeoutError
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.http import HTTPFileSystem as _HTTPFileSystem

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_E = TypeVar("_E", bound=BaseException)


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


# Directory names the listings cache used to create under the cache dir but never writes to any
# more. ``False`` came from ``CacheExpiry.INFINITE`` and from a disabled cache, ``0.0`` from the
# download-side filesystem registration, ``0.01`` from ``CacheExpiry.NO_CACHE``. In every one of
# those cases ``use_listings_cache`` was False, so the directory was created and then never written
# to. They are swept on the next run, guarded by an emptiness check so that a directory which does
# somehow hold entries is left alone.
_LEGACY_LISTINGS_CACHE_DIR_NAMES = frozenset({"False", "0.0", "0.01"})
_legacy_cleanup_lock = threading.Lock()
_legacy_cleanup_done: set[Path] = set()


def _remove_legacy_listings_cache_dirs(cache_root: Path, keep: str) -> None:
    """Remove empty listings-cache directories left behind by earlier versions.

    Runs once per cache root per process, and is best-effort throughout: a cache directory that
    cannot be tidied is not a reason to fail the request that happened to trigger the sweep.

    Args:
        cache_root: Directory the per-TTL listings cache folders live in.
        keep: Name of the folder the caller is about to use, never removed.

    """
    with _legacy_cleanup_lock:
        if cache_root in _legacy_cleanup_done:
            return
        _legacy_cleanup_done.add(cache_root)

    from diskcache import Cache  # noqa: PLC0415

    for name in _LEGACY_LISTINGS_CACHE_DIR_NAMES - {keep}:
        stale = cache_root / name
        if not stale.is_dir():
            continue
        try:
            with Cache(directory=str(stale)) as cache:
                # cull expired rows first: the ``False`` folder is full of them, because
                # ``CacheExpiry.INFINITE`` used to store every listing already expired. What
                # matters is whether anything still *valid* is in there.
                cache.expire()
                entries = len(cache)
            if entries:
                log.debug(f"Keeping listings cache folder {stale}, it still holds {entries} entries")
                continue
            shutil.rmtree(stale)
            log.info(f"Removed orphaned listings cache folder {stale}")
        except Exception:
            log.debug(f"Failed removing orphaned listings cache folder {stale}", exc_info=True)


def _rebuild_file_dir_cache(
    listings_expiry_time: float | None,
    use_listings_cache: bool,  # noqa: FBT001
    listings_cache_location: Path | None,
) -> FileDirCache:
    """Rebuild a FileDirCache from its pickled state.

    ``FileDirCache.__init__`` takes keyword-only arguments, so unpickling needs this
    positional shim.
    """
    return FileDirCache(
        listings_expiry_time,
        use_listings_cache=use_listings_cache,
        listings_cache_location=listings_cache_location,
    )


class FileDirCache(MutableMapping):
    """File-based cache for FSSPEC."""

    def __init__(
        self,
        listings_expiry_time: float | None,
        *,
        use_listings_cache: bool,
        listings_cache_location: Path | None = None,
    ) -> None:
        """Initialize the FileDirCache.

        Args:
            listings_expiry_time: Time in seconds that a listing is considered valid. A falsy
                value (as carried by ``CacheExpiry.INFINITE``, which is ``False``) means the
                listing never expires.
            use_listings_cache: If False, this cache never returns items, but always reports KeyError.
            listings_cache_location: Directory path at which the listings cache file is stored.

        """
        # ``CacheExpiry.INFINITE`` reaches us as ``False``. Map it to ``None``, diskcache's "no
        # expiry" sentinel -- passing ``False`` straight through made diskcache compute an expiry
        # of ``now + False == now``, so entries were born expired and the listings cache silently
        # never hit. Only False/None mean "never expire": a numeric 0 has to keep meaning "expire
        # immediately", since silently upgrading it to "cache forever on disk" fails open.
        if listings_expiry_time is None or listings_expiry_time is False:
            self.listings_expiry_time = None
        else:
            self.listings_expiry_time = float(listings_expiry_time)
        self.use_listings_cache = use_listings_cache
        self._listings_cache_location = listings_cache_location

        if not use_listings_cache:
            # Nothing will ever be stored, so don't create a cache directory for it.
            self.cache_location = None
            self._cache = None
            return

        import platformdirs  # noqa: PLC0415
        from diskcache import Cache  # noqa: PLC0415

        subdir = "infinite" if self.listings_expiry_time is None else str(self.listings_expiry_time)
        if listings_cache_location:
            cache_location = Path(listings_cache_location) / subdir
        else:
            cache_location = Path(platformdirs.user_cache_dir(appname="wetterdienst-fsspec")) / subdir

        _remove_legacy_listings_cache_dirs(cache_location.parent, keep=cache_location.name)

        try:
            log.info(f"Creating dircache folder at {cache_location}")
            cache_location.mkdir(exist_ok=True, parents=True)
        except OSError:
            log.exception(f"Failed creating dircache folder at {cache_location}")

        self.cache_location = cache_location
        self._cache = Cache(directory=str(cache_location))

    def __getitem__(self, item: str) -> list[dict]:
        """Draw item from cache, retry if timeout occurs."""
        # ``self._cache is None`` is exactly the "caching disabled" case; binding it to a local
        # keeps the None-check visible to the type checker in every method below.
        cache = self._cache
        if cache is None:
            raise KeyError(item)
        _missing = object()
        value = cache.get(key=item, default=_missing, read=True, retry=True)
        if value is _missing:
            raise KeyError(item)
        return value

    def clear(self) -> None:
        """Clear cache."""
        cache = self._cache
        if cache is None:
            return
        cache.clear()

    def __len__(self) -> int:
        """Return number of items in cache."""
        cache = self._cache
        if cache is None:
            return 0
        return len(cache)

    def __contains__(self, item: object) -> bool:
        """Check if item is in cache and not expired."""
        cache = self._cache
        if cache is None:
            return False
        return item in cache

    def __setitem__(self, key: str, value: list[dict]) -> None:
        """Store listing in cache."""
        cache = self._cache
        if cache is None:
            return
        cache.set(key=key, value=value, expire=self.listings_expiry_time, retry=True)

    def __delitem__(self, key: str) -> None:
        """Remove item from cache."""
        cache = self._cache
        if cache is None:
            raise KeyError(key)
        del cache[key]

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys in cache."""
        cache = self._cache
        if cache is None:
            return iter([])
        return iter(cache)

    def __reduce__(self) -> tuple:
        """Return state information for pickling."""
        return (
            _rebuild_file_dir_cache,
            (self.listings_expiry_time, self.use_listings_cache, self._listings_cache_location),
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

        # aiohttp >= 3.9 rejects any bare numeric timeout -- int and float alike -- so wrap one in
        # ClientTimeout. ``client_kwargs`` is optional and may legitimately be passed as None (that
        # is fsspec's own default), so check for a dict rather than for the key being present.
        client_kwargs = kwargs.get("client_kwargs")
        client_kwargs = client_kwargs if isinstance(client_kwargs, dict) else {}
        timeout = client_kwargs.get("timeout")
        if isinstance(timeout, (int, float)) and not isinstance(timeout, bool):
            import aiohttp  # noqa: PLC0415

            kwargs["client_kwargs"] = {**client_kwargs, "timeout": aiohttp.ClientTimeout(total=timeout)}

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

    async def _ls(self, url: str, detail: bool = True, **kwargs) -> list:  # noqa: ANN003, FBT001, FBT002
        """List a directory, going through the dircache with a single lookup.

        Overrides the upstream implementation for two reasons:

        * upstream probes ``url in self.dircache`` and then indexes it, which races with TTL
          expiry between the two calls and raises a ``KeyError`` that nothing catches,
        * upstream caches whatever shape ``detail`` asked for, so one ``detail=False`` call
          poisons every later ``detail=True`` read of the same URL. We always cache the
          detailed listing and derive the name-only view from it.
        """
        # a cached listing is always a list (possibly empty), so None is a safe "miss" sentinel
        out: list[dict] | None = self.dircache.get(url) if self.use_listings_cache else None
        if out is None:
            out = await self._ls_real(url, detail=True, **kwargs)
            self.dircache[url] = out
        return out if detail else sorted(entry["name"] for entry in out)

    # the parent binds ``ls`` to *its* ``_ls`` function object, so the override above only
    # takes effect for callers that look ``_ls`` up dynamically (``find``/``walk``). Rebind
    # it so the plain synchronous ``ls()`` goes through our implementation too.
    ls = sync_wrapper(_ls)


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
            # inert while use_listings_cache is False, but keeps the listings cache out of the
            # platformdirs fallback location should it ever be enabled here
            listings_cache_location=cache_dir,
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
    # knmi sends its API key, metno frost its basic auth and metoffice its bearer token this way,
    # and aiohttp merges those headers into the request info it hangs on an error
    sent_credentials = _sends_credentials(client_kwargs)
    try:
        for attempt in stamina.retry_context(
            on=(FileNotFoundError, FSTimeoutError, ClientConnectorError, ClientResponseError, ClientPayloadError),
            attempts=2,
        ):
            with attempt:
                try:
                    payload = filesystem.cat_file(url)
                except Exception as e:  # noqa: BLE001 -- re-raised, never swallowed
                    # scrubbed here as well as on the way out, because stamina's retry hook logs
                    # ``repr(caused_by)`` on the first failure -- and that repr renders the request
                    # info, header and all, before any of the handlers below are reached
                    raise _without_credentials(e, sent_credentials=sent_credentials) from None
                log.info(f"Downloaded file {url}")
                return File(url=url, content=BytesIO(payload), status=200)
        msg = "unreachable"
        raise AssertionError(msg)
    except FileNotFoundError as e:
        log.info(f"Failed to download file {url}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=404)
    except FSTimeoutError as e:
        log.info(f"Failed to download file {url}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=408)
    except ClientConnectorError as e:
        log.info(f"No internet connection while downloading file {url}.")
        return File(url=url, content=NoInternetError(str(e)), status=503)
    except ClientResponseError as e:
        log.info(f"Failed to download file {url}.")
        return File(
            url=url,
            content=_without_credentials(e, sent_credentials=sent_credentials),
            status=e.status or 500,
        )
    except ClientError as e:
        # ClientPayloadError among them, and every other aiohttp client failure -- a dropped
        # keep-alive connection (ServerDisconnectedError), a reset, too many redirects. Caught as
        # the base class so that none of them leaves by way of a traceback through this frame, where
        # the caller's client kwargs, credentials included, are a local
        log.info(f"Failed to download file {url}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=500)


#: header names a credential is sent under. `Authorization` is the standard one -- KNMI's API key,
#: met.no Frost's basic auth and Met Office's bearer token all go there -- but AEMET wants `api_key`,
#: and a header named anything else is a header this cannot know to redact: a provider that invents
#: one has to name it here for its failures to be scrubbed along with the rest.
_CREDENTIAL_HEADERS = frozenset({"authorization", "proxy-authorization", "api_key", "api-key", "x-api-key"})


def _sends_credentials(client_kwargs: dict | None) -> bool:
    """Whether these client kwargs carry a credential in a header."""
    headers = (client_kwargs or {}).get("headers") or {}
    return any(str(name).lower() in _CREDENTIAL_HEADERS for name in headers)


def _without_credentials(error: _E, *, sent_credentials: bool) -> _E:
    """Keep the credential of an authenticated request out of the error it produced.

    Two places hold it, neither of them ``str(error)`` -- which is what makes it easy to miss:

    - the request info aiohttp hangs on a ``ClientResponseError``, and on its ``args``, which is
      what a ``repr`` renders, and
    - the traceback, whose frames in this module have the header, its encoding and the caller's
      client kwargs as locals. That is what ``pytest --showlocals`` prints and what an error
      reporter capturing frame locals sends.

    The error is handed back to a caller to log, raise or store, so both are dealt with before it
    travels. The traceback is dropped only for a request that carried credentials: for every other
    one it is worth more than it costs.
    """
    if not sent_credentials:
        return error
    error = error.with_traceback(None)
    # only a response error carries request info; a timeout or a dropped connection has none, and
    # for those the traceback was the whole of the exposure
    if not isinstance(error, ClientResponseError):
        return error
    request_info = error.request_info
    if request_info is None:
        return error
    carried = [name for name in request_info.headers if str(name).lower() in _CREDENTIAL_HEADERS]
    if not carried:
        return error
    headers = request_info.headers.copy()
    for name in carried:
        # assignment replaces every entry of that name rather than adding one
        headers[name] = "<redacted>"
    # rebuilt as the same (immutable) mapping type the request info was given, without naming it
    scrubbed = request_info._replace(headers=type(request_info.headers)(headers))
    error.request_info = scrubbed
    # the history is the responses of a redirect chain, each holding its own copy of the request and
    # so of the header. Dropped rather than rebuilt: what a redirected request has to say is that it
    # was redirected, which the status already says, and ClientResponse keeps its request info
    # behind a property with no setter
    error.history = ()
    # aiohttp builds args as (request_info, history); rewritten only where that still holds, rather
    # than assuming the first element of any subclass's args is the request info
    if error.args and error.args[0] is request_info:
        error.args = (scrubbed, (), *error.args[2:])
    return error


# How long a post waits when the caller's ``client_kwargs`` does not say. Settings carries a
# default of the same length, so this stands in only for a caller that passes none at all.
_POST_TIMEOUT_SECONDS = 30.0


def post_file(
    url: str,
    *,
    auth: tuple[str, str] | None = None,
    client_kwargs: dict | None = None,
    use_certifi: bool = False,
) -> File:
    """Post to a URL and return the response body.

    The download path cannot express this: ``download_file`` is a GET through a caching filesystem,
    where minting a token is a POST whose answer must never be cached. It still goes through
    fsspec's HTTP filesystem -- its event loop, its aiohttp session, its SSL handling and the
    caller's client settings -- so one HTTP stack serves every request the package makes rather
    than a second client being carried for one of them.

    Failures come back as a ``File`` carrying the exception and a status, the same shape
    ``download_file`` returns them in, so a caller decides what a failed exchange means rather than
    having an exception thrown through it. A redirect is not followed and arrives as itself, so a
    caller that expected a body should read ``File.status`` before the content.

    Args:
        url: The URL to post to.
        auth: Username and password for HTTP basic auth, if the endpoint wants them.
        client_kwargs: Additional keyword arguments for the client, ``timeout`` among them.
        use_certifi: If True, use certifi certificate bundle instead of system certificates.

    Returns:
        A File holding the response body, or the exception that stopped it.

    """
    filesystem = HTTPFileSystem(
        use_listings_cache=False,
        listings_expiry_time=0,
        use_certifi=use_certifi,
        # a default for a caller that set none, rather than an argument of its own: every caller
        # here passes ``Settings.fsspec_client_kwargs``, which always carries a timeout, so a
        # separate parameter could be passed and never take effect
        client_kwargs={"timeout": _POST_TIMEOUT_SECONDS, **(client_kwargs or {})},
    )
    # RFC 7617 by hand rather than through aiohttp: its ``BasicAuth`` and the ``auth=`` parameter are
    # both deprecated for removal in aiohttp 4, and its replacement (``encode_basic_auth``) is newer
    # than the aiohttp any given install carries. Sent per request, so credentials never reach
    # ``client_kwargs`` -- which is hashed into the filesystem cache key.
    headers = None
    if auth:
        headers = {"Authorization": f"Basic {base64.b64encode(':'.join(auth).encode()).decode('ascii')}"}
    sent_credentials = headers is not None or _sends_credentials(client_kwargs)

    async def _post() -> tuple[int, bytes]:
        session = await filesystem.set_session()
        # A POST is not repeated as a POST across a redirect: aiohttp would follow it as a GET and
        # answer with whatever that returned -- an HTML login page reads as a 200 with an
        # unparseable body, where the 302 says plainly what happened. So the redirect is the answer.
        async with session.post(url, headers=headers, allow_redirects=False) as response:
            response.raise_for_status()
            return response.status, await response.read()

    log.info(f"Posting to {url}")
    try:
        # fsspec keeps one filesystem instance -- and so one aiohttp session and its keep-alive
        # pool -- for the life of the process, where a token is minted days apart. The first attempt
        # can therefore pick a pooled connection the server closed hours ago, which the second gets
        # to retry on a fresh one. A response that did arrive is never retried: a 401 is an answer.
        for attempt in stamina.retry_context(
            on=(ClientConnectionError, FSTimeoutError, TimeoutError),
            attempts=2,
        ):
            with attempt:
                try:
                    status, payload = sync(filesystem.loop, _post)
                except Exception as e:  # noqa: BLE001 -- re-raised, never swallowed
                    # as in download_file: stamina's retry hook logs ``repr(caused_by)``, which
                    # renders an aiohttp error's request info. None of the errors retried here
                    # carries one today, which is exactly the kind of thing a later edit changes
                    raise _without_credentials(e, sent_credentials=sent_credentials) from None
                log.info(f"Posted to {url}")
                return File(url=url, content=BytesIO(payload), status=status)
        msg = "unreachable"
        raise AssertionError(msg)
    except ClientResponseError as e:
        log.info(f"Failed to post to {url}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=e.status or 500)
    except ClientConnectorError as e:
        log.info(f"No internet connection while posting to {url}.")
        return File(url=url, content=NoInternetError(str(e)), status=503)
    except (FSTimeoutError, TimeoutError) as e:
        log.info(f"Failed to post to {url}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=408)
    except ClientError as e:
        # every other aiohttp client failure -- a dropped keep-alive connection
        # (ServerDisconnectedError), a reset, a broken payload. Caught as the base class rather than
        # named one by one, because the promise made above is that a failure comes back as a File.
        log.info(f"Failed to post to {url}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=500)


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
