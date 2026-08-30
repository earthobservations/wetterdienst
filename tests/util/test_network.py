# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for network utilities."""

import pickle
import time
from collections.abc import Iterator, MutableMapping
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import stamina
from aiohttp import ClientConnectorError, ClientResponseError, ClientTimeout
from diskcache import Cache
from fsspec.exceptions import FSTimeoutError

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.network import (
    File,
    FileDirCache,
    HTTPFileSystem,
    NetworkFilesystemManager,
    _legacy_cleanup_done,
    download_file,
    list_remote_directory_fsspec,
    list_remote_files_fsspec,
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


def test_download_file_retries_on_429_and_succeeds() -> None:
    """download_file() retries on HTTP 429 and returns the file on the second attempt."""
    error_429 = ClientResponseError(request_info=MagicMock(), history=(), status=429)
    payload = b"data"

    mock_fs = MagicMock()
    mock_fs.cat_file.side_effect = [error_429, payload]

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
