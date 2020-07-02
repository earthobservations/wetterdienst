from enum import Enum


class DatetimeFormat(Enum):
    YMDH = "%Y%m%d%H"
    YMDH_COLUMN_M = "%Y%m%d%H:%M"
    YMD_TIME_H = "%Y-%m-%dT%H"
