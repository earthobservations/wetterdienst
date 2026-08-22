"""Tests for resolution metadata."""

import datetime as dt
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.metadata.resolution import Frequency, Resolution, count_readings, reading_interval

UTC = ZoneInfo("UTC")
ROOT = Path(__file__).parent.parent.parent
API_TYPES = ROOT / "app" / "shared" / "types" / "api.ts"


@pytest.mark.parametrize(
    ("resolution", "start_date", "end_date", "expected"),
    [
        # both ends are included, so an hour holds five quarter-hour readings and not four
        (Resolution.MINUTE_15, dt.datetime(2026, 1, 1, 0, tzinfo=UTC), dt.datetime(2026, 1, 1, 1, tzinfo=UTC), 5),
        (Resolution.MINUTE_1, dt.datetime(2026, 1, 1, 0, tzinfo=UTC), dt.datetime(2026, 1, 1, 0, 10, tzinfo=UTC), 11),
        (Resolution.HOURLY, dt.datetime(2026, 1, 1, 0, tzinfo=UTC), dt.datetime(2026, 1, 2, 0, tzinfo=UTC), 25),
        (Resolution.HOUR_6, dt.datetime(2026, 1, 1, 0, tzinfo=UTC), dt.datetime(2026, 1, 2, 0, tzinfo=UTC), 5),
        (Resolution.DAILY, dt.datetime(2026, 1, 1, tzinfo=UTC), dt.datetime(2026, 1, 31, tzinfo=UTC), 31),
        # a window shorter than one step still holds the reading at its own start
        (Resolution.DAILY, dt.datetime(2026, 1, 1, tzinfo=UTC), dt.datetime(2026, 1, 1, 6, tzinfo=UTC), 1),
        # where in the hour the readings fall does not change how many of them fit
        (Resolution.HOURLY, dt.datetime(2026, 1, 1, 0, 7, tzinfo=UTC), dt.datetime(2026, 1, 1, 3, 7, tzinfo=UTC), 4),
        (Resolution.HOURLY, dt.datetime(2026, 1, 2, tzinfo=UTC), dt.datetime(2026, 1, 1, tzinfo=UTC), 0),
    ],
)
def test_count_readings_of_a_fixed_step(
    resolution: Resolution,
    start_date: dt.datetime,
    end_date: dt.datetime,
    expected: int,
) -> None:
    """Test that a resolution with a fixed step is counted from the step alone."""
    assert count_readings(resolution, start_date, end_date) == expected


@pytest.mark.parametrize(
    ("resolution", "start_date", "end_date", "expected"),
    [
        # a reading of a month is dated to the first of it, so a window opening on the first
        # contains that month and one opening later does not
        (Resolution.MONTHLY, dt.datetime(2026, 1, 1, tzinfo=UTC), dt.datetime(2026, 3, 10, tzinfo=UTC), 3),
        (Resolution.MONTHLY, dt.datetime(2026, 1, 15, tzinfo=UTC), dt.datetime(2026, 3, 10, tzinfo=UTC), 2),
        # the anchor rolls over the turn of the year rather than into a thirteenth month
        (Resolution.MONTHLY, dt.datetime(2026, 12, 15, tzinfo=UTC), dt.datetime(2027, 2, 1, tzinfo=UTC), 2),
        (Resolution.MONTHLY, dt.datetime(2026, 1, 15, tzinfo=UTC), dt.datetime(2026, 1, 20, tzinfo=UTC), 0),
        (Resolution.ANNUAL, dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2026, 6, 1, tzinfo=UTC), 7),
        (Resolution.ANNUAL, dt.datetime(2020, 6, 1, tzinfo=UTC), dt.datetime(2026, 6, 1, tzinfo=UTC), 6),
        (Resolution.ANNUAL, dt.datetime(2026, 6, 1, tzinfo=UTC), dt.datetime(2026, 8, 1, tzinfo=UTC), 0),
    ],
)
def test_count_readings_of_a_calendar_step(
    resolution: Resolution,
    start_date: dt.datetime,
    end_date: dt.datetime,
    expected: int,
) -> None:
    """Test that a calendar resolution is counted from the anchors its readings are dated to."""
    assert count_readings(resolution, start_date, end_date) == expected


def test_count_readings_of_a_resolution_without_an_interval() -> None:
    """Test that a resolution naming no interval answers with nothing rather than with a number.

    `subdaily` is a bucket for "coarser than hourly, finer than daily" rather than an interval,
    and its two providers do not agree on one: DWD takes three Termin readings a day while
    Meteo-France SYNOP reports every three hours. Answering `1h` -- which is what `Frequency` says,
    since over-completing a grid is harmless -- would measure a DWD station that delivered every
    one of its 90 January readings against 721 and skip it for being seven-eighths empty.
    """
    resolution = Resolution.SUBDAILY
    assert reading_interval(resolution) is None
    assert count_readings(resolution, dt.datetime(2026, 1, 1, tzinfo=UTC), dt.datetime(2026, 2, 1, tzinfo=UTC)) is None


def test_reading_interval_answers_for_every_resolution_that_can_be_counted() -> None:
    """Test that the two tables agree: a resolution has an interval exactly when it has a count."""
    start_date, end_date = dt.datetime(2026, 1, 1, tzinfo=UTC), dt.datetime(2026, 2, 1, tzinfo=UTC)
    for resolution in Resolution:
        assert (reading_interval(resolution) is None) == (count_readings(resolution, start_date, end_date) is None), (
            resolution
        )


def test_frequency_answers_for_every_resolution() -> None:
    """Test that the grid `interpolate` and `summarize` build can be built for any resolution.

    `create_date_range` looks the interval up as `Frequency[resolution.name]`, so a resolution
    without a member of that name raises a KeyError there rather than falling back -- and a
    `Frequency` member no resolution is named after is reached by nothing at all.

    Read through `__members__` rather than by iterating, which skips `SUBDAILY`: it is declared as
    an alias of `HOURLY`, the one resolution whose grid is deliberately finer than its readings.
    """
    assert set(Frequency.__members__) == {resolution.name for resolution in Resolution}


def test_the_app_names_the_same_resolutions() -> None:
    """Test that the app's `Resolution` union restates this enum and nothing else.

    The app is TypeScript and cannot import the enum, so it declares the same vocabulary a second
    time -- and it drifted both ways: it carried `undefined` and `dynamic` long after the
    providers resolving to them started reporting a real interval, and never gained `6_minutes`,
    which Meteo-France has been served under all along. A missing member is a type error at every
    call site handling that resolution; a surplus one is a value the app offers and the backend
    rejects.
    """
    source = API_TYPES.read_text(encoding="utf-8")
    union = re.search(r"export type Resolution\n(.*?)\n\n", source, re.DOTALL)
    assert union, f"no `Resolution` union found in {API_TYPES}"
    declared = set(re.findall(r"'([^']+)'", union.group(1)))
    assert declared == {resolution.value for resolution in Resolution}
