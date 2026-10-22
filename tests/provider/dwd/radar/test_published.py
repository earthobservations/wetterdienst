# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what a remote radar test makes of an empty answer (GH-3282)."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from _pytest.outcomes import Failed, Skipped

from tests.provider.dwd.radar.published import SWEEP_FIRST_FILE_DELAY, require_published

UTC = ZoneInfo("UTC")


def test_an_answer_is_enough_whatever_the_age_of_the_slot() -> None:
    """Test that a request that answered a file passes, for a slot that is old and for one that has just begun."""
    require_published([object()], dt.datetime.now(UTC) - dt.timedelta(days=1), SWEEP_FIRST_FILE_DELAY, "the sweep")
    require_published([object()], dt.datetime.now(UTC), SWEEP_FIRST_FILE_DELAY, "the sweep")


def test_an_empty_answer_for_a_young_slot_is_skipped_for_the_reason() -> None:
    """Test that DWD is given the time it takes to publish the first file before its silence is a failure."""
    with pytest.raises(Skipped, match="publishes the first file within"):
        require_published([], dt.datetime.now(UTC) - dt.timedelta(seconds=30), SWEEP_FIRST_FILE_DELAY, "the sweep")


@pytest.mark.parametrize("age", [SWEEP_FIRST_FILE_DELAY + dt.timedelta(seconds=1), dt.timedelta(days=1)])
def test_an_empty_answer_for_an_old_slot_fails(age: dt.timedelta) -> None:
    """Test that an empty answer after the delay is a failure, for a naive start (UTC) as for an aware one."""
    with pytest.raises(Failed, match="no file"):
        require_published([], dt.datetime.now(UTC) - age, SWEEP_FIRST_FILE_DELAY, "the sweep")
    with pytest.raises(Failed, match="no file"):
        require_published([], (dt.datetime.now(UTC) - age).replace(tzinfo=None), SWEEP_FIRST_FILE_DELAY, "the sweep")
