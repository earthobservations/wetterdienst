# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for network utilities."""

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.network import NetworkFilesystemManager


def test_create_fsspec_filesystem() -> None:
    """Test if a fsspec filesystem can be created."""
    default_settings = Settings()
    fs1 = NetworkFilesystemManager.get(
        cache_dir=default_settings.cache_dir,
        ttl=CacheExpiry.METAINDEX,
        client_kwargs=default_settings.fsspec_client_kwargs,
        cache_disable=default_settings.cache_disable,
    )
    fs2 = NetworkFilesystemManager.get(
        cache_dir=default_settings.cache_dir,
        ttl=CacheExpiry.METAINDEX,
        client_kwargs=default_settings.fsspec_client_kwargs,
        cache_disable=default_settings.cache_disable,
    )
    assert id(fs1) == id(fs2)
