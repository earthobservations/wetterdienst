# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Kind(Enum):
    OBSERVATION = "observation"
    FORECAST = "mosmix"
    RADAR = "radar"
