# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the one way a timestamp is written in a body the library hands out (GH-2633)."""

import datetime as dt

import polars as pl
import pytest

from wetterdienst.util.datetime import format_timestamp, parse_date, timestamps_to_string


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (dt.datetime(2026, 9, 1, tzinfo=dt.UTC), "2026-09-01T00:00:00.000000+00:00"),
        (dt.datetime(1926, 5, 1, 12, 30, 15, 123456, tzinfo=dt.UTC), "1926-05-01T12:30:15.123456+00:00"),
        # no zone is UTC, as everywhere in the library
        (dt.datetime(2026, 9, 1, 6), "2026-09-01T06:00:00.000000+00:00"),  # noqa: DTZ001
        # another zone is converted, not written with its offset
        (dt.datetime(2026, 9, 1, 2, tzinfo=dt.timezone(dt.timedelta(hours=2))), "2026-09-01T00:00:00.000000+00:00"),
    ],
)
def test_format_timestamp_writes_utc_to_the_microsecond(value: dt.datetime, expected: str) -> None:
    """Test that a datetime is written as ISO 8601 in UTC, to the microsecond, with its offset."""
    assert format_timestamp(value) == expected


@pytest.mark.parametrize("time_unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("time_zone", ["UTC", "Europe/Berlin", None])
def test_timestamps_to_string_agrees_with_format_timestamp(time_unit: str, time_zone: str | None) -> None:
    """Test that a frame's column is written as `format_timestamp` writes one, whatever its unit and zone.

    Polars' own ISO text has as many digits as the unit has, so a stations frame of milliseconds and a
    values frame of microseconds wrote two formats.
    """
    values = [dt.datetime(2026, 9, 1, 0, 0, 0, 123000, tzinfo=dt.UTC), dt.datetime(1926, 5, 1, tzinfo=dt.UTC), None]
    series = pl.Series("timestamp", values, dtype=pl.Datetime("us", "UTC")).cast(pl.Datetime(time_unit, "UTC"))
    if time_zone is None:
        series = series.dt.replace_time_zone(None)
    elif time_zone != "UTC":
        series = series.dt.convert_time_zone(time_zone)
    written = timestamps_to_string(series.to_frame()).get_column("timestamp")
    assert written.to_list() == [
        "2026-09-01T00:00:00.123000+00:00",
        "1926-05-01T00:00:00.000000+00:00",
        None,
    ]
    assert written.to_list()[:2] == [format_timestamp(value) for value in values[:2] if value is not None]


def test_timestamps_to_string_leaves_the_other_columns_and_the_columns_not_named() -> None:
    """Test that only the datetime columns asked for are written, and the others keep their type."""
    df = pl.DataFrame(
        {
            "start": [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)],
            "end": [dt.datetime(2020, 1, 2, tzinfo=dt.UTC)],
            "value": [1.0],
        },
    )
    assert timestamps_to_string(df, ["start"]).schema == {
        "start": pl.String,
        "end": pl.Datetime("us", "UTC"),
        "value": pl.Float64,
    }
    assert timestamps_to_string(df).schema == {"start": pl.String, "end": pl.String, "value": pl.Float64}
    # a column that is not there is not an error: an empty result of no columns has no stamps to write
    assert timestamps_to_string(pl.DataFrame(), ["start"]).is_empty()


def test_a_written_timestamp_reads_back_as_a_date_the_requests_take() -> None:
    """Test that what a listing writes, as `/api/issues` does, is accepted by `parse_date` as a request."""
    value = dt.datetime(2026, 10, 4, 6, tzinfo=dt.UTC)
    assert parse_date(format_timestamp(value)) == value
