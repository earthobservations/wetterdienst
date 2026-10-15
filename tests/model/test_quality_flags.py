# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for how the flags of a reading are written into `quality_flags`."""

from __future__ import annotations

import polars as pl
import pytest

from wetterdienst.model.quality_flags import (
    OutOfRange,
    Sentinel,
    clear_sentinels,
    join_quality_flags,
    null_sentinels,
    raw_column,
    unpivot_with_raw,
)


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


def _clean(values: list, *sentinels: Sentinel, **kwargs: bool) -> tuple[list, list]:
    """Give the cleaned values and the raw texts of a column of values."""
    cleaned, raw = null_sentinels(pl.col("v"), *sentinels, **kwargs)
    out = pl.DataFrame({"v": values}).select(cleaned.alias("cleaned"), raw.alias("raw"))
    return out.get_column("cleaned").to_list(), out.get_column("raw").to_list()


def test_a_sentinel_read_from_text_is_nulled_and_its_text_kept_as_written() -> None:
    """Test that the token is the cell as the source wrote it: `-999.0` stays `-999.0`, padding is stripped."""
    cleaned, raw = _clean(["  -999", "-999.0", "5", "", None, "-9999"], Sentinel("-999"))
    assert cleaned == [None, None, "5", "", None, "-9999"]
    assert raw == ["-999", "-999.0", None, None, None, None]


def test_a_sentinel_read_from_a_number_is_written_as_declared() -> None:
    """Test that a number carries the declared text, `-999`, where formatting the float would say `-999.0`."""
    cleaned, raw = _clean(
        [-999.0, 5.0, None, float("nan"), 99.9], Sentinel("-999", "99.9"), Sentinel("NaN"), text=False
    )
    assert cleaned == [None, 5.0, None, None, None]
    assert raw == ["-999", None, None, "NaN", "99.9"]


def test_a_sentinel_can_stand_for_a_value() -> None:
    """Test that `to` keeps the text of the sentinel beside the value it means (FMI's -1 for no precipitation)."""
    cleaned, raw = _clean(["-1", "0.4", "NaN", None], Sentinel("-1", to=0.0), Sentinel("NaN"))
    assert cleaned == [0.0, 0.4, None, None]
    assert raw == ["-1", None, "NaN", None]


def test_a_sentinel_can_be_limited_to_the_values_an_expression_selects() -> None:
    """Test that `where` leaves the same number alone where it is a reading."""
    cleaned, raw = null_sentinels(pl.col("v"), Sentinel("9", where=pl.col("parameter") == "n"))
    out = pl.DataFrame({"parameter": ["n", "t"], "v": ["9", "9"]}).select(cleaned.alias("cleaned"), raw.alias("raw"))
    assert out.get_column("cleaned").to_list() == [None, "9"]
    assert out.get_column("raw").to_list() == ["9", None]


def test_the_first_sentinel_that_matches_decides() -> None:
    """Test that a value is mapped once, by the first rule that holds."""
    cleaned, raw = _clean(["-1"], Sentinel("-1", to=0.0), Sentinel("-1"))
    assert cleaned == [0.0]
    assert raw == ["-1"]


def test_text_that_is_no_number_can_be_a_sentinel_too() -> None:
    """Test that `non_numeric` maps `mq` and `---` with their text, and leaves a blank and a number alone."""
    cleaned, raw = _clean(["mq", "---", "", " ", None, "3.5", "-999"], Sentinel("-999"), non_numeric=True)
    assert cleaned == [None, None, None, None, None, 3.5, None]
    assert raw == ["mq", "---", None, None, None, None, "-999"]


def test_a_nan_or_an_infinity_in_a_text_is_no_reading_either() -> None:
    """Test that `cast` taking `nan` and `inf` for numbers does not let them through as values."""
    cleaned, raw = _clean(["nan", "-inf", "1.5"], non_numeric=True)
    assert cleaned == [None, None, 1.5]
    assert raw == ["nan", "-inf", None]


def test_a_text_with_the_separator_of_the_tokens_is_kept_without_it() -> None:
    """Test that a free text cannot split the string: its comma is written as a semicolon."""
    cleaned, raw = _clean(["n/a, see note"], non_numeric=True)
    assert cleaned == [None]
    assert raw == ["n/a; see note"]


def test_a_number_has_no_text_that_could_be_no_number() -> None:
    """Test that `non_numeric` needs the text of the source."""
    with pytest.raises(ValueError, match="needs `text=True`"):
        null_sentinels(pl.col("v"), non_numeric=True, text=False)


@pytest.mark.parametrize("text", ["", " ", "-9,9"])
def test_a_sentinel_text_is_a_token_of_a_comma_separated_string(text: str) -> None:
    """Test that a text that is blank or holds the separator cannot be declared."""
    with pytest.raises(ValueError, match="cannot be the text of a sentinel"):
        Sentinel(text)


def test_a_sentinel_needs_a_text() -> None:
    """Test that a rule without a text is refused."""
    with pytest.raises(ValueError, match="needs the text"):
        Sentinel()


