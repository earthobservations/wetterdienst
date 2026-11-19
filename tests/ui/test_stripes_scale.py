# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the colour scale of the climate stripes: Hawkins' method and its fallback (GH-4157)."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

import pytest

from wetterdienst.ui import stripes_scale
from wetterdienst.ui.stripes_scale import (
    BLUES,
    BRBG_DRY,
    BRBG_WET,
    CLASS_SIGMA,
    CLASSES,
    MIN_CENTRE_YEARS,
    MIN_SPREAD_YEARS,
    PRECIPITATION_PALETTE,
    REDS,
    TEMPERATURE_PALETTE,
    StripesReference,
    StripesReferenceStat,
    _sample,
    stripe_class,
    stripes_palette,
    stripes_reference,
)

# ColorBrewer's 9-class sequential Blues and Reds (https://colorbrewer2.org/#type=sequential&scheme=Blues&n=9 and
# ...scheme=Reds&n=9), from the palest to the darkest
COLORBREWER_BLUES_9 = (
    "#f7fbff",
    "#deebf7",
    "#c6dbef",
    "#9ecae1",
    "#6baed6",
    "#4292c6",
    "#2171b5",
    "#08519c",
    "#08306b",
)
COLORBREWER_REDS_9 = ("#fff5f0", "#fee0d2", "#fcbba1", "#fc9272", "#fb6a4a", "#ef3b2c", "#cb181d", "#a50f15", "#67000d")
# the pixels of Ed Hawkins' own published graphics (climate-lab-book.ac.uk/files/2018/05/globalcore.png,
# germanycore2.png and cetcore.png): each holds exactly these 16 colours, the 8 most saturated of the two palettes
HAWKINS_GRAPHICS = frozenset(
    {
        "#08306b", "#08519c", "#2171b5", "#4292c6", "#6baed6", "#9ecae1", "#c6dbef", "#deebf7",
        "#fee0d2", "#fcbba1", "#fc9272", "#fb6a4a", "#ef3b2c", "#cb181d", "#a50f15", "#67000d",
    }
)  # fmt: skip


def _reference(mean: float = 10.0, sigma: float = 1.0) -> StripesReference:
    """Give a reference of the method itself, from a record of 100 years."""
    stat = {"first_year": 1901, "last_year": 2000, "years": 100, "fallback": False}
    return StripesReference(
        centre=StripesReferenceStat(value=mean, **stat),
        spread=StripesReferenceStat(value=sigma, **stat),
        range_sigma=2.6,
        classes=16,
    )


def _record(first: int, last: int, *, gaps: set[int] | None = None) -> tuple[list[int], list[float]]:
    """Give a warming record: a value every year of `first` to `last` but the `gaps`, 8 degrees and 0.05 a year."""
    years = [year for year in range(first, last + 1) if year not in (gaps or set())]
    return years, [8.0 + 0.05 * (year - 1900) + (0.3 if year % 2 else -0.3) for year in years]


def test_the_palette_is_the_eight_most_saturated_blues_and_reds_of_colorbrewer() -> None:
    """The 16 colours are Hawkins': the 9-class Blues and Reds without their palest colour, low value first."""
    assert tuple(reversed(COLORBREWER_BLUES_9[1:])) == BLUES
    assert COLORBREWER_REDS_9[1:] == REDS
    assert TEMPERATURE_PALETTE == BLUES + REDS
    assert frozenset(TEMPERATURE_PALETTE) == HAWKINS_GRAPHICS
    assert stripes_palette("temperature") is TEMPERATURE_PALETTE
    assert stripes_palette("precipitation") is PRECIPITATION_PALETTE
    assert len(TEMPERATURE_PALETTE) == len(PRECIPITATION_PALETTE) == CLASSES


