from abc import abstractmethod
from datetime import datetime
from pytz import timezone

from wetterdienst.metadata.source import Source
from wetterdienst.metadata.timezone import Timezone


class Core:
    """ Core class for any related requests of wetterdienst """

    # Time of request
    _now = datetime.utcnow()

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
    def _source(self) -> Source:
        """Abstract representation of source that is related to the request, used for
        identification of returned data"""
        pass

    @property
    def _now_local(self) -> datetime:
        """Local now time based on the given timezone that represents the request time
        in local time"""
        return self._now.astimezone(self.tz)
