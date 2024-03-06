# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.metadata.resolution import Resolution


class EcccObservationResolution(Enum):
    DAILY = Resolution.DAILY.value
    HOURLY = Resolution.HOURLY.value
    MONTHLY = Resolution.MONTHLY.value
