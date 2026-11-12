# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The grids of the five KNMI resolutions: the boundaries of an interval, and the step from one to the next.

Shared by the reader of the files (`api`) and the reader of the EDR API (`edr`), which must agree on what a moment is.
"""

from __future__ import annotations

import datetime as dt

from wetterdienst.metadata.resolution import Resolution

STEP_BY_RESOLUTION = {
    Resolution.MINUTE_10: dt.timedelta(minutes=10),
    Resolution.HOURLY: dt.timedelta(hours=1),
    Resolution.DAILY: dt.timedelta(days=1),
}

#: The periods of a month and of a year, which are no fixed length
CALENDAR_RESOLUTIONS = (Resolution.MONTHLY, Resolution.ANNUAL)


def add_months(moment: dt.datetime, months: int) -> dt.datetime:
    """Move a moment on the first of a month by a number of months, back if it is negative."""
    index = moment.year * 12 + moment.month - 1 + months
    return moment.replace(year=index // 12, month=index % 12 + 1)


def floor(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Snap a moment down to its resolution's interval boundary (:X0 / :00 / midnight / the 1st / 1 January)."""
    if resolution == Resolution.MINUTE_10:
        return moment.replace(minute=moment.minute - moment.minute % 10, second=0, microsecond=0)
    if resolution == Resolution.HOURLY:
        return moment.replace(minute=0, second=0, microsecond=0)
    if resolution == Resolution.MONTHLY:
        return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if resolution == Resolution.ANNUAL:
        return moment.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def advance(moment: dt.datetime, resolution: Resolution, steps: int = 1) -> dt.datetime:
    """Move a moment on its boundary by a number of steps (back if negative): 10 minutes, hours, days, months, years."""
    if resolution == Resolution.MONTHLY:
        return add_months(moment, steps)
    if resolution == Resolution.ANNUAL:
        return add_months(moment, 12 * steps)
    return moment + steps * STEP_BY_RESOLUTION[resolution]


def ceil(moment: dt.datetime, resolution: Resolution) -> dt.datetime:
    """Snap a moment up to its resolution's interval boundary, the moment itself if it is on one."""
    floored = floor(moment, resolution)
    return floored if floored == moment else advance(floored, resolution)
