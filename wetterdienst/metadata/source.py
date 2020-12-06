# -*- coding: utf-8 -*-
from enum import Enum


class Source(Enum):
    """Source of weather information given as tuple of local name, english name and
    country"""

    DWD = "Deutscher Wetterdienst", "German Weather Service", "Germany"
