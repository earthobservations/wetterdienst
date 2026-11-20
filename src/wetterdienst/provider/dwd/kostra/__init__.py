# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD KOSTRA-DWD-2020 heavy-rainfall statistics: depth, intensity and uncertainty by duration and return period."""

from wetterdienst.provider.dwd.kostra.api import DwdKostraRequest, DwdKostraResult
from wetterdienst.provider.dwd.kostra.metadata import DURATIONS, EDITION, RETURN_PERIODS

__all__ = [
    "DURATIONS",
    "EDITION",
    "RETURN_PERIODS",
    "DwdKostraRequest",
    "DwdKostraResult",
]
