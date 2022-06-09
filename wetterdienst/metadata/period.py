# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.

import functools
from enum import Enum


class PeriodType(Enum):
    FIXED = "fixed"
    MULTI = "multi"
    UNDEFINED = "undefined"


@functools.total_ordering
class OrderedPeriod(Enum):
    @property
    def _period_type_order_mapping(self):
        # IMPORTANT: THIS DEPENDS ON THE NAMING CONVENTIONS USED IN THE Period
        # ENUMERATION AS SHOWN BELOW
        return {
            Period.UNDEFINED.name: -1,
            Period.HISTORICAL.name: 0,
            Period.RECENT.name: 1,
            Period.NOW.name: 2,
            Period.FUTURE.name: 3,
        }

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self._period_type_order_mapping[self.name] < self._period_type_order_mapping[other.name]
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self._period_type_order_mapping[self.name] > self._period_type_order_mapping[other.name]
        return NotImplemented

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return not self.__lt__(other)
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return not self.__gt__(other)
        return NotImplemented


class Period(OrderedPeriod):
    """enumeration for different period types of storage on dwd server

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
