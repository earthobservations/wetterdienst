# -*- coding: utf-8 -*-
# Copyright (c) 2018-2020 earthobservations
# Copyright (c) 2018-2020 Andreas Motl <andreas.motl@panodata.org>
# Copyright (c) 2018-2020 Benjamin Gutzmann <gutzemann@gmail.com>
from enum import Enum

from wetterdienst.metadata.resolution import Resolution


class DWDRadarResolution(Enum):
    MINUTE_5 = Resolution.MINUTE_5.value
    HOURLY = Resolution.HOURLY.value
    DAILY = Resolution.DAILY.value
