from enum import Enum
from typing import Dict

from wetterdienst.dwd.metadata.datetime import DatetimeFormat


class DWDObservationResolution(Enum):
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


RESOLUTION_TO_DATETIME_FORMAT_MAPPING: Dict[DWDObservationResolution, str] = {
    DWDObservationResolution.MINUTE_1: DatetimeFormat.YMDHM.value,
    DWDObservationResolution.MINUTE_10: DatetimeFormat.YMDHM.value,
    DWDObservationResolution.HOURLY: DatetimeFormat.YMDH.value,
    DWDObservationResolution.SUBDAILY: DatetimeFormat.YMDH.value,
    DWDObservationResolution.DAILY: DatetimeFormat.YMD.value,
    DWDObservationResolution.MONTHLY: DatetimeFormat.YMD.value,
    DWDObservationResolution.ANNUAL: DatetimeFormat.YMD.value,
}
