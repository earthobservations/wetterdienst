import os
import logging
import platform

import appdirs
from dogpile.cache import make_region


log = logging.getLogger()

# Python on Windows has no "fcntl", which is required by the dbm backend.
# TODO: Make backend configurable, e.g. better use Redis.
platform = platform.system()
backend = "dogpile.cache.dbm"
if platform == "Windows":
    backend = "dogpile.cache.memory"

# Compute cache directory.
cache_dir = appdirs.user_cache_dir(appname="wetterdienst")
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
log.info("Cache directory is %s", cache_dir)

# Define cache regions.
metaindex_cache = make_region().configure(
    backend,
    expiration_time=1 * 60,
    arguments={"filename": os.path.join(cache_dir, "metaindex_1min.dbm")},
)

fileindex_cache_five_minutes = make_region().configure(
    backend,
    expiration_time=5 * 60,
    arguments={"filename": os.path.join(cache_dir, "fileindex_5min.dbm")},
)

fileindex_cache_one_hour = make_region().configure(
    backend,
    expiration_time=60 * 60,
    arguments={"filename": os.path.join(cache_dir, "fileindex_60min.dbm")},
)

payload_cache_one_hour = make_region().configure(
    backend,
    expiration_time=60 * 60,
    arguments={"filename": os.path.join(cache_dir, "payload_60min.dbm")},
)
