# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Enumeration for radar resolutions."""

from enum import Enum

from wetterdienst.metadata.resolution import Resolution


class DwdRadarResolution(Enum):
    """Enumeration for radar resolutions."""

    MINUTE_5 = Resolution.MINUTE_5.value
    HOURLY = Resolution.HOURLY.value
    DAILY = Resolution.DAILY.value
