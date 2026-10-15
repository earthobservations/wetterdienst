# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the file index helpers of the IMGW providers."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import portion
import pytest

from wetterdienst.provider.imgw.fileindex import keep_files_overlapping

UTC = ZoneInfo("UTC")


def _kept(interval: portion.Interval) -> list[str]:
    """Name the files of 2020, 2021 and 2022 that a window keeps, each covering its year."""
    df = pl.DataFrame({"file": ["a", "b", "c"], "year": [2020, 2021, 2022]})
    start = pl.datetime(pl.col("year"), 1, 1, time_zone="UTC")
    end = pl.datetime(pl.col("year"), 12, 31, time_zone="UTC")
    return keep_files_overlapping(df, start, end, interval).get_column("file").to_list()


def test_keep_files_overlapping_includes_both_ends_of_a_period() -> None:
    """Test that a window touching the first or last instant of a period keeps its file."""
    window = portion.closed(dt.datetime(2020, 12, 31, tzinfo=UTC), dt.datetime(2021, 1, 1, tzinfo=UTC))
    assert _kept(window) == ["a", "b"]
    window = portion.closed(dt.datetime(2021, 12, 31, 1, tzinfo=UTC), dt.datetime(2022, 1, 1, tzinfo=UTC))
    assert _kept(window) == ["c"]


def test_keep_files_overlapping_compares_instants_not_wall_clocks() -> None:
    """Test that a window written in another zone cuts at the same instants as one written in UTC."""
    berlin = ZoneInfo("Europe/Berlin")
    # 2020-12-31 00:30 in Berlin is 2020-12-30 23:30 UTC, before the last instant of the file of 2020 (2020-12-31
    # 00:00 UTC); read as UTC it would be half an hour after it
    instant = dt.datetime(2020, 12, 31, 0, 30, tzinfo=berlin)
    assert _kept(portion.closed(instant, instant)) == ["a"]


def test_keep_files_overlapping_keeps_nothing_for_an_empty_window() -> None:
    """Test that a window that ends before it starts overlaps no file, however wide the files are."""
    assert _kept(portion.closed(dt.datetime(2021, 6, 1, tzinfo=UTC), dt.datetime(2021, 5, 1, tzinfo=UTC))) == []


def test_keep_files_overlapping_refuses_a_file_without_a_period() -> None:
    """Test that a file whose period is null is an error that names it, not a file left out."""
    df = pl.DataFrame({"file": ["a", "b"], "year": [2020, None]})
    start = pl.datetime(pl.col("year"), 1, 1, time_zone="UTC")
    end = pl.datetime(pl.col("year"), 12, 31, time_zone="UTC")
    window = portion.closed(dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 2, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match=r"\['b'\]"):
        keep_files_overlapping(df, start, end, window)


def test_keep_files_overlapping_drops_a_period_that_ends_before_it_starts() -> None:
    """Test that a file whose period is empty overlaps no window, as an empty interval did."""
    df = pl.DataFrame({"file": ["a", "b"], "first": [2020, 2022], "last": [2021, 2019]})
    start = pl.datetime(pl.col("first"), 1, 1, time_zone="UTC")
    end = pl.datetime(pl.col("last"), 12, 31, time_zone="UTC")
    window = portion.closed(dt.datetime(2019, 1, 1, tzinfo=UTC), dt.datetime(2023, 1, 1, tzinfo=UTC))
    assert keep_files_overlapping(df, start, end, window).get_column("file").to_list() == ["a"]
