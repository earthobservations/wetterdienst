from enum import Enum
from typing import Dict

from wetterdienst.dwd.metadata.datetime import DatetimeFormat


class DWDObsTimeResolution(Enum):
    """
    enumeration for granularity/resolution of the weather
    observations stored on dwd server
    """

    MINUTE_1 = "1_minute"
    MINUTE_5 = "5_minutes"
    MINUTE_15 = "15_minutes"
    MINUTE_10 = "10_minutes"
    HOURLY = "hourly"
    SUBDAILY = "subdaily"
    DAILY = "daily"
    MONTHLY = "monthly"
    ANNUAL = "annual"


TIME_RESOLUTION_TO_DATETIME_FORMAT_MAPPING: Dict[DWDObsTimeResolution, str] = {
    DWDObsTimeResolution.MINUTE_1: DatetimeFormat.YMDHM.value,
    DWDObsTimeResolution.MINUTE_10: DatetimeFormat.YMDHM.value,
    DWDObsTimeResolution.HOURLY: DatetimeFormat.YMDH.value,
    DWDObsTimeResolution.SUBDAILY: DatetimeFormat.YMDH.value,
    DWDObsTimeResolution.DAILY: DatetimeFormat.YMD.value,
    DWDObsTimeResolution.MONTHLY: DatetimeFormat.YMD.value,
    DWDObsTimeResolution.ANNUAL: DatetimeFormat.YMD.value,
}
