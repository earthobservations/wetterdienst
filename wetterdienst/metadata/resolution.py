# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
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
    observation
    """

    MINUTE_1 = "1_minute"  # used by DWD for file server
    MINUTE_5 = "5_minutes"
    MINUTE_10 = "10_minutes"  # used by DWD for file server
    MINUTE_15 = "15_minutes"  # used by DWD for file server
    HOURLY = "hourly"  # used by DWD for file server
    HOUR_6 = "6_hour"
    SUBDAILY = "subdaily"  # used by DWD for file server
    DAILY = "daily"  # used by DWD for file server
    MONTHLY = "monthly"  # used by DWD for file server
    ANNUAL = "annual"  # used by DWD for file server

    # For sources without resolution
    UNDEFINED = "undefined"
    DYNAMIC = ResolutionType.DYNAMIC.value


class Frequency(Enum):
    MINUTE_1 = "1min"
    MINUTE_5 = "5min"
    MINUTE_10 = "10min"
    MINUTE_15 = "15min"
    MINUTE_60 = "60min"  # similar to hourly, needed for WSV frequency detection
    HOURLY = "1H"
    HOUR_6 = "6H"
    SUBDAILY = "1H"
    DAILY = "1D"
    MONTHLY = "MS"  # month start
    ANNUAL = "AS"  # year start
