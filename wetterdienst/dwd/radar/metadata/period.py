from enum import Enum

from wetterdienst.metadata.period import Period


class DWDRadarPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value
    RECENT = Period.RECENT.value
