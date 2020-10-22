from enum import Enum


class DWDRadarPeriod(Enum):
    """ enumeration for different period types of storage on dwd server"""

    HISTORICAL = "historical"
    RECENT = "recent"
