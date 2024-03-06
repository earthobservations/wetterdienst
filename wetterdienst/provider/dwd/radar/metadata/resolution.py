# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.metadata.resolution import Resolution


class DwdRadarResolution(Enum):
    MINUTE_5 = Resolution.MINUTE_5.value
    HOURLY = Resolution.HOURLY.value
    DAILY = Resolution.DAILY.value
