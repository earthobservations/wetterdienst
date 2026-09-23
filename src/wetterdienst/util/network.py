# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Network utilities for the wetterdienst package."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import shutil
import ssl
import threading
import time
from collections.abc import Iterator, MutableMapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http import HTTPStatus
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
    from_cache: bool = False
    """Whether the body was served from the on-disk cache rather than fetched.

    A caller that cannot use what it was given needs this to know whether asking again could
    answer differently: a cached body says nothing about what the server has now, while one that
    has just come off the wire cannot have changed in the meantime (GH-1947).
    """

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


#: header names a credential is sent under. `Authorization` is the standard one -- KNMI's API key,
#: met.no Frost's basic auth and Met Office's bearer token all go there -- but AEMET wants `api_key`,
#: and a header named anything else is a header this cannot know to redact: a provider that invents
#: one has to name it here for its failures to be scrubbed along with the rest.
#:
#: These names carry a second job now: they are the part of `client_kwargs` that says *who is
#: asking*, and so the only part that may separate one caller's cached bodies from another's. See
#: `NetworkFilesystemManager._identity_suffix`.
_CREDENTIAL_HEADERS = frozenset({"authorization", "proxy-authorization", "api_key", "api-key", "x-api-key"})


def _credential_headers(client_kwargs: dict | None) -> dict[str, str] | None:
    """Read the credential-bearing headers these kwargs carry, or `None` where that cannot be read.

    aiohttp takes headers as a mapping or as an iterable of pairs, so both are read here. One
    reader, because two callers have to agree about the answer -- the scrubber that keeps a
    credential out of an error it hands back, and the cache path that keeps one caller's bodies away
    from another's -- and both fail dangerously on a false negative: one logs the header, the other
    files an authenticated body where an unauthenticated request will be given it.

    So a shape neither can read is `None`, "there may be a credential here", rather than `{}`.
    """
    headers = (client_kwargs or {}).get("headers")
    if not headers:
        return {}
    try:
        items = headers.items() if hasattr(headers, "items") else headers
        return {str(name).lower(): str(value) for name, value in items if str(name).lower() in _CREDENTIAL_HEADERS}
    except (AttributeError, TypeError, ValueError):
        return None


#: Names the layout of `cache_dir/fsspec`, so that a directory written under an older one can be
#: told apart from a live one by its name alone rather than by guessing from its age or contents.
#: Bump it whenever `_cache_path` changes shape, and every directory left by the previous shape is
#: reclaimed on the next run.
_CACHE_LAYOUT_VERSION = "v2"

#: Blob directories already swept of expired entries in this process. Process-wide rather than
#: thread-local, because the directory is shared by every thread while the registry naming it is not.
_swept_dirs: set[Path] = set()

#: Held across everything that opens or deletes a file under `cache_dir/fsspec`: building a caching
#: filesystem, sweeping one of expired blobs, and reclaiming the directories nothing can reach.
#:
#: One lock over all three rather than one each, because *building* a filesystem reads its
#: directory's metadata file and the other two can delete it. On POSIX that is harmless -- an unlink
#: leaves the open handle readable -- which is why separate locks looked sufficient and why this
#: passed everywhere it was run. On Windows it is `PermissionError: [Errno 13]` out of fsspec's
#: `CacheMetadata._load`, and CI said so.
_cache_dir_lock = threading.Lock()


def _sweep_expired_blobs(
    filesystem: WholeFileCacheFileSystem,
    cache_path: Path,
    ttl_value: float | Literal[False],
) -> None:
    """Drop blobs this directory's own TTL has already made useless.

    Once per directory per process, and never able to raise: every one of the three ways the
    obvious version of this went wrong is a way of failing a download that would otherwise have
    worked (GH-1955).

    * **A TTL that is not a positive number is not swept at all.** `CacheExpiry.INFINITE` is
      `False`, `int(False)` is `0`, and fsspec reads an expiry of zero as "everything is
      expired" -- it removes every entry and then `rmtree`s the directory. `lhmt` and both
      `meteofrance` providers use `INFINITE` for immutable archives, so the first such download
      in a fresh process would have destroyed the archive cache and re-fetched it. The read path
      gets this right (`_check_file` reads `if cfs.expiry and ...`); only the sweep did not.
    * **The directory is marked swept before the attempt, not after.** `clear_expired` raises
      for a half-written entry -- exactly the case worth surviving -- and a sweep retried on
      every `register` would fail every download for this TTL rather than the one that met it.
    * **The caller holds `_cache_dir_lock` across this**, which is what keeps siblings out.
      `clear_expired` works from the snapshot its filesystem loaded and saves that snapshot back,
      so a sweep running beside a `download_files` thread pool would drop rows its siblings had
      just written and orphan their blobs -- the leak this exists to close. It also deletes the
      metadata file that *building* a filesystem for this directory reads, which on Windows is a
      `PermissionError` for the builder rather than the harmless POSIX unlink.

    Args:
        filesystem: The caching filesystem that owns this directory.
        cache_path: The directory the blobs live in, which names the sweep.
        ttl_value: The TTL behind it, as `resolve_ttl` returns it.

    """
    # `bool` is a subclass of `int`, and `CacheExpiry.INFINITE` is `False`
    if isinstance(ttl_value, bool) or not isinstance(ttl_value, (int, float)) or ttl_value <= 0:
        return
    if cache_path in _swept_dirs:
        return
    _swept_dirs.add(cache_path)
    try:
        # a second line rather than the line: the guard above already means this is positive, but
        # fsspec substitutes `self.expiry` for a falsy argument and for an `INFINITE` cache that is
        # the `0` described above, so what reaches it is said rather than left implied
        filesystem.clear_expired_cache(expiry_time=ttl_value)
    except Exception:
        log.debug(f"Failed sweeping expired blobs in {cache_path}", exc_info=True)


