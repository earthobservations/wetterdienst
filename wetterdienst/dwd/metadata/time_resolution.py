from enum import Enum
from typing import Dict

from wetterdienst.dwd.metadata.datetime import DatetimeFormat


class DWDObservationTimeResolution(Enum):
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


TIME_RESOLUTION_TO_DATETIME_FORMAT_MAPPING: Dict[DWDObservationTimeResolution, str] = {
    DWDObservationTimeResolution.MINUTE_1: DatetimeFormat.YMDHM.value,
    DWDObservationTimeResolution.MINUTE_10: DatetimeFormat.YMDHM.value,
    DWDObservationTimeResolution.HOURLY: DatetimeFormat.YMDH.value,
    DWDObservationTimeResolution.SUBDAILY: DatetimeFormat.YMDH.value,
    DWDObservationTimeResolution.DAILY: DatetimeFormat.YMD.value,
    DWDObservationTimeResolution.MONTHLY: DatetimeFormat.YMD.value,
    DWDObservationTimeResolution.ANNUAL: DatetimeFormat.YMD.value,
}
