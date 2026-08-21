# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Enumeration for resolution types and values."""

from __future__ import annotations

import datetime as dt
from enum import Enum


class Resolution(Enum):
    """Enumeration for granularity/resolution of the weather observation."""

    MINUTE_1 = "1_minute"  # used by DWD for file server
    MINUTE_5 = "5_minutes"
    MINUTE_6 = "6_minutes"  # used by Météo-France
    MINUTE_10 = "10_minutes"  # used by DWD for file server
    MINUTE_15 = "15_minutes"  # used by DWD for file server
    HOURLY = "hourly"  # used by DWD for file server
    HOUR_6 = "6_hour"
    SUBDAILY = "subdaily"  # used by DWD for file server
    DAILY = "daily"  # used by DWD for file server
    MONTHLY = "monthly"  # used by DWD for file server
    ANNUAL = "annual"  # used by DWD for file server

    # For sources without resolution
    UNDEFINED = "undefined"


class Frequency(Enum):
    """Enumeration for frequency of the weather observation."""

    MINUTE_1 = "1m"
    MINUTE_2 = "2m"
    MINUTE_5 = "5m"
    MINUTE_6 = "6m"
    MINUTE_10 = "10m"
    MINUTE_15 = "15m"
    HOURLY = "1h"
    HOUR_6 = "6h"
    SUBDAILY = HOURLY
    DAILY = "1d"
    MONTHLY = "1mo"  # month start
    ANNUAL = "1y"  # year start


# the interval between two readings of a resolution, as a polars interval string.
#
# `SUBDAILY` is deliberately absent, and so is `UNDEFINED`: subdaily is a bucket for "coarser than
# hourly, finer than daily" rather than an interval, and its two providers do not agree on one --
# DWD takes three Termin readings a day (06/12/18 UTC) while Meteo-France SYNOP reports every three
# hours. Naming either as the interval would misjudge the other by a factor of nearly three.
#
# `Frequency` above spells the same intervals for the date ranges `interpolate` and `summarize`
# build, but it does answer for subdaily, since over-completing a grid is harmless where measuring
# a station against the wrong one is not.
_RESOLUTION_INTERVALS: dict[Resolution, str] = {
    Resolution.MINUTE_1: "1m",
    Resolution.MINUTE_5: "5m",
    Resolution.MINUTE_6: "6m",
    Resolution.MINUTE_10: "10m",
    Resolution.MINUTE_15: "15m",
    Resolution.HOURLY: "1h",
    Resolution.HOUR_6: "6h",
    Resolution.DAILY: "1d",
    Resolution.MONTHLY: "1mo",
    Resolution.ANNUAL: "1y",
}

# how much time one reading stands for, for the resolutions whose step is a fixed span. The
# calendar resolutions are absent: a month and a year are not, so `count_readings` counts by
# calendar instead
_RESOLUTION_STEPS: dict[Resolution, dt.timedelta] = {
    Resolution.MINUTE_1: dt.timedelta(minutes=1),
    Resolution.MINUTE_5: dt.timedelta(minutes=5),
    Resolution.MINUTE_6: dt.timedelta(minutes=6),
    Resolution.MINUTE_10: dt.timedelta(minutes=10),
    Resolution.MINUTE_15: dt.timedelta(minutes=15),
    Resolution.HOURLY: dt.timedelta(hours=1),
    Resolution.HOUR_6: dt.timedelta(hours=6),
    Resolution.DAILY: dt.timedelta(days=1),
}


def reading_interval(resolution: Resolution) -> str | None:
    """Give the interval between two readings of a resolution, as a polars interval string.

    None where the resolution names no single interval, which is every case `count_readings`
    answers None for -- the two are asked together and agree by construction.
    """
    return _RESOLUTION_INTERVALS.get(resolution)


def count_readings(resolution: Resolution, start_date: dt.datetime, end_date: dt.datetime) -> int | None:
    """Count the readings a resolution can hold in a window, both ends included.

    Counted arithmetically rather than by building the timestamps and measuring them, so the
    count of a decade of 1-minute readings costs the same as the count of a day of them.

    A resolution with a fixed step is counted from the step alone -- where in the hour the
    readings happen to fall does not change how many of them fit in the window. The calendar
    resolutions are counted from the anchors instead, since a reading of a month or a year is
    dated to its first day and a window that begins mid-month does not contain that anchor.

    Returns None for a resolution that names no interval, where the question has no answer.
    """
    if resolution not in _RESOLUTION_INTERVALS:
        return None
    if end_date < start_date:
        return 0
    if resolution == Resolution.MONTHLY:
        anchor = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if anchor < start_date:
            anchor = anchor.replace(
                year=anchor.year + anchor.month // 12,
                month=anchor.month % 12 + 1,
            )
        if anchor > end_date:
            return 0
        return (end_date.year - anchor.year) * 12 + end_date.month - anchor.month + 1
    if resolution == Resolution.ANNUAL:
        anchor = start_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        if anchor < start_date:
            anchor = anchor.replace(year=anchor.year + 1)
        if anchor > end_date:
            return 0
        return end_date.year - anchor.year + 1
    return (end_date - start_date) // _RESOLUTION_STEPS[resolution] + 1
