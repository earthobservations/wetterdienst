# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class DWDForecastDate(Enum):
    """
    Enumeration for pointing to different forecast dates.
    """

    LATEST = "latest"
