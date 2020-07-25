from typing import Dict

from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat

TIME_RESOLUTION_TO_DATETIME_FORMAT_MAPPING: Dict[TimeResolution, str] = {
    TimeResolution.MINUTE_1: DatetimeFormat.YMDHM.value,
    TimeResolution.MINUTE_10: DatetimeFormat.YMDHM.value,
    TimeResolution.HOURLY: DatetimeFormat.YMDH.value,
    TimeResolution.SUBDAILY: DatetimeFormat.YMDH.value,
    TimeResolution.DAILY: DatetimeFormat.YMD.value,
    TimeResolution.MONTHLY: DatetimeFormat.YMD.value,
    TimeResolution.ANNUAL: DatetimeFormat.YMD.value,
}
