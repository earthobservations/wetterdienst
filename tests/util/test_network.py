# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.network import NetworkFilesystemManager


def test_create_fsspec_filesystem():
    fs1 = NetworkFilesystemManager.get(settings=Settings(), ttl=CacheExpiry.METAINDEX)
    fs2 = NetworkFilesystemManager.get(settings=Settings(), ttl=CacheExpiry.METAINDEX)
    assert id(fs1) == id(fs2)
