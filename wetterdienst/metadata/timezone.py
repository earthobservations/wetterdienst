# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Timezone(Enum):
    GERMANY = "Europe/Berlin"
    UTC = "UTC"
    USA = "US/Washington"
    DYNAMIC = "dynamic"  # station based timezone (get tz from lon/lat)
