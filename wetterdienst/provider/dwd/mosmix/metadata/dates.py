# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class DwdForecastDate(Enum):
    """
    Enumeration for pointing to different mosmix dates.
    """

    LATEST = "latest"
