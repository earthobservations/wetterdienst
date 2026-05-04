# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for network utilities."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import ClientConnectorError

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.network import File, NetworkFilesystemManager, download_file


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
