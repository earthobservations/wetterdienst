from enum import Enum


class DWDRadarResolution(Enum):
    """
    enumeration for granularity/resolution of the weather
    observations stored on dwd server
    """

    MINUTE_5 = "5_minutes"
    HOURLY = "hourly"
    DAILY = "daily"
