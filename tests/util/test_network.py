# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for network utilities."""

import json
import logging
import os
import pickle
import threading
import time
from collections.abc import Callable, Iterator, MutableMapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import stamina
from aiohttp import (
    ClientConnectorError,
    ClientOSError,
    ClientPayloadError,
    ClientResponseError,
    ClientTimeout,
    ServerDisconnectedError,
)
from diskcache import Cache
from fsspec.exceptions import FSTimeoutError
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.memory import MemoryFileSystem

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util import network
from wetterdienst.util.network import (
    _BLOB_CACHE_DIR,
    _IDENTITY_CACHE_DIR,
    File,
    FileDirCache,
    HTTPFileSystem,
    NetworkFilesystemManager,
    _credential_headers,
    _is_superseded_layout,
    _legacy_cleanup_done,
    _reclaim_done,
    _sends_credentials,
    _swept_dirs,
    download_file,
    list_remote_directory_fsspec,
    list_remote_files_fsspec,
    post_file,
)


def test_create_fsspec_filesystem() -> None:
    """Test if a fsspec filesystem can be created."""
    default_settings = Settings()
    fs1 = NetworkFilesystemManager.get(
        cache_dir=default_settings.cache_dir,
        cache_expiry=CacheExpiry.METAINDEX,
        client_kwargs=default_settings.fsspec_client_kwargs,
        cache_disable=default_settings.cache_disable,
    )
    fs2 = NetworkFilesystemManager.get(
        cache_dir=default_settings.cache_dir,
        cache_expiry=CacheExpiry.METAINDEX,
        client_kwargs=default_settings.fsspec_client_kwargs,
        cache_disable=default_settings.cache_disable,
    )
    assert id(fs1) == id(fs2)


def test_file_raise_if_exception_no_internet_does_not_raise() -> None:
    """File.raise_if_exception() must not raise for NoInternetError."""
    f = File(url="http://example.com/file.txt", content=NoInternetError("no internet"), status=503)
    f.raise_if_exception()  # should return silently


def test_file_raise_if_exception_other_exception_raises() -> None:
    """File.raise_if_exception() must still raise for non-NoInternetError exceptions."""
    f = File(url="http://example.com/file.txt", content=FileNotFoundError("not found"), status=404)
    with pytest.raises(FileNotFoundError):
        f.raise_if_exception()


def test_file_is_no_internet_error_true() -> None:
    """File.is_no_internet_error returns True when content is NoInternetError."""
    f = File(url="http://example.com/file.txt", content=NoInternetError("no internet"), status=503)
    assert f.is_no_internet_error is True


def test_file_is_no_internet_error_false() -> None:
    """File.is_no_internet_error returns False when content is BytesIO."""
    f = File(url="http://example.com/file.txt", content=BytesIO(b"data"), status=200)
    assert f.is_no_internet_error is False


def test_download_file_returns_no_internet_error_on_connector_error() -> None:
    """download_file() stores NoInternetError in File when ClientConnectorError occurs."""
    connector_error = ClientConnectorError(connection_key=MagicMock(), os_error=OSError("Network unreachable"))

    mock_fs = MagicMock()
    mock_fs.cat_file.side_effect = connector_error

    default_settings = Settings(cache_disable=True)

    with patch("wetterdienst.util.network.NetworkFilesystemManager.get", return_value=mock_fs):
        result = download_file(
            url="http://example.com/file.txt",
            cache_dir=default_settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=default_settings.fsspec_client_kwargs,
            cache_disable=default_settings.cache_disable,
        )

    assert result.is_no_internet_error
    assert result.status == 503
    assert isinstance(result.content, NoInternetError)


def test_download_file_does_not_retry_a_rate_limit() -> None:
    """download_file() takes a 429 for the answer it is, rather than asking again at once.

    The providers that rate-limit are rate-limiting a free account -- AEMET, met.no Frost -- and a
    second request a tenth of a second later is how that gets worse rather than better. It used to
    be retried, which is the behaviour this replaces.
    """
    error_429 = ClientResponseError(request_info=MagicMock(), history=(), status=429)

    mock_fs = MagicMock()
    mock_fs.cat_file.side_effect = [error_429, b"data"]

    default_settings = Settings(cache_disable=True)

    with (
        stamina.set_testing(True, attempts=2),
        patch("wetterdienst.util.network.NetworkFilesystemManager.get", return_value=mock_fs),
    ):
        result = download_file(
            url="http://example.com/file.txt",
            cache_dir=default_settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=default_settings.fsspec_client_kwargs,
            cache_disable=default_settings.cache_disable,
        )

    assert mock_fs.cat_file.call_count == 1
    assert result.status == 429
    assert result.content is error_429


def test_download_file_retries_on_500_and_succeeds() -> None:
    """download_file() retries on HTTP 500 and returns the file on the second attempt."""
    error_500 = ClientResponseError(request_info=MagicMock(), history=(), status=500)
    payload = b"data"

    mock_fs = MagicMock()
    mock_fs.cat_file.side_effect = [error_500, payload]

    default_settings = Settings(cache_disable=True)

    with (
        stamina.set_testing(True, attempts=2),
        patch("wetterdienst.util.network.NetworkFilesystemManager.get", return_value=mock_fs),
    ):
        result = download_file(
            url="http://example.com/file.txt",
            cache_dir=default_settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=default_settings.fsspec_client_kwargs,
            cache_disable=default_settings.cache_disable,
        )

    assert mock_fs.cat_file.call_count == 2
    assert result.status == 200
    assert isinstance(result.content, BytesIO)
    assert result.content.read() == payload


def test_download_file_retries_on_fstimeout_and_succeeds() -> None:
    """download_file() retries on FSTimeoutError and returns the file on the second attempt."""
    payload = b"data"

    mock_fs = MagicMock()
    mock_fs.cat_file.side_effect = [FSTimeoutError(), payload]

    default_settings = Settings(cache_disable=True)

    with (
        stamina.set_testing(True, attempts=2),
        patch("wetterdienst.util.network.NetworkFilesystemManager.get", return_value=mock_fs),
    ):
        result = download_file(
            url="http://example.com/file.txt",
            cache_dir=default_settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=default_settings.fsspec_client_kwargs,
            cache_disable=default_settings.cache_disable,
        )

    assert mock_fs.cat_file.call_count == 2
    assert result.status == 200
    assert isinstance(result.content, BytesIO)
    assert result.content.read() == payload


def test_download_file_retries_on_404_and_returns_file() -> None:
    """download_file() retries on FileNotFoundError and returns it as File after all attempts."""
    mock_fs = MagicMock()
    mock_fs.cat_file.side_effect = FileNotFoundError("not found")

    default_settings = Settings(cache_disable=True)

    with (
        stamina.set_testing(True, attempts=3),
        patch("wetterdienst.util.network.NetworkFilesystemManager.get", return_value=mock_fs),
    ):
        result = download_file(
            url="http://example.com/file.txt",
            cache_dir=default_settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=default_settings.fsspec_client_kwargs,
            cache_disable=default_settings.cache_disable,
        )

    assert mock_fs.cat_file.call_count == 3
    assert result.status == 404
    assert isinstance(result.content, FileNotFoundError)


def test_download_file_returns_file_after_exhausting_retries() -> None:
    """download_file() returns File with error status once all retry attempts are exhausted."""
    error_500 = ClientResponseError(request_info=MagicMock(), history=(), status=500)

    mock_fs = MagicMock()
    mock_fs.cat_file.side_effect = error_500

    default_settings = Settings(cache_disable=True)

    with (
        stamina.set_testing(True, attempts=2),
        patch("wetterdienst.util.network.NetworkFilesystemManager.get", return_value=mock_fs),
    ):
        result = download_file(
            url="http://example.com/file.txt",
            cache_dir=default_settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=default_settings.fsspec_client_kwargs,
            cache_disable=default_settings.cache_disable,
        )

    assert mock_fs.cat_file.call_count == 2
    assert result.status == 500
    assert isinstance(result.content, ClientResponseError)


