# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum
from typing import Dict

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat

HIGH_RESOLUTIONS = (
    Resolution.MINUTE_1,
    Resolution.MINUTE_5,
    Resolution.MINUTE_10,
)


RESOLUTION_TO_DATETIME_FORMAT_MAPPING: Dict[Resolution, str] = {
    Resolution.MINUTE_1: DatetimeFormat.YMDHM.value,
    Resolution.MINUTE_10: DatetimeFormat.YMDHM.value,
    Resolution.HOURLY: DatetimeFormat.YMDH.value,
    Resolution.SUBDAILY: DatetimeFormat.YMDH.value,
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
