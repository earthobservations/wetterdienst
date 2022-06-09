# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from abc import ABCMeta, abstractmethod
from datetime import datetime

import pandas as pd
from pytz import timezone

from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.timezone import Timezone


class Core(metaclass=ABCMeta):
    """Core class for any related requests of wetterdienst"""

    def __init__(self):
        # Time of request.
        self.now = datetime.utcnow()

    @property
    def tz(self) -> timezone:
        """timezone of country that may be used for internal date parsing or reflection
        of release schedules"""
        return timezone(self._tz.value)

    @property
    @abstractmethod
    def _tz(self) -> Timezone:
        """Abstract representation of timezone that has to be implemented by source
        class, uses the Timezone enumeration"""
        pass

    @property
    @abstractmethod
    def provider(self) -> Provider:
        """Abstract representation of source that is related to the request, used for
        identification of returned data"""
        pass

    @property
    def _now_local(self) -> datetime:
        """Local now time based on the given timezone that represents the request time
        in local time"""
        return pd.Timestamp(self.now, tz=self.tz)
