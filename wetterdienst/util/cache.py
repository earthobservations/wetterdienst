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
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "metaindex.dbm")},
)

fileindex_cache_five_minutes = make_region().configure(
    backend,
    expiration_time=60 * 5,
    arguments={"filename": os.path.join(cache_dir, "fileindex_5m.dbm")},
)

fileindex_cache_one_hour = make_region().configure(
    backend,
    expiration_time=60 * 60,
    arguments={"filename": os.path.join(cache_dir, "fileindex_1h.dbm")},
)

fileindex_cache_twelve_hours = make_region().configure(
    backend,
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "fileindex_12h.dbm")},
)

payload_cache_five_minutes = make_region().configure(
    backend,
    expiration_time=60 * 5,
    arguments={"filename": os.path.join(cache_dir, "payload_5m.dbm")},
)

payload_cache_one_hour = make_region().configure(
    backend,
    expiration_time=60 * 60,
    arguments={"filename": os.path.join(cache_dir, "payload_1h.dbm")},
)

payload_cache_twelve_hours = make_region().configure(
    backend,
    expiration_time=60 * 60 * 12,
    arguments={"filename": os.path.join(cache_dir, "payload_12h.dbm")},
)
