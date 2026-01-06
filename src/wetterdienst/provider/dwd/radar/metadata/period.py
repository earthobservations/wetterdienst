# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Enumeration for radar periods."""

from enum import Enum

from wetterdienst.metadata.period import Period


class DwdRadarPeriod(Enum):
    """Enumeration for radar periods."""

    HISTORICAL = Period.HISTORICAL.value
    RECENT = Period.RECENT.value
