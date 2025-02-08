# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Enumeration for period types."""

import functools
from enum import Enum


class PeriodType(Enum):
    """Enumeration for period types."""

    FIXED = "fixed"
    MULTI = "multi"
    UNDEFINED = "undefined"


@functools.total_ordering
class OrderedPeriod(Enum):
    """Enumeration for period types and values."""

    @property
    def _period_type_order_mapping(self) -> dict["Period", int]:
        # IMPORTANT: THIS DEPENDS ON THE NAMING CONVENTIONS USED IN THE Period
        # ENUMERATION AS SHOWN BELOW
        return {
            Period.UNDEFINED.name: -1,
            Period.HISTORICAL.name: 0,
            Period.RECENT.name: 1,
            Period.NOW.name: 2,
            Period.FUTURE.name: 3,
        }

    def __lt__(self, other: "OrderedPeriod") -> bool:
        """Less than comparison."""
        if not isinstance(other, OrderedPeriod):
            return False
        return self._period_type_order_mapping[self.name] < self._period_type_order_mapping[other.name]

    def __gt__(self, other: "OrderedPeriod") -> bool:
        """Greater than comparison."""
        if not isinstance(other, OrderedPeriod):
            return False
        return self._period_type_order_mapping[self.name] > self._period_type_order_mapping[other.name]

    def __ge__(self, other: "OrderedPeriod") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, OrderedPeriod):
            return False
        return not self.__lt__(other)

    def __le__(self, other: "OrderedPeriod") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, OrderedPeriod):
            return False
        return not self.__gt__(other)


class Period(OrderedPeriod):
    """Enumeration for different period types of storage on dwd server.

    Source: https://stackoverflow.com/questions/39268052/how-to-compare-enums-in-python
    Ordering is required for the PeriodType enumeration in order for it to be sorted.
    PeriodType needs to be sortable for the request definition where for the case of
    requesting data for several periods, we want preferably the historical data with
    quality marks and drop overlapping values from other periods.
    """

    UNDEFINED = PeriodType.UNDEFINED.value
    HISTORICAL = "historical"
    RECENT = "recent"
    NOW = "now"
    FUTURE = "future"
