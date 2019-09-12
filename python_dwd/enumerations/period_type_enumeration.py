""" enumeration for period_type """
from enum import Enum


class PeriodType(Enum):
    """ enumeration for different period types of storages on dwd server"""
    HISTORICAL = "historical"
    RECENT = "recent"
    NOW = "now"
    ROW = ""
