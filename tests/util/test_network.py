# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for network utilities."""

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.network import NetworkFilesystemManager


def test_create_fsspec_filesystem() -> None:
    """Test if a fsspec filesystem can be created."""
    fs1 = NetworkFilesystemManager.get(settings=Settings(), ttl=CacheExpiry.METAINDEX)
    fs2 = NetworkFilesystemManager.get(settings=Settings(), ttl=CacheExpiry.METAINDEX)
    assert id(fs1) == id(fs2)