#: Any blob directory this module has ever written: `ttl-<NAME>` with an optional hash suffix,
#: under an optional layout prefix (the first layout had none). Matching every layout rather than
#: only the one before this is what makes `_CACHE_LAYOUT_VERSION` self-cleaning: a build reclaims
#: what any other layout wrote, in both directions, so alternating between two versions costs a
#: re-download rather than a directory that neither of them will ever collect.
#:
#: `<NAME>` is a character class rather than the `CacheExpiry` members, deliberately: the directories
#: worth reclaiming are the ones *older* builds wrote, and a TTL one of them had may since have been
#: renamed or removed. So it is written to match any enum member name a build could have produced,
#: which is wider than today's enum and cannot be pinned by a test against it. What a test does pin
#: is the other direction -- that every directory this build writes is one this recognises.
_BLOB_CACHE_DIR = re.compile(r"^(?:v\d+-)?ttl-[A-Z0-9_]+(?:-[0-9a-f]{8})?$")

#: A blob directory of the current layout that a *credential* names. The unsuffixed ones are named
#: by every run and their liveness is never in question; these are the only ones that can stop being
#: named while the library goes on working, because the credential they are named for has rotated.
_IDENTITY_CACHE_DIR = re.compile(rf"^{_CACHE_LAYOUT_VERSION}-ttl-[A-Z_]+-[0-9a-f]{{8}}$")

#: Touched whenever a directory is named, so that "nothing has asked for this in a month" can be
#: read off it. The blobs cannot answer that themselves: an archive that is read on every run and
#: written on none has file times as old as the day it was fetched.
_CACHE_USE_MARKER = ".last-used"
_UNUSED_CACHE_SECONDS = 30 * 24 * 3600

#: Stands in for a credential in headers that `_credential_headers` could not read. A constant, so
#: that such a caller gets one directory rather than a new one per process, and eight hex digits so
#: that it is aged out like any other directory a credential names.
_UNREADABLE_IDENTITY = hashlib.sha256(b"unreadable credential headers").hexdigest()[:8]

_reclaim_done: set[Path] = set()


def _is_superseded_layout(name: str) -> bool:
    """Whether this is a blob directory of some layout other than the one in use.

    No key this build can produce names one, so nothing can reach it to expire it -- which is the
    whole of why it is removed rather than left to a TTL.
    """
    return bool(_BLOB_CACHE_DIR.match(name)) and not name.startswith(f"{_CACHE_LAYOUT_VERSION}-")


def _mark_cache_dir_used(cache_path: Path) -> None:
    """Record that something asked for this directory, which is what keeps it from being reclaimed."""
    try:
        (cache_path / _CACHE_USE_MARKER).touch()
    except OSError:
        log.debug(f"Failed marking {cache_path} as used", exc_info=True)


def _last_used(directory: Path) -> float:
    """When this directory was last named, falling back to the directory's own time."""
    marker = directory / _CACHE_USE_MARKER
    try:
        return marker.stat().st_mtime if marker.exists() else directory.stat().st_mtime
    except OSError:
        # unreadable is not "long unused": leave it to the next run rather than remove it blind
        return time.time()


