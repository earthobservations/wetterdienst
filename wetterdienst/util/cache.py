# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
import sys
from enum import Enum

import appdirs

# FSSPEC aiohttp client kwargs, may be used to pass extra arguments
# such as proxies etc to aiohttp
FSSPEC_CLIENT_KWARGS = {}

# Whether caching should be disabled at all.
WD_CACHE_DISABLE = "WD_CACHE_DISABLE" in os.environ

# Configure cache directory.
try:
    cache_dir = os.environ["WD_CACHE_DIR"]
except KeyError:
    cache_dir = appdirs.user_cache_dir(appname="wetterdienst")

# Early reporting.
if WD_CACHE_DISABLE:
    sys.stderr.write("INFO: Wetterdienst cache is disabled\n")


class CacheExpiry(Enum):
    """
    Describe some convenient caching expiry presets.
    This is part of the new network i/o subsystem based on FSSPEC.
    """

    INFINITE = False
    NO_CACHE = 0.01
    FIVE_SECONDS = 5
    ONE_MINUTE = 60 * 1
    FIVE_MINUTES = 60 * 5
    ONE_HOUR = 60 * 60
    TWELVE_HOURS = 60 * 60 * 12

    METAINDEX = TWELVE_HOURS
    FILEINDEX = FIVE_MINUTES
