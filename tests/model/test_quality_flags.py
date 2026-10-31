# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for how the flags of a reading are written into `quality_flags`."""

from __future__ import annotations

import polars as pl
import pytest

from wetterdienst.model.plausibility import Plausibility
from wetterdienst.model.quality_flags import (
    SPEED_BESIDE,
    Floor,
    NoReading,
    OutOfRange,
    Sentinel,
    calm,
    clear_sentinels,
    join_quality_flags,
    null_sentinels,
    raw_column,
    standard_station_pressure,
    station_pressure_range,
    unpivot_with_raw,
    with_speed_beside,
)

#: every check hard, as the stuck check is not by default
HARD = Plausibility(stuck="hard")


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


def _verdicts(raw: list[str | None]) -> list[str | None]:
    """Write the raw texts the rules gave as `join_quality_flags` writes them into the column."""
    frame = pl.DataFrame({"r": raw}, schema={"r": pl.String})
    return frame.select(join_quality_flags(raw=pl.col("r"))).get_column("quality_flags").to_list()


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
    assert _verdicts(raw) == [
        "rejected:range,raw:4021",
        "rejected:range,raw:110.26",
        None,
        None,
        "rejected:range,raw:-90.5",
        None,
        "raw:NaN",
        None,
    ]


def test_a_text_outside_its_range_keeps_the_cell_as_written() -> None:
    """Test that a value read from text is kept as the source wrote it, and a text that is no number is left alone."""
    cleaned, raw = _clean([" 4021.0", "12", "---", ""], OutOfRange(-90.0, 60.0))
    assert cleaned == [None, "12", "---", ""]
    assert _verdicts(raw) == ["rejected:range,raw:4021.0", None, None, None]


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
    assert _verdicts(out.get_column("raw").to_list()) == [
        "rejected:range,raw:999",
        None,
        "rejected:range,raw:5",
        None,
        "raw:-999",
    ]


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
    assert _verdicts(long.get_column("raw").to_list()) == [None, None, "rejected:range,raw:4021", None]


def test_a_value_below_its_floor_is_the_floor_and_keeps_the_number() -> None:
    """Test that `Floor` maps what is below it to the floor, written as short as it goes, and no more (GH-3263)."""
    cleaned, raw = _clean([-0.02, -0.1, 0.0, 1.2, None, float("nan")], Floor(0.0), text=False)
    assert cleaned[:4] == [0.0, 0.0, 0.0, 1.2]
    assert cleaned[4] is None
    assert cleaned[5] != cleaned[5]  # a NaN is no value below the floor, and stays one
    assert _verdicts(raw) == ["rejected:floor,raw:-0.02", "rejected:floor,raw:-0.1", None, None, None, None]


def test_a_text_below_its_floor_is_read_as_a_number_and_keeps_the_cell() -> None:
    """Test that a text column becomes numbers, the cell as written is the token, and a non-number is null."""
    cleaned, raw = _clean(["-0.10", "2.5", "---", ""], Floor(0.0))
    assert cleaned == [0.0, 2.5, None, None]
    assert _verdicts(raw) == ["rejected:floor,raw:-0.10", None, None, None]


def test_a_floor_can_be_limited_to_the_values_an_expression_selects_and_follows_the_first_rule() -> None:
    """Test that `where` keeps the floor to its parameter, and a sentinel before it decides first."""
    cleaned, raw = null_sentinels(
        pl.col("v"), Sentinel("-999"), Floor(0.0, where=pl.col("parameter") == "rr1"), text=False
    )
    out = pl.DataFrame(
        {"parameter": ["rr1", "rr1", "ttt", "rr1"], "v": [-0.02, -999.0, -0.02, 0.4]},
    ).select(cleaned.alias("cleaned"), raw.alias("raw"))
    assert out.get_column("cleaned").to_list() == [0.0, None, -0.02, 0.4]
    assert _verdicts(out.get_column("raw").to_list()) == ["rejected:floor,raw:-0.02", "raw:-999", None, None]


def test_a_wide_column_below_its_floor_goes_through_the_unpivot_with_its_number() -> None:
    """Test that `clear_sentinels` takes a floor, and keeps an earlier text beside the column."""
    df = pl.DataFrame({"at": [1, 2, 3], "r": [-0.02, None, 0.5], "r__raw": [None, "-", None]})
    long = unpivot_with_raw(clear_sentinels(df, ["r"], Floor(0.0)), index=["at"])
    assert long.get_column("value").to_list() == [0.0, None, 0.5]
    assert _verdicts(long.get_column("raw").to_list()) == ["rejected:floor,raw:-0.02", "raw:-", None]


def test_a_period_that_is_no_reading_nulls_what_it_selects_and_keeps_the_value() -> None:
    """Test that a hard `NoReading` nulls every number its `where` selects, and not a blank (GH-3031)."""
    cleaned, raw = null_sentinels(pl.col("v"), NoReading(pl.col("stuck")), text=False, plausibility=HARD)
    out = pl.DataFrame(
        {"stuck": [True, True, False, True], "v": [0.0, 980.0, 980.0, None]},
    ).select(cleaned.alias("cleaned"), raw.alias("raw"))
    assert out.get_column("cleaned").to_list() == [None, None, 980.0, None]
    assert _verdicts(out.get_column("raw").to_list()) == ["rejected:stuck,raw:0", "rejected:stuck,raw:980", None, None]


