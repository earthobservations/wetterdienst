from enum import Enum
from typing import Dict

from wetterdienst.dwd.metadata.datetime import DatetimeFormat


class TimeResolution(Enum):
    """
    enumeration for granularity/resolution of the weather
    observations stored on dwd server
    """

    MINUTE_1 = "1_minute"
    MINUTES_10 = "10_minutes"
    HOURLY = "hourly"
    SUBDAILY = "subdaily"
    DAILY = "daily"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    MINUTE_5 = "5_minutes"
    MINUTE_15 = "15_minutes"


TIME_RESOLUTION_TO_DATETIME_FORMAT_MAPPING: Dict[TimeResolution, str] = {
    TimeResolution.MINUTE_1: DatetimeFormat.YMDHM.value,
    TimeResolution.MINUTES_10: DatetimeFormat.YMDHM.value,
    TimeResolution.HOURLY: DatetimeFormat.YMDH.value,
    TimeResolution.SUBDAILY: DatetimeFormat.YMDH.value,
    TimeResolution.DAILY: DatetimeFormat.YMD.value,
    TimeResolution.MONTHLY: DatetimeFormat.YMD.value,
    TimeResolution.ANNUAL: DatetimeFormat.YMD.value,
}