class _RacyDirCache(MutableMapping):
    """dircache whose entry expires between ``__contains__`` and ``__getitem__``.

    Reproduces the TTL race that made the previous two-step dircache lookup raise an
    uncaught KeyError out of ``ls()``. Like FileDirCache it is a MutableMapping, so the
    inherited ``get()`` routes through ``__getitem__``.
    """

    def __contains__(self, item: object) -> bool:
        return True

    def __getitem__(self, item: str) -> list[dict]:
        raise KeyError(item)

    def __setitem__(self, key: str, value: list[dict]) -> None:
        pass

    def __delitem__(self, key: str) -> None:
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter([])

    def __len__(self) -> int:
        return 0


def _fake_listing(url: str) -> list[dict]:
    return [
        {"name": f"{url}b.zip", "size": 1, "type": "file"},
        {"name": f"{url}a.zip", "size": 1, "type": "file"},
    ]


def test_file_dir_cache_stores_and_returns_listing(tmp_path: Path) -> None:
    """FileDirCache round-trips a listing."""
    cache = FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)
    listing = _fake_listing("http://example.com/")
    cache["http://example.com/"] = listing
    assert cache.get("http://example.com/") == listing
    assert cache["http://example.com/"] == listing
    assert len(cache) == 1


def test_file_dir_cache_reports_containment(tmp_path: Path) -> None:
    """__contains__ reflects what is stored.

    The keys here are deliberately not URL-shaped. CodeQL's incomplete-url-substring-sanitization
    rule flags ``"http://..." in x`` without knowing that x is a mapping rather than a string, and
    the other tests read the cache through ``get()`` -- which is what ``_ls`` itself now uses.
    """
    cache = FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)
    cache["listing-a"] = _fake_listing("http://example.com/")
    assert "listing-a" in cache
    assert "listing-b" not in cache


def test_file_dir_cache_infinite_expiry_is_stored(tmp_path: Path) -> None:
    """A falsy expiry (CacheExpiry.INFINITE is False) means "never expire", not "already expired"."""
    cache = FileDirCache(
        CacheExpiry.INFINITE.value,
        use_listings_cache=True,
        listings_cache_location=tmp_path,
    )
    assert cache.listings_expiry_time is None
    cache["http://example.com/"] = _fake_listing("http://example.com/")
    assert cache.get("http://example.com/") == _fake_listing("http://example.com/")
    assert cache.cache_location.name == "infinite"


def test_file_dir_cache_honours_expiry(tmp_path: Path) -> None:
    """Entries disappear once the expiry time has passed.

    Deliberately asserts only on the post-expiry state: a "still cached" assert taken right
    after the write would race a slow scheduler under ``pytest -n auto``. That the entry was
    stored at all is covered by test_file_dir_cache_stores_and_returns_listing.
    """
    cache = FileDirCache(0.2, use_listings_cache=True, listings_cache_location=tmp_path)
    cache["http://example.com/"] = _fake_listing("http://example.com/")
    time.sleep(0.4)
    assert cache.get("http://example.com/") is None


def test_file_dir_cache_disabled_stores_nothing_and_creates_no_directory(tmp_path: Path) -> None:
    """A disabled cache neither stores entries nor leaves a cache directory behind."""
    cache = FileDirCache(
        CacheExpiry.INFINITE.value,
        use_listings_cache=False,
        listings_cache_location=tmp_path,
    )
    cache["http://example.com/"] = _fake_listing("http://example.com/")
    assert cache.get("http://example.com/") is None
    assert len(cache) == 0
    assert list(cache) == []
    with pytest.raises(KeyError):
        _ = cache["http://example.com/"]
    assert list(tmp_path.iterdir()) == []


def test_file_dir_cache_is_picklable(tmp_path: Path) -> None:
    """FileDirCache survives a pickle round-trip (its __reduce__ used to pass bad arguments)."""
    cache = FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)
    restored = pickle.loads(pickle.dumps(cache))  # noqa: S301
    assert isinstance(restored, FileDirCache)
    assert restored.listings_expiry_time == 300.0
    assert restored.use_listings_cache is True
    assert restored.cache_location == cache.cache_location


def test_http_filesystem_ls_caches_listing(tmp_path: Path) -> None:
    """The second ls() of the same URL is served from the dircache."""
    calls = []

    async def fake_ls_real(self, url, detail=True, **kwargs):  # noqa: ANN001, ANN003, ANN202, ARG001, FBT002
        calls.append(url)
        return _fake_listing(url)

    fs = HTTPFileSystem(use_listings_cache=True, listings_expiry_time=300.0, listings_cache_location=tmp_path)
    with patch.object(HTTPFileSystem, "_ls_real", fake_ls_real):
        first = fs.ls("http://example.com/", detail=True)
        second = fs.ls("http://example.com/", detail=True)
    assert calls == ["http://example.com/"]
    assert first == second


def test_http_filesystem_ls_detail_false_returns_names_without_poisoning_cache(tmp_path: Path) -> None:
    """A detail=False call returns names and still leaves the detailed listing cached."""
    calls = []

    async def fake_ls_real(self, url, detail=True, **kwargs):  # noqa: ANN001, ANN003, ANN202, ARG001, FBT002
        calls.append(url)
        return _fake_listing(url)

    fs = HTTPFileSystem(use_listings_cache=True, listings_expiry_time=300.0, listings_cache_location=tmp_path)
    with patch.object(HTTPFileSystem, "_ls_real", fake_ls_real):
        names = fs.ls("http://example.com/", detail=False)
        detailed = fs.ls("http://example.com/", detail=True)
    assert names == ["http://example.com/a.zip", "http://example.com/b.zip"]
    assert detailed == _fake_listing("http://example.com/")
    assert calls == ["http://example.com/"]


def test_http_filesystem_ls_survives_entry_expiring_mid_lookup(tmp_path: Path) -> None:
    """ls() refetches instead of raising when a dircache entry expires mid-lookup."""

    async def fake_ls_real(self, url, detail=True, **kwargs):  # noqa: ANN001, ANN003, ANN202, ARG001, FBT002
        return _fake_listing(url)

    fs = HTTPFileSystem(use_listings_cache=True, listings_expiry_time=300.0, listings_cache_location=tmp_path)
    fs.dircache = _RacyDirCache()
    with patch.object(HTTPFileSystem, "_ls_real", fake_ls_real):
        assert fs.ls("http://example.com/", detail=True) == _fake_listing("http://example.com/")


@pytest.mark.parametrize(
    "cache_expiry",
    [CacheExpiry.FILEINDEX, CacheExpiry.METAINDEX, CacheExpiry.INFINITE],
)
def test_list_remote_files_fsspec_uses_listings_cache(tmp_path: Path, cache_expiry: CacheExpiry) -> None:
    """list_remote_files_fsspec() hits the network once per URL for every cached TTL, INFINITE included."""
    calls = []

    async def fake_ls_real(self, url, detail=True, **kwargs):  # noqa: ANN001, ANN003, ANN202, ARG001, FBT002
        calls.append(url)
        return _fake_listing(url)

    settings = Settings(cache_dir=tmp_path)
    with patch.object(HTTPFileSystem, "_ls_real", fake_ls_real):
        first = list_remote_files_fsspec("http://example.com/", settings=settings, cache_expiry=cache_expiry)
        second = list_remote_files_fsspec("http://example.com/", settings=settings, cache_expiry=cache_expiry)
    assert first == ["http://example.com/a.zip", "http://example.com/b.zip"]
    assert first == second
    assert calls == ["http://example.com/"]


@pytest.mark.parametrize(
    ("cache_expiry", "cache_disable"),
    [(CacheExpiry.NO_CACHE, False), (CacheExpiry.METAINDEX, True)],
)
def test_list_remote_files_fsspec_bypasses_cache(
    tmp_path: Path,
    cache_expiry: CacheExpiry,
    *,
    cache_disable: bool,
) -> None:
    """NO_CACHE and cache_disable both make every call go to the network."""
    calls = []

    async def fake_ls_real(self, url, detail=True, **kwargs):  # noqa: ANN001, ANN003, ANN202, ARG001, FBT002
        calls.append(url)
        return _fake_listing(url)

    settings = Settings(cache_dir=tmp_path, cache_disable=cache_disable)
    with patch.object(HTTPFileSystem, "_ls_real", fake_ls_real):
        list_remote_files_fsspec("http://example.com/", settings=settings, cache_expiry=cache_expiry)
        list_remote_files_fsspec("http://example.com/", settings=settings, cache_expiry=cache_expiry)
    assert calls == ["http://example.com/", "http://example.com/"]


