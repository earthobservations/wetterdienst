# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the real Frost serves of windows that have not closed, held to properties and never to a value (GH-3856).

The values of an open period change by the minute, so these tests assert what must hold whatever they are: a daily value
that is returned is of a window that has closed, a monthly value is marked exactly when its window is open, and the
warning is the one the offline tests pin. The windows are re-stated here from Frost's documentation, not read from the
reader.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from tests.conftest import FROST_RESOLVER_ON_MACOS
from wetterdienst.provider.metno.frost.api import MetnoFrostRequest
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

OSLO_BLINDERN = "SN18700"
UTC = dt.UTC
HOUR = dt.timedelta(hours=1)

pytestmark = [
    pytest.mark.remote,
    pytest.mark.skipif(
        not MetnoFrostRequest.is_configured(),
        reason="MET Norway Frost credentials not set — provide WD_AUTH__METNO_FROST=<client_id>",
    ),
    FROST_RESOLVER_ON_MACOS,
]

# the hours after the start of the last day of the window that the standard series close at ("PT0H": the end of it)
DAILY = {
    "temperature_air_max_2m": 18,
    "temperature_air_min_2m": 18,
    "precipitation_amount": 6,
    "temperature_air_mean_2m": 24,
    "pressure_air_site_mean": 24,
}
MONTHLY = {"temperature_air_mean_2m": 24, "precipitation_amount": 6, "temperature_air_max_2m": 18}


def _month_end_day(month: dt.datetime) -> dt.datetime:
    """Give 00:00 UTC of the last day of the month that starts at `month`."""
    following = (month + dt.timedelta(days=32)).replace(day=1)
    return following - dt.timedelta(days=1)


def test_metno_frost_a_daily_value_that_is_returned_is_of_a_window_that_has_closed() -> None:
    """Test that no daily value of the current window comes back, whichever of the standard series it is.

    Frost serves the date from 00:00 UTC, and the three days asked for hold the current date, whose window is open for
    all but the last hours of it.
    """
    now = dt.datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    begin_response()

    df = (
        MetnoFrostRequest(
            parameters=[("daily", "data", name) for name in DAILY],
            start=today - dt.timedelta(days=3),
            end=today,
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values()
        .all()
        .df
    )

    after = dt.datetime.now(UTC)
    assert not df.is_empty()
    for row in df.select("parameter", "timestamp").unique().iter_rows(named=True):
        closes = row["timestamp"] + dt.timedelta(hours=DAILY[row["parameter"]])
        assert closes <= after, f"{row['parameter']} of {row['timestamp']} was returned before its window closed"
    told = [w for w in recorded_warnings() if w["code"] == "window-not-closed"]
    for warning in told:
        assert warning["parameter"].startswith("daily/data/")
        assert "is left out of the answer" in warning["message"]
        assert "the earliest closes at" in warning["message"]


def test_metno_frost_a_monthly_value_is_marked_incomplete_exactly_while_its_window_is_open() -> None:
    """Test that the current month carries `completeness:Incomplete` and a closed month does not.

    The window of a month closes on its last day at 06 UTC (the precipitation sum), 18 UTC (the maximum) or at the end
    of the day (the mean). A month whose window closes between the request and the check is not judged.
    """
    before = dt.datetime.now(UTC)
    this_month = before.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = (this_month - dt.timedelta(days=1)).replace(day=1)
    begin_response()

    df = (
        MetnoFrostRequest(
            parameters=[("monthly", "data", name) for name in MONTHLY],
            start=start,
            end=this_month,
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values()
        .all()
        .df
    )

    after = dt.datetime.now(UTC)
    assert not df.is_empty()
    judged = 0
    for row in df.select("parameter", "timestamp", "quality_flags").iter_rows(named=True):
        closes = _month_end_day(row["timestamp"]) + dt.timedelta(hours=MONTHLY[row["parameter"]])
        tokens = (row["quality_flags"] or "").split(",")
        if closes > after:
            assert "completeness:Incomplete" in tokens, f"{row['parameter']} of {row['timestamp']} is not marked"
            judged += 1
        elif closes <= before:
            assert "completeness:Incomplete" not in tokens, f"{row['parameter']} of {row['timestamp']} is marked"
            judged += 1
    assert judged
    told = [w for w in recorded_warnings() if w["code"] == "window-not-closed"]
    open_rows = df.filter(pl.col("quality_flags").str.contains("completeness:Incomplete").fill_null(value=False))
    assert bool(told) == (not open_rows.is_empty())
    for warning in told:
        assert warning["parameter"].startswith("monthly/data/")
        assert "marked `completeness:Incomplete`" in warning["message"]