@pytest.mark.parametrize("lazy", [False, True], ids=["eager", "lazy"])
def test_a_wind_direction_of_0_is_a_calm_only_beside_a_speed_of_0(lazy: bool) -> None:  # noqa: FBT001
    """Test that the 0 of a direction is null with `raw:0` beside a speed of 0 of its reading alone (GH-3222).

    A 0 beside a wind that blows, or beside a speed the source does not give, stays; the rows keep their order.
    """
    df = pl.DataFrame(
        {
            "timestamp": [1, 1, 2, 2, 3, 3, 4],
            "parameter": ["dd", "ff", "ff", "dd", "dd", "ff", "dd"],
            "value": ["0", "0.0", "1.5", "0", "250", "0", "0"],
        }
    )
    frame = with_speed_beside(df.lazy() if lazy else df, {"dd": "ff"}, on=["timestamp"])
    value, raw = null_sentinels(pl.col("value"), calm(pl.col(SPEED_BESIDE)))
    out = frame.select("timestamp", "parameter", value.alias("value"), raw.alias("raw"))
    out = out.collect() if isinstance(out, pl.LazyFrame) else out
    assert out.rows() == [
        (1, "dd", None, "0"),
        (1, "ff", "0.0", None),
        (2, "ff", "1.5", None),
        (2, "dd", "0", None),
        (3, "dd", "250", None),
        (3, "ff", "0", None),
        (4, "dd", "0", None),
    ]


@pytest.mark.parametrize(
    ("elevation", "expected"),
    # the table of the standard atmosphere: 898.76 hPa at 1,000 m, 795.01 at 2,000 m, 701.21 at 3,000 m, 540.48 at 5 km
    [(0.0, 1013.25), (1000.0, 898.76), (2000.0, 795.01), (3000.0, 701.21), (5000.0, 540.48), (48.0, 1007.5)],
)
def test_the_standard_station_pressure_follows_the_barometric_formula(elevation: float, expected: float) -> None:
    """Test that the pressure expected at an elevation is that of the standard atmosphere (GH-3627)."""
    assert standard_station_pressure(elevation) == pytest.approx(expected, abs=0.5)


def test_a_station_pressure_is_held_to_75_hpa_around_the_formula_in_the_unit_of_the_source() -> None:
    """Test that the range is the pressure of the elevation less and plus 75 hPa, 100 times that in Pa (GH-3627)."""
    hectopascal = station_pressure_range(48.0)
    assert hectopascal is not None
    assert (hectopascal.low, hectopascal.high) == pytest.approx((932.5, 1082.5), abs=0.1)
    pascal = station_pressure_range(48.0, per_hectopascal=100.0)
    assert pascal is not None
    assert (pascal.low, pascal.high) == pytest.approx((93_250.0, 108_250.0), abs=10.0)


def test_a_station_pressure_outside_the_range_of_its_elevation_is_null_with_its_text() -> None:
    """Test that the rule is an OutOfRange: 909.5 hPa at 48 m is null with `raw:909.5`, 1038.9 and the edge stay."""
    rule = station_pressure_range(48.0)
    assert rule is not None
    cleaned, raw = null_sentinels(pl.col("value"), rule, text=False)
    df = pl.DataFrame({"value": [909.5, 932.4, 932.6, 1038.9, 1082.4, 1082.6, 1093.3]}).select(
        cleaned.alias("value"), raw.alias("raw")
    )
    assert df.get_column("value").to_list() == [None, None, 932.6, 1038.9, 1082.4, None, None]
    assert _verdicts(df.get_column("raw").to_list()) == [
        "rejected:elevation,raw:909.5",
        "rejected:elevation,raw:932.4",
        None,
        None,
        None,
        "rejected:elevation,raw:1082.6",
        "rejected:elevation,raw:1093.3",
    ]


def test_a_deep_low_at_a_station_near_sea_level_is_kept_and_a_typo_of_the_zugspitze_is_not() -> None:
    """Test that 940 hPa at 43 m (Dumont d'Urville, 1,008 expected) stays and the Zugspitze's outliers go (GH-3627)."""
    low = station_pressure_range(43.0)
    assert low is not None
    cleaned, raw = null_sentinels(pl.col("value"), low, text=False)
    sea = pl.DataFrame({"value": [940.0, 938.2, 909.5]}).select(cleaned.alias("value"), raw.alias("raw"))
    assert sea.get_column("value").to_list() == [940.0, 938.2, None]
    assert _verdicts(sea.get_column("raw").to_list()) == [None, None, "rejected:elevation,raw:909.5"]
    high = station_pressure_range(2956.0)
    assert high is not None
    cleaned, raw = null_sentinels(pl.col("value"), high, text=False)
    zugspitze = pl.DataFrame({"value": [713.0, 780.0, 802.2, 908.6, 968.6]}).select(
        cleaned.alias("value"), raw.alias("raw")
    )
    assert zugspitze.get_column("value").to_list() == [713.0, 780.0, None, None, None]
    assert _verdicts(zugspitze.get_column("raw").to_list()) == [
        None,
        None,
        "rejected:elevation,raw:802.2",
        "rejected:elevation,raw:908.6",
        "rejected:elevation,raw:968.6",
    ]


@pytest.mark.parametrize("elevation", [None, float("nan"), -999.0, 12_000.0])
def test_a_station_without_a_plausible_elevation_has_no_pressure_rule(elevation: float | None) -> None:
    """Test that a catalogue without an elevation, or with a code or a typo for one, is no ground to null a reading."""
    assert station_pressure_range(elevation) is None


def test_any_parameter_can_be_laid_beside_another_under_a_name_of_its_own() -> None:
    """Test that `into` names the column, so that the air temperature can be laid beside the road surface (GH-3624)."""
    df = pl.DataFrame(
        {
            "timestamp": [1, 1, 2],
            "parameter": ["surface", "air", "surface"],
            "value": [30.0, 5.0, 31.0],
        }
    )
    out = with_speed_beside(df, {"surface": "air"}, on=["timestamp"], into="__air")
    assert SPEED_BESIDE not in out.columns
    assert out.get_column("__air").to_list() == [5.0, None, None]
