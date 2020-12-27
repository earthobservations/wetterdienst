# -*- coding: utf-8 -*-
# Copyright (c) 2018-2020 earthobservations
# Copyright (c) 2018-2020 Andreas Motl <andreas.motl@panodata.org>
# Copyright (c) 2018-2020 Benjamin Gutzmann <gutzemann@gmail.com>
from enum import Enum

from wetterdienst.metadata.period import Period


class DWDObservationPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value
    RECENT = Period.RECENT.value
    NOW = Period.NOW.value
