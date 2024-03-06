# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class DataRange(Enum):
    """Enumeration for data range. This is required for querying data
    which can not be queried in a fixed file format and must be defined
    over start and end date"""

    FIXED = "fixed"
    LOOSELY = "loosely"