def test_list_remote_directory_fsspec_uses_listings_cache(tmp_path: Path) -> None:
    """list_remote_directory_fsspec() caches its non-recursive listing too."""
    calls = []

    async def fake_ls_real(self, url, detail=True, **kwargs):  # noqa: ANN001, ANN003, ANN202, ARG001, FBT002
        calls.append(url)
        return _fake_listing(url)

    settings = Settings(cache_dir=tmp_path)
    with patch.object(HTTPFileSystem, "_ls_real", fake_ls_real):
        first = list_remote_directory_fsspec("http://example.com/", settings=settings)
        second = list_remote_directory_fsspec("http://example.com/", settings=settings)
    assert first == _fake_listing("http://example.com/")
    assert first == second
    assert calls == ["http://example.com/"]


def test_file_dir_cache_sweeps_orphaned_legacy_dirs(tmp_path: Path) -> None:
    """Empty cache folders left by earlier versions are removed on the next run."""
    _legacy_cleanup_done.clear()
    for name in ("False", "0.0", "0.01"):
        (tmp_path / name).mkdir()
    live = tmp_path / "43200.0"
    live.mkdir()
    (tmp_path / "fsspec").mkdir()

    FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)

    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == ["300.0", "43200.0", "fsspec"]


def test_file_dir_cache_keeps_legacy_dir_that_holds_entries(tmp_path: Path) -> None:
    """A legacy-named folder that somehow still holds entries is left alone."""
    _legacy_cleanup_done.clear()
    stale = tmp_path / "0.01"
    stale.mkdir()
    with Cache(directory=str(stale)) as cache:
        cache.set(key="http://example.com/", value=_fake_listing("http://example.com/"))

    FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)

    assert stale.is_dir()


def test_file_dir_cache_sweeps_legacy_dir_holding_only_expired_entries(tmp_path: Path) -> None:
    """The real-world ``False`` folder is full of rows that were stored already expired.

    ``CacheExpiry.INFINITE`` used to hand diskcache an expiry of ``now + False == now``, so the
    folder is not empty by row count even though nothing in it is readable. It still goes.
    """
    _legacy_cleanup_done.clear()
    stale = tmp_path / "False"
    stale.mkdir()
    with Cache(directory=str(stale)) as cache:
        cache.set(key="http://example.com/", value=_fake_listing("http://example.com/"), expire=False)
        assert len(cache) == 1

    FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)

    assert not stale.exists()


def test_file_dir_cache_never_sweeps_the_dir_it_is_about_to_use(tmp_path: Path) -> None:
    """A cache legitimately created at a legacy-looking TTL is not swept out from under itself."""
    _legacy_cleanup_done.clear()
    cache = FileDirCache(0.01, use_listings_cache=True, listings_cache_location=tmp_path)
    assert cache.cache_location.name == "0.01"
    assert cache.cache_location.is_dir()


def test_legacy_cache_sweep_runs_once_per_root(tmp_path: Path) -> None:
    """The sweep is skipped on later constructions for the same cache root."""
    _legacy_cleanup_done.clear()
    FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)
    assert tmp_path in _legacy_cleanup_done
    # a folder created after the sweep survives, proving the sweep did not run a second time
    (tmp_path / "False").mkdir()
    FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)
    assert (tmp_path / "False").is_dir()


def test_legacy_cache_sweep_survives_unremovable_dir(tmp_path: Path) -> None:
    """A folder that cannot be removed is logged, not raised."""
    _legacy_cleanup_done.clear()
    (tmp_path / "False").mkdir()
    with patch("wetterdienst.util.network.shutil.rmtree", side_effect=OSError("permission denied")):
        FileDirCache(300.0, use_listings_cache=True, listings_cache_location=tmp_path)
    assert (tmp_path / "300.0").is_dir()


def test_http_filesystem_accepts_client_kwargs_none(tmp_path: Path) -> None:
    """client_kwargs=None is fsspec's own default and must not crash the constructor."""
    fs = HTTPFileSystem(
        use_listings_cache=False,
        listings_expiry_time=0.0,
        listings_cache_location=tmp_path,
        client_kwargs=None,
        skip_instance_cache=True,
    )
    assert fs.client_kwargs == {}


def test_http_filesystem_wraps_int_timeout_in_client_timeout(tmp_path: Path) -> None:
    """A bare int timeout is wrapped in aiohttp.ClientTimeout, which aiohttp >= 3.9 requires."""
    fs = HTTPFileSystem(
        use_listings_cache=False,
        listings_expiry_time=0.0,
        listings_cache_location=tmp_path,
        client_kwargs={"timeout": 30, "headers": {"User-Agent": "wetterdienst"}},
        skip_instance_cache=True,
    )
    assert isinstance(fs.client_kwargs["timeout"], ClientTimeout)
    assert fs.client_kwargs["timeout"].total == 30
    assert fs.client_kwargs["headers"] == {"User-Agent": "wetterdienst"}


def test_http_filesystem_wraps_float_timeout_in_client_timeout(tmp_path: Path) -> None:
    """Aiohttp rejects a bare float timeout just as it rejects a bare int, so both get wrapped."""
    fs = HTTPFileSystem(
        use_listings_cache=False,
        listings_expiry_time=0.0,
        listings_cache_location=tmp_path,
        client_kwargs={"timeout": 30.5},
        skip_instance_cache=True,
    )
    assert isinstance(fs.client_kwargs["timeout"], ClientTimeout)
    assert fs.client_kwargs["timeout"].total == 30.5


def test_http_filesystem_leaves_client_timeout_untouched(tmp_path: Path) -> None:
    """An already-wrapped timeout is passed through as-is."""
    timeout = ClientTimeout(total=15)
    fs = HTTPFileSystem(
        use_listings_cache=False,
        listings_expiry_time=0.0,
        listings_cache_location=tmp_path,
        client_kwargs={"timeout": timeout},
        skip_instance_cache=True,
    )
    assert fs.client_kwargs["timeout"] is timeout


def test_file_dir_cache_zero_expiry_is_not_treated_as_infinite(tmp_path: Path) -> None:
    """Only False/None mean "never expire" -- a numeric 0 must still expire immediately."""
    cache = FileDirCache(0, use_listings_cache=True, listings_cache_location=tmp_path)
    assert cache.listings_expiry_time == 0.0
    cache["http://example.com/"] = _fake_listing("http://example.com/")
    assert cache.get("http://example.com/") is None


def test_network_filesystem_manager_accepts_client_kwargs_none(tmp_path: Path) -> None:
    """download_file() defaults client_kwargs to None, so the manager must build a filesystem for it."""
    HTTPFileSystem.clear_instance_cache()
    NetworkFilesystemManager._get_filesystems().clear()  # noqa: SLF001
    fs = NetworkFilesystemManager.get(
        cache_dir=tmp_path,
        cache_expiry=CacheExpiry.NO_CACHE,
        client_kwargs=None,
        cache_disable=True,
    )
    assert isinstance(fs, HTTPFileSystem)


def _every_carrier_of(error: BaseException) -> str:
    """Render everything an exception hands onward: its text, its repr, and its frames' locals.

    ``--showlocals`` and an error reporter's frame capture read the last of those, which is where a
    credential hides when the exception itself looks clean.
    """
    import traceback  # noqa: PLC0415

    rendered = [repr(error), str(error), *traceback.format_exception(type(error), error, error.__traceback__)]
    frame = error.__traceback__
    while frame:
        rendered.append(repr(frame.tb_frame.f_locals))
        frame = frame.tb_next
    return "".join(rendered)


#: what the stand-in token endpoint answers with, and what each of its paths is for
_TOKEN_BODY = json.dumps({"access_token": "t"}).encode()
_STATUS_BY_PATH = {"/denied": 401, "/rate-limited": 429, "/boom": 500}


def _answer_for(path: str, *, asked_before: bool) -> tuple[int, bytes, dict[str, str]]:
    """Return the status, body and extra headers a path is served with."""
    if path == "/login-redirect":
        return 302, b"", {"Location": "/denied"}
    if path == "/flaky":
        # a blip: the first caller gets a 502, everyone after it gets an answer
        return (200, _TOKEN_BODY, {}) if asked_before else (502, b"", {})
    if path in _STATUS_BY_PATH:
        return _STATUS_BY_PATH[path], b"", {}
    return 200, _TOKEN_BODY, {}