def _reclaim_unreachable_cache_dirs(fsspec_root: Path, keep: Path) -> None:
    """Remove blob directories nothing can reach any more.

    Runs once per cache root per process, and is best-effort throughout: a directory that cannot be
    removed is not a reason to fail the download that happened to trigger the sweep. Two kinds go,
    and neither holds anything that is not re-downloadable:

    * **An earlier `_cache_path` layout.** Nothing can expire these, because the key that named them
      cannot be produced by this version at all. Until `_cache_path` stopped hashing transport
      settings the User-Agent carried the version number, so every release left a full set behind:
      one developer machine held 129 directories under 98 distinct hashes and 4.3 GB in all, of
      which 115 MB was reachable (GH-1959).
    * **A credential that has rotated.** `_identity_suffix` names a directory for the credential it
      was fetched with, and Met Office mints a three-day JWT -- so that provider renames its
      directory twice a week and would otherwise leave the previous one behind for good. Aged out
      by the marker rather than by the blobs' own file times, and only ever for a directory a
      credential names: the shared ones are named on every run, and reclaiming one for looking idle
      would throw away the main cache.

    Args:
        fsspec_root: The `fsspec` directory under the cache dir that blob directories live in.
        keep: The directory the caller is about to use, never removed however it looks.

    Note:
        The caller holds `_cache_dir_lock`: this deletes directories whose metadata another thread
        may be in the middle of opening.

    """
    if fsspec_root in _reclaim_done:
        return
    _reclaim_done.add(fsspec_root)

    try:
        entries = [d for d in fsspec_root.iterdir() if d.is_dir() and d != keep]
    except OSError:
        log.debug(f"Failed listing {fsspec_root} for unreachable cache directories", exc_info=True)
        return

    cutoff = time.time() - _UNUSED_CACHE_SECONDS
    stale = [
        directory
        for directory in entries
        if _is_superseded_layout(directory.name)
        or (_IDENTITY_CACHE_DIR.match(directory.name) and _last_used(directory) < cutoff)
    ]

    reclaimed = 0
    for directory in stale:
        try:
            # walked for the log line alone, and cheap enough to be worth it: blobs are few and
            # large, so the 4.3 GB measured above is under 5000 files and a quarter of a second
            size = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
            shutil.rmtree(directory)
        except OSError:
            log.debug(f"Failed removing unreachable cache directory {directory}", exc_info=True)
            continue
        reclaimed += size
    if stale:
        log.info(f"Reclaimed {reclaimed / 1e6:.1f} MB from {len(stale)} unreachable cache directories in {fsspec_root}")


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
    def _registry_key(
        cache_dir: Path,
        cache_expiry: CacheExpiry,
        client_kwargs: dict | None,
        *,
        cache_disable: bool,
        use_certifi: bool,
    ) -> str:
        """Name a filesystem by everything `register` builds it from.

        Everything, because `register` runs only for a key that is new -- so whatever the key
        leaves out, the first caller in a thread decides for every later one. `cache_dir`,
        `cache_disable` and `use_certifi` were all left out. `CacheExpiry.METAINDEX` being an alias
        of `TWELVE_HOURS`, any earlier metaindex download from any provider was enough to leave a
        caching filesystem under that key, and a later request made with caching disabled, or
        against a different `WD_CACHE_DIR`, was then served by it (GH-1947).

        This names the instance in memory and nothing on disk. Where the blobs live is
        `_cache_path`, and the two answer different questions: an instance is separated by
        everything it is *built* from, a blob only by what changes the bytes a server sends back.
        `use_certifi` and a timeout are the clearest case -- they decide how the request is made and
        nothing about what comes back, so they name an instance and must not name a directory.
        """
        ttl_name, _ = NetworkFilesystemManager.resolve_ttl(cache_expiry)
        parts = [
            # through `resolve_ttl`, as `_cache_path` reads it: the two agree today only because
            # that function returns the name verbatim, and a key that reads an input its own way is
            # how this drifted in the first place
            f"ttl-{ttl_name}",
            NetworkFilesystemManager._client_kwargs_suffix(client_kwargs),
            f"-dir-{hashlib.sha256(str(cache_dir).encode()).hexdigest()[:8]}",
            "-nocache" if cache_disable else "",
            "-certifi" if use_certifi else "",
        ]
        return "".join(parts)

    @staticmethod
    def _cache_path(cache_dir: Path, cache_expiry: CacheExpiry, client_kwargs: dict | None) -> Path:
        """Where the blobs for this TTL live.

        Separated by the TTL, and by *who is asking* -- never by how the asking is done. This used
        to hash the whole of `client_kwargs`, which mixes the two: an `Authorization` header decides
        what a server sends back, where a timeout, a proxy and a User-Agent decide nothing about it.
        The default User-Agent carries the version number, so the directory was renamed by every
        release and the cache re-downloaded from empty; nothing reads the old name again and, until
        `_reclaim_legacy_cache_dirs`, nothing removed it either (GH-1959).
        """
        ttl_name, _ = NetworkFilesystemManager.resolve_ttl(cache_expiry)
        suffix = NetworkFilesystemManager._identity_suffix(client_kwargs)
        return Path(cache_dir) / "fsspec" / f"{_CACHE_LAYOUT_VERSION}-ttl-{ttl_name}{suffix}"

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
    def _identity_suffix(client_kwargs: dict | None) -> str:
        """Name the credential these kwargs carry, and nothing else about them.

        Empty for an unauthenticated request, which is most of them: the DWD and every other open
        provider then share one directory per TTL whose name never moves. Two different API keys
        still get two directories, because a body fetched with one is not a body the other may be
        handed back.

        A credential that rotates -- Met Office mints a three-day JWT -- renames the directory with
        it, and the previous one is left holding blobs nothing will ask for again. Keying on the
        long-lived credential instead would spare that, but `Settings.auth` is not visible from
        here; so the cost is paid and then collected, by `_reclaim_unreachable_cache_dirs`, rather
        than left to accumulate. Sharing one directory between two keys is the one thing not on
        offer: every provider here authenticates rather than selects with its credential, but a
        cache is a bad place to bet on that staying true.
        """
        carried = _credential_headers(client_kwargs)
        if carried is None:
            # headers in a shape this cannot read. Never the shared directory: returning "" here
            # would file an authenticated body exactly where an unauthenticated request looks for
            # one. A directory of its own, the same one every time, is the safe answer
            return f"-{_UNREADABLE_IDENTITY}"
        if not carried:
            return ""
        return "-" + hashlib.sha256(json.dumps(carried, sort_keys=True).encode()).hexdigest()[:8]

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
        _, ttl_value = cls.resolve_ttl(cache_expiry)
        key = cls._registry_key(
            cache_dir, cache_expiry, client_kwargs, cache_disable=cache_disable, use_certifi=use_certifi
        )
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
            real_cache_dir = cls._cache_path(cache_dir, cache_expiry, client_kwargs)
            # built inside the lock, not merely tidied inside it: building reads this directory's
            # metadata file, and the sweep and the reclaim below delete metadata files. On POSIX an
            # unlink leaves an open handle readable and this was invisible; on Windows the builder
            # gets `PermissionError` from fsspec's `CacheMetadata._load`
            with _cache_dir_lock:
                filesystem_effective = WholeFileCacheFileSystem(
                    fs=fs,
                    cache_storage=str(real_cache_dir),
                    expiry_time=int(ttl_value),
                )
                # the tidying is before the registry assignment below, and none of it able to raise: a
                # cache that cannot be tidied must still be a cache that can be read.
                #
                # The mark goes after the sweep, not before: a sweep that leaves the cache empty has
                # fsspec `rmtree` the whole directory and rebuild it, which takes the marker with it --
                # and a directory whose marker is missing reads as one nothing has asked for in a month
                _sweep_expired_blobs(filesystem_effective, real_cache_dir, ttl_value)
                _mark_cache_dir_used(real_cache_dir)
                _reclaim_unreachable_cache_dirs(real_cache_dir.parent, keep=real_cache_dir)
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
        key = cls._registry_key(
            cache_dir, cache_expiry, client_kwargs, cache_disable=cache_disable, use_certifi=use_certifi
        )
        if key not in cls._get_filesystems():
            cls.register(
                cache_dir=cache_dir,
                cache_expiry=cache_expiry,
                client_kwargs=client_kwargs,
                cache_disable=cache_disable,
                use_certifi=use_certifi,
            )
        return cls._get_filesystems()[key]


