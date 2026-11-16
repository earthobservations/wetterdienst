# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The colour scale of the climate stripes: Ed Hawkins' method, with a documented fallback for a short record (GH-4157).

The method, as `showyourstripes.info`'s FAQ states it: "For each country, the average temperature in 1971-2000 is set
as the boundary between blue and red colours, and the colour scale varies from +/- 2.6 standard deviations of the
annual average temperatures between 1901-2000." The 16 colours are the 8 most saturated classes of ColorBrewer's
9-class Blues and Reds (read from the published graphics, whose pixels hold these 16 colours and no other).

A year's class is therefore its anomaly to the mean of 1971-2000 in steps of `2.6 / 8` standard deviations of the
annual values of 1901-2000, the two outermost classes taking whatever lies beyond. It depends on the station's record
and on no window of years: a year keeps its colour whatever `start_year` and `end_year` show.

A station short of either period takes the whole record in its place, for the mean and for the spread each on its
own, and says so in the `reference` of its answer. The classes count from the lowest value (0) to the highest (15).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Sequence

#: the years whose mean is the boundary between the blue and the red classes
CENTRE_PERIOD = (1971, 2000)
#: the years whose standard deviation sets the width of the classes
SPREAD_PERIOD = (1901, 2000)
#: the scale reaches this many standard deviations to either side of the centre
RANGE_SIGMA = 2.6
#: 8 classes below the centre and 8 above
CLASSES = 16
#: a class is this many standard deviations wide
CLASS_SIGMA = RANGE_SIGMA / (CLASSES // 2)

#: the fewest years with data a period needs to stand for its reference, else the whole record does: 20 of the 30
#: years of 1971-2000 for the mean, and 30 of the 100 years of 1901-2000 for the standard deviation
MIN_CENTRE_YEARS = 20
MIN_SPREAD_YEARS = 30
#: the fewest years with data a record needs for a scale of its own: a standard deviation of fewer is no spread
MIN_RECORD_YEARS = 10

#: ColorBrewer's 9-class Blues and Reds without the palest of the nine (#f7fbff and #fff5f0): the 8 most saturated
#: of each. The blues run dark to pale below the centre, the reds pale to dark above it, so the colours go from the
#: lowest class (0) to the highest (15)
BLUES = ("#08306b", "#08519c", "#2171b5", "#4292c6", "#6baed6", "#9ecae1", "#c6dbef", "#deebf7")
REDS = ("#fee0d2", "#fcbba1", "#fc9272", "#fb6a4a", "#ef3b2c", "#cb181d", "#a50f15", "#67000d")
TEMPERATURE_PALETTE = (*BLUES, *REDS)

#: the half-ramps of ColorBrewer's 11-class BrBG without its neutral middle, and the 8 colours of each side sampled
#: along them at even steps in RGB (`_sample`): Hawkins has no precipitation stripes, so this is our own choice
BRBG_DRY = ("#543005", "#8c510a", "#bf812d", "#dfc27d", "#f6e8c3")
BRBG_WET = ("#c7eae5", "#80cdc1", "#35978f", "#01665e", "#003c30")
PRECIPITATION_PALETTE = (
    "#543005",
    "#744308",
    "#93580f",
    "#b07323",
    "#c89444",
    "#dab972",
    "#e9d29b",
    "#f6e8c3",
    "#c7eae5",
    "#9ed9d0",
    "#75c5ba",
    "#4aa69d",
    "#268981",
    "#086d65",
    "#01544a",
    "#003c30",
)


def _sample(anchors: Sequence[str], count: int = CLASSES // 2) -> list[str]:
    """Give `count` colours at even steps along the colours `anchors`, mixed in RGB (the end ones are the ends)."""
    channels = [[int(anchor[i : i + 2], 16) for i in (1, 3, 5)] for anchor in anchors]
    colours = []
    for step in range(count):
        position = step / (count - 1) * (len(anchors) - 1)
        low = min(int(position), len(anchors) - 2)
        share = position - low
        mixed = (round(a + (b - a) * share) for a, b in zip(channels[low], channels[low + 1], strict=True))
        colours.append("#" + "".join(f"{channel:02x}" for channel in mixed))
    return colours


class StripesReferenceStat(BaseModel):
    """One number of the reference, and which years it was calculated from."""

    model_config = {"extra": "forbid"}

    value: float = Field(description="The mean (centre) or the standard deviation (spread), in the unit of the values.")
    first_year: int = Field(description="The first year the number was calculated from.")
    last_year: int = Field(description="The last year the number was calculated from.")
    years: int = Field(description="How many years with data it was calculated from.")
    fallback: bool = Field(
        description="True where the station has too few years with data in the period of the method (1971-2000 for "
        "the mean, 1901-2000 for the standard deviation) and the whole record stands in for it."
    )


class StripesReference(BaseModel):
    """What the colour classes of the stripes are relative to, and so which scale a year's class is read on."""

    model_config = {"extra": "forbid"}

    centre: StripesReferenceStat = Field(description="The mean the anomaly is taken to: the blue/red boundary.")
    spread: StripesReferenceStat = Field(description="The standard deviation of the annual values the classes span.")
    range_sigma: float = Field(
        description="The scale reaches this many standard deviations to either side of the centre."
    )
    classes: int = Field(description="The number of classes, from the lowest value (0) to the highest.")

    def note(self) -> str:
        """Say in one ASCII sentence which reference the classes are relative to, and where the whole record is used."""
        text = (
            f"The anomaly and class of each year were calculated from the provider's annual values: the mean of "
            f"{_years(self.centre)} is the centre and the scale spans +/-{self.range_sigma:g} standard deviations of "
            f"{_years(self.spread)} in {self.classes} classes (Hawkins' method)"
        )
        used = [
            f"{name} the whole record ({stat.first_year}-{stat.last_year}, {stat.years} years)"
            for name, stat in (("for the mean", self.centre), ("for the standard deviation", self.spread))
            if stat.fallback
        ]
        if used:
            text += f"; the station has too few years in the period of the method, so it takes {' and '.join(used)}"
        return text + "."


def _years(stat: StripesReferenceStat) -> str:
    return f"{stat.first_year}-{stat.last_year}"


def _stat(
    years: Sequence[int],
    values: Sequence[float],
    period: tuple[int, int],
    minimum: int,
    calculate: Literal["mean", "std"],
) -> StripesReferenceStat:
    in_period = [(y, v) for y, v in zip(years, values, strict=True) if period[0] <= y <= period[1]]
    fallback = len(in_period) < minimum
    chosen = list(zip(years, values, strict=True)) if fallback else in_period
    numbers = [v for _, v in chosen]
    mean = math.fsum(numbers) / len(numbers)
    if calculate == "mean":
        value = mean
    else:
        # the sample standard deviation: an estimate from the years there are
        value = math.sqrt(math.fsum((n - mean) ** 2 for n in numbers) / (len(numbers) - 1)) if len(numbers) > 1 else 0.0
    return StripesReferenceStat(
        value=value,
        first_year=min(y for y, _ in chosen),
        last_year=max(y for y, _ in chosen),
        years=len(chosen),
        fallback=fallback,
    )


def stripes_reference(years: Sequence[int], values: Sequence[float]) -> StripesReference:
    """Calculate the reference of a station's whole record of annual values (the years with data, not any window).

    The mean of 1971-2000 is the centre where that period holds `MIN_CENTRE_YEARS` years, and the standard deviation
    of 1901-2000 the spread where it holds `MIN_SPREAD_YEARS`; the whole record takes the place of whichever is short.
    The caller refuses a record shorter than `MIN_RECORD_YEARS`.
    """
    return StripesReference(
        centre=_stat(years, values, CENTRE_PERIOD, MIN_CENTRE_YEARS, "mean"),
        spread=_stat(years, values, SPREAD_PERIOD, MIN_SPREAD_YEARS, "std"),
        range_sigma=RANGE_SIGMA,
        classes=CLASSES,
    )


def stripe_class(value: float, reference: StripesReference) -> int:
    """Give the class of a value, 0 (the lowest) to 15: its anomaly in steps of `CLASS_SIGMA` standard deviations.

    The centre is the boundary between the 8th class and the 9th: a value equal to it is in the 9th (the lowest of the
    upper half). What lies beyond 2.6 standard deviations takes the end class. A spread of 0 (every year alike) puts a
    value that differs at the end it lies at.
    """
    anomaly = value - reference.centre.value
    sigma = reference.spread.value
    if sigma <= 0:
        position = math.copysign(math.inf, anomaly) if anomaly else 0.0
    else:
        position = math.floor(anomaly / sigma / CLASS_SIGMA)
    return int(min(CLASSES - 1, max(0, CLASSES // 2 + position)))


def stripes_palette(kind: Literal["temperature", "precipitation"]) -> tuple[str, ...]:
    """Give the 16 colours of a kind of stripes, from the lowest class to the highest."""
    return TEMPERATURE_PALETTE if kind == "temperature" else PRECIPITATION_PALETTE
