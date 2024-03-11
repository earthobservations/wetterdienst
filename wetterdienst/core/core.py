# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from abc import ABCMeta, abstractmethod
from zoneinfo import ZoneInfo

from wetterdienst.metadata.timezone import Timezone


class Core(metaclass=ABCMeta):
    """Core class for any related requests of wetterdienst"""

    def __init__(self):
        # Time of request.
        self.now = dt.datetime.now(ZoneInfo("UTC"))

    @property
    def tz(self) -> ZoneInfo:
        """timezone of country that may be used for internal date parsing or reflection
        of release schedules"""
        return ZoneInfo(self._tz.value)

    @property
    @abstractmethod
    def _tz(self) -> Timezone:
        """Abstract representation of timezone that has to be implemented by source
        class, uses the Timezone enumeration"""
        pass

    @property
    def _now_local(self) -> dt.datetime:
        """Local now time based on the given timezone that represents the request time
        in local time"""
        return self.now.astimezone(self.tz)
