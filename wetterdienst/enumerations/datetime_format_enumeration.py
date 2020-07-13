from enum import Enum


class DatetimeFormat(Enum):
    YMD = "%Y%m%d"
    YMDH = "%Y%m%d%H"
    YMDHM = "%Y%m%d%H%M"
    YMDH_COLUMN_M = "%Y%m%d%H:%M"
    YMD_TIME_H = "%Y-%m-%dT%H"
