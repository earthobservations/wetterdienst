# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Source(Enum):
    """Source of weather information given as tuple of local name, english name and
    country"""

    DWD = "Deutscher Wetterdienst", "German Weather Service", "Germany"
