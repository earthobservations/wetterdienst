# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Enumeration for cache expiry presets."""

from enum import Enum


class CacheExpiry(Enum):
    """Describe some convenient caching expiry presets.

    This is part of the new network i/o subsystem based on FSSPEC.
    """

    INFINITE = False
    NO_CACHE = 0.01
    FIVE_SECONDS = 5
    ONE_MINUTE = 60
    FIVE_MINUTES = 300
    ONE_HOUR = 3600
    TWELVE_HOURS = 43200

    METAINDEX = TWELVE_HOURS
    FILEINDEX = FIVE_MINUTES