def test_the_raw_token_comes_after_the_flag_and_the_other_kinds() -> None:
    """Test `G,raw:-9999` for a source with a plain flag, and `3,element:E,raw:-999` with a further kind."""
    cleaned, raw = null_sentinels(pl.col("v"), Sentinel("-9999", "-999"))
    out = pl.DataFrame({"v": ["-9999", "4.0", "-999"], "q": ["G", "G", "3"], "e": [None, None, "E"]}).select(
        cleaned.alias("v"),
        join_quality_flags(pl.col("q"), element=pl.col("e"), raw=raw),
    )
    assert out.get_column("v").to_list() == [None, "4.0", None]
    assert out.get_column("quality_flags").to_list() == ["G,raw:-9999", "G", "3,element:E,raw:-999"]


def test_a_wide_frame_keeps_the_text_beside_its_column_through_the_unpivot() -> None:
    """Test that the rules of a column record the first match and the long frame has it as `raw`."""
    df = pl.DataFrame({"at": [1, 2, 3], "t": ["1", "-999", "2"], "w": ["3", "990", "-999"]})
    df = clear_sentinels(df, ["t", "w", "missing"], Sentinel("-999"))
    df = clear_sentinels(df, ["w"], Sentinel("990"))
    long = unpivot_with_raw(df, index=["at"]).sort("parameter", "at")
    assert long.columns == ["at", "parameter", "value", "raw"]
    assert long.get_column("value").to_list() == ["1", None, "2", "3", None, None]
    assert long.get_column("raw").to_list() == [None, "-999", None, None, "990", "-999"]


def test_a_numeric_column_of_a_wide_frame_is_read_as_a_number() -> None:
    """Test that the dtype of the column decides, and the token of a number is the declared text."""
    df = clear_sentinels(pl.DataFrame({"t": [-999, 5], "s": ["-999.0", "5"]}).lazy(), ["t", "s"], Sentinel("-999"))
    out = df.collect()
    assert out.get_column("t").to_list() == [None, 5]
    assert out.get_column(raw_column("t")).to_list() == ["-999", None]
    assert out.get_column(raw_column("s")).to_list() == ["-999.0", None]


def test_a_column_without_a_rule_has_no_raw_text() -> None:
    """Test that the unpivot gives a null `raw` to a column no rule cleaned."""
    long = unpivot_with_raw(pl.DataFrame({"at": [1], "t": ["1"]}), index=["at"])
    assert long.get_column("raw").to_list() == [None]


def test_a_number_outside_its_range_is_nulled_and_written_as_short_as_it_goes() -> None:
    """Test that 4021 is no 4021.0 in the token, the bounds are readings, and a NaN lies outside every range."""
    cleaned, raw = _clean(
        [4021.0, 110.26, 60.0, -90.0, -90.5, None, float("nan"), 0.0], OutOfRange(-90.0, 60.0), text=False
    )
    assert cleaned == [None, None, 60.0, -90.0, None, None, None, 0.0]
    assert raw == ["4021", "110.26", None, None, "-90.5", None, "NaN", None]


def test_a_text_outside_its_range_keeps_the_cell_as_written() -> None:
    """Test that a value read from text is kept as the source wrote it, and a text that is no number is left alone."""
    cleaned, raw = _clean([" 4021.0", "12", "---", ""], OutOfRange(-90.0, 60.0))
    assert cleaned == [None, "12", "---", ""]
    assert raw == ["4021.0", None, None, None]


def test_a_range_can_be_limited_to_the_values_an_expression_selects() -> None:
    """Test that `where` holds each parameter to its own range, and a sentinel before it decides first."""
    cleaned, raw = null_sentinels(
        pl.col("v"),
        Sentinel("-999"),
        OutOfRange(0.0, 130.0, where=pl.col("parameter") == "humidity"),
        OutOfRange(300.0, 1_100.0, where=pl.col("parameter") == "pressure"),
        text=False,
    )
    out = pl.DataFrame(
        {
            "parameter": ["humidity", "pressure", "pressure", "temperature", "humidity"],
            "v": [999.0, 1013.2, 5.0, 999.0, -999.0],
        }
    ).select(cleaned.alias("cleaned"), raw.alias("raw"))
    assert out.get_column("cleaned").to_list() == [None, 1013.2, None, 999.0, None]
    assert out.get_column("raw").to_list() == ["999", None, "5", None, "-999"]


def test_a_range_that_holds_no_value_is_refused() -> None:
    """Test that swapped bounds are a defect of the reader, not a rule that nulls everything."""
    with pytest.raises(ValueError, match="holds no value"):
        OutOfRange(60.0, -90.0)


def test_a_wide_column_outside_its_range_goes_through_the_unpivot_with_its_text() -> None:
    """Test that `clear_sentinels` takes a range, and the long frame carries what the value was."""
    df = clear_sentinels(
        pl.DataFrame({"at": [1, 2], "t": [4021.0, 17.5], "p": [1013.2, 5.0]}), ["t"], OutOfRange(-90.0, 60.0)
    )
    long = unpivot_with_raw(df, index=["at"]).sort("parameter", "at")
    assert long.get_column("value").to_list() == [1013.2, 5.0, None, 17.5]
    assert long.get_column("raw").to_list() == [None, None, "4021", None]
