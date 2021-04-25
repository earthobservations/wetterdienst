# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import NetworkFilesystemManager


def test_create_fsspec_filesystem():
    fs1 = NetworkFilesystemManager.get(ttl=CacheExpiry.METAINDEX)
    fs2 = NetworkFilesystemManager.get(ttl=CacheExpiry.METAINDEX)

    assert id(fs1) == id(fs2)
