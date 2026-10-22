# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a remote radar test makes of an empty answer (GH-3282).

A test that asks DWD for data it holds fails on an empty answer. The one request that can be empty without a fault is
for the slot of now, which DWD publishes some time after it starts, and it is excused for that time and no longer.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

# How long after the start of a slot of 5 minutes the first file of a sweep of BOO is listed at the latest: 227 s of
# the 576 slots of 2026-10-20 to 22 (the median 61 s for the precipitation scan, 85 s for the volume scan; the listing
# times of `content.log.bz2` of https://opendata.dwd.de/weather/radar/ against the times in the names), and 13 s more.
# It holds for any file of the precipitation scan and for the first of the volume scan, the sweep 0, not for the others.
SWEEP_FIRST_FILE_DELAY = dt.timedelta(seconds=240)

# The same for the sweep 1 of the volume scan, which is scanned after the sweep 0: 323 s of 1152 files (median 108 s),
# and 17 s more.
SWEEP_ELEVATION_1_DELAY = dt.timedelta(seconds=340)

# How long after its mark HH:50 the file of RADOLAN_CDC `recent` (daily and hourly) is listed: 26 to 31 minutes for all
# but about 0.5 % of the 15831 marks (the 99th percentile 31.3 minutes, read 2026-10-22), which are listed up to hours,
# rarely days, later: a failure on one of those (about 0.2 % of the runs) is a late file, no regression.
RADOLAN_CDC_DELAY = dt.timedelta(minutes=40)


def require_published(results: Sequence[object], slot_start: dt.datetime, delay: dt.timedelta, what: str) -> None:
    """Fail on an empty answer for a slot that DWD has had `delay` to publish, skip while it has not.

    Args:
        results: what the request answered
        slot_start: the start of the slot asked for (aware, or UTC if naive)
        delay: the time after `slot_start` by which DWD has published its first file
        what: the product, for the message

    """
    if results:
        return
    utc = ZoneInfo("UTC")
    start = slot_start.replace(tzinfo=utc) if slot_start.tzinfo is None else slot_start
    age = dt.datetime.now(utc) - start
    if age < delay:
        pytest.skip(f"{what} of {start:%H:%M} UTC is {age} old and DWD publishes the first file within {delay}")
    pytest.fail(f"{what} of {start:%H:%M} UTC is {age} old, longer than the {delay} DWD takes to publish it: no file")
