""" enumeration for period_type """
from enum import Enum
import functools

"""
Source: https://stackoverflow.com/questions/39268052/how-to-compare-enums-in-python
Ordering is required for the PeriodType enumeration in order for it to be sorted.
PeriodType needs to be sortable for the request definition where for the case of
requesting data for several periods, we want preferably the historical data with
quality marks and drop overlapping values from other periods.
"""


@functools.total_ordering
class PeriodType(Enum):
    """ enumeration for different period types of storage on dwd server"""

    HISTORICAL = "historical"
    RECENT = "recent"
    NOW = "now"

    @property
    def _period_type_order_mapping(self):
        # IMPORTANT: THIS DEPENDS ON THE NAMING CONVENTIONS USED IN THE PeriodType
        # ENUMERATION AS SHOWN BELOW
        return {"HISTORICAL": 0, "RECENT": 1, "NOW": 2}

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return (
                self._period_type_order_mapping[self.name]
                < self._period_type_order_mapping[other.name]
            )
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return (
                self._period_type_order_mapping[self.name]
                > self._period_type_order_mapping[other.name]
            )
        return NotImplemented

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return not self.__lt__(other)
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return not self.__gt__(other)
        return NotImplemented
