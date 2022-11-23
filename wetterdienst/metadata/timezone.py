# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Timezone(Enum):
    GERMANY = "Europe/Berlin"
    FRANCE = "Europe/Paris"
    UTC = "UTC"
    USA = "US/Washington"
    UK = "Europe/London"
    DYNAMIC = "dynamic"  # station based timezone (get tz from lon/lat)
