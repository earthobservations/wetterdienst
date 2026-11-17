# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check `floor` of the forecast networks clips round-off only (GH-4182).

A value a model writes a little below 0 for an amount that cannot be negative is set to 0.0 with the number as written
kept as `raw:` (soft: kept and `suspect:floor`). One further below than the tolerance of its quantity
(`FLOORS` of `model/judge.py`) is no round-off: it is not clipped, and the range of the parameter judges it. On a
forecast network every check but `floor` and `limits` is soft, so the range keeps the value and flags it
`suspect:range`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from tests.provider.value_stubs import dwd_dmo_values, dwd_mosmix_values
from wetterdienst import Options

if TYPE_CHECKING:
    import pytest

KEEP = {"drop_nulls": False, "convert_units": False}


def _flags(df: pl.DataFrame, parameter: str) -> tuple[list[float | None], list[str | None]]:
    df = df.filter(pl.col("parameter") == parameter).sort("timestamp")
    return df["value"].to_list(), df["quality_flags"].to_list()


def _snow(monkeypatch: pytest.MonkeyPatch, values: str, **options: object) -> pl.DataFrame:
    return dwd_mosmix_values(
        monkeypatch,
        {"SnCv": values},
        [("hourly", "snow", "sncv")],
        options=Options(**KEEP, **options),
    )


def test_a_snow_depth_within_the_tolerance_is_zero_and_a_larger_negative_is_the_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """-0.02 and -0.04 m (to 5 cm) are round-off; -0.06 m and -15 m are not, and are flagged by the range."""
    values, flags = _flags(_snow(monkeypatch, "-0.02 -0.04 -0.06"), "snow_depth")
    assert values == [0.0, 0.0, -0.06]
    assert flags == ["rejected:floor,raw:-0.02", "rejected:floor,raw:-0.04", "suspect:range"]
    # -0.06 m is above the -10 cm that the table allows a reading of a station: the floor's 0 is the low end here
    values, flags = _flags(_snow(monkeypatch, "0.30 -15.00 -0.01"), "snow_depth")
    assert values == [0.3, -15.0, 0.0]
    assert flags == [None, "suspect:range", "rejected:floor,raw:-0.01"]


def test_the_same_in_the_units_of_the_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tolerance is in the canonical unit (cm), whatever unit the source writes: -0.02 m is -2 cm."""
    df = dwd_mosmix_values(
        monkeypatch,
        {"SnCv": "-0.02 -15.00 0.30"},
        [("hourly", "snow", "sncv")],
        options=Options(drop_nulls=False),
    )
    values, flags = _flags(df, "snow_depth")
    assert values == [0.0, -1500.0, 30.0]
    assert flags == ["rejected:floor,raw:-0.02", "suspect:range", None]


def test_a_soft_floor_keeps_the_round_off_and_flags_it_and_the_range_still_judges_the_large(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`floor` soft: the number is kept as `suspect:floor` within the tolerance; below it, `suspect:range` as before."""
    values, flags = _flags(_snow(monkeypatch, "-0.02 -15.00 0.30", plausibility={"floor": "soft"}), "snow_depth")
    assert values == [-0.02, -15.0, 0.3]
    assert flags == ["suspect:floor", "suspect:range", None]
    # every check soft, the forecast's mode for all but `floor`: the same
    values, flags = _flags(_snow(monkeypatch, "-0.02 -15.00 0.30", plausibility="soft"), "snow_depth")
    assert values == [-0.02, -15.0, 0.3]
    assert flags == ["suspect:floor", "suspect:range", None]


def test_a_large_negative_of_a_station_range_is_flagged_where_the_range_is_asked_to_be_hard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A forecast is judged soft in `range` whatever the request sets (GH-3681): the value stays, flagged."""
    values, flags = _flags(_snow(monkeypatch, "-15.00 0.00 0.30", plausibility={"range": "hard"}), "snow_depth")
    assert values == [-15.0, 0.0, 0.3]
    assert flags == ["suspect:range", None, None]


def test_dmo_precipitation_and_radiation_follow_the_same_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """ICON's round-off (-0.02 and -0.10 mm, -0.77 J/cm2) is 0.0; -5 mm and -50 J/cm2 are no round-off."""
    df = dwd_dmo_values(
        monkeypatch,
        {"RR1": "-0.02 -0.10 -5.00", "Rad1h": "-0.77 -50.00 0.00"},
        [("hourly", "icon", "rr1"), ("hourly", "icon", "rad1h")],
        options=Options(**KEEP),
    )
    assert _flags(df, "precipitation_amount_last_1h") == (
        [0.0, 0.0, -5.0],
        ["rejected:floor,raw:-0.02", "rejected:floor,raw:-0.1", "suspect:range"],
    )
    # in J/cm2 as ICON writes them: 50 J/cm2 are 0.5 MJ/m2 (the radiation is judged in MJ/m2)
    values, flags = _flags(df, "radiation_global")
    assert values == [0.0, -50.0, 0.0]
    assert flags == ["rejected:floor,raw:-0.77", "suspect:range", None]


def test_mosmix_l_percentages_wind_and_probabilities_below_zero_are_the_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    """`RSunD` to -10 %, `N05` to -8 %, `wwS` -1 % and `FF` -0.51 m/s are held to a lower bound of 0 (GH-4182).

    They are no round-off and `floor` does not name them: the range of their parameter flags them (soft on a forecast,
    so the value stays). `E_DD`, a signed error, has no bound and is left as written.
    """
    cases = {
        "RSunD": ("rsund", "sunshine_duration_relative_last_24h", "-10 50 100", [-10.0, 50.0, 100.0]),
        "N05": ("n05", "cloud_cover_below_500ft", "-8 0 10", [-8.0, 0.0, 10.0]),
        "wwS": ("wws", "probability_precipitation_solid_last_1h", "-1 20 100", [-1.0, 20.0, 100.0]),
        "FF": ("ff", "wind_speed", "-0.51 3.00 4.00", [-0.51, 3.0, 4.0]),
    }
    for element, (original, name, text, expected) in cases.items():
        df = dwd_mosmix_values(
            monkeypatch,
            {element: text},
            [("hourly", "large", original)],
            options=Options(**KEEP),
        )
        values, flags = _flags(df, name)
        assert values == expected, element
        assert flags == ["suspect:range", None, None], element
    df = dwd_mosmix_values(monkeypatch, {"E_DD": "-4 10 20"}, [("hourly", "large", "e_dd")], options=Options(**KEEP))
    values, flags = _flags(df, "error_absolute_wind_direction")
    assert values == [-4.0, 10.0, 20.0]
    assert flags == [None, None, None]
