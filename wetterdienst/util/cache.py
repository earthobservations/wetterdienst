# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import os
import platform
import sys
from enum import Enum

import appdirs
from dogpile.cache import make_region
from dogpile.cache.util import kwarg_function_key_generator

log = logging.getLogger()

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
else:
    sys.stderr.write("INFO: Wetterdienst cache directory is %s\n" % cache_dir)

# Ensure cache directories exist.
# FIXME: Get rid of this as it executes "os.makedirs()" on the module level.
#        This is not really good style but it is needed for the dogpile setup.
if not WD_CACHE_DISABLE:
    cache_directories = [
        os.path.join(cache_dir, "dogpile"),
        os.path.join(cache_dir, "fsspec"),
    ]
    for cache_directory in cache_directories:
        if not os.path.exists(cache_directory):
            os.makedirs(cache_directory, exist_ok=True)

# Configure cache backend.
# TODO: Make cache backend configurable, e.g. optionally use Redis for running
#       in multi-threaded environments.
platform = platform.system()
backend = "dogpile.cache.dbm"
# Python on Windows has no "fcntl", which is required by the dbm backend.
if WD_CACHE_DISABLE or platform == "Windows":
    backend = "dogpile.cache.memory"


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


# Define cache regions.
metaindex_cache = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "dogpile", "metaindex.dbm")},
)

fileindex_cache_five_minutes = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 5,
    arguments={"filename": os.path.join(cache_dir, "dogpile", "fileindex_5m.dbm")},
)

fileindex_cache_twelve_hours = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "dogpile", "fileindex_12h.dbm")},
)

payload_cache_twelve_hours = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "dogpile", "payload_12h.dbm")},
)
