# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class ResolutionType(Enum):
    FIXED = "fixed"
    MULTI = "multi"
    DYNAMIC = "dynamic"
    UNDEFINED = "undefined"


class Resolution(Enum):
    """
    enumeration for granularity/resolution of the weather
    observations
    """

    MINUTE_1 = "1_minute"
    MINUTE_5 = "5_minutes"
    MINUTE_10 = "10_minutes"
    HOURLY = "hourly"
    SUBDAILY = "subdaily"
    DAILY = "daily"
    MONTHLY = "monthly"
    ANNUAL = "annual"

    # For sources without resolution
    UNDEFINED = "undefined"
    DYNAMIC = ResolutionType.DYNAMIC.value


class Frequency(Enum):
    MINUTE_1 = "1min"
    MINUTE_5 = "5min"
    MINUTE_10 = "10min"
    HOURLY = "1H"
    SUBDAILY = "1H"
    DAILY = "1D"
    MONTHLY = "1M"
    ANNUAL = "1A"