class _TokenEndpoint(BaseHTTPRequestHandler):
    """The answers an authenticated endpoint gives, recording what was asked of it.

    A real server rather than a mocked transport: what is under test is the request that goes out --
    its credential header, its refusal to follow a redirect -- and the error that comes back, both
    of which a mock at that level stands in front of.
    """

    def do_POST(self) -> None:
        self._record("POST")
        self._answer()

    def do_GET(self) -> None:
        self._record("GET")
        self._answer()

    def log_message(self, *_args: object) -> None:
        """Keep the test output free of the server's own access log."""

    def _record(self, method: str) -> None:
        self.server.requests.append({"method": method, "path": self.path, "headers": dict(self.headers)})

    def _answer(self) -> None:
        if self.path == "/drop":
            # answer nothing and hang up, which aiohttp reports as ServerDisconnectedError
            self.connection.close()
            return
        if self.path == "/truncated":
            # promise a body and stop halfway through it, which aiohttp reports as ClientPayloadError
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b'{"access_')
            self.connection.close()
            return
        asked_before = len([r for r in self.server.requests if r["path"] == self.path]) > 1
        status, body, headers = _answer_for(self.path, asked_before=asked_before)
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        if body:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)


@pytest.fixture
def http_server() -> Iterator[tuple[str, list]]:
    """Run `_TokenEndpoint` on a port of its own, and hand back its URL and what it was asked.

    Paths: `/token` answers with a token, `/denied` 401, `/rate-limited` 429, `/boom` 500,
    `/login-redirect` 302 to `/denied`, `/flaky` 502 to its first caller and a token after that,
    `/truncated` stops halfway through a body it promised, and `/drop` hangs up without answering at
    all.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TokenEndpoint)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", server.requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_post_file_returns_a_dropped_connection_as_a_file() -> None:
    """A connection the server closed comes back as a File, not as an exception through the caller.

    fsspec keeps one filesystem -- and one aiohttp session with its keep-alive pool -- for the life
    of the process, so a caller that posts days apart can be handed a connection closed long ago.
    ``ServerDisconnectedError`` is neither of the two connection errors named above it, which is why
    the base class is caught.
    """
    error = ServerDisconnectedError()

    with (
        stamina.set_testing(True, attempts=1),
        patch("wetterdienst.util.network.sync", side_effect=error),
    ):
        result = post_file("http://example.com/token", auth=("user", "pass"))

    assert result.status == 500
    assert result.content is error
    assert not result.is_no_internet_error


def test_post_file_retries_a_dropped_connection_once() -> None:
    """A dropped connection is retried, where a response that did arrive would not be."""
    payload = b'{"access_token": "t"}'

    with (
        stamina.set_testing(True, attempts=2),
        patch("wetterdienst.util.network.sync", side_effect=[ServerDisconnectedError(), (200, payload)]) as mock_sync,
    ):
        result = post_file("http://example.com/token")

    assert mock_sync.call_count == 2
    assert result.status == 200
    assert result.content.getvalue() == payload


def test_post_file_keeps_the_callers_timeout() -> None:
    """A timeout the caller configured is honoured; the module's own stands in only when none is."""
    with (
        patch("wetterdienst.util.network.HTTPFileSystem") as mock_filesystem,
        patch("wetterdienst.util.network.sync", return_value=(200, b"{}")),
    ):
        post_file("http://example.com/token", client_kwargs={"timeout": 120})
        post_file("http://example.com/token")

    configured, defaulted = mock_filesystem.call_args_list
    assert configured.kwargs["client_kwargs"]["timeout"] == 120
    assert defaulted.kwargs["client_kwargs"]["timeout"] == 30.0


def test_post_file_sends_basic_auth_and_does_not_follow_a_redirect(http_server: tuple[str, list]) -> None:
    """Against a real server: the Authorization header is sent, and a redirect comes back as itself.

    These are the two things the mocked tests above cannot see, ``sync`` standing in for the whole
    request: aiohttp follows a redirected POST as a GET, which would turn a login page into a 200
    with a body that parses as nothing, and the basic-auth header is built here rather than by a
    library.
    """
    import base64  # noqa: PLC0415

    base_url, requests = http_server

    ok = post_file(f"{base_url}/token", auth=("user", "pa:ss"))
    assert ok.status == 200
    assert json.loads(ok.content.getvalue()) == {"access_token": "t"}

    # RFC 7617: base64 of "user:pa:ss" -- a colon is allowed in the password, not in the username
    expected = base64.b64encode(b"user:pa:ss").decode()
    assert requests[-1]["headers"]["Authorization"] == f"Basic {expected}"
    assert requests[-1]["method"] == "POST"

    redirected = post_file(f"{base_url}/login-redirect", auth=("user", "pa:ss"))
    assert redirected.status == 302
    # one request, not two: the redirect was not followed, and never became a GET
    assert len(requests) == 2


def test_post_file_keeps_credentials_out_of_the_error_it_returns(http_server: tuple[str, list]) -> None:
    """A 401 comes back as an error whose repr does not carry the credential that earned it.

    aiohttp hangs the request headers on the exception and on its ``args``, so a repr -- a pytest
    dump, an error reporter walking the object -- would otherwise print the base64 of
    username:password.
    """
    import base64  # noqa: PLC0415

    base_url, _ = http_server

    result = post_file(f"{base_url}/denied", auth=("user", "pa:ss"))

    assert result.status == 401
    assert isinstance(result.content, ClientResponseError)
    secret = base64.b64encode(b"user:pa:ss").decode()
    assert secret not in repr(result.content)
    assert secret not in str(result.content)
    assert result.content.request_info.headers["Authorization"] == "<redacted>"
    # and not in the traceback either, whose frames in network.py held the header as a local
    assert secret not in _every_carrier_of(result.content)


@pytest.mark.parametrize("header", ["Authorization", "api_key"])
def test_download_file_keeps_a_credential_header_out_of_its_error(
    header: str,
    http_server: tuple[str, list],
    tmp_path: Path,
) -> None:
    """A provider's API key does not travel in the error a failed download hands back.

    KNMI sends its key, met.no Frost its basic auth and Met Office its bearer token as
    ``Authorization`` -- but AEMET sends its key as ``api_key``, and a scrub that knows only the
    standard name leaves the one provider with a header of its own the only one still leaking.
    """
    base_url, requests = http_server
    key = "SUPER-SECRET-API-KEY"

    result = download_file(
        url=f"{base_url}/denied",
        cache_dir=tmp_path,
        ttl=CacheExpiry.NO_CACHE,
        client_kwargs={"headers": {header: key}},
        cache_disable=True,
    )

    # the header did reach the server, so the scrubbing under test actually had something to do:
    # without this the test would pass just as well on a request that never carried the key
    assert requests[0]["headers"][header] == key
    assert result.status == 401
    assert key not in _every_carrier_of(result.content)


def test_download_file_keeps_credentials_out_of_a_redirect_chain(
    http_server: tuple[str, list],
    tmp_path: Path,
) -> None:
    """A redirect that ends in a refusal leaves no copy of the header in the error's history.

    ``ClientResponseError.history`` holds the responses that came before, each with its own request
    and so its own copy of the header -- a second carrier that redacting the final request info
    alone leaves untouched. It is the shape a login-page redirect takes.
    """
    base_url, requests = http_server
    key = "SUPER-SECRET-API-KEY"

    result = download_file(
        url=f"{base_url}/login-redirect",
        cache_dir=tmp_path,
        ttl=CacheExpiry.NO_CACHE,
        client_kwargs={"headers": {"Authorization": key}},
        cache_disable=True,
    )

    # the redirect was followed, so there was a history to scrub -- the first two of them, the 401
    # being retried once and so asking the whole chain again
    assert [request["path"] for request in requests[:2]] == ["/login-redirect", "/denied"]
    assert result.status == 401
    assert not result.content.history
    assert key not in _every_carrier_of(result.content)


