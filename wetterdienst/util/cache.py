# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


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