def test_the_precipitation_palette_is_brbg_sampled_at_even_steps() -> None:
    """Brown for dry, teal for wet: the 16 colours are the two half-ramps of BrBG, 8 mixed along each (our choice)."""
    assert (*_sample(BRBG_DRY), *_sample(BRBG_WET)) == PRECIPITATION_PALETTE
    # the ends are ColorBrewer's own darkest brown and darkest blue-green, and the middle pair is pale on both sides
    assert (PRECIPITATION_PALETTE[0], PRECIPITATION_PALETTE[-1]) == (BRBG_DRY[0], BRBG_WET[-1])
    assert (PRECIPITATION_PALETTE[7], PRECIPITATION_PALETTE[8]) == (BRBG_DRY[-1], BRBG_WET[0])


def test_the_sample_mixes_in_rgb_and_keeps_the_ends() -> None:
    """`_sample` gives the ends as they are and the colour between two anchors as their mean."""
    assert _sample(["#000000", "#ffffff"], 2) == ["#000000", "#ffffff"]
    assert _sample(["#000000", "#ffffff"], 3) == ["#000000", "#808080", "#ffffff"]
    assert _sample(["#000000", "#ff0000", "#ffffff"], 3) == ["#000000", "#ff0000", "#ffffff"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10.0, 8),  # the centre is the boundary: the lowest class of the upper half
        (10.3, 8),
        (10.33, 9),
        (9.99, 7),
        (9.68, 7),  # 0.32 below, within the first class below the centre
        (9.67, 6),
        (11.0, 11),  # 1 sigma = 3.08 classes
        (9.0, 4),
        (12.58, 15),  # the 8th class above: 2.58 sigma
        (12.6, 15),  # 2.6 sigma, and what lies beyond takes the end class
        (13.0, 15),
        (100.0, 15),
        (7.43, 0),  # -2.57 sigma: the 8th class below
        (7.4, 0),
        (7.0, 0),
        (-100.0, 0),
    ],
)
def test_a_value_is_in_the_class_of_its_anomaly_in_steps_of_a_class_width(value: float, expected: int) -> None:
    """A class is 2.6 / 8 = 0.325 standard deviations wide, the 8th one on either side taking all beyond 2.6 sigma."""
    assert pytest.approx(0.325) == CLASS_SIGMA
    assert stripe_class(value, _reference()) == expected


def test_the_class_follows_the_spread_of_the_record() -> None:
    """The same anomaly is a class further out where the spread is narrower."""
    assert stripe_class(11.0, _reference(sigma=1.0)) == 11
    assert stripe_class(11.0, _reference(sigma=0.25)) == 15
    assert stripe_class(11.0, _reference(sigma=2.0)) == 9


def test_years_that_differ_in_a_record_of_no_spread_take_the_end_they_lie_at() -> None:
    """A spread of 0 does not divide: a year at the centre is in the lowest class above it, others at their end."""
    flat = _reference(sigma=0.0)
    assert [stripe_class(value, flat) for value in (10.0, 11.0, 9.0)] == [8, 15, 0]


def test_the_reference_of_a_long_record_is_the_methods() -> None:
    """The mean of 1971-2000 is the centre and the standard deviation of 1901-2000 the spread, both of the record."""
    years, values = _record(1901, 2020)
    reference = stripes_reference(years, values)

    centre = [v for y, v in zip(years, values, strict=True) if 1971 <= y <= 2000]
    spread = [v for y, v in zip(years, values, strict=True) if 1901 <= y <= 2000]
    assert reference.centre.value == pytest.approx(statistics.fmean(centre))
    assert reference.spread.value == pytest.approx(statistics.stdev(spread))
    assert (reference.centre.first_year, reference.centre.last_year, reference.centre.years) == (1971, 2000, 30)
    assert (reference.spread.first_year, reference.spread.last_year, reference.spread.years) == (1901, 2000, 100)
    assert not reference.centre.fallback
    assert not reference.spread.fallback
    assert (reference.range_sigma, reference.classes) == (2.6, 16)
    assert reference.note() == (
        "The anomaly and class of each year were calculated from the provider's annual values: the mean of "
        "1971-2000 is the centre and the scale spans +/-2.6 standard deviations of 1901-2000 in 16 classes "
        "(Hawkins' method)."
    )


