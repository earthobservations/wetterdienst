# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

from enum import Enum

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat

HIGH_RESOLUTIONS = (
    Resolution.MINUTE_1,
    Resolution.MINUTE_5,
    Resolution.MINUTE_10,
)


RESOLUTION_TO_DATETIME_FORMAT_MAPPING: dict[Resolution, str] = {
    Resolution.MINUTE_1: DatetimeFormat.YMDHM.value,
    Resolution.MINUTE_10: DatetimeFormat.YMDHM.value,
    Resolution.HOURLY: DatetimeFormat.YMDHM.value,
    Resolution.SUBDAILY: DatetimeFormat.YMDHM.value,
    Resolution.DAILY: DatetimeFormat.YMD.value,
    Resolution.MONTHLY: DatetimeFormat.YMD.value,
    Resolution.ANNUAL: DatetimeFormat.YMD.value,
}


class DwdObservationResolution(Enum):
    MINUTE_1 = Resolution.MINUTE_1.value
    MINUTE_5 = Resolution.MINUTE_5.value
    MINUTE_10 = Resolution.MINUTE_10.value
    HOURLY = Resolution.HOURLY.value
    SUBDAILY = Resolution.SUBDAILY.value
    DAILY = Resolution.DAILY.value
    MONTHLY = Resolution.MONTHLY.value
    ANNUAL = Resolution.ANNUAL.value
