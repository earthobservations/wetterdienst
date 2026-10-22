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
SWEEP_FIRST_FILE_DELAY = dt.timedelta(seconds=240)

# How long after its mark HH:50 the file of RADOLAN_CDC `recent` (daily and hourly) is listed: 26 to 31 minutes in all
# but a few that were put there again days later (the 99th percentile 31.3 minutes of 15831 marks, read 2026-10-22).
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
