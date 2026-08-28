# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for network utilities."""

import pickle
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import fsspec
import pytest
import stamina
from aiohttp import ClientConnectorError, ClientResponseError
from fsspec.exceptions import FSTimeoutError

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.network import (
    File,
    FileDirCache,
    NetworkFilesystemManager,
    download_file,
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


def test_file_dir_cache_stores_and_returns_listings(tmp_path: Path) -> None:
    """FileDirCache stores listings on disk and returns them again."""
    listing = [{"name": "https://example.com/dir/a.txt", "size": 1, "type": "file"}]
    cache = FileDirCache(listings_expiry_time=300, use_listings_cache=True, listings_cache_location=tmp_path)
    cache["https://example.com/dir/"] = listing

    assert "https://example.com/dir/" in cache
    assert cache["https://example.com/dir/"] == listing
    assert list(cache) == ["https://example.com/dir/"]
    assert len(cache) == 1


def test_file_dir_cache_persists_between_instances(tmp_path: Path) -> None:
    """FileDirCache listings survive a new instance pointing at the same location."""
    listing = [{"name": "https://example.com/dir/a.txt", "size": 1, "type": "file"}]
    cache = FileDirCache(listings_expiry_time=300, use_listings_cache=True, listings_cache_location=tmp_path)
    cache["https://example.com/dir/"] = listing

    other = FileDirCache(listings_expiry_time=300, use_listings_cache=True, listings_cache_location=tmp_path)

    assert other["https://example.com/dir/"] == listing


def test_file_dir_cache_infinite_expiry_does_not_expire(tmp_path: Path) -> None:
    """A falsy expiry, as with CacheExpiry.INFINITE, means listings never expire."""
    listing = [{"name": "https://example.com/dir/a.txt", "size": 1, "type": "file"}]
    cache = FileDirCache(
        listings_expiry_time=CacheExpiry.INFINITE.value,
        use_listings_cache=True,
        listings_cache_location=tmp_path,
    )
    cache["https://example.com/dir/"] = listing

    assert cache.listings_expiry_time is None
    assert "https://example.com/dir/" in cache
    assert cache["https://example.com/dir/"] == listing


def test_file_dir_cache_expires_listings(tmp_path: Path) -> None:
    """FileDirCache drops listings once their expiry time has passed."""
    listing = [{"name": "https://example.com/dir/a.txt", "size": 1, "type": "file"}]
    cache = FileDirCache(listings_expiry_time=0.1, use_listings_cache=True, listings_cache_location=tmp_path)
    cache["https://example.com/dir/"] = listing
    time.sleep(0.2)

    assert "https://example.com/dir/" not in cache
    assert list(cache) == []
    assert len(cache) == 0
    with pytest.raises(KeyError):
        _ = cache["https://example.com/dir/"]


def test_file_dir_cache_disabled_does_not_touch_disk(tmp_path: Path) -> None:
    """A disabled FileDirCache neither caches listings nor creates anything on disk."""
    cache = FileDirCache(listings_expiry_time=0.0, use_listings_cache=False, listings_cache_location=tmp_path)
    cache["https://example.com/dir/"] = [{"name": "https://example.com/dir/a.txt"}]

    assert "https://example.com/dir/" not in cache
    assert list(cache) == []
    assert len(cache) == 0
    assert cache.cache_location is None
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(KeyError):
        _ = cache["https://example.com/dir/"]


def test_file_dir_cache_unusable_location_falls_back_to_no_caching(tmp_path: Path) -> None:
    """An unusable cache location disables the listings cache instead of raising."""
    with patch("diskcache.Cache", side_effect=OSError("read-only file system")):
        cache = FileDirCache(listings_expiry_time=300, use_listings_cache=True, listings_cache_location=tmp_path)
    cache["https://example.com/dir/"] = [{"name": "https://example.com/dir/a.txt"}]

    assert "https://example.com/dir/" not in cache
    assert cache.cache_location is None
    with pytest.raises(KeyError):
        _ = cache["https://example.com/dir/"]


def test_file_dir_cache_is_picklable(tmp_path: Path) -> None:
    """FileDirCache can be pickled, as fsspec filesystems may be sent to other processes."""
    listing = [{"name": "https://example.com/dir/a.txt", "size": 1, "type": "file"}]
    cache = FileDirCache(listings_expiry_time=300, use_listings_cache=True, listings_cache_location=tmp_path)
    cache["https://example.com/dir/"] = listing

    restored = pickle.loads(pickle.dumps(cache))  # noqa: S301

    assert restored.use_listings_cache is True
    assert restored.listings_expiry_time == 300.0
    assert restored.cache_location == cache.cache_location
    assert restored["https://example.com/dir/"] == listing


def test_list_remote_files_fsspec_reuses_cached_listing(tmp_path: Path) -> None:
    """Listings are read back from disk, even by a freshly created filesystem instance."""
    url = "https://example.com/dir/"
    listing = [{"name": "https://example.com/dir/a.txt", "size": 1, "type": "file"}]
    calls = []

    async def fake_ls_real(self, url: str, detail: bool = True, **kwargs) -> list[dict]:  # noqa: ANN001, ANN003, ARG001, FBT001, FBT002
        calls.append(url)
        return listing

    settings = Settings(cache_dir=tmp_path)
    with patch("fsspec.implementations.http.HTTPFileSystem._ls_real", fake_ls_real):
        assert list_remote_files_fsspec(url, settings, CacheExpiry.FILEINDEX) == [listing[0]["name"]]
        # drop the fsspec instance cache so that a new filesystem, with a new FileDirCache, is built
        fsspec.spec.AbstractFileSystem._cache.clear()  # noqa: SLF001
        assert list_remote_files_fsspec(url, settings, CacheExpiry.FILEINDEX) == [listing[0]["name"]]

    assert calls == [url]


def test_network_filesystem_manager_does_not_create_listings_cache(tmp_path: Path) -> None:
    """Filesystems for downloads don't cache listings, so they must not create a listings cache folder."""
    settings = Settings(cache_dir=tmp_path)
    NetworkFilesystemManager.register(
        cache_dir=tmp_path,
        cache_expiry=CacheExpiry.METAINDEX,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=True,
    )

    assert list(tmp_path.iterdir()) == []
