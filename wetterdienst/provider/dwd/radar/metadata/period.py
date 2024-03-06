# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.metadata.period import Period


class DwdRadarPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value
    RECENT = Period.RECENT.value