def test_the_years_after_2000_do_not_enter_the_reference() -> None:
    """The reference is of 1971-2000 and 1901-2000: a warmer 2001 to 2020 does not move it, and is only classed."""
    years, values = _record(1901, 2000)
    cut = stripes_reference(years, values)
    later_years, later_values = _record(1901, 2020)
    full = stripes_reference(later_years, later_values)

    assert full == cut
    # the later years are warmer than the 1971-2000 mean, and so red
    assert all(stripe_class(v, full) >= 8 for y, v in zip(later_years, later_values, strict=True) if y > 2000)
    assert stripe_class(max(later_values), full) > stripe_class(values[-1], full)


@pytest.mark.parametrize(("have", "fallback"), [(MIN_CENTRE_YEARS, False), (MIN_CENTRE_YEARS - 1, True)])
def test_the_mean_of_a_station_short_of_1971_2000_is_the_whole_records(have: int, fallback: bool) -> None:  # noqa: FBT001
    """A station with too few years in 1971-2000 takes its whole record for the centre, and says so."""
    # a record of 1941 to 2020 whose 1971-2000 has `have` years: the others of those 30 are gaps
    gaps = set(range(1971 + have, 2001))
    years, values = _record(1941, 2020, gaps=gaps)
    reference = stripes_reference(years, values)

    assert reference.centre.fallback is fallback
    if fallback:
        assert reference.centre.value == pytest.approx(statistics.fmean(values))
        assert (reference.centre.first_year, reference.centre.last_year, reference.centre.years) == (
            1941,
            2020,
            len(years),
        )
        assert "for the mean the whole record (1941-2020" in reference.note()
    else:
        assert reference.centre.years == have
        assert (reference.centre.first_year, reference.centre.last_year) == (1971, 1971 + have - 1)
    # the spread has 60 years of 1901-2000 either way
    assert not reference.spread.fallback


@pytest.mark.parametrize(("have", "fallback"), [(MIN_SPREAD_YEARS, False), (MIN_SPREAD_YEARS - 1, True)])
def test_the_spread_of_a_station_short_of_1901_2000_is_the_whole_records(have: int, fallback: bool) -> None:  # noqa: FBT001
    """A station with too few years in 1901-2000 takes its whole record for the standard deviation, and says so."""
    years, values = _record(2000 - have + 1, 2020)
    reference = stripes_reference(years, values)

    assert reference.spread.fallback is fallback
    expected = values if fallback else [v for y, v in zip(years, values, strict=True) if y <= 2000]
    assert reference.spread.value == pytest.approx(statistics.stdev(expected))
    # these have the 29 or 30 years of 1971-2000 the mean needs
    assert not reference.centre.fallback
    if fallback:
        assert "for the standard deviation the whole record" in reference.note()


def test_a_record_of_recent_years_has_the_whole_record_for_both() -> None:
    """A station that started in 1991 has neither period: the note names the whole record for both."""
    years, values = _record(1991, 2020)
    reference = stripes_reference(years, values)

    assert reference.centre.fallback
    assert reference.spread.fallback
    assert reference.centre.value == pytest.approx(statistics.fmean(values))
    assert reference.spread.value == pytest.approx(statistics.stdev(values))
    note = reference.note()
    assert note.endswith(
        "so it takes for the mean the whole record (1991-2020, 30 years) and for the standard deviation the whole "
        "record (1991-2020, 30 years)."
    )
    assert note.isascii()


