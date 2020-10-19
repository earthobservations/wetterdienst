from enum import Enum


class DWDRadarTimeResolution(Enum):
    """
    enumeration for granularity/resolution of the weather
    observations stored on dwd server
    """

    MINUTE_5 = "5_minutes"
    HOURLY = "hourly"
    DAILY = "daily"
