# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for shared interpolation and summary tools."""

import datetime as dt
import logging
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.core.util import build_date_grid
from wetterdienst.metadata.resolution import Resolution, reading_interval

UTC = ZoneInfo("UTC")


@pytest.mark.parametrize(
    ("resolution", "start_date", "end_date", "expected_height", "expected_first"),
    [
        (
            Resolution.MINUTE_10,
            dt.datetime(2024, 1, 1, tzinfo=UTC),
            dt.datetime(2024, 1, 2, tzinfo=UTC),
            145,
            dt.datetime(2024, 1, 1, tzinfo=UTC),
        ),
        (
            Resolution.DAILY,
            dt.datetime(2020, 1, 1, tzinfo=UTC),
            dt.datetime(2020, 3, 1, tzinfo=UTC),
            61,
            dt.datetime(2020, 1, 1, tzinfo=UTC),
        ),
        (
            # a monthly reading is dated to the first, which is what the range is rounded onto
            Resolution.MONTHLY,
            dt.datetime(2020, 1, 15, tzinfo=UTC),
            dt.datetime(2021, 6, 1, tzinfo=UTC),
            17,
            dt.datetime(2020, 1, 1, tzinfo=UTC),
        ),
        (
            Resolution.ANNUAL,
            dt.datetime(2000, 1, 1, tzinfo=UTC),
            dt.datetime(2010, 1, 1, tzinfo=UTC),
            11,
            dt.datetime(2000, 1, 1, tzinfo=UTC),
        ),
    ],
)
def test_build_date_grid_spans_the_window_at_the_resolution(
    resolution: Resolution,
    start_date: dt.datetime,
    end_date: dt.datetime,
    expected_height: int,
    expected_first: dt.datetime,
) -> None:
    """Test that the grid covers the window at the interval the resolution records at."""
    df = build_date_grid(resolution, start_date, end_date)

    assert df.columns == ["date"]
    assert df.height == expected_height
    assert df.get_column("date").min() == expected_first


def test_build_date_grid_snaps_an_off_phase_window_to_the_wall_clock() -> None:
    """Test that a window opening at half past does not carry its phase through the whole series.

    The range is generated from the window and then rounded to the same interval, so a request
    from 00:30 answers for whole hours rather than for every half past -- which is what every
    station's readings are joined onto, by an exact join.
    """
    df = build_date_grid(
        Resolution.HOURLY,
        dt.datetime(2024, 1, 1, 0, 30, tzinfo=UTC),
        dt.datetime(2024, 1, 1, 6, 30, tzinfo=UTC),
    )

    assert df.get_column("date").dt.minute().unique().to_list() == [0]
    assert df.get_column("date").min() == dt.datetime(2024, 1, 1, 1, tzinfo=UTC)


def test_build_date_grid_treats_subdaily_as_hourly() -> None:
    """Test that subdaily gets a grid, at the one interval available for it.

    `reading_interval` declines to name an interval for subdaily -- it is a bucket rather than an
    interval, and DWD takes three Termin readings a day where Meteo-France SYNOP reports every
    three hours. A grid still needs one, and naming it too fine only leaves rows no station has a
    reading for, which is harmless here in a way it is not where a station is measured against how
    much of a window it filled.
    """
    assert reading_interval(Resolution.SUBDAILY) is None

    df = build_date_grid(
        Resolution.SUBDAILY,
        dt.datetime(2024, 1, 1, tzinfo=UTC),
        dt.datetime(2024, 1, 2, tzinfo=UTC),
    )

    assert df.height == 25  # hourly, both ends included


def test_report_height_exclusions_raises_where_nothing_is_left() -> None:
    """A request emptied by heights alone is a question that cannot be answered as asked.

    Left to itself it comes back as an empty frame with the reason in a server-side log, which is
    the one place the caller cannot look -- so it is raised, and the message says what to do about
    it. Thirteen providers have stations without heights, FMI's, IPMA's and the Environment
    Agency's being all of them.
    """
    from wetterdienst.core.util import report_height_exclusions  # noqa: PLC0415
    from wetterdienst.exceptions import NoStationsWithHeightError  # noqa: PLC0415

    param_key = ("daily", "climate_summary", "temperature_air_mean_2m")
    with pytest.raises(NoStationsWithHeightError, match=r"no answer at 200\.0 m for daily/climate_summary/temperature"):
        report_height_exclusions({}, {param_key}, 200.0)


def test_report_height_exclusions_warns_where_something_still_answers(caplog: pytest.LogCaptureFixture) -> None:
    """A parameter emptied beside one that answered is named, not raised.

    There is a result to read the warning against, and taking the whole request down over one of
    its parameters would throw away readings the caller can use.
    """
    from wetterdienst.core.util import _ParameterData, report_height_exclusions  # noqa: PLC0415

    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    answered = _ParameterData(grid.with_columns(pl.Series("00011", [1.0, 2.0, 3.0])))
    param_dict = {("daily", "climate_summary", "precipitation_height"): answered}
    with caplog.at_level(logging.WARNING):
        report_height_exclusions(param_dict, {("daily", "climate_summary", "temperature_air_mean_2m")}, 200.0)
    assert "daily/climate_summary/temperature_air_mean_2m" in caplog.text
    assert "the rest of the result stands" in caplog.text


def test_report_height_exclusions_keeps_quiet_where_the_answer_stands() -> None:
    """A station turned away where another was taken cost the answer nothing.

    Nor is a request that lost no station to a height worth a word: the helper runs on every
    interpolation and summary, elevation or not.
    """
    from wetterdienst.core.util import _ParameterData, report_height_exclusions  # noqa: PLC0415

    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    param_key = ("daily", "climate_summary", "temperature_air_mean_2m")
    answered = {param_key: _ParameterData(grid.with_columns(pl.Series("00011", [1.0, 2.0, 3.0])))}
    # the parameter kept a station of its own, so the one turned away is not worth reporting
    report_height_exclusions(answered, {param_key}, 200.0)
    # and nothing was turned away at all
    report_height_exclusions({}, set(), None)
