# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Test the polars utility functions."""

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.util.polars_util import read_fwf_from_df


@pytest.fixture
def df() -> pl.DataFrame:
    """Provide DataFrame with a header."""
    return pl.DataFrame({"abcdefABCDEF": ["abcdefABCDEF"]}, orient="col")


@pytest.fixture
def df_short_header() -> pl.DataFrame:
    """Provide DataFrame with a short header."""
    return pl.DataFrame({"short": ["abcdefABCDEF"]}, orient="col")


@pytest.fixture
def df_expected_no_header() -> pl.DataFrame:
    """Provide expected DataFrame without header."""
    return pl.DataFrame({"column_0": ["abcdef"], "column_1": ["ABCDEF"]}, orient="col")


def test_read_fwf_from_df(df: pl.DataFrame) -> None:
    """Test that reading fwf from a DataFrame works correctly."""
    df_given = read_fwf_from_df(df, column_specs=((0, 5), (6, 11)), header=True)
    df_expected = pl.DataFrame({"abcdef": ["abcdef"], "ABCDEF": ["ABCDEF"]}, orient="col")
    assert_frame_equal(df_given, df_expected)


def test_read_fwf_from_df_no_header(df: pl.DataFrame, df_expected_no_header: pl.DataFrame) -> None:
    """Test that no header is handled correctly."""
    df_given = read_fwf_from_df(df, column_specs=((0, 5), (6, 11)), header=False)
    assert_frame_equal(df_given, df_expected_no_header)


def test_read_fwf_from_df_short_header(df_short_header: pl.DataFrame, df_expected_no_header: pl.DataFrame) -> None:
    """Test that a short header is handled correctly."""
    df_given = read_fwf_from_df(df_short_header, column_specs=((0, 5), (6, 11)), header=True)
    assert_frame_equal(df_given, df_expected_no_header)


def test_read_fwf_from_df_column_specs_out_of_bounds(df: pl.DataFrame) -> None:
    """Test that column specs out of bounds are handled correctly."""
    df = read_fwf_from_df(df, column_specs=((100, 110),))
    assert df.get_column("column_0").item() is None


def test_read_fwf_from_df_multiple_columns_fail() -> None:
    """Test that reading fwf from a DataFrame only supports one column."""
    df = pl.DataFrame({"a": ["foo"], "b": ["bar"]}, orient="col")
    with pytest.raises(ValueError, match="reading fwf from a DataFrame only supports one column"):
        read_fwf_from_df(df, ((0, 2), (2, 3)))