def _worth_retrying(error: Exception) -> bool:
    """Whether a failed post is worth a second attempt.

    A response that arrived is an answer, and a 401 will not become a 200 by asking again -- unless
    the server said the fault was its own. A 502 or a 503 from a token endpoint is a blip, and the
    request that meets it is the one least able to afford failing: a token is minted once every
    three days, and a mint that fails empties a whole query rather than one file of it.

    A 429 is deliberately not retried. The endpoints that rate-limit are rate-limiting a free
    account, and asking again a tenth of a second later is how that gets worse rather than better;
    it comes back as the answer it is, for the caller to report.
    """
    # ClientPayloadError is a body that stopped arriving mid-read, which is the same kind of blip
    # as a connection that never carried one -- and it is no subclass of ClientConnectionError
    if isinstance(error, (ClientConnectionError, ClientPayloadError, FSTimeoutError, TimeoutError)):
        return True
    return isinstance(error, ClientResponseError) and error.status >= HTTPStatus.INTERNAL_SERVER_ERROR


def _worth_retrying_download(error: Exception) -> bool:
    """Whether a failed download is worth a second attempt.

    The same answer as for a post, plus the missing file fsspec raises for a 404 -- a file index is
    read minutes before the files it names are fetched, and a listing can race a publication either
    way, so a download asks once more before believing a file is not there.
    """
    return isinstance(error, FileNotFoundError) or _worth_retrying(error)


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
    try:
        # `find` walks with `on_error="omit"` by default, which catches `(FileNotFoundError,
        # OSError)` and returns nothing -- and aiohttp's `ClientOSError` is an `OSError`. So a
        # connection reset mid-walk was swallowed inside fsspec, never reached the retry wrapping
        # this call, and arrived at the caller as an empty directory would. Every provider that
        # lists then had to decide what an empty list meant, and none of them could (GH-1947).
        #
        # Raised instead, and the two told apart here: a directory that is not there is an answer,
        # and callers have always had it as `[]`; anything else is a failure to read, which the
        # retry above is for and which a caller should hear about rather than infer
        return fs.find(url, on_error="raise")
    except FileNotFoundError:
        return []
    except ClientConnectorError:
        # the one `OSError` that is not a failure to read this listing: it is the whole library
        # being offline, which every other path here degrades on rather than reports -- a download
        # comes back carrying `NoInternetError` for `raise_if_exception` to log at debug, and
        # providers answer with empty frames. A listing has no `File` to carry that in, so it
        # degrades the way it always did, and the offline user keeps getting empty frames instead
        # of an aiohttp traceback from the one path that lists
        log.debug(f"No internet connection available for {url}, returning no files.")
        return []


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
        # a 429 is not asked again: the providers that rate-limit are rate-limiting a free
        # account, and a second request a tenth of a second later is how that gets worse. What is
        # worth asking twice, `_worth_retrying_download` says, and it says the same as a post does
        for attempt in stamina.retry_context(on=_worth_retrying_download, attempts=2):
            with attempt:
                try:
                    # asked per attempt and before the read, because reading is what populates the
                    # cache -- and because an attempt that re-downloads after a cached read failed
                    # must not inherit the first attempt's answer. `_check_file` is how
                    # `WholeFileCacheFileSystem` says whether it holds an unexpired copy; a plain
                    # filesystem has no such question and always says no.
                    #
                    # Inside the `try`, because it reaches the disk: `_mkcache` can raise on a
                    # read-only or full cache dir and the metadata load on a truncated file, and an
                    # exception escaping here carries a traceback whose frame holds `client_kwargs`
                    # -- the Authorization header -- which is exactly what the handler below drops
                    served_from_cache = bool(getattr(filesystem, "_check_file", lambda _url: False)(url))
                    payload = filesystem.cat_file(url)
                except Exception as e:  # noqa: BLE001 -- re-raised, never swallowed
                    # scrubbed here as well as on the way out, because stamina's retry hook logs
                    # ``repr(caused_by)`` on the first failure -- and that repr renders the request
                    # info, header and all, before any of the handlers below are reached
                    raise _without_credentials(e, sent_credentials=sent_credentials) from None
                log.info(f"Downloaded file {url}")
                return File(url=url, content=BytesIO(payload), status=200, from_cache=served_from_cache)
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


