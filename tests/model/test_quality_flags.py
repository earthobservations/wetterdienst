# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for how the flags of a reading are written into `quality_flags`."""

from __future__ import annotations

import polars as pl
import pytest

from wetterdienst.model.quality_flags import join_quality_flags


def _flags(df: pl.DataFrame, expr: pl.Expr) -> list[str | None]:
    return df.select(expr).get_column("quality_flags").to_list()


def test_a_source_with_one_flag_writes_its_plain_code() -> None:
    """Test that the flag of a single-flag source is the code as the source writes it, null where it is blank."""
    df = pl.DataFrame({"flag": ["T", " Good ", "", None]})
    assert _flags(df, join_quality_flags(pl.col("flag"))) == ["T", "Good", None, None]


def test_a_number_is_written_without_a_decimal_point() -> None:
    """Test that an integer code is written as its digits."""
    df = pl.DataFrame({"flag": [3, 10, None]})
    assert _flags(df, join_quality_flags(pl.col("flag"))) == ["3", "10", None]


def test_the_quality_flag_is_plain_and_the_other_kinds_follow_with_their_name() -> None:
    """Test `quality,kind:code,...` in the order the kinds are given, a blank flag left out and no `quality:` prefix."""
    df = pl.DataFrame(
        {
            "q": ["G", None, "", "X", None],
            "m": ["T", "T", "", None, ""],
            "s": [7, None, None, 1, None],
        },
    )
    expr = join_quality_flags(pl.col("q"), measurement=pl.col("m"), source=pl.col("s"))
    assert _flags(df, expr) == [
        "G,measurement:T,source:7",
        "measurement:T",
        None,
        "X,source:1",
        None,
    ]


def test_a_further_kind_is_appended_without_changing_the_rest() -> None:
    """Test that a kind added at the end leaves the tokens before it as they were, so a caller's split holds."""
    df = pl.DataFrame({"q": ["3"], "e": ["E"], "r": ["-9999"]})
    before = _flags(df, join_quality_flags(pl.col("q"), element=pl.col("e")))
    after = _flags(df, join_quality_flags(pl.col("q"), element=pl.col("e"), raw=pl.col("r")))
    assert before == ["3,element:E"]
    assert after == ["3,element:E,raw:-9999"]
    assert after[0].split(",")[:2] == before[0].split(",")


def test_a_source_with_only_further_kinds_leaves_the_quality_flag_out() -> None:
    """Test that `None` for the quality flag writes only the kinds."""
    df = pl.DataFrame({"s": ["0", None]})
    assert _flags(df, join_quality_flags(None, source=pl.col("s"))) == ["source:0", None]


def test_a_call_without_a_flag_is_refused() -> None:
    """Test that there is nothing to join without a flag."""
    with pytest.raises(ValueError, match="at least one flag"):
        join_quality_flags()
