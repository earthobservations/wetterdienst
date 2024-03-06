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


# required for cutting of finer granularity when creating full date range
DAILY_AT_MOST = [
    Resolution.MINUTE_1,
    Resolution.MINUTE_5,
    Resolution.MINUTE_10,
    Resolution.MINUTE_15,
    Resolution.HOURLY,
    Resolution.HOUR_6,
    Resolution.SUBDAILY,
    Resolution.DAILY,
]


class Frequency(Enum):
    MINUTE_1 = "1m"
    MINUTE_2 = "2m"
    MINUTE_5 = "5m"
    MINUTE_10 = "10m"
    MINUTE_15 = "15m"
    MINUTE_60 = "60m"  # similar to hourly, needed for WSV frequency detection
    HOURLY = "1h"
    HOUR_6 = "6h"
    SUBDAILY = "1h"
    DAILY = "1d"
    MONTHLY = "1mo"  # month start
    ANNUAL = "1y"  # year start