def test_the_classes_of_the_whole_record_span_the_scale_where_the_record_is_the_reference() -> None:
    """With the whole record for both, a year 2.6 sigma beyond the mean takes the end class."""
    years, values = _record(1991, 2020)
    reference = stripes_reference(years, values)
    classes = [stripe_class(v, reference) for v in values]

    assert all(0 <= c < 16 for c in classes)
    assert stripe_class(reference.centre.value + 2.6 * reference.spread.value + 1e-9, reference) == 15
    assert stripe_class(reference.centre.value - 2.6 * reference.spread.value - 1e-9, reference) == 0
    # the warming shows: the first year is below the centre, the last above
    assert classes[0] < 8 <= classes[-1]


def test_the_thresholds_are_the_ones_the_docs_state() -> None:
    """The fallback thresholds are documented (docs/usage/stripes.md); a change of them is a change of the docs."""
    assert (stripes_scale.MIN_CENTRE_YEARS, stripes_scale.MIN_SPREAD_YEARS, stripes_scale.MIN_RECORD_YEARS) == (
        20,
        30,
        10,
    )
    assert (stripes_scale.CENTRE_PERIOD, stripes_scale.SPREAD_PERIOD) == ((1971, 2000), (1901, 2000))
    assert stripes_scale.RANGE_SIGMA == 2.6


# --- the app holds to the same scale -------------------------------------------------------------------------------

GOLDEN = Path(__file__).parent / "stripes_scale.golden.json"
APP_STRIPES = Path(__file__).parents[2] / "app" / "app" / "utils" / "stripes.ts"


def _golden_cases() -> list[dict]:
    """Give the records the app's fixtures are written for, with what the backend gives them."""
    long_years, long_values = _record(1901, 2020, gaps=set(range(1950, 1956)))
    short_years, short_values = _record(1991, 2020)
    spread_years, spread_values = _record(1981, 2020)
    extreme_years, extreme_values = _record(1941, 2020)
    extreme_values[extreme_years.index(2020)] = 40.0
    extreme_values[extreme_years.index(1941)] = -30.0
    cases = []
    for name, years, values in (
        ("long record with a gap", long_years, long_values),
        ("short record, the whole of it for both", short_years, short_values),
        ("record from 1981, the whole of it for the spread", spread_years, spread_values),
        ("outliers beyond 2.6 standard deviations", extreme_years, extreme_values),
    ):
        reference = stripes_reference(years, values)
        cases.append(
            {
                "name": name,
                "years": years,
                "values": values,
                "reference": {
                    "centre": reference.centre.model_dump(),
                    "spread": reference.spread.model_dump(),
                },
                "classes": [stripe_class(value, reference) for value in values],
            }
        )
    return cases


def test_the_golden_cases_of_the_app_are_the_backends() -> None:
    """`stripes_scale.golden.json` holds what the backend gives these records, which the app's test helper is held to.

    The app calculates no class: it draws the ones the answer has. Its tests write answers for their fixtures with a
    port of this scale, and `app/tests/unit/stripes-answer.test.ts` holds the port to this file. Written again with
    `uv run python -m tests.ui.test_stripes_scale` after an intended change of the scale.
    """
    assert json.loads(GOLDEN.read_text(encoding="utf-8")) == json.loads(json.dumps(_golden_cases()))


def test_the_app_draws_the_colours_of_the_backend() -> None:
    """The 16 colours of each kind in the app (`app/app/utils/stripes.ts`) are the backend image's, class for class."""
    source = APP_STRIPES.read_text(encoding="utf-8")
    for kind, palette in (("temperature", TEMPERATURE_PALETTE), ("precipitation", PRECIPITATION_PALETTE)):
        block = re.search(rf"\b{kind}: \[(.*?)\],", source, re.DOTALL)
        assert block, f"no {kind} palette in {APP_STRIPES}"
        assert tuple(re.findall(r"'(#[0-9a-f]{6})'", block.group(1))) == palette


if __name__ == "__main__":
    GOLDEN.write_text(json.dumps(_golden_cases(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN}")  # noqa: T201
