# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import os
import platform

import appdirs
from dogpile.cache import make_region
from dogpile.cache.util import kwarg_function_key_generator

log = logging.getLogger()

# Python on Windows has no "fcntl", which is required by the dbm backend.
# TODO: Make cache backend configurable, e.g. optionally use Redis for running
#       in multi-threaded environments.
platform = platform.system()
backend = "dogpile.cache.dbm"
if "WD_CACHE_DISABLE" in os.environ or platform == "Windows":
    backend = "dogpile.cache.memory"

# Compute cache directory.
try:
    cache_dir = os.environ["WD_CACHE_DIR"]
except KeyError:
    cache_dir = appdirs.user_cache_dir(appname="wetterdienst")

if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
log.info("Cache directory is %s", cache_dir)

# Define cache regions.
metaindex_cache = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "metaindex.dbm")},
)

fileindex_cache_five_minutes = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 5,
    arguments={"filename": os.path.join(cache_dir, "fileindex_5m.dbm")},
)

fileindex_cache_one_hour = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 60,
    arguments={"filename": os.path.join(cache_dir, "fileindex_1h.dbm")},
)

fileindex_cache_twelve_hours = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "fileindex_12h.dbm")},
)

payload_cache_five_minutes = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 5,
    arguments={"filename": os.path.join(cache_dir, "payload_5m.dbm")},
)

payload_cache_one_hour = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 60,
    arguments={"filename": os.path.join(cache_dir, "payload_1h.dbm")},
)

payload_cache_twelve_hours = make_region(
    function_key_generator=kwarg_function_key_generator
).configure(
    backend,
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "payload_12h.dbm")},
)
