# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class DwdRoadWeatherObservationPeriod(Enum):
    """RoadWeather Observation period types"""

    LATEST = "latest"
    ALL = "all"
