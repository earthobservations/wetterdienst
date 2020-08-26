""" enumeration for time_resoltution """
from enum import Enum


class TimeResolution(Enum):
    """
    enumeration for granularity/resolution of the weather
    observations stored on dwd server
    """

    MINUTE_1 = "1_minute"
    MINUTE_10 = "10_minutes"
    HOURLY = "hourly"
    SUBDAILY = "subdaily"
    DAILY = "daily"
    MONTHLY = "monthly"
    ANNUAL = "annual"