def test_download_file_keeps_credentials_out_of_the_retry_log(
    http_server: tuple[str, list],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The credential does not reach stamina's retry hook, which logs a repr of what failed.

    That hook fires on the first failure of every retried download, before any handler here is
    reached, and ``repr`` of an aiohttp error renders the request info with its headers. So the
    error is scrubbed on the way into the retry as well as on the way out of it.
    """
    base_url, _ = http_server
    key = "SUPER-SECRET-API-KEY"

    with (
        stamina.set_testing(True, attempts=2),
        caplog.at_level(logging.DEBUG, logger="stamina"),
    ):
        result = download_file(
            url=f"{base_url}/boom",
            cache_dir=tmp_path,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs={"headers": {"Authorization": key}},
            cache_disable=True,
        )

    assert result.status == 500
    assert caplog.records, "stamina logged nothing, so this test would pass for the wrong reason"
    assert not [record for record in caplog.records if key in record.getMessage() + str(record.__dict__)]


def test_download_file_returns_a_dropped_connection_as_a_file(
    http_server: tuple[str, list],
    tmp_path: Path,
) -> None:
    """A server that hangs up is answered with a File, not with an exception through the caller.

    ServerDisconnectedError is none of the specific errors named above, and an exception leaving
    this way carries a traceback whose frames hold the caller's client kwargs -- credentials and
    all -- as locals.
    """
    base_url, _ = http_server
    key = "SUPER-SECRET-API-KEY"

    result = download_file(
        url=f"{base_url}/drop",
        cache_dir=tmp_path,
        ttl=CacheExpiry.NO_CACHE,
        client_kwargs={"headers": {"Authorization": key}},
        cache_disable=True,
    )

    assert result.status == 500
    assert isinstance(result.content, ServerDisconnectedError)
    assert key not in _every_carrier_of(result.content)


def test_post_file_asks_again_when_the_server_says_the_fault_is_its_own(http_server: tuple[str, list]) -> None:
    """A 5xx is a blip worth a second attempt, where a mint failing empties a whole query."""
    base_url, requests = http_server

    with stamina.set_testing(True, attempts=2):
        result = post_file(f"{base_url}/flaky")

    assert [request["path"] for request in requests] == ["/flaky", "/flaky"]
    assert result.status == 200
    assert json.loads(result.content.getvalue()) == {"access_token": "t"}


@pytest.mark.parametrize("path", ["/denied", "/rate-limited"])
def test_post_file_takes_an_answer_for_an_answer(path: str, http_server: tuple[str, list]) -> None:
    """A 401 will not become a 200 by asking again, and a 429 gets worse for being asked.

    The endpoints that rate-limit are rate-limiting a free account, so a second attempt a tenth of a
    second later is the wrong thing to do with one.
    """
    base_url, requests = http_server

    with stamina.set_testing(True, attempts=2):
        result = post_file(f"{base_url}{path}", auth=("user", "pa:ss"))

    assert len(requests) == 1
    assert result.status == _STATUS_BY_PATH[path]


def test_post_file_asks_again_when_the_body_stops_arriving(http_server: tuple[str, list]) -> None:
    """A body that stops mid-read is the same kind of blip as a connection that never carried one.

    ``ClientPayloadError`` subclasses ``ClientError`` directly rather than ``ClientConnectionError``,
    so it is named in its own right or it is taken for an answer.
    """
    base_url, requests = http_server

    with stamina.set_testing(True, attempts=2):
        result = post_file(f"{base_url}/truncated")

    assert [request["path"] for request in requests] == ["/truncated", "/truncated"]
    assert isinstance(result.content, ClientPayloadError)


def test_filesystem_key_separates_caching_from_not_caching(tmp_path: Path) -> None:
    """`cache_disable` decided what `register` built, and was not part of what it was filed under.

    `register` runs only for a key that is new, so the first caller in a thread decided for every
    later one -- and `CacheExpiry.METAINDEX` being an alias of `TWELVE_HOURS`, any earlier
    metaindex download from any provider was enough to leave a caching filesystem under that key.
    A later request made with caching disabled was then served from disk (GH-1947).
    """
    cached = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.METAINDEX, cache_disable=False)
    uncached = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.METAINDEX, cache_disable=True)

    assert isinstance(cached, WholeFileCacheFileSystem)
    assert not isinstance(uncached, WholeFileCacheFileSystem)
    # and asking again gives the same instance for each, which is what the registry is for
    assert (
        NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.METAINDEX, cache_disable=False)
        is cached
    )
    # the key names the instance in memory; where the blobs live is `_cache_path`, which separates
    # on the TTL and on who is asking, and on nothing else (GH-1959)
    assert cached.storage[-1] == str(tmp_path / "fsspec" / "v2-ttl-TWELVE_HOURS")


def test_filesystem_key_separates_one_cache_dir_from_another(tmp_path: Path) -> None:
    """`cache_dir` decided where blobs went and was not part of the key either.

    So a second `Settings` with a different `WD_CACHE_DIR` in the same process kept writing to the
    first one -- the same defect as `cache_disable`, and the one that made the tests here pass
    against whatever an earlier test had registered rather than against their own `tmp_path`.
    """
    other = tmp_path / "other"
    other.mkdir()

    first = NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=CacheExpiry.FIVE_MINUTES, cache_disable=False)
    second = NetworkFilesystemManager.get(cache_dir=other, cache_expiry=CacheExpiry.FIVE_MINUTES, cache_disable=False)

    assert first is not second
    assert first.storage[-1].startswith(str(tmp_path))
    assert second.storage[-1].startswith(str(other))


def test_a_directory_that_is_not_there_is_an_answer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A 404 stays `[]`, which is what every caller has always had it as."""

    def find(_self: object, _url: str, **_kwargs: object) -> list[str]:
        msg = "404"
        raise FileNotFoundError(msg)

    monkeypatch.setattr(HTTPFileSystem, "find", find)

    assert list_remote_files_fsspec("https://example.com/none/", Settings(cache_dir=tmp_path)) == []


def test_a_directory_that_could_not_be_read_is_not_an_answer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed walk used to arrive as an empty directory would, and be believed.

    `find` walks with `on_error="omit"`, which catches `(FileNotFoundError, OSError)` and returns
    nothing -- and aiohttp's `ClientOSError` is an `OSError`. So a connection reset was swallowed
    inside fsspec, never reached the retry wrapping this call, and every provider that lists had to
    decide what an empty list meant, which none of them could.
    """
    attempts = []

    def find(_self: object, _url: str, **kwargs: object) -> list[str]:
        attempts.append(kwargs)
        raise ClientOSError(104, "Connection reset by peer")

    monkeypatch.setattr(HTTPFileSystem, "find", find)

    with pytest.raises(ClientOSError):
        list_remote_files_fsspec("https://example.com/blip/", Settings(cache_dir=tmp_path))

    # the kwarg is the whole of it: with the default `on_error="omit"` the walk inside fsspec
    # catches this and returns nothing, so neither the retry nor the caller ever learns of it
    assert all(attempt["on_error"] == "raise" for attempt in attempts)
    # and the retry that always wrapped this call finally sees one
    assert len(attempts) > 1


def test_a_file_says_whether_it_came_off_the_wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A caller that cannot use what it was given needs to know whether asking again could differ.

    A cached body says nothing about what the server has now; one that has just been fetched cannot
    have changed in the meantime.

    Exercised against a real `WholeFileCacheFileSystem` rather than a stubbed `_check_file`, so the
    flag is decided by the predicate as it is actually called, over the URL as it is actually
    hashed -- a mocked answer would pass even if the question were the wrong one.
    """
    source = MemoryFileSystem()
    source.pipe_file("/a.txt", b"payload")
    caching = WholeFileCacheFileSystem(fs=source, cache_storage=str(tmp_path), expiry_time=3600)
    monkeypatch.setattr(NetworkFilesystemManager, "get", lambda **_kwargs: caching)

    first = download_file(url="/a.txt", cache_dir=tmp_path, ttl=CacheExpiry.TWELVE_HOURS)
    second = download_file(url="/a.txt", cache_dir=tmp_path, ttl=CacheExpiry.TWELVE_HOURS)

    assert first.from_cache is False
    assert second.from_cache is True
    assert first.content.read() == second.content.read() == b"payload"


def test_a_file_fetched_without_a_cache_never_claims_otherwise(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A plain filesystem holds nothing to have served, so the flag is false however often it is asked."""
    monkeypatch.setattr(HTTPFileSystem, "cat_file", lambda _self, _url, **_kw: b"payload")

    url = "https://example.com/b.txt"
    first = download_file(url=url, cache_dir=tmp_path, ttl=CacheExpiry.NO_CACHE)
    second = download_file(url=url, cache_dir=tmp_path, ttl=CacheExpiry.NO_CACHE)

    assert first.from_cache is False
    assert second.from_cache is False


def test_a_listing_made_offline_degrades_as_the_rest_of_the_library_does(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Being offline is not this listing failing to read; it is every path being offline.

    A download comes back carrying `NoInternetError` for `raise_if_exception` to log at debug, and
    providers answer with empty frames -- `dmi`, `rmi`, `smhi`, `nws` and `fmi` all rely on it. A
    listing has no `File` to carry that in, so raising here would make the one path that lists abort
    with an aiohttp traceback where every other path degrades quietly.
    """
    from unittest.mock import Mock  # noqa: PLC0415

    def find(_self: object, _url: str, **_kwargs: object) -> list[str]:
        raise ClientConnectorError(Mock(ssl=None, host="opendata.dwd.de", port=443), OSError("offline"))

    monkeypatch.setattr(HTTPFileSystem, "find", find)

    assert list_remote_files_fsspec("https://example.com/offline/", Settings(cache_dir=tmp_path)) == []


def test_a_cache_that_cannot_be_read_is_scrubbed_like_a_failed_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The cache probe reaches the disk, so it belongs inside the handler that scrubs credentials.

    `_mkcache` can raise on a read-only or full cache dir and the metadata load on a truncated
    file. Outside the `try`, such an exception skipped `_without_credentials` entirely -- and that
    scrubbing is load-bearing rather than belt and braces, because stamina's retry hook logs
    `repr(caused_by)` on the first failure, before any handler below is reached.
    """
    scrubbed: list[str] = []

    def check_file(_self: object, _url: str) -> bool:
        msg = "cache dir is read-only"
        raise PermissionError(msg)

    def without_credentials(error: Exception, *, sent_credentials: bool) -> Exception:
        scrubbed.append(type(error).__name__)
        assert sent_credentials is True
        return error

    monkeypatch.setattr(WholeFileCacheFileSystem, "_check_file", check_file)
    monkeypatch.setattr(network, "_without_credentials", without_credentials)

    with pytest.raises(PermissionError):
        download_file(
            url="https://example.com/secret.txt",
            cache_dir=tmp_path,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs={"headers": {"Authorization": "Bearer hunter2"}},
        )

    # the probe's failure went through the scrubber, as a failed read always has
    assert scrubbed == ["PermissionError"]


@pytest.fixture
def _fresh_cache_sweeps() -> Iterator[None]:
    """Let each test meet a process that has swept nothing yet."""
    _reclaim_done.clear()
    _swept_dirs.clear()
    yield
    _reclaim_done.clear()
    _swept_dirs.clear()


def _blob_dir(
    cache_dir: Path,
    cache_expiry: CacheExpiry = CacheExpiry.TWELVE_HOURS,
    client_kwargs: dict | None = None,
) -> Path:
    """Where a caching filesystem built from these settings actually writes its blobs."""
    filesystem = NetworkFilesystemManager.get(
        cache_dir=cache_dir,
        cache_expiry=cache_expiry,
        client_kwargs=client_kwargs,
        cache_disable=False,
    )
    return Path(filesystem.storage[-1])


def _in_a_fresh_thread(call: Callable[[], object]) -> object:
    """Run ``call`` where the filesystem registry is empty, since that registry is thread-local.

    Which is how a second process-first registration is reached without reaching into the registry:
    a new thread has to build its own filesystem, and so takes every path `register` takes.
    """
    outcome: dict[str, object] = {}

    def run() -> None:
        try:
            outcome["value"] = call()
        except BaseException as error:  # noqa: BLE001
            outcome["error"] = error

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def _seed_blob(storage: Path, *, expiry_time: float) -> list[Path]:
    """Fetch one file into ``storage`` through a real caching filesystem, and return what it wrote."""
    source = MemoryFileSystem()
    source.pipe_file("/seeded.txt", b"payload")
    WholeFileCacheFileSystem(fs=source, cache_storage=str(storage), expiry_time=expiry_time).cat_file("/seeded.txt")
    return sorted(path for path in storage.iterdir() if path.name != "cache")


def _age(directory: Path, *, days: float, marker: bool = True) -> None:
    """Backdate a blob directory, and by default the marker that says when it was last asked for."""
    when = time.time() - days * 24 * 3600
    for path in directory.rglob("*"):
        if marker or path.name != ".last-used":
            os.utime(path, (when, when))
    os.utime(directory, (when, when))


def _age_metadata(storage: Path, seconds: float) -> None:
    """Backdate every entry of an on-disk cache, which is all an old cache is."""
    metadata_path = storage / "cache"
    metadata = json.loads(metadata_path.read_text())
    for detail in metadata.values():
        detail["time"] -= seconds
    metadata_path.write_text(json.dumps(metadata))


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_the_blob_directory_does_not_move_when_the_version_does(tmp_path: Path) -> None:
    """A release must not rename the cache out from under itself (GH-1959).

    The default ``client_kwargs`` carries a User-Agent with the version in it. While the whole of
    ``client_kwargs`` was hashed into the directory name, every release began from an empty cache
    and left the previous one behind unreachable -- 98 distinct hashes and 4.2 GB on one developer
    machine, of which 115 MB was reachable.
    """
    client_kwargs = Settings(cache_dir=tmp_path).fsspec_client_kwargs
    user_agent = client_kwargs["headers"]["User-Agent"]
    next_release = {**client_kwargs, "headers": {**client_kwargs["headers"], "User-Agent": f"{user_agent}-next"}}

    assert _blob_dir(tmp_path, client_kwargs=client_kwargs) == _blob_dir(tmp_path, client_kwargs=next_release)


@pytest.mark.usefixtures("_fresh_cache_sweeps")
@pytest.mark.parametrize(
    "client_kwargs",
    [
        None,
        {},
        {"timeout": 30},
        {"timeout": 999},
        {"headers": {"User-Agent": "anything at all"}},
        {"trust_env": True},
    ],
    ids=["none", "empty", "timeout", "other-timeout", "user-agent", "trust-env"],
)
def test_transport_settings_do_not_name_a_blob_directory(tmp_path: Path, client_kwargs: dict | None) -> None:
    """How a request is made decides nothing about what comes back, so it may not separate blobs.

    This is the rule ``use_certifi`` was already held to. ``client_kwargs`` is the one input
    carrying identity and transport together, and so the one that was not held to it.
    """
    assert _blob_dir(tmp_path, client_kwargs=client_kwargs) == tmp_path / "fsspec" / "v2-ttl-TWELVE_HOURS"


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_two_credentials_do_not_share_a_blob_directory(tmp_path: Path) -> None:
    """A body fetched with one API key is not a body another may be handed back."""
    first = _blob_dir(tmp_path, client_kwargs={"timeout": 30, "headers": {"Authorization": "Bearer aaa"}})
    second = _blob_dir(tmp_path, client_kwargs={"timeout": 30, "headers": {"Authorization": "Bearer bbb"}})

    assert first != second
    # and neither is the directory an unauthenticated request reads
    assert _blob_dir(tmp_path) not in {first, second}


@pytest.mark.usefixtures("_fresh_cache_sweeps")
@pytest.mark.parametrize("header", ["Authorization", "api_key", "X-Api-Key", "Proxy-Authorization"])
def test_a_credential_under_any_known_header_name_separates_blobs(tmp_path: Path, header: str) -> None:
    """AEMET sends its key as ``api_key`` rather than ``Authorization``; both are credentials."""
    assert _blob_dir(tmp_path, client_kwargs={"headers": {header: "secret"}}) != _blob_dir(tmp_path)


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_the_registry_still_separates_what_a_filesystem_is_built_from(tmp_path: Path) -> None:
    """The in-memory key is not the disk path, and must keep every input the disk path drops.

    ``register`` runs only for a key that is new, so whatever that key omits, the first caller in a
    thread decides for every later one -- which is how one provider's ``Authorization`` header came
    to be reused for the next caller's request (GH-1947). Transport settings belong in it for the
    same reason they do not belong in a directory name.
    """
    instances = [
        NetworkFilesystemManager.get(
            cache_dir=tmp_path,
            cache_expiry=CacheExpiry.TWELVE_HOURS,
            client_kwargs=client_kwargs,
            cache_disable=False,
        )
        for client_kwargs in ({"timeout": 30}, {"timeout": 999}, {"headers": {"Authorization": "Bearer aaa"}})
    ]

    assert len({id(instance) for instance in instances}) == 3
    # while two of the three share a directory, because a timeout changes nothing about the bytes
    assert instances[0].storage[-1] == instances[1].storage[-1] != instances[2].storage[-1]


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_directories_of_an_earlier_layout_are_reclaimed(tmp_path: Path) -> None:
    """Nothing can reach a directory the current key cannot name, so nothing can expire it either."""
    fsspec_root = tmp_path / "fsspec"
    fsspec_root.mkdir()
    legacy = [
        fsspec_root / "ttl-TWELVE_HOURS-6a88018f",
        fsspec_root / "ttl-FIVE_MINUTES",
        fsspec_root / "ttl-INFINITE-cf205963",
        # and a layout that does not exist yet, which a build of this one still cannot read
        fsspec_root / "v9-ttl-TWELVE_HOURS",
    ]
    for directory in legacy:
        directory.mkdir()
        (directory / "blob").write_bytes(b"x" * 16)

    _blob_dir(tmp_path)

    assert not any(directory.exists() for directory in legacy)


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_the_reclaim_keeps_the_live_layout_and_anything_it_does_not_recognise(tmp_path: Path) -> None:
    """It removes one layout by name, rather than everything that is not in use right now."""
    fsspec_root = tmp_path / "fsspec"
    fsspec_root.mkdir()
    # a live directory of the current layout, for a TTL this call is not asking for
    other_live = fsspec_root / "v2-ttl-FIVE_MINUTES"
    other_live.mkdir()
    # and something that is not a blob directory at all
    stranger = fsspec_root / "notes.txt"
    stranger.write_text("not mine")

    _blob_dir(tmp_path)

    assert other_live.is_dir()
    assert stranger.is_file()


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_the_reclaim_runs_once_per_cache_root(tmp_path: Path) -> None:
    """A directory created after the sweep survives, which is what proves it did not run again."""
    _blob_dir(tmp_path)
    assert tmp_path / "fsspec" in _reclaim_done

    later = tmp_path / "fsspec" / "ttl-TWELVE_HOURS-deadbeef"
    later.mkdir()
    _in_a_fresh_thread(lambda: _blob_dir(tmp_path))

    assert later.is_dir()


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_the_reclaim_survives_a_directory_it_cannot_remove(tmp_path: Path) -> None:
    """A cache that cannot be tidied must still be a cache that can be read."""
    fsspec_root = tmp_path / "fsspec"
    fsspec_root.mkdir()
    (fsspec_root / "ttl-TWELVE_HOURS").mkdir()

    with patch("wetterdienst.util.network.shutil.rmtree", side_effect=OSError("permission denied")):
        storage = _blob_dir(tmp_path)

    assert storage == fsspec_root / "v2-ttl-TWELVE_HOURS"


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_an_infinite_cache_is_never_swept(tmp_path: Path) -> None:
    """The sweep that looked like the whole fix destroys exactly the caches worth keeping (GH-1955).

    ``CacheExpiry.INFINITE`` is ``False``, ``int(False)`` is ``0``, and fsspec reads an expiry of
    zero as "every entry is expired": it removes them all and then ``rmtree``s the directory.
    ``lhmt`` and both ``meteofrance`` providers use ``INFINITE`` for immutable archives, so the
    first such download in a fresh process would have thrown the archive away and re-fetched it.
    """
    storage = tmp_path / "fsspec" / "v2-ttl-INFINITE"
    blobs = _seed_blob(storage, expiry_time=0)
    assert blobs
    # as old as it likes: nothing about an immutable archive goes stale
    _age_metadata(storage, seconds=10 * 365 * 24 * 3600)

    assert _blob_dir(tmp_path, CacheExpiry.INFINITE) == storage
    assert all(blob.is_file() for blob in blobs)


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_a_blob_its_own_ttl_has_expired_is_swept(tmp_path: Path) -> None:
    """The leak this closes: a five-minute blob was kept for as long as the disk lasted."""
    storage = tmp_path / "fsspec" / "v2-ttl-FIVE_MINUTES"
    blobs = _seed_blob(storage, expiry_time=CacheExpiry.FIVE_MINUTES.value)
    assert blobs
    _age_metadata(storage, seconds=CacheExpiry.FIVE_MINUTES.value * 2)

    _blob_dir(tmp_path, CacheExpiry.FIVE_MINUTES)

    assert not any(blob.exists() for blob in blobs)


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_a_blob_still_within_its_ttl_survives_the_sweep(tmp_path: Path) -> None:
    """Sweeping is for what the TTL has already made useless, and for nothing else."""
    storage = tmp_path / "fsspec" / "v2-ttl-TWELVE_HOURS"
    blobs = _seed_blob(storage, expiry_time=CacheExpiry.TWELVE_HOURS.value)
    assert blobs

    _blob_dir(tmp_path, CacheExpiry.TWELVE_HOURS)

    assert all(blob.is_file() for blob in blobs)


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_a_sweep_that_fails_is_not_retried_and_does_not_fail_the_download(tmp_path: Path) -> None:
    """``clear_expired`` raises for a half-written entry -- the case most worth surviving.

    Marked before the attempt rather than after, so one corrupt row cannot fail every download for
    this TTL for the life of the process.
    """
    attempts: list[str] = []

    def clear_expired_cache(_self: object, expiry_time: float | None = None) -> None:  # noqa: ARG001
        attempts.append("swept")
        msg = "Cache metadata does not contain 'fn' for https://example.com/half-written"
        raise RuntimeError(msg)

    with patch.object(WholeFileCacheFileSystem, "clear_expired_cache", clear_expired_cache):
        first = _blob_dir(tmp_path)
        second = _in_a_fresh_thread(lambda: _blob_dir(tmp_path))

    assert attempts == ["swept"]
    assert first == second == tmp_path / "fsspec" / "v2-ttl-TWELVE_HOURS"


@pytest.mark.usefixtures("_fresh_cache_sweeps")
@pytest.mark.parametrize("cache_expiry", list(CacheExpiry))
def test_fsspec_is_never_handed_an_expiry_it_reads_as_zero(tmp_path: Path, cache_expiry: CacheExpiry) -> None:
    """The one number that must never reach ``clear_expired_cache``, from any TTL the library has.

    fsspec substitutes ``self.expiry`` for a falsy argument, and for an ``INFINITE`` cache that is
    ``int(False)`` -- zero, which it reads as "every entry is expired". So the expiry is passed
    explicitly rather than left to that fallback, and a TTL that cannot produce a positive one is
    not swept at all.
    """
    seen: list[object] = []

    def clear_expired_cache(_self: object, expiry_time: float | None = None) -> None:
        seen.append(expiry_time)

    with patch.object(WholeFileCacheFileSystem, "clear_expired_cache", clear_expired_cache):
        # not `_blob_dir`: `NO_CACHE` is answered with a plain filesystem that has no storage at all
        NetworkFilesystemManager.get(cache_dir=tmp_path, cache_expiry=cache_expiry, cache_disable=False)

    unsafe = [
        expiry
        for expiry in seen
        if not (isinstance(expiry, (int, float)) and not isinstance(expiry, bool) and expiry > 0)
    ]
    assert unsafe == []


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_no_thread_reaches_a_directory_while_it_is_being_swept(tmp_path: Path) -> None:
    """The lock is held across the sweep, not merely around the bookkeeping that records it.

    ``clear_expired`` works from the snapshot its filesystem loaded and saves that snapshot back, so
    a sweep running beside a ``download_files`` thread pool would drop rows its siblings had just
    written and orphan their blobs -- the very leak this closes. Every path to a download in this
    directory passes through the sweep first, so a second thread is made to wait for it.
    """
    sweeping = threading.Event()
    may_finish = threading.Event()
    arrived = threading.Event()
    sweeps: list[str] = []

    def clear_expired_cache(_self: object, expiry_time: float | None = None) -> None:  # noqa: ARG001
        sweeps.append("swept")
        sweeping.set()
        may_finish.wait(timeout=10)

    def second_caller() -> None:
        _blob_dir(tmp_path)
        arrived.set()

    with patch.object(WholeFileCacheFileSystem, "clear_expired_cache", clear_expired_cache):
        sweeper = threading.Thread(target=lambda: _blob_dir(tmp_path))
        sweeper.start()
        assert sweeping.wait(timeout=10), "the first caller never started sweeping"
        other = threading.Thread(target=second_caller)
        other.start()
        try:
            # it has no filesystem for this directory yet, and so nothing to download through
            assert not arrived.wait(timeout=0.5)
        finally:
            may_finish.set()
        sweeper.join(timeout=10)
        other.join(timeout=10)

    # and once let go it gets one, without sweeping a directory that has just been swept
    assert arrived.is_set()
    assert sweeps == ["swept"]


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_the_directory_of_a_rotated_credential_is_reclaimed(tmp_path: Path) -> None:
    """Keying a directory on a secret means a new directory each time the secret changes.

    Met Office mints a three-day JWT, so that provider renames its blob directory twice a week and
    would otherwise leave the previous one behind for good -- the same unbounded leak as GH-1959,
    on a faster clock. Aged out by when something last asked for the directory, which is a thing
    the blobs cannot say: an archive read on every run and written on none has file times as old
    as the day it was fetched.
    """
    rotated = _blob_dir(tmp_path, client_kwargs={"headers": {"Authorization": "Bearer last-week"}})
    (rotated / "blob").write_bytes(b"x" * 16)
    _age(rotated, days=31)

    _reclaim_done.clear()
    _blob_dir(tmp_path, client_kwargs={"headers": {"Authorization": "Bearer this-week"}})

    assert not rotated.exists()


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_a_credentialed_directory_still_being_asked_for_is_kept(tmp_path: Path) -> None:
    """What ages a directory out is nothing asking for it, not nothing writing to it.

    A fully cached archive behind a long-lived credential is read on every run and written on none,
    so its blobs look as old as the day they were fetched however heavily it is used.
    """
    client_kwargs = {"headers": {"Authorization": "Bearer long-lived"}}
    live = _blob_dir(tmp_path, client_kwargs=client_kwargs)
    (live / "blob").write_bytes(b"x" * 16)
    # every file in it is a month old, including the blobs; only the marker says otherwise
    _age(live, days=31, marker=False)

    _reclaim_done.clear()
    _blob_dir(tmp_path, client_kwargs={"headers": {"Authorization": "Bearer someone-else"}})

    assert live.is_dir()


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_a_shared_directory_is_never_aged_out(tmp_path: Path) -> None:
    """The unsuffixed directories are named on every run, so idleness says nothing about them.

    And they are where the DWD and every other open provider keep everything, so reclaiming one for
    looking idle would throw away the main cache rather than a leftover.
    """
    shared = _blob_dir(tmp_path, CacheExpiry.FIVE_MINUTES)
    (shared / "blob").write_bytes(b"x" * 16)
    _age(shared, days=400)

    _reclaim_done.clear()
    _blob_dir(tmp_path, CacheExpiry.TWELVE_HOURS)

    assert shared.is_dir()


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_the_directory_being_registered_is_never_reclaimed(tmp_path: Path) -> None:
    """However old it looks, the caller is about to write to it.

    Ordinarily the mark written on the way in is what saves it, so this takes that away: marking is
    best-effort -- a read-only cache dir logs and carries on -- and a directory being handed to a
    caller is not one to remove whether or not its marker could be written.
    """
    client_kwargs = {"headers": {"Authorization": "Bearer mine"}}
    mine = _blob_dir(tmp_path, client_kwargs=client_kwargs)
    (mine / "blob").write_bytes(b"x" * 16)
    _age(mine, days=400)

    _reclaim_done.clear()
    with patch.object(network, "_mark_cache_dir_used", lambda _path: None):
        again = _in_a_fresh_thread(lambda: _blob_dir(tmp_path, client_kwargs=client_kwargs))

    assert again == mine
    assert mine.is_dir()


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_a_directory_that_has_just_been_used_says_so(tmp_path: Path) -> None:
    """The mark has to survive the sweep that runs beside it.

    A sweep that leaves the cache empty has fsspec ``rmtree`` the whole directory and rebuild it,
    which takes an already-written marker with it -- and a directory whose marker is missing reads
    as one nothing has asked for in a month, which is how a live cache would be reclaimed.
    """
    storage = _blob_dir(tmp_path, client_kwargs={"headers": {"Authorization": "Bearer mine"}})

    assert (storage / ".last-used").is_file()


@pytest.mark.parametrize(
    ("name", "superseded"),
    [
        ("ttl-TWELVE_HOURS", True),
        ("ttl-TWELVE_HOURS-6a88018f", True),
        ("v1-ttl-TWELVE_HOURS", True),
        ("v9-ttl-TWELVE_HOURS-6a88018f", True),
        ("v2-ttl-TWELVE_HOURS", False),
        ("v2-ttl-TWELVE_HOURS-6a88018f", False),
        ("notes.txt", False),
        ("v2-ttl-lowercase", False),
    ],
)
def test_every_layout_but_the_current_one_is_superseded(name: str, *, superseded: bool) -> None:
    """What makes the layout version self-cleaning, rather than one more thing left behind.

    Matching only the layout immediately before this one would mean the next bump strands every
    directory this one wrote -- the same unbounded leak as GH-1959, just deferred. A build reclaims
    what any other layout wrote, in both directions, so alternating between two versions costs a
    re-download rather than directories neither of them will ever collect.
    """
    assert _is_superseded_layout(name) is superseded


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_a_credential_sent_as_a_pair_list_is_still_a_credential(tmp_path: Path) -> None:
    """Aiohttp takes headers as a mapping or as an iterable of pairs, and both carry credentials.

    Read as a mapping only, a pair list yields no credential at all -- so two API keys shared one
    blob directory, and a failure carrying one of them went unscrubbed into the retry log.
    """
    first = {"headers": [("Authorization", "Bearer aaa")]}
    second = {"headers": [("Authorization", "Bearer bbb")]}

    assert _blob_dir(tmp_path, client_kwargs=first) != _blob_dir(tmp_path, client_kwargs=second)
    assert _blob_dir(tmp_path, client_kwargs=first) != _blob_dir(tmp_path)
    assert _sends_credentials(first) is True


@pytest.mark.usefixtures("_fresh_cache_sweeps")
def test_headers_that_cannot_be_read_never_share_the_unauthenticated_directory(tmp_path: Path) -> None:
    """Both readers of this question fail dangerously on a false negative.

    Answering "no credentials" for a shape that cannot be read files an authenticated body exactly
    where an unauthenticated request looks for one, and lets a failure carrying the header through
    the scrubber unchanged. So an unreadable shape counts as carrying one.
    """
    unreadable = {"headers": object()}

    assert _credential_headers(unreadable) is None
    assert _sends_credentials(unreadable) is True
    assert _blob_dir(tmp_path, client_kwargs=unreadable) != _blob_dir(tmp_path)
    # and the same directory every time, rather than a new one per process
    assert _blob_dir(tmp_path, client_kwargs=unreadable) == _blob_dir(tmp_path, client_kwargs={"headers": object()})


@pytest.mark.parametrize("cache_expiry", list(CacheExpiry))
@pytest.mark.parametrize(
    "client_kwargs", [None, {"headers": {"Authorization": "Bearer aaa"}}], ids=["shared", "credentialed"]
)
def test_every_directory_this_writes_is_one_the_reclaim_can_recognise(
    tmp_path: Path,
    cache_expiry: CacheExpiry,
    client_kwargs: dict | None,
) -> None:
    """The matcher has to cover what `_cache_path` actually produces, for every TTL there is.

    Asserted against the enum rather than against a pattern written beside it, because the two
    drifting apart is silent: a directory the matcher does not recognise is simply never reclaimed,
    which is the defect this whole change is about. A TTL name carrying a digit was the case that
    did not match when this was first written.
    """
    filesystem = NetworkFilesystemManager.get(
        cache_dir=tmp_path,
        cache_expiry=cache_expiry,
        client_kwargs=client_kwargs,
        cache_disable=False,
    )
    if cache_expiry is CacheExpiry.NO_CACHE:
        # answered with a plain filesystem, which writes no blobs and so names no directory
        assert not isinstance(filesystem, WholeFileCacheFileSystem)
        return
    name = Path(filesystem.storage[-1]).name

    assert _BLOB_CACHE_DIR.match(name), name
    assert not _is_superseded_layout(name), name
    # and a credentialed one is aged out like any other, where a shared one is never aged out
    assert bool(_IDENTITY_CACHE_DIR.match(name)) is (client_kwargs is not None), name