def _sends_credentials(client_kwargs: dict | None) -> bool:
    """Whether these client kwargs carry a credential in a header.

    Headers this cannot read count as carrying one: scrubbing a failure that held no credential
    costs a traceback, where not scrubbing one that did puts the header in a log.
    """
    carried = _credential_headers(client_kwargs)
    return carried is None or bool(carried)


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

    A request that fails the way a server does -- a 5xx, a dropped connection, a body that stops
    arriving -- is made a second time, which assumes the post is one that may safely be made twice.
    That holds for asking an endpoint for a token, which is what this exists for; a post that
    *changes* something at the other end wants a caller that knows a 500 may arrive after the change
    was applied.

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
        # to retry on a fresh one. What else is worth asking twice, `_worth_retrying` says.
        for attempt in stamina.retry_context(on=_worth_retrying, attempts=2):
            with attempt:
                try:
                    status, payload = sync(filesystem.loop, _post)
                except Exception as e:  # noqa: BLE001 -- re-raised, never swallowed
                    # load-bearing, not belt and braces: stamina's retry hook logs
                    # ``repr(caused_by)``, which renders an aiohttp error's request info -- and a
                    # 5xx is retried here, so that repr is of an error carrying the Authorization
                    # header this function just built. This is the only thing keeping it out of the
                    # retry log
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
